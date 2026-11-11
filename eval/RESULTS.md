## Evaluation

I compared three setups on 12 topics (all with the same writer model, `groq/openai/gpt-oss-120b`):
**A** a plain LLM answer, **B** numbered web sources + one draft, **C** the full ThinkMesh
write → critique → revise loop. B and C used identical source pages. A separate model
(`nvidia/nemotron-3-ultra-550b-a55b`, free tier) scored every report. Settings: 3 sources per
topic, 2,500 characters per page, target score 8, max 2 revisions. Code version: tag `eval-v1`.
Raw data: `eval/results/`, full table: `eval/RESULTS.md`.

| Setup | Judge quality (/10) | Cited claims supported | Uncited sentences / report |
| --- | --- | --- | --- |
| A: plain AI answer | 8.5 | n/a (no citations) | 39.8 |
| B: sources + writer | 7.8 | 62% (107/174) | 9.8 |
| C: full ThinkMesh | 7.9 | 54% (123/225) | 7.5 |

**Findings**
- The revision loop raised the pipeline's own critic score (6.5 → 7.8) but showed no
  measurable gain in judge quality (C vs B: 4 wins / 2 ties / 6 losses) or in citation support
  (4 / 0 / 7). With 12 topics and swings of ±30 points per topic, B and C are not distinguishable.
- C took a median of 78 s per report vs 4 s for B (about 20× longer).
- A scored highest on the judge's quality rubric, but its reports are longer (about 1,150 words
  vs about 700) and the judge never sees sources, so this does not measure accuracy.

**Limitations**
- One free-tier AI judge, not checked against humans.
- "Supported" means an AI judge found the claim in the cited source excerpt. It is not a measure of truth. "Partial" matches are not counted as supported.
- Source excerpts are short (first 2,500 characters of each page) and some contain website clutter.
- A manual spot check of 10 random cited claims found 2 (both from C) whose key terms do not
  appear in the cited excerpts, so the model sometimes adds outside knowledge while citing.
- Small sample (12 topics); topics were chosen before running and the code was frozen
  before the final run.