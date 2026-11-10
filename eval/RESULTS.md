# ThinkMesh evaluation

Based on **2 topics** where all three setups finished and were judged (2 topics started).

Writer model: `groq/openai/gpt-oss-120b` · Judge model: `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` · sources per topic: 3 · characters per page: 2500 · target score: 8 · max revisions: 2 · started: 2026-11-06 22:25

## Results

| Setup | Judge quality (/10) | Cited claims supported | Grounded in retrieved sources | Uncited sentences (avg) | Words (avg) |
| --- | --- | --- | --- | --- | --- |
| A: plain AI answer | 9.0 | — (no citations) | 19% (11/68) | 34.0 | 1446 |
| B: sources + writer | 8.5 | 77% (22/29) | — (not measured) | 12.0 | 685 |
| C: full ThinkMesh | 8.5 | 66% (18/27) | — (not measured) | 13.0 | 692 |

Percentages are the average over topics; the brackets are claims supported / claims checked, added up over all topics. Quality parts (C vs B vs A): depth 8.5 / 8.5 / 9.0, structure 9.0 / 9.0 / 9.0, balance 8.0 / 8.0 / 8.5.

## Head to head (topics won / tied / lost)

- C vs B, judge quality: 0 / 2 / 0
- C vs B, share of cited claims supported: 0 / 0 / 2
- B vs A, judge quality: 0 / 1 / 1
- C vs A, judge quality: 0 / 1 / 1

## What the revision loop did (setup C)

- Average critic score of the first draft: 7.5, of the best draft: 7.5 (this is ThinkMesh's own critic, not the judge)
- Average revisions per report: 1.00; reports that were revised at all: 50%

## Per topic

| Topic | Quality A / B / C | Support B / C | Critic scores in C |
| --- | --- | --- | --- |
| Current status of solid-state batteries for electric vehicles | 9 / 8 / 8 | 53% / 38% | 7 → 6 → 7 |
| Retrieval-augmented generation versus fine-tuning for enterprise LLM a | 9 / 9 / 9 | 100% / 93% | 8 |

## Limitations (read before quoting any number)

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
