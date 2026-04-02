# 1 Clement Heuristic Improvement Notes

**Date:** 2026-02-06
**Changes:** Options A (word overlap gate) + D (minimum chunk word count filter)

## Summary

The heuristic classifier was updated to combine vector similarity scores with a word overlap gate. This resolved the over-classification problem where 99.7% of chunks were labeled `close_paraphrase`.

## Before (report_20260122_152324)

| Match Type | Count | Percentage |
|---|---|---|
| exact | 2 | 0.3% |
| close_paraphrase | 655 | 99.7% |
| loose_paraphrase | 0 | 0.0% |
| allusion | 0 | 0.0% |
| non_biblical | 0 | 0.0% |
| **Total chunks** | **657** | |

## After (report_20260206_160805)

| Match Type | Count | Percentage |
|---|---|---|
| exact | 2 | 0.3% |
| close_paraphrase | 55 | 8.5% |
| loose_paraphrase | 224 | 34.5% |
| allusion | 206 | 31.7% |
| non_biblical | 163 | 25.1% |
| **Total chunks** | **650** | |

## Key Improvements

1. **close_paraphrase reduced by 91.6%**: 655 → 55 (target was <100)
2. **non_biblical introduced**: 0 → 163 chunks correctly identified as non-biblical
3. **Full match type spectrum**: All 5 categories now populated with reasonable distribution
4. **Both known exact matches preserved**:
   - Acts 7:28 (score=0.959, shared_words=6) — 1 Clement 4:10
   - Galatians 3:6 (score=0.953, shared_words=8) — 1 Clement 10:6
5. **Zero-overlap chunks correctly rejected**: All 163 chunks with 0 shared content words → non_biblical
6. **Short chunks filtered**: 7 fewer chunks processed (657 → 650) due to 4-word minimum

## Changes Made

### 1. `src/search/detector.py` — Word overlap gate (Option A)

Added module-level functions:
- `_normalize_greek(text)` — strips diacritics (NFKD), removes punctuation, normalizes final sigma (ς → σ), lowercases
- `_count_shared_words(text_a, text_b)` — counts shared words >2 characters between two texts

Updated `_heuristic_classify()` to require both score AND word overlap:

| Score | Shared Words | Classification |
|---|---|---|
| ≥ 0.95 | ≥ 5 | exact (95% confidence) |
| ≥ 0.90 | ≥ 3 | close_paraphrase (85%) |
| ≥ 0.85 | ≥ 2 | loose_paraphrase (70%) |
| ≥ 0.80 | ≥ 1 | allusion (55%) |
| else | any | non_biblical (60%) |

Chunks with < 4 words → non_biblical regardless of score.

### 2. `scripts/test_patristic.py` — Minimum chunk size (Option D)

Added `len(chunk.split()) < 4` filter alongside existing 20-character minimum. This removes very short chunks that cannot be reliably classified.

### 3. `_normalize_greek` — Punctuation and sigma handling

Two key normalization improvements were needed for accurate word matching:
- **Punctuation stripping**: The input text contained attached punctuation (e.g., `θέλεις,`) that prevented matching with the biblical text (`θελεισ`)
- **Final sigma normalization**: Greek uses ς at word endings vs σ elsewhere. The biblical database stores both forms inconsistently, so normalizing all sigma to σ ensures consistent matching

Without these, the Acts 7:28 exact match had only 4 shared words (below the ≥5 threshold). After fixing, it correctly reports 6 shared words.

### 4. `tests/test_word_overlap.py` — 18 unit tests

Covers: identical texts, disjoint texts, articles-only overlap, known exact matches (Acts 7:28, Galatians 3:6), diacritics handling, empty strings, sigma normalization.

## Word Overlap Distribution

| Shared Words | Chunks | % | Typical Classification |
|---|---|---|---|
| 0 | 163 | 25.1% | non_biblical |
| 1 | 206 | 31.7% | allusion |
| 2 | 126 | 19.4% | loose_paraphrase |
| 3 | 54 | 8.3% | close_paraphrase |
| 4 | 16 | 2.5% | close_paraphrase |
| 5+ | 85 | 13.1% | close_paraphrase/exact |

## Why Thresholds Alone Could Not Work

The embedding model (`intfloat/multilingual-e5-large`) compresses all Koine Greek text into a narrow similarity band:

- **Score range**: 0.857–0.959
- **Standard deviation**: 0.013
- **68% of scores fall between**: 0.879–0.905

With such a narrow band, no single threshold can separate true matches from false. The word overlap gate provides the discriminating signal that the embedding model cannot.

---

## Update: Phase 5b — Multi-Signal Scoring (April 2, 2026)

### Further Improvements Beyond Word Overlap Gate

The word overlap gate (Options A+D) was a critical first step. Phase 5b replaced the threshold+gate system with a **weighted multi-signal scoring model** combining 5 independent signals:

| Signal | Weight | Purpose |
|---|---|---|
| Vector similarity | 0.25 | Semantic match (rescaled from [0.80, 1.0]) |
| Word overlap | 0.25 | Surface-form word matching (capped at 8) |
| Lemma overlap | 0.20 | Stem-based matching for Greek morphology (capped at 10) |
| N-gram overlap | 0.15 | Word-order similarity via shared bigrams (capped at 5) |
| Quotation formula | 0.15 | Binary: Greek introductory marker detected |

Classification now uses continuous confidence scores with dual gates:

| Match Type | Confidence | Word Gate |
|---|---|---|
| exact | >= 70 | >= 5 shared words |
| close_paraphrase | >= 50 | >= 3 |
| loose_paraphrase | >= 35 | >= 2 |
| allusion | >= 20 | >= 1 word OR >= 2 lemmas |
| non_biblical | below | — |

### Qdrant Re-indexing with e5 Prefixes

The `intfloat/multilingual-e5-large` model requires `query:` and `passage:` instruction prefixes for optimal performance. After adding these prefixes to the code, all 77,491 vectors were re-indexed (16.7 min, 77.3 verses/sec).

### Comparison Across All Phases

| Phase | Report Date | Detected | close_paraphrase | non_biblical | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| Pre-improvement | Jan 22 | 655 | 655 (99.7%) | 0 (0%) | ~0.3% | N/A | N/A |
| Option A+D | Feb 6 | 487 | 55 (8.5%) | 163 (25.1%) | 1.44% | 19.05% | 2.67% |
| Multi-signal + e5 re-index | Apr 2 (conf=50) | 30 | 27 (4.2%) | 449 (69.1%) | 10.00% | 14.29% | 11.76% |
| Multi-signal + e5 (conf=20) | Apr 2 | 201 | 27 (4.2%) | 449 (69.1%) | 3.48% | 23.81% | 6.08% |

### Tuning Experiments (April 2, 2026)

Four configurations were tested to find the precision-recall sweet spot:

| Run | Config | Detected | Precision | Recall | F1 | Refs Found |
|---|---|---|---|---|---|---|
| Run 0 | conf=50, default weights | 30 | **10.00%** | 14.29% | **11.76%** | 3/21 |
| Run A | conf=20, default weights | 201 | 3.48% | 23.81% | 6.08% | 5/21 |
| Run B | conf=20, relaxed gates | 193 | 3.63% | 23.81% | 6.29% | 5/21 |
| Run C | conf=20, rebalanced weights | 356 | 2.25% | **33.33%** | 4.17% | 7/21 |

**Key finding**: Relaxing gates (Run B) barely changed results — the word overlap gates are not the bottleneck. Rebalancing weights (Run C) gets the most recall but at the cost of precision.

## Update: Phase 5c — FTS Fallback & Retrieval Diagnosis (April 2, 2026)

### Missed Reference Diagnostic

All 15 consistently missed ground-truth references were investigated by searching Qdrant directly with the ground-truth Clement text. **All 15 are retrieval failures** — the correct biblical verse never appears in the top-k results.

| Missed Reference | What Qdrant Returns Instead | Why |
|---|---|---|
| Romans 12:5 ("one body in Christ") | 1 Corinthians 12:27 | Same theme, different verse |
| Matthew 26:24 ("better not born") | Mark 9:45 | Similar "better" phrasing |
| Acts 20:35 ("giving vs receiving") | Wisdom literature | No distinctive shared vocab |
| Hebrews 1:3-5 ("radiance of glory") | Sirach 44:2 | Both use μεγαλωσύνη |
| Luke 6:36-38 ("be merciful") | Baruch 3:2 / Matthew 7:7 | Similar imperative structure |
| 1 Corinthians 1:10-12 | Ephesians 1:1, Colossians 1:1 | "Paul apostle" formula |

### Fixes Applied

1. **FTS fallback search**: SQLite FTS5 keyword search supplements Qdrant, catching cases where exact words match but embedding similarity is low
2. **Evaluator verse-range matching**: `Matthew 7:1-2` now matches detected `Matthew 7:2` via `expand_verse_range()` helper
3. **Increased top_k**: 10 → 20 for better candidate coverage

### Results After Fixes

Best result (conf=20, FTS+top_k=20): P=4.48%, R=28.57%, F1=7.74%, 6/21 refs found.

### Remaining Retrieval Ceiling

15/21 ground-truth quotations are unreachable because:
- Many 1 Clement quotations route through the **Septuagint (OT)** — database is NT-only
- Thematic allusions share no distinctive vocabulary with the NT source verse
- Embedding model retrieves semantically similar but wrong verses

**Next step**: Phase 6 — Septuagint/LXX ingestion to break through this ceiling.
