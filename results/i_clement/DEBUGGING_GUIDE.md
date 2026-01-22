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
