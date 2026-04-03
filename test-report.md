# Test Report: Multi-Signal Scoring & Detection Improvements

**PR**: https://github.com/cdobratz/biblical-quotation-detector/pull/2
**Session**: https://app.devin.ai/sessions/c98658377afe49eea5ef03bb4ae9bf50
**Date**: 2026-04-02

## Summary

Tested all new helper functions and the evaluation script via shell commands. All 6 tests passed (31/31 assertions). One bug was found and fixed during testing: quotation formula regex patterns failed to match precomposed Greek Unicode characters (e.g. `ὕ` U+1F55). Fixed by NFKD-decomposing input and using base-character-only patterns.

## Escalations

- **Cannot test full end-to-end detection**: `bible.db` and Qdrant vectors are not populated on this machine (data files not in repo). Re-indexing with the new `query:`/`passage:` prefixes and running a full detection pass against 1 Clement requires the source data.
- **Cannot test selective LLM verification**: Requires an Anthropic API key to verify Claude is only called for borderline cases (confidence 20-65).
- **Evaluation baseline precision is low (1.44%)**: This is expected — the baseline report was generated before these improvements. After re-indexing with e5 prefixes and multi-signal scoring, precision should improve significantly.

## Test Results

- **Test 1: Quotation formula detection** -- PASSED (13/13)
  - All 10 known Greek formula patterns correctly detected (including precomposed Unicode variants)
  - All 3 non-formula texts correctly rejected
- **Test 2: Stem-based lemma overlap** -- PASSED (4/4)
  - Morphological variants `θεός/θεοῦ` share lemmas (overlap=2 vs word overlap=1)
  - Unrelated texts return 0; identical texts return exact word count
- **Test 3: N-gram overlap** -- PASSED (4/4)
  - Identical 5-token text: 4 shared bigrams
  - Reversed text: 0 shared bigrams (word order matters)
  - Partial overlap: correctly returns 2
- **Test 4: Multi-signal score computation** -- PASSED (7/7)
  - High confidence (sim=0.98, 8 words, formula=True): score=98.0 (>= 80)
  - Low confidence (sim=0.82, 0 words, no formula): score=2.0 (<= 20)
  - Medium confidence (sim=0.90, 3 words): score=36.0 (in [25, 70])
  - Ordering correct: 98.0 > 36.0 > 2.0; all in [0, 100]
- **Test 5: Evaluation script** -- PASSED
  - Ran against baseline report (650 chunks, 487 detected)
  - Outputs precision (1.44%), recall (19.05%), F1 (2.67%)
  - Per-type recall: exact=50%, close_paraphrase=12.5%, allusion=0%
  - Found 4 references, missed 17 — consistent with pre-improvement baseline
- **Test 6: Existing unit tests (Regression)** -- PASSED (18/18)
  - All 18 tests in `tests/test_word_overlap.py` pass with no regressions

## Bug Found & Fixed During Testing

**Issue**: `_detect_quotation_formula("οὕτως λέγει ὁ θεός")` returned `False` instead of `True`.

**Root cause**: Precomposed Greek Unicode characters (e.g. `ὕ` = U+1F55, upsilon with dasia+oxia) didn't match regex character classes like `[υὐ]`. Additionally, pattern literals like `ὡς` and `ὁ` contained diacritics that didn't match after text decomposition.

**Fix** (2 commits):
1. NFKD-decompose input text and strip combining marks before pattern matching
2. Rewrite all regex patterns using only base Greek characters (no diacritics)

## What Could Not Be Tested

| Feature | Reason | How to Test |
|---|---|---|
| e5 `query:`/`passage:` prefix impact | No `bible.db` or populated Qdrant on test machine | Re-index with `uv run python scripts/ingest.py`, then run detection |
| Selective LLM verification | No Anthropic API key available | Run detection with `ANTHROPIC_API_KEY` set, check logs for borderline-only calls |
| Full detection improvement | No source data for re-indexing | After re-indexing, compare `evaluate.py` results against baseline |

---

## Post-Merge Validation (April 2, 2026)

Re-indexed Qdrant with e5 `passage:` prefixes (77,491 vectors, 16.7 min), then ran four detection configurations against 1 Clement to find optimal tuning.

### Results Comparison

| Metric | Run 0 (baseline) | Run A (low conf) | Run B (relaxed gates) | Run C (rebalanced) |
|--------|-----------------|-------------------|----------------------|---------------------|
| **Config** | conf=50, default | conf=20, default | conf=20, relaxed gates | conf=20, relaxed gates + new weights |
| Detected | 30 | 201 | 193 | 356 |
| True Positives | 3 | 7 | 7 | 8 |
| False Positives | 27 | 194 | 186 | 348 |
| **Precision** | **10.00%** | 3.48% | 3.63% | 2.25% |
| **Recall** | 14.29% | 23.81% | 23.81% | **28.57%** |
| **F1** | **11.76%** | 6.08% | 6.29% | 4.17% |
| Refs found | 3 | 5 | 5 | 6 |

### References Found Per Run

| Reference | Run 0 | Run A | Run B | Run C |
|-----------|-------|-------|-------|-------|
| Acts 7:28 | yes | yes | yes | yes |
| Galatians 3:6 | yes | yes | yes | yes |
| 1 Corinthians 2:9 | yes | yes | yes | yes |
| 1 Peter 5:5 | - | yes | yes | yes |
| 1 Peter 4:8 | - | yes | yes | yes |
| Romans 3:28 | - | - | - | yes |

### Key Takeaways

1. **Run 0 (default, conf=50) has the best F1** at 11.76% — highest precision (10%) outweighs its lower recall.

2. **Lowering min-confidence from 50 to 20** (Run A) recovers 2 more references but at the cost of 167 more false positives. The classification logic already labels things correctly — the issue is that 16 of 21 ground-truth quotations aren't being matched to the right biblical reference at all.

3. **Relaxing gates** (Run B) barely changes results vs Run A — the word overlap gates aren't the bottleneck.

4. **Rebalancing weights** (Run C) gets the most recall (28.57%, 6 refs) but precision craters (2.25%).

5. **The real bottleneck is reference matching**: 15-16 quotations are consistently missed regardless of tuning. These are likely cases where 1 Clement paraphrases so loosely that the vector search doesn't surface the right biblical verse in the top results at all — a retrieval problem, not a scoring problem.

### Missed Reference Diagnostic (April 2, 2026)

Searched Qdrant directly with each ground-truth Clement text to classify failures as **retrieval** (target verse not in top-5 results) vs **scoring** (target found but scored too low).

**Result: All 15 missed references are retrieval failures.** The correct biblical verse never appears in the top-5 search results. No amount of threshold/weight tuning can fix this.

Two additional problems compound the retrieval issue:

#### Problem A: Verse-Range Matching in Evaluator

The evaluator uses exact string matching on references. Ground truth uses ranges like `Matthew 7:1-2`, but the detector returns single verses like `Matthew 7:2`. These are **not counted as matches** even when the correct verse is found. Affected cases:
- `1 Corinthians 13:4-7` — detector finds `1 Corinthians 13:7` and `13:8` (near-miss)
- `Matthew 7:1-2` — detector finds `Matthew 7:2` with conf=48 (near-miss)
- `1 Corinthians 12:21-22`, `1 Corinthians 1:10-12`, `Luke 6:36-38`, `Romans 1:29-32`, `Hebrews 1:3-5`

#### Problem B: Retrieval Returns Wrong Verses

For many ground-truth quotations, the embedding model retrieves semantically similar but wrong verses:
- `Romans 12:5` ("one body in Christ") → retrieves `1 Corinthians 12:27` (same theme, wrong verse)
- `Matthew 26:24` ("better not born") → retrieves `Mark 9:45` (similar "better" phrasing)
- `Acts 20:35` ("giving vs receiving") → retrieves unrelated wisdom literature
- `Matthew 28:19` (Great Commission) → retrieves `2 Thessalonians 2:14`
- `Romans 11:33` ("unsearchable depths") → retrieves wisdom literature with similar vocabulary

#### Summary of Failure Modes

| Failure Mode | Count | Fix |
|---|---|---|
| Retrieval failure (wrong verse in top-k) | 10 | Increase top_k, add FTS fallback search |
| Evaluator verse-range matching | 5+ | Fuzzy reference matching (book + chapter + overlapping verses) |
| Scoring too low (but retrievable) | 0 | N/A — not the bottleneck |

---

## Fixes Applied (April 2, 2026)

Three fixes were implemented to address the diagnostic findings:

### Fix 1: Evaluator verse-range matching (`scripts/evaluate.py`)

Added `expand_verse_range()` helper that expands ground-truth ranges like `Matthew 7:1-2` into `{Matthew 7:1, Matthew 7:2, Matthew 7:1-2}`. Updated `build_known_refs()` to expand all ground-truth entries. Recall is now counted by **ground-truth entry** (denominator=21), not by individual expanded verse, so ranges don't inflate the denominator.

### Fix 2: FTS fallback search (`src/search/detector.py`)

Added `_fts_search()` method that queries the existing SQLite FTS5 index (`verses_fts`) using content words from the input text. After Qdrant vector search, FTS results are merged (deduplicated by reference, Qdrant results take priority). Only queries the `SR` source to avoid duplicates. FTS results get a synthetic similarity score of 0.80.

### Fix 3: Increased top_k from 10 to 20 (`src/search/detector.py`)

Changed the default `top_k` parameter in `QuotationDetector.__init__()` from 10 to 20. More candidates means better coverage for the scoring/classification logic.

### Results After Fixes

| Metric | Run 0 (pre-fix) | Fixed (conf=20) | Fixed (conf=50) |
|--------|-----------------|-----------------|-----------------|
| Detected | 30 | 201 | 30 |
| True Positives | 3 | 9 | 3 |
| False Positives | 27 | 192 | 27 |
| Precision | 10.00% | 4.48% | 10.00% |
| Recall | 14.29% | 28.57% | 14.29% |
| F1 | 11.76% | 7.74% | 11.76% |
| Refs found | 3/21 | 6/21 | 3/21 |

References found with fixes (conf=20): Acts 7:28, Galatians 3:6, 1 Corinthians 2:9, 1 Peter 4:8, 1 Peter 5:5, Matthew 7:1-2.

### Remaining Retrieval Ceiling

15 of 21 ground-truth quotations remain missed across all configurations. These are genuine retrieval failures where Clement's paraphrasing is too loose for either vector search or keyword matching. Root causes:
- Many 1 Clement quotations route through the **Septuagint (OT)**, not the NT directly — the database only contains NT verses
- Thematic allusions share no distinctive vocabulary with the source verse
- The embedding model retrieves semantically similar but wrong verses (e.g., same theme, different book)

Improving beyond this ceiling will likely require **Septuagint/LXX support** (Phase 6) and/or cross-reference chain detection.

---

## Phase 6: Scoring Improvements Test Results (April 2-3, 2026)

**PR**: [#5](https://github.com/cdobratz/biblical-quotation-detector/pull/5) (merged)
**Session**: https://app.devin.ai/sessions/c98658377afe49eea5ef03bb4ae9bf50

### Summary

Tested all 5 new features + the `_verse_to_entry` bug fix via adversarial Python scripts. **7/7 tests passed.** All shell-based (no GUI).

### Test Results

- **Test 1: `_verse_to_entry` set-based fix (THE BUG FIX)** -- PASSED
  - `_verse_to_entry["1 Peter 5:5"]` correctly maps to `{'1 Peter 5:5', 'Proverbs 3:34'}` (both entries, not just one)
  - Both entries present in `_entries["all"]` — no overwrites
- **Test 2: Evaluate recall with overlapping cross-references** -- PASSED
  - Detecting "James 4:6" correctly credits BOTH "1 Peter 5:5" and "Proverbs 3:34" ground-truth entries
  - `ground_truth_found` = 2, `ground_truth_missed` = 0
- **Test 3: Multi-candidate scoring selects best candidate** -- PASSED
  - With 3 candidates (high sim/no overlap, medium, low sim/high overlap), correctly selected candidate #3 (Galatians 3:6)
  - Explanation: `best_candidate=#3`, confidence=56, match_type=`close_paraphrase`
- **Test 4: Context-aware formula detection boosts scoring** -- PASSED
  - Score WITHOUT context formula: 20
  - Score WITH context formula: 35 (75% boost)
  - Explanation correctly shows `context_formula=yes`
- **Test 5: Ground truth expanded to 30 entries** -- PASSED
  - 4 exact + 8 close_paraphrase + 18 allusions = 30 total
  - All 9 OT entries verified present and correctly categorized
- **Test 6: Cross-reference loading integrity** -- PASSED
  - Both `_load_cross_references()` (detector.py) and `load_cross_references()` (evaluate.py) return identical 126-entry mappings across 32 groups
  - Genesis 15:6 → {Genesis 15:6, Romans 4:3, Galatians 3:6, James 2:23}
  - 1 Peter 5:5 → {1 Peter 5:5, Proverbs 3:34, James 4:6}
- **Test 7: Regression -- existing unit tests** -- PASSED (18/18)

### Not Tested (Out of Scope)

| Feature | Reason | How to Test |
|---|---|---|
| LXX ingestion end-to-end | No `bible.db` on test machine | Run `uv run python scripts/ingest_lxx.py` on machine with bible.db |
| Full detection pipeline | No populated Qdrant vector store | After LXX ingestion + re-indexing, run detection on 1 Clement |
| LLM verification path | No Anthropic API key | Run with `ANTHROPIC_API_KEY` set |
| `_llm_verify` fallback `context_has_formula` | Low-priority error path | Not fixed in this PR |
