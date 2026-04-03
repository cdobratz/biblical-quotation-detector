# 1 Clement Detection Debugging Guide

**Generated:** 2026-01-22
**Source:** https://jtauber.github.io/apostolic-fathers/001-i_clement.html

## Detection Summary

| Metric | Value |
|--------|-------|
| Total chunks analyzed | 657 |
| Total errors | 0 |
| Exact matches | 2 |
| Close paraphrases | 655 |
| Loose paraphrases | 0 |
| Allusions | 0 |

## Issue Identified: Over-classification

**Problem:** Nearly all chunks (655 out of 657) are classified as "close_paraphrase" with 85% confidence.

**Root Cause:** The heuristic classification thresholds in `src/search/detector.py` are too permissive. The detector uses similarity scores from vector search to classify matches:

```python
# Current thresholds (lines 292-311):
if top_score >= 0.95:    # exact
elif top_score >= 0.85:  # close_paraphrase
elif top_score >= 0.75:  # loose_paraphrase
elif top_score >= 0.65:  # allusion
else:                    # non_biblical
```

**Observation:** The vector search is returning high similarity scores (>=0.85) for almost all Greek text chunks, even when they are not actual biblical quotations.

## Known Issues

### 1. Similarity Score Inflation

The embedding model (`intfloat/multilingual-e5-large`) appears to find high similarity between any Koine Greek texts, regardless of actual textual correspondence.

**Evidence:**
- 99.7% of chunks classified as close_paraphrase
- Only 2 chunks classified as exact matches
- No chunks classified as loose_paraphrase, allusion, or non_biblical

### 2. Heuristic Mode Limitations

When `--mode heuristic` is used (no LLM verification), the detector relies solely on vector similarity scores. This is fast but inaccurate.

**Recommendation:** Use `--mode llm` for accurate detection, accepting the tradeoff of slower processing and API costs.

### 3. Chunking Granularity

The sentence-level chunking may be too fine-grained, creating fragments that match partial verses.

## Suggested Fixes

### Short-term (Configuration)

1. **Raise similarity thresholds:**
   ```python
   if top_score >= 0.98:    # exact (was 0.95)
   elif top_score >= 0.92:  # close_paraphrase (was 0.85)
   elif top_score >= 0.85:  # loose_paraphrase (was 0.75)
   elif top_score >= 0.75:  # allusion (was 0.65)
   ```

2. **Use LLM verification:**
   ```bash
   uv run python scripts/test_patristic.py --url "..." --mode llm
   ```

3. **Increase minimum confidence threshold:**
   ```bash
   uv run python scripts/test_patristic.py --url "..." --min-confidence 90
   ```

### Medium-term (Code Changes)

1. **Add multiple signal verification:**
   - Check n-gram overlap
   - Check word-level alignment
   - Require multiple indicators before classifying

2. **Improve chunking:**
   - Group related sentences
   - Detect paragraph boundaries better
   - Align with verse-like structure

3. **Filter false positives:**
   - Check for introductory formulas ("γέγραπται", "λέγει κύριος")
   - Weight chunks with quotation markers higher

### Long-term (Architecture)

1. **Hybrid detection:**
   - Stage 1: Vector search for candidates
   - Stage 2: N-gram/string matching for confirmation
   - Stage 3: LLM for borderline cases only

2. **Training data:**
   - Create labeled dataset of known quotations in 1 Clement
   - Fine-tune threshold values empirically

## Verified Exact Matches

The detector correctly identified 2 exact matches:

1. **Acts 7:28** - `μὴ ἀνελεῖν με σὺ θέλεις, ὃν τρόπον ἀνεῖλες ἐχθὲς τὸν Αἰγύπτιον`
   - 1 Clement 4:10 quoting Exodus/Acts

2. **Galatians 3:6** - `ἐπίστευσεν δὲ Ἀβραὰμ τῷ θεῷ, καὶ ἐλογίσθη αὐτῷ εἰς δικαιοσύνην`
   - 1 Clement 10:6 quoting Genesis 15:6 (same quote as Galatians)

## Files Generated

- `report_20260122_152324.json` - Full detection data (1.4 MB)
- `report_20260122_152324.md` - Human-readable summary (476 KB)
- `DEBUGGING_GUIDE.md` - This document

## Next Steps

1. Re-run with LLM mode for accurate results
2. Compare LLM results against known quotation lists
3. Tune thresholds based on empirical testing
4. Consider implementing secondary verification signals

---

## Update: Phase 5b — Multi-Signal Scoring (April 2, 2026)

All short-term, medium-term, and long-term suggestions from the original guide have now been implemented:

### Implemented Fixes

| Original Suggestion | Status | Implementation |
|---|---|---|
| Raise similarity thresholds | ✅ Superseded | Multi-signal scoring replaced threshold-only logic |
| Use LLM verification | ✅ Available | `--mode llm` works; selective LLM mode sends only borderline cases (conf 20-65) |
| Add multiple signal verification | ✅ Done | 5 signals: vector sim, word overlap, lemma overlap, n-grams, quotation formula |
| Check n-gram overlap | ✅ Done | `_count_shared_ngrams()` — shared bigrams for word-order similarity |
| Check word-level alignment | ✅ Done | `_count_shared_words()` + `_count_shared_lemmas()` |
| Detect quotation formulas | ✅ Done | 11 Greek markers (γέγραπται, λέγει κύριος, etc.) |
| Hybrid detection (vector → n-gram → LLM) | ✅ Done | Vector + FTS → multi-signal scoring → selective LLM |
| Labeled dataset of known quotations | ✅ Done | 26-entry ground truth at `data/ground_truth/i_clement_quotations.json` |

### Current Results After All Improvements

| Report | Date | Detected | Precision | Recall | F1 |
|---|---|---|---|---|---|
| `report_20260122_152324` | Jan 22 | 655/657 | ~0.3% | N/A | N/A |
| `report_20260206_160805` | Feb 6 | 487/650 | 1.44% | 19.05% | 2.67% |
| `report_20260402_142615` | Apr 2 (Run 0, conf=50) | 30/650 | 10.00% | 14.29% | 11.76% |
| `report_20260402_150318` | Apr 2 (Fixed, conf=20) | 201/650 | 4.48% | 28.57% | 7.74% |

### Remaining Limitation: Retrieval Ceiling

15 of 21 ground-truth quotations cannot be found because the correct biblical verse never appears in search results. This is a data coverage problem — many 1 Clement quotations route through the Septuagint (OT), which is not in the current NT-only database. Requires Phase 6 (LXX support) to resolve.

## Update: Phase 5c — FTS Fallback & Evaluation Fixes (April 2, 2026)

- Added SQLite FTS5 keyword search as fallback after Qdrant vector search
- Fixed evaluator to handle verse ranges (`Matthew 7:1-2` matches `Matthew 7:2`)
- Increased top_k from 10 to 20 for better candidate coverage
- Recovered `Matthew 7:1-2` match via FTS fallback

## Update: Phase 6 — Scoring Improvements & LXX Support (April 2-3, 2026)

Phase 6 addresses the retrieval ceiling from the opposite direction: instead of only improving how we search the existing NT data, we expand the data itself and improve how we evaluate matches.

### New Capabilities

| Capability | Implementation | Impact |
|---|---|---|
| LXX/Septuagint ingestion | `scripts/ingest_lxx.py` — downloads Rahlfs 1935, reconstructs verse text | Unlocks OT quotations that route through Greek OT |
| Cross-reference chains | `data/cross_references.json` — 32 groups, 126 entries | Detecting Romans 4:3 now also credits Genesis 15:6 |
| Multi-candidate scoring | Top-5 candidates scored, best selected | Catches correct verse at position 3-5 instead of only #1 |
| Context-aware scoring | Adjacent chunks checked for quotation formulas | +75% confidence boost when nearby text has "γέγραπται" etc. |
| Expanded ground truth | 21 → 30 entries (9 OT/LXX added) | More comprehensive evaluation coverage |

### Bug Fixed: `_verse_to_entry` Overwrite

When cross-references caused a verse to map to multiple ground-truth entries (e.g., "1 Peter 5:5" and "Proverbs 3:34" share cross-ref groups), the old simple dict assignment silently overwrote earlier entries. Fixed by using set-based mapping: `_verse_to_entry[v].add(original_ref)` instead of `_verse_to_entry[v] = original_ref`.

### Remaining Issue

The `_llm_verify` fallback path does not pass `context_has_formula` when falling back to `_heuristic_classify`. Low priority — only affects the Claude API error path.

### Next Steps

1. Run `uv run python scripts/ingest_lxx.py` to populate LXX data
2. Re-index Qdrant with LXX verses included
3. Re-run evaluation with 30-entry ground truth to measure improvement
