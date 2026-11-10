"""Step 7: evaluation. Is ThinkMesh actually better than simpler setups?

Three setups are run on every topic, all with the SAME writer model:

    A  plain AI answer        one prompt, no web sources, no citations
    B  sources + writer       the numbered sources and the writer, one draft
    C  full ThinkMesh         sources + write -> critique -> revise loop

B and C get exactly the same source pages (gathered once per topic), so the only
difference between them is the critique/revise loop.

A DIFFERENT model (the judge, set with JUDGE_PROVIDER / JUDGE_MODEL) then scores
every report. The judge is never the writer, so a model is not grading its own work.

Run it:
    python -m backend.evaluate --limit 2     # try 2 topics first
    python -m backend.evaluate               # all topics in eval/topics.txt
    python -m backend.evaluate --summary     # only rebuild the table (no AI calls)

Progress is saved after every single step, so you can stop (Ctrl+C) at any time
and run the same command again: finished steps are skipped.
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, field_validator

load_dotenv()

from backend import agents  # noqa: E402  (needs .env loaded first)
from backend import custom_tools, graph, sources as sources_mod  # noqa: E402
from backend.eval_summary import SETUPS, summarize, write_summary  # noqa: E402
from backend.pipeline import run_research_pipeline  # noqa: E402
from backend.sources import format_sources_for_prompt, gather_sources  # noqa: E402
from backend.textclean import clean_report_text  # noqa: E402
from backend.verify import CITATION, extract_sentences, verify_report  # noqa: E402

EVAL_DIR = Path(os.getenv("EVAL_DIR", "eval"))
TOPICS_FILE = EVAL_DIR / "topics.txt"
RESULTS_DIR = EVAL_DIR / "results"

PAUSE_SECONDS = float(os.getenv("EVAL_SLEEP_SECONDS", "5"))  # between steps
MAX_TRIES = int(os.getenv("EVAL_MAX_TRIES", "4"))  # per AI call
RETRY_WAIT = float(os.getenv("EVAL_RETRY_WAIT", "10"))  # first wait; doubles each time
MAX_CLAIMS_JUDGED = int(os.getenv("EVAL_MAX_CLAIMS", "60"))  # app default is 40

_sleep = time.sleep  # a variable so the tests can replace it

# words in an error message that mean "try again later" (rate limit, overload...)
RETRYABLE = (
    "429",
    "rate limit",
    "rate_limit",
    "quota",
    "resource_exhausted",
    "overloaded",
    "unavailable",
    "503",
    "502",
    "504",
    "timeout",
    "timed out",
    "temporarily",
)


# ---------------------------------------------------------------- retry helpers

# A DAILY limit never clears by waiting a few seconds, so it must not be retried.
DAILY_WORDS = ("per-day", "per_day", "per day", "perday", "daily")


class DailyLimitReached(Exception):
    """A provider's daily quota is used up: stop the run, continue after it resets."""


def is_daily_limit(text) -> bool:
    text = str(text).lower()
    return any(word in text for word in DAILY_WORDS)


def is_retryable(text: str) -> bool:
    text = str(text).lower()
    if is_daily_limit(text):
        return False
    return any(word in text for word in RETRYABLE)


def with_retry(fn, what: str):
    """Call fn(). Wait and try again on rate limits; fail fast on real errors
    (wrong API key, bad request...), because waiting never fixes those."""
    for attempt in range(1, MAX_TRIES + 1):
        try:
            return fn()
        except Exception as exc:
            if is_daily_limit(exc):
                raise DailyLimitReached(str(exc)[:300]) from exc
            if attempt == MAX_TRIES or not is_retryable(exc):
                raise
            wait = min(90.0, RETRY_WAIT * 2 ** (attempt - 1))
            print(
                f"    {what}: temporary error, waiting {wait:.0f}s ({attempt}/{MAX_TRIES - 1})"
            )
            _sleep(wait)


# ---------------------------------------------------------------- text helpers


def slugify(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:60] or "topic"


def strip_sources_section(report: str) -> str:
    """The report without the '## Sources' list that the code adds at the end."""
    return re.split(r"\n+## Sources\b", report, maxsplit=1)[0].strip()


def strip_for_judge(body: str) -> str:
    """Remove [1][2] markers so the quality judge cannot tell which setup wrote
    the report (A has no citations, B and C have them)."""
    text = CITATION.sub("", body)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"[ \t]+([.,;:!?])", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def tag_every_sentence(body: str, sources: list[dict]) -> str:
    """For setup A: add every source number to every sentence, so the fact-checker
    asks 'is this sentence backed by ANY of the retrieved sources?'"""
    tags = "".join(f"[{s['id']}]" for s in sources)
    return "\n".join(f"{sentence} {tags}" for sentence in extract_sentences(body))


# ---------------------------------------------------------------- the three setups

plain_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an expert research writer. Write clear, structured and insightful reports.",
        ),
        (
            "human",
            """Write a detailed research report on the topic below.

Topic: {topic}

Structure the report as:
- Introduction
- Key Findings (minimum 3 well-explained points)
- Conclusion

Be detailed, factual and professional. Aim for about 700 words.""",
        ),
    ]
)


def generate_a(topic: str, sources: list[dict]) -> dict:
    chain = plain_prompt | agents.llm | StrOutputParser()
    body = clean_report_text(
        with_retry(lambda: chain.invoke({"topic": topic}), "A: write")
    )
    if not body:
        raise ValueError("The model returned an empty report.")
    return {"body": body, "meta": {}}


def generate_b(topic: str, sources: list[dict]) -> dict:
    research = format_sources_for_prompt(sources)
    body = with_retry(
        lambda: agents.writer_chain.invoke({"topic": topic, "research": research}),
        "B: write",
    ).strip()
    if not body:
        raise ValueError("The writer returned an empty report.")
    return {"body": body, "meta": {}}


def c_problem(state: dict) -> str | None:
    """Why a full-pipeline run cannot be trusted, or None if it is fine.

    The pipeline is built to survive failures: if the critic or a revision hits a
    rate limit it quietly carries on. That is good for users, but it would turn a
    'full ThinkMesh' result into a half-run one, so the evaluation rejects it.
    """
    if state.get("status") != "success":
        return f"pipeline failed: {state.get('error')}"
    if not state.get("scores"):
        return "the critic never returned a score"
    for warning in state.get("warnings", []):
        if "critic could not review" in warning or (
            "Revision" in warning and "failed" in warning
        ):
            return warning
    return None


def generate_c(topic: str, sources: list[dict]) -> dict:
    problem = None
    for attempt in range(1, MAX_TRIES + 1):
        state = run_research_pipeline(topic, sources=sources)
        problem = c_problem(state)
        if problem is None:
            break
        if is_daily_limit(problem):
            raise DailyLimitReached(problem[:300])
        if attempt == MAX_TRIES or not is_retryable(problem):
            raise RuntimeError(problem)
        wait = min(90.0, RETRY_WAIT * 2 ** (attempt - 1))
        print(
            f"    C: incomplete run ({problem[:80]}), waiting {wait:.0f}s and retrying"
        )
        _sleep(wait)

    return {
        "body": strip_sources_section(state["report"]),
        "meta": {
            "scores": state["scores"],  # critic score of every round
            "revisions": state["revisions"],
        },
    }


GENERATORS = {"A": generate_a, "B": generate_b, "C": generate_c}


# ---------------------------------------------------------------- the judge


class QualityScore(BaseModel):
    depth: int = Field(description="1-10: explains and analyses, specific, not generic")
    structure: int = Field(description="1-10: clear organisation and writing")
    balance: int = Field(description="1-10: limits, risks and counter-views covered")
    overall: int = Field(description="1-10 overall quality")
    comment: str = Field(description="One short sentence explaining the overall score")

    @field_validator("depth", "structure", "balance", "overall")
    @classmethod
    def keep_in_range(cls, value: int) -> int:
        return max(1, min(10, value))


quality_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a strict, impartial editor who scores research reports. "
            "You never see who or what wrote a report.",
        ),
        (
            "human",
            """Score the research report below.

Judge only:
- depth: does it explain and analyse with specific details, or list generic points?
- structure: is it well organised and clearly written (Introduction, Key Findings, Conclusion)?
- balance: does it cover limits, risks or counter-views where relevant?

Do NOT judge factual accuracy (you cannot check it here). Reference markers were
removed on purpose, so do not penalise the lack of references.

Do not reward length for its own sake: a shorter report that is specific and well
organised can score higher than a long one.

Use the whole 1-10 scale. 5 is an average report. 8 or more is excellent and rare.
Give "overall" as your honest overall score.

Report:
{report}""",
        ),
    ]
)


def build_judge() -> dict:
    """Build the judge model. It must be a different model from the writer."""
    provider = os.getenv("JUDGE_PROVIDER", "").strip()
    if not provider:
        raise SystemExit(
            "Set JUDGE_PROVIDER in .env (for example gemini) and its API key.\n"
            "The judge must be a different model from the writer, "
            "so a model never grades its own work."
        )
    judge_id = agents.resolve_model(provider, os.getenv("JUDGE_MODEL") or None)
    writer_id = agents.resolve_model()
    if judge_id == writer_id:
        raise SystemExit(
            f"The judge and the writer are the same model ({writer_id[0]}/{writer_id[1]}). "
            "Choose a different JUDGE_PROVIDER or JUDGE_MODEL."
        )
    judge_llm = agents.get_llm(*judge_id)
    return {
        "id": judge_id,
        "writer": writer_id,
        "quality": quality_prompt | judge_llm.with_structured_output(QualityScore),
        "verifier": agents.verifier_prompt
        | judge_llm.with_structured_output(agents.VerificationResult),
    }


def _fact_check(body: str, sources: list[dict], chain) -> dict:
    """verify_report, but a fact-check that silently did not run is an error."""
    result = verify_report(body, sources, chain, max_claims=MAX_CLAIMS_JUDGED)
    if result["claims_total"] and not result["llm_used"]:
        raise RuntimeError("; ".join(result["notes"]) or "the fact-check did not run")
    return result


def _numbers(v: dict) -> dict:
    return {
        "claims_total": v["claims_total"],
        "checked": v["checked"],
        "supported": v["supported"],
        "partial": v["partial"],
        "unsupported": v["unsupported"],
        "support_rate": v["support_rate"],
        "uncited_sentences": v["uncited_sentences"],
        "invalid_citations": len(v["invalid_citations"]),
        "figures_not_found": v["figures_not_found"],
    }


def judge_report(setup: str, body: str, sources: list[dict], judge: dict) -> dict:
    """Quality score + citation numbers for one report, all by the judge model."""
    score = with_retry(
        lambda: judge["quality"].invoke({"report": strip_for_judge(body)}),
        f"{setup}: quality judge",
    )
    out = {
        "quality": {
            "depth": score.depth,
            "structure": score.structure,
            "balance": score.balance,
            "overall": score.overall,
            "comment": score.comment,
        },
        "words": len(body.split()),
    }

    # free automatic numbers (uncited sentences etc.), no AI
    free = verify_report(body, sources, None)
    out["uncited_sentences"] = free["uncited_sentences"]
    out["cited_sentences"] = free["claims_total"]

    if setup in ("B", "C"):
        # does each sentence's own cited source really say it?
        checked = with_retry(
            lambda: _fact_check(body, sources, judge["verifier"]),
            f"{setup}: citation judge",
        )
        out["citations"] = _numbers(checked)
    else:
        # A has no citations: ask if ANY retrieved source backs each sentence
        tagged = tag_every_sentence(body, sources)
        checked = with_retry(
            lambda: _fact_check(tagged, sources, judge["verifier"]),
            "A: grounding judge",
        )
        out["pack"] = _numbers(checked)
    return out


# ---------------------------------------------------------------- files and resume


def read_topics() -> list[str]:
    if not TOPICS_FILE.exists():
        raise SystemExit(f"{TOPICS_FILE} not found. Create it with one topic per line.")
    lines = [line.strip() for line in TOPICS_FILE.read_text().splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def load_json(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(path)  # a crash can never leave a half-written results file


def current_config(judge: dict) -> dict:
    return {
        "writer": "/".join(judge["writer"]),
        "judge": "/".join(judge["id"]),
        "max_sources": sources_mod.MAX_SOURCES,
        "max_page_chars": custom_tools.MAX_PAGE_CHARS,
        "target_score": graph.TARGET_SCORE,
        "max_revisions": graph.MAX_REVISIONS,
        "max_claims_judged": MAX_CLAIMS_JUDGED,
    }


def check_config(config: dict) -> None:
    """Results from different settings must never be mixed in one table."""
    path = RESULTS_DIR / "config.json"
    saved = load_json(path)
    if saved is None:
        save_json(path, {**config, "created": time.strftime("%Y-%m-%d %H:%M")})
        return
    old = {k: v for k, v in saved.items() if k != "created"}
    if old != config:
        raise SystemExit(
            "The settings changed since this evaluation started:\n"
            f"  saved:   {old}\n  current: {config}\n"
            f"Put the old settings back, or move {RESULTS_DIR} away to start a new run."
        )


def run_topic(topic: str, judge: dict) -> None:
    path = RESULTS_DIR / f"{slugify(topic)}.json"
    data = load_json(path) or {"topic": topic, "sources": None, "setups": {}}

    # the same pages for every setup (and for every resume)
    if not data["sources"]:
        found, warnings = with_retry(lambda: gather_sources(topic), "search")
        data["sources"], data["source_warnings"] = found, warnings
        save_json(path, data)
    sources = data["sources"]

    for setup in SETUPS:
        record = data["setups"].get(setup) or {}
        if record.get("report") and record.get("judge"):
            print(f"  {setup}: done already")
            continue

        # 1) write the report (saved before judging, so a judge failure loses nothing)
        if not record.get("report"):
            started = time.time()
            try:
                made = GENERATORS[setup](topic, sources)
            except DailyLimitReached:
                raise
            except Exception as exc:
                data["setups"][setup] = {"report": None, "gen_error": str(exc)[:300]}
                save_json(path, data)
                print(f"  {setup}: FAILED to write ({str(exc)[:100]})")
                continue
            record = {
                "report": made["body"],
                "meta": made["meta"],
                "seconds": round(time.time() - started, 1),
                "judge": None,
            }
            data["setups"][setup] = record
            save_json(path, data)
            _sleep(PAUSE_SECONDS)

        # 2) judge it with the other model
        try:
            record["judge"] = judge_report(setup, record["report"], sources, judge)
            record.pop("judge_error", None)
            q = record["judge"]["quality"]["overall"]
            print(f"  {setup}: written and judged (quality {q}/10)")
        except DailyLimitReached:
            save_json(path, data)  # the written report stays saved
            raise
        except Exception as exc:
            record["judge_error"] = str(exc)[:300]
            print(f"  {setup}: written, but judging FAILED ({str(exc)[:100]})")
        save_json(path, data)
        _sleep(PAUSE_SECONDS)


# ---------------------------------------------------------------- command line


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ThinkMesh evaluation (A vs B vs C)")
    parser.add_argument("--limit", type=int, help="only the first N topics")
    parser.add_argument("--summary", action="store_true", help="only rebuild the table")
    args = parser.parse_args(argv)

    if args.summary:
        print(write_summary(summarize(RESULTS_DIR), EVAL_DIR / "RESULTS.md"))
        return 0

    os.environ["VERIFY_WITH_LLM"] = "false"  # the judge does the fact-check instead
    topics = read_topics()[: args.limit]
    judge = build_judge()
    check_config(current_config(judge))

    print(f"Writer: {'/'.join(judge['writer'])}   Judge: {'/'.join(judge['id'])}")
    for number, topic in enumerate(topics, start=1):
        print(f"\n[{number}/{len(topics)}] {topic}")
        try:
            run_topic(topic, judge)
        except DailyLimitReached as exc:
            print(f"\n  STOPPED: a daily limit is used up ({str(exc)[:150]}).")
            print(
                "  Nothing is lost. Run the same command again after the limit resets"
            )
            print("  (OpenRouter and Gemini reset at midnight UTC = 5:30 AM in India).")
            break
        except Exception as exc:  # e.g. the search failed: skip, keep going
            print(f"  SKIPPED this topic: {str(exc)[:150]}")

    print("\n" + write_summary(summarize(RESULTS_DIR), EVAL_DIR / "RESULTS.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
