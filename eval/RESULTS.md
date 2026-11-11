# ThinkMesh evaluation

Based on **12 topics** where all three setups finished and were judged (12 topics started).

Writer model: `groq/openai/gpt-oss-120b` · Judge model: `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` · sources per topic: 3 · characters per page: 2500 · target score: 8 · max revisions: 2 · started: 2026-11-10 21:35

## Results

| Setup | Judge quality (/10) | Cited claims supported | Grounded in retrieved sources | Uncited sentences (avg) | Words (avg) |
| --- | --- | --- | --- | --- | --- |
| A: plain AI answer | 8.5 | — (no citations) | 13% (65/478) | 39.8 | 1150 |
| B: sources + writer | 7.8 | 62% (107/174) | — (not measured) | 9.8 | 672 |
| C: full ThinkMesh | 7.9 | 54% (123/225) | — (not measured) | 7.5 | 720 |

Percentages are the average over topics; the brackets are claims supported / claims checked, added up over all topics. Quality parts (C vs B vs A): depth 7.9 / 7.8 / 8.8, structure 8.8 / 8.9 / 9.3, balance 7.8 / 6.9 / 7.6.

## Head to head (topics won / tied / lost)

- C vs B, judge quality: 4 / 2 / 6
- C vs B, share of cited claims supported: 4 / 0 / 7
- B vs A, judge quality: 1 / 5 / 6
- C vs A, judge quality: 2 / 2 / 8

## What the revision loop did (setup C)

- Average critic score of the first draft: 6.5, of the best draft: 7.8 (this is ThinkMesh's own critic, not the judge)
- Average revisions per report: 1.67; reports that were revised at all: 100%

## Per topic

| Topic | Quality A / B / C | Support B / C | Critic scores in C |
| --- | --- | --- | --- |
| Adoption of Rust in systems programming and its safety benefits | 8 / 8 / 7 | 71% / 38% | 7 → 7 → 9 |
| Carbon capture and storage: technology, costs and scalability | 8 / 10 / 8 | 76% / 52% | 7 → 8 |
| Cybersecurity threats in the age of generative AI: risks, attacks and  | 8 / 8 / 7 | 75% / 90% | 7 → 6 → 7 |
| Economics of vertical farming | 9 / 8 / 8 | 25% / 39% | 7 → 7 → 8 |
| Effects of remote and hybrid work on employee productivity | 9 / 9 / 7 | — / 71% | 6 → 7 → 7 |
| GLP-1 weight-loss drugs: effectiveness, side effects and access | 9 / 7 / 7 | 54% / 23% | 6 → 6 → 7 |
| Growth of UPI digital payments in India | 7 / 5 / 9 | 93% / 56% | 7 → 8 |
| Health effects of microplastics in humans | 9 / 9 / 8 | 38% / 67% | 4 → 7 → 6 |
| How CRISPR-based therapy for sickle cell disease works and what it cos | 9 / 8 / 9 | 60% / 37% | 7 → 8 |
| Obligations for general-purpose AI models under the EU AI Act | 9 / 7 / 8 | 61% / 42% | 7 → 8 |
| Progress in quantum error correction | 8 / 6 / 9 | 83% / 65% | 6 → 7 → 8 |
| Small modular nuclear reactors: promises, costs and risks | 9 / 9 / 8 | 44% / 63% | 7 → 7 → 8 |

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
