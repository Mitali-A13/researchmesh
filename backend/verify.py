"""Checks the citations in a finished report.

Two layers:
1. Automatic checks (no AI, free and instant):
   - does every cited number [n] point to a real source?
   - which sources were never cited?
   - how many sentences have no citation?
   - do the figures in a sentence (51%, $1.75, 380,000...) appear in the
     sources it cites?
2. Optional AI fact-check (one call): a model compares each cited claim with
   the text of the sources it cites and answers supported / partial / unsupported.

The checker only reports. It never edits the report, and a failure here never
breaks report generation.
"""

import os
import re

CITATION = re.compile(r"\[(\d+)\]")
NUMBER = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?%?")

MAX_CLAIMS = int(os.getenv("MAX_CLAIMS_TO_CHECK", "40"))
MIN_WORDS = 6  # shorter fragments are not treated as sentences
MAX_FLAGGED_SHOWN = 8

LABELS = {
    "partial": "partly supported",
    "unsupported": "not supported",
    "invalid_citation": "invalid citation",
    "figure_not_found": "figure not found",
}


# ---------- reading the report ----------


def _prepare_line(raw: str) -> str:
    line = raw.strip()
    if not line or line.startswith("#"):
        return ""
    if re.fullmatch(r"[\s|:\-]+", line):  # table separator row
        return ""
    if line.startswith("|"):  # table row: keep it only if it carries a citation
        if not CITATION.search(line):
            return ""
        cells = [c.strip() for c in line.strip("|").split("|")]
        line = " — ".join(c for c in cells if c)
    line = re.sub(r"^([-*+]|\d+[.)])\s+", "", line)  # bullet or list number
    return line.replace("**", "").replace("__", "").strip()


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z\["“(])', text)
    merged: list[str] = []
    for part in parts:
        # a lone "[3]." after a full stop belongs to the sentence before it
        if merged and re.fullmatch(r"(?:\[\d+\]\s*)+[.!?]?", part.strip()):
            merged[-1] += " " + part.strip()
        else:
            merged.append(part)
    return [p.strip() for p in merged]


def _plain(sentence: str) -> str:
    """Sentence without its [n] markers, tidied for display."""
    text = CITATION.sub("", sentence)
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"\s+([.,;:!?])", r"\1", text).strip()


def extract_sentences(body: str) -> list[str]:
    sentences = []
    for raw in body.splitlines():
        line = _prepare_line(raw)
        if not line:
            continue
        sentences.extend(
            s for s in _split_sentences(line) if len(s.split()) >= MIN_WORDS
        )
    return sentences


# ---------- figures ----------


def _figures(sentence: str) -> list[str]:
    """Numbers worth checking: 2+ digits, decimals, percentages and money."""
    text = CITATION.sub("", sentence)
    found = []
    for match in NUMBER.finditer(text):
        token = match.group()
        digits = re.sub(r"[^\d.]", "", token).rstrip(".")
        important = (
            len(digits.replace(".", "")) >= 2
            or "." in digits
            or token.endswith("%")
            or token.startswith("$")
        )
        if important and digits:
            found.append(digits)
    return found


def _normalize_source(text: str) -> str:
    return re.sub(r"(?<=\d),(?=\d)", "", text)  # 380,000 -> 380000


def _figure_in_text(figure: str, text: str) -> bool:
    pattern = r"(?<![\d.])" + re.escape(figure) + r"(?!\d|\.\d)"
    return re.search(pattern, text) is not None


# ---------- AI fact-check ----------


def _normalize_verdict(value) -> str:
    text = str(value).lower().strip()
    if "unsupport" in text or "not support" in text or "contradict" in text:
        return "unsupported"
    if "partial" in text:
        return "partial"
    if text.startswith("support"):
        return "supported"
    return "partial"  # unclear answers are never counted as fully supported


def _llm_check(claims: list[dict], sources: list[dict], chain):
    sources_text = "\n\n".join(
        f"[{s['id']}] {s['title']}\n{s['text']}" for s in sources
    )
    claims_text = "\n".join(
        f"{c['id']}. (cites {''.join('[' + str(i) + ']' for i in c['citations'])}) {c['text']}"
        for c in claims
    )
    return chain.invoke({"sources": sources_text, "claims": claims_text}).checks


# ---------- main entry ----------


def verify_report(
    body: str, sources: list[dict], verifier_chain=None, max_claims=None
) -> dict:
    """Check the citations in `body` (the report text, without its Sources list)."""
    cap = MAX_CLAIMS if max_claims is None else max_claims
    valid = {s["id"] for s in sources}
    source_text = {s["id"]: _normalize_source(s["text"]) for s in sources}

    cited, uncited, used = [], 0, set()
    for sentence in extract_sentences(body):
        ids = sorted({int(n) for n in CITATION.findall(sentence)})
        if not ids:
            uncited += 1
            continue
        cited.append({"id": len(cited) + 1, "text": sentence, "citations": ids})
        used.update(ids)

    result = {
        "claims_total": len(cited),
        "uncited_sentences": uncited,
        "invalid_citations": sorted(used - valid),
        "unused_sources": sorted(valid - used),
        "figures_not_found": 0,
        "llm_used": False,
        "checked": 0,
        "supported": 0,
        "partial": 0,
        "unsupported": 0,
        "support_rate": None,
        "flagged": [],
        "notes": [],
    }

    def flag(claim, verdict, reason):
        result["flagged"].append(
            {
                "claim": _plain(claim["text"]),
                "citations": claim["citations"],
                "verdict": verdict,
                "reason": reason,
            }
        )

    # layer 1: automatic checks
    for claim in cited:
        bad = [i for i in claim["citations"] if i not in valid]
        good = [i for i in claim["citations"] if i in valid]
        if bad:
            flag(
                claim,
                "invalid_citation",
                "cites " + ", ".join(f"[{i}]" for i in bad) + ", which does not exist",
            )
        if good:
            missing = [
                f
                for f in _figures(claim["text"])
                if not any(_figure_in_text(f, source_text[i]) for i in good)
            ]
            if missing:
                result["figures_not_found"] += 1
                flag(
                    claim,
                    "figure_not_found",
                    "figure(s) "
                    + ", ".join(missing)
                    + " not found in the cited sources (could be a calculation)",
                )

    # layer 2: AI fact-check, one batched call
    to_check = [c for c in cited if any(i in valid for i in c["citations"])][:cap]
    if verifier_chain is not None and to_check:
        try:
            checks = _llm_check(to_check, sources, verifier_chain)
        except Exception as exc:
            result["notes"].append(f"AI fact-check skipped: {str(exc)[:120]}")
        else:
            by_id = {c["id"]: c for c in to_check}
            seen = set()
            for check in checks:
                claim = by_id.get(getattr(check, "id", None))
                if claim is None or claim["id"] in seen:
                    continue
                seen.add(claim["id"])
                verdict = _normalize_verdict(getattr(check, "verdict", ""))
                result[verdict] += 1
                if verdict != "supported":
                    flag(claim, verdict, (getattr(check, "reason", "") or "").strip())
            result["llm_used"] = True
            result["checked"] = len(seen)
            if seen:
                result["support_rate"] = round(result["supported"] / len(seen), 3)
            if len(seen) < len(to_check):
                result["notes"].append(
                    f"{len(to_check) - len(seen)} claim(s) were not returned by the fact-checker"
                )
    if len(cited) > cap and verifier_chain is not None:
        result["notes"].append(f"Only the first {cap} cited claims were fact-checked")

    return result


def format_verification(v: dict) -> str:
    """Text block appended to the critique card."""
    lines = ["---", "", "**Citation check**", ""]
    if v["llm_used"] and v["checked"]:
        percent = round(100 * v["supported"] / v["checked"])
        lines.append(
            f"{v['supported']} of {v['checked']} cited claims are fully supported by their sources ({percent}%)."
        )
        lines += [
            "",
            f"- Partly supported: {v['partial']}",
            f"- Not supported: {v['unsupported']}",
        ]
    else:
        lines.append(
            f"Automatic checks only. {v['claims_total']} sentences carry citations."
        )
        lines.append("")
    invalid = ", ".join(f"[{i}]" for i in v["invalid_citations"]) or "none"
    unused = ", ".join(f"[{i}]" for i in v["unused_sources"]) or "none"
    lines += [
        f"- Sentences without a citation: {v['uncited_sentences']}",
        f"- Citations to sources that do not exist: {invalid}",
        f"- Sources never cited: {unused}",
        f"- Sentences with figures not found in their sources: {v['figures_not_found']}",
    ]
    if v["flagged"]:
        lines += ["", "Flagged claims:", ""]
        for item in v["flagged"][:MAX_FLAGGED_SHOWN]:
            text = (
                item["claim"]
                if len(item["claim"]) <= 160
                else item["claim"][:157] + "..."
            )
            cites = "".join(f"[{i}]" for i in item["citations"])
            label = LABELS.get(item["verdict"], item["verdict"])
            reason = f": {item['reason']}" if item["reason"] else ""
            lines.append(f'- "{text}" {cites} ({label}){reason}')
        hidden = len(v["flagged"]) - MAX_FLAGGED_SHOWN
        if hidden > 0:
            lines.append(f"- ...and {hidden} more")
    for note in v["notes"]:
        lines.append(f"- Note: {note}")
    return "\n".join(lines)
