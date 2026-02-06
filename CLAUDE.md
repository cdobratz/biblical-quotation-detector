# Biblical Quotation Detector - Heuristic Match Improvement (Options A + D)

## Problem

The heuristic classifier in `src/search/detector.py` over-classifies results. In the 1 Clement test (`results/i_clement/`), 655 of 657 chunks were labeled `close_paraphrase` because the embedding model (`intfloat/multilingual-e5-large`) compresses all Koine Greek into a narrow similarity band (0.857–0.959). 29% of those have zero actual word overlap with the matched verse.

## Goal

Implement Option A (minimum word overlap gate) + Option D (minimum chunk word count filter) to reduce false positives while preserving true matches. After changes, re-run the 1 Clement test and verify improved distribution.

## Data-Driven Targets

From `results/i_clement/report_20260122_152324.json` analysis:
- Score range: 0.857–0.959 (stdev 0.013) — thresholds alone cannot separate true from false
- 192 chunks (29.2%) have 0 meaningful shared words — must be rejected
- 228 chunks (34.7%) have only 1 shared word — should be allusion at most
- 114 chunks (17.4%) have ≥3 shared words — legitimate candidates
- 54 chunks (8.2%) have ≤5 words — too short to reliably classify
- 7 chunks (1.1%) have ≤3 words — noise
- The 2 true exact matches have 7+ word overlap — must be preserved

## Tasks

### Task 1: Add word overlap utility function

**File:** `src/search/detector.py`

Add a helper function `_count_shared_words(text_a: str, text_b: str) -> int` that:
- Normalizes both texts (strip diacritics via `unicodedata.normalize('NFKD')`, lowercase)
- Splits into word sets
- Filters out words with ≤2 characters (articles, particles like ο, η, εν, τα)
- Returns count of shared content words

Place it as a static/private method on `QuotationDetector` or as a module-level function above the class.

### Task 2: Update `_heuristic_classify` with word overlap gate

**File:** `src/search/detector.py`, method `_heuristic_classify` (lines 268–326)

Replace the current threshold-only logic with combined score + word overlap:

```
shared_words = _count_shared_words(text, best_candidate_text)
input_word_count = len(text.split())

# Gate: reject short chunks as unreliable
if input_word_count < 4:
    → non_biblical

# Combined classification
if top_score >= 0.95 and shared_words >= 5:
    → exact, confidence 95
elif top_score >= 0.90 and shared_words >= 3:
    → close_paraphrase, confidence 85
elif top_score >= 0.85 and shared_words >= 2:
    → loose_paraphrase, confidence 70
elif top_score >= 0.80 and shared_words >= 1:
    → allusion, confidence 55
else:
    → non_biblical, confidence 60
```

Update the explanation string to include shared word count, e.g.:
`"Heuristic: score=0.912, shared_words=4. Top match: Matthew 5:3."`

### Task 3: Update chunk minimum in `test_patristic.py`

**File:** `scripts/test_patristic.py`, function `chunk_text` (line 177)

Change the minimum chunk filter from character-based to also require minimum word count:
- Keep `len(chunk) < 20` character check
- Add: skip chunks with fewer than 4 words (`len(chunk.split()) < 4`)

### Task 4: Add tests for the word overlap function

**File:** Create `tests/test_word_overlap.py`

Write unit tests for `_count_shared_words`:
- Two identical Greek texts → high overlap count
- Two completely different texts → 0
- Texts sharing only articles/particles (≤2 char words) → 0
- Known 1 Clement exact match (Acts 7:28 text vs matched verse) → ≥5
- Short text (3 words) → correct count
- Mixed Greek with diacritics vs normalized → same result

### Task 5: Re-run 1 Clement heuristic test

Run: `uv run python scripts/test_patristic.py --url "https://jtauber.github.io/apostolic-fathers/001-i_clement.html" --mode heuristic --min-confidence 50 --chunk-size sentence --output results/i_clement/`

### Task 6: Verify improved distribution

After re-run, analyze the new report and confirm:
- `close_paraphrase` count dropped significantly (target: <100, was 655)
- `non_biblical` count increased substantially
- The 2 known exact matches are still detected (Acts 7:28, Galatians 3:6)
- Chunks with ≥3 word overlap are classified as close_paraphrase or better
- Chunks with 0 word overlap are classified as non_biblical
- No regressions in the detection pipeline (no crashes, all chunks processed)

If distribution is still off, adjust thresholds iteratively. Write findings to `results/i_clement/IMPROVEMENT_NOTES.md`.

## Files to Modify

- `src/search/detector.py` — main changes (Tasks 1, 2)
- `scripts/test_patristic.py` — chunk filter (Task 3)
- `tests/test_word_overlap.py` — new file (Task 4)

## Files NOT to Modify

- `src/llm/claude_client.py` — LLM path is separate, no changes needed
- `src/memory/qdrant_manager.py` — vector search unchanged
- `src/models.py` — data models unchanged
- `src/api/` — API layer unchanged

## Constraints

- Do not change the `DetectionResult` or `DetectionSource` dataclass schemas
- Do not change vector search behavior or Qdrant config
- Do not modify LLM verification path (`_llm_verify`)
- Keep the heuristic classifier fast (no network calls, no model loading)
- Use only stdlib for the word overlap function (`unicodedata`, `re`)
- Preserve backward compatibility: existing API consumers see same response shape
