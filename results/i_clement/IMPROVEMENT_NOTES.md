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
