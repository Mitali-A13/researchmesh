"""Turns the saved evaluation files into a table (and eval/RESULTS.md).

No AI calls here: it only reads the JSON files that backend/evaluate.py saved,
so you can run it as often as you like:

    python -m backend.eval_summary
"""

import json
import sys
from pathlib import Path

SETUPS = ("A", "B", "C")
NAMES = {
    "A": "A: plain AI answer",
    "B": "B: sources + writer",
    "C": "C: full ThinkMesh",
}

LIMITATIONS = """\
- The judge is one AI model. Its scores are opinions, not ground truth, and AI judges
  tend to be generous and to cluster scores. Compare setups with each other; do not
  treat any single number as an absolute grade.
- "Supported" means: the judge found that claim in the source text the report cited.
  The source text is only the first part of each page, so a true claim can be marked
  unsupported when it comes from a part that was cut off.
- Setup A has no citations. Its "grounded" number asks whether ANY of the retrieved
  sources backs each sentence. A can be factually right and still score low there,
  because it did not use these pages. It measures grounding, not truth.
- The quality judge never sees the sources, so it cannot judge accuracy. Its rubric
  (depth, structure, balance) is close to what ThinkMesh's own critic optimises, which
  favours C. Citation support is the fairer comparison between B and C.
- The same writer model produces A, B and C, and the critic/reviser inside C is that
  same model, so C measures "a loop around this model", not a better model.
- A small number of topics is a small sample. A gap of about one point of quality, or
  a few percentage points of support, is within normal run-to-run noise.
- Only reports that finished and were judged are counted. Topics where any setup
  failed are listed but left out of the averages, so all three setups use the same topics.
"""


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def pct(value, digits=0):
    return "—" if value is None else f"{100 * value:.{digits}f}%"


def num(value, digits=1):
    return "—" if value is None else f"{value:.{digits}f}"


def usable(record) -> bool:
    return bool(record and record.get("report") and record.get("judge"))


def load_results(results_dir) -> list[dict]:
    results_dir = Path(results_dir)
    topics = []
    for path in sorted(results_dir.glob("*.json")):
        if path.name == "config.json":
            continue
        topics.append(json.loads(path.read_text()))
    return topics


def _stats_for(setup: str, topics: list[dict]) -> dict:
    records = [t["setups"][setup] for t in topics]
    judges = [r["judge"] for r in records]
    cited = [j.get("citations") for j in judges if j.get("citations")]
    pack = [j.get("pack") for j in judges if j.get("pack")]

    stats = {
        "quality": mean(j["quality"]["overall"] for j in judges),
        "depth": mean(j["quality"]["depth"] for j in judges),
        "structure": mean(j["quality"]["structure"] for j in judges),
        "balance": mean(j["quality"]["balance"] for j in judges),
        "words": mean(j["words"] for j in judges),
        "uncited": mean(j["uncited_sentences"] for j in judges),
        "uncited_rate": mean(
            j["uncited_sentences"] / (j["uncited_sentences"] + j["cited_sentences"])
            for j in judges
            if (j["uncited_sentences"] + j["cited_sentences"]) > 0
        ),
        "cite_macro": mean(c["support_rate"] for c in cited),
        "cite_checked": sum(c["checked"] for c in cited),
        "cite_supported": sum(c["supported"] for c in cited),
        "figures_not_found": mean(c["figures_not_found"] for c in cited),
        "pack_macro": mean(p["support_rate"] for p in pack),
        "pack_checked": sum(p["checked"] for p in pack),
        "pack_supported": sum(p["supported"] for p in pack),
    }
    if setup == "C":
        scores = [r["meta"].get("scores", []) for r in records]
        scores = [s for s in scores if s]
        stats["first_score"] = mean(s[0] for s in scores)
        stats["best_score"] = mean(max(s) for s in scores)
        stats["revisions"] = mean(r["meta"].get("revisions", 0) for r in records)
        stats["revised_share"] = mean(
            1.0 if r["meta"].get("revisions", 0) > 0 else 0.0 for r in records
        )
    return stats


def _compare(topics, first, second, getter):
    """Per-topic head-to-head: how often `first` beats / ties / loses to `second`."""
    wins = ties = losses = 0
    for t in topics:
        a, b = getter(t["setups"][first]), getter(t["setups"][second])
        if a is None or b is None:
            continue
        if a > b:
            wins += 1
        elif a < b:
            losses += 1
        else:
            ties += 1
    return wins, ties, losses


def summarize(results_dir) -> dict:
    topics = load_results(results_dir)
    complete = [
        t for t in topics if all(usable(t.get("setups", {}).get(s)) for s in SETUPS)
    ]
    config = None
    config_path = Path(results_dir) / "config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text())

    summary = {
        "config": config,
        "topics_total": len(topics),
        "topics_complete": len(complete),
        "incomplete": [t["topic"] for t in topics if t not in complete],
        "stats": {s: _stats_for(s, complete) for s in SETUPS} if complete else {},
        "rows": complete,
    }
    if complete:
        q = lambda r: r["judge"]["quality"]["overall"]  # noqa: E731
        sup = lambda r: (r["judge"].get("citations") or {}).get("support_rate")  # noqa: E731
        summary["c_vs_b_quality"] = _compare(complete, "C", "B", q)
        summary["c_vs_b_support"] = _compare(complete, "C", "B", sup)
        summary["b_vs_a_quality"] = _compare(complete, "B", "A", q)
        summary["c_vs_a_quality"] = _compare(complete, "C", "A", q)
    return summary


def render(summary: dict) -> str:
    out = ["# ThinkMesh evaluation", ""]
    n, total = summary["topics_complete"], summary["topics_total"]
    if not n:
        out.append(
            f"No topic has all three setups finished and judged yet ({total} started)."
        )
        return "\n".join(out)

    cfg = summary["config"] or {}
    out += [
        f"Based on **{n} topics** where all three setups finished and were judged "
        f"({total} topics started).",
        "",
    ]
    if cfg:
        out += [
            f"Writer model: `{cfg.get('writer')}` · Judge model: `{cfg.get('judge')}` · "
            f"sources per topic: {cfg.get('max_sources')} · characters per page: "
            f"{cfg.get('max_page_chars')} · target score: {cfg.get('target_score')} · "
            f"max revisions: {cfg.get('max_revisions')} · started: {cfg.get('created', '?')}",
            "",
        ]

    st = summary["stats"]
    out += [
        "## Results",
        "",
        "| Setup | Judge quality (/10) | Cited claims supported | Grounded in retrieved sources | Uncited sentences (avg) | Words (avg) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for s in SETUPS:
        x = st[s]
        if s == "A":
            cited = "— (no citations)"
            grounded = (
                f"{pct(x['pack_macro'])} ({x['pack_supported']}/{x['pack_checked']})"
            )
        else:
            cited = (
                f"{pct(x['cite_macro'])} ({x['cite_supported']}/{x['cite_checked']})"
            )
            grounded = "— (not measured)"
        out.append(
            f"| {NAMES[s]} | {num(x['quality'])} | {cited} | {grounded} | "
            f"{num(x['uncited'])} | {num(x['words'], 0)} |"
        )

    c = st["C"]
    out += [
        "",
        f"Percentages are the average over topics; the brackets are claims supported / claims "
        f"checked, added up over all topics. Quality parts (C vs B vs A): depth "
        f"{num(c['depth'])} / {num(st['B']['depth'])} / {num(st['A']['depth'])}, structure "
        f"{num(c['structure'])} / {num(st['B']['structure'])} / {num(st['A']['structure'])}, "
        f"balance {num(c['balance'])} / {num(st['B']['balance'])} / {num(st['A']['balance'])}.",
        "",
        "## Head to head (topics won / tied / lost)",
        "",
    ]
    for label, key in (
        ("C vs B, judge quality", "c_vs_b_quality"),
        ("C vs B, share of cited claims supported", "c_vs_b_support"),
        ("B vs A, judge quality", "b_vs_a_quality"),
        ("C vs A, judge quality", "c_vs_a_quality"),
    ):
        w, t, l = summary[key]
        out.append(f"- {label}: {w} / {t} / {l}")

    out += [
        "",
        "## What the revision loop did (setup C)",
        "",
        f"- Average critic score of the first draft: {num(c['first_score'])}, of the best draft: "
        f"{num(c['best_score'])} (this is ThinkMesh's own critic, not the judge)",
        f"- Average revisions per report: {num(c['revisions'], 2)}; reports that were revised at all: "
        f"{pct(c['revised_share'])}",
        "",
        "## Per topic",
        "",
        "| Topic | Quality A / B / C | Support B / C | Critic scores in C |",
        "| --- | --- | --- | --- |",
    ]
    for t in summary["rows"]:
        s = t["setups"]
        quality = " / ".join(str(s[k]["judge"]["quality"]["overall"]) for k in SETUPS)
        support = " / ".join(
            pct((s[k]["judge"].get("citations") or {}).get("support_rate"))
            for k in ("B", "C")
        )
        path = " → ".join(str(v) for v in s["C"]["meta"].get("scores", [])) or "—"
        out.append(f"| {t['topic'][:70]} | {quality} | {support} | {path} |")

    if summary["incomplete"]:
        out += ["", "Left out (a setup failed or was not judged yet):", ""]
        out += [f"- {topic}" for topic in summary["incomplete"]]

    out += ["", "## Limitations (read before quoting any number)", "", LIMITATIONS]
    return "\n".join(out)


def write_summary(summary: dict, path) -> str:
    text = render(summary)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return text


if __name__ == "__main__":
    import os

    eval_dir = Path(os.getenv("EVAL_DIR", "eval"))
    print(write_summary(summarize(eval_dir / "results"), eval_dir / "RESULTS.md"))
    sys.exit(0)
