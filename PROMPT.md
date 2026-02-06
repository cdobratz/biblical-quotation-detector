# Ralph Loop: Improve Heuristic Match Classification (Options A + D)

## Context

Read `CLAUDE.md` for the full task specification, data analysis, and constraints.

The heuristic classifier in `src/search/detector.py` over-classifies all Greek text as `close_paraphrase` because the embedding model produces a narrow score band (0.857–0.959). We need to add a word overlap gate (Option A) and minimum chunk word count filter (Option D).

## Instructions

Work through these steps in order. Check git status and existing files before each step to see what prior iterations have already completed. Skip completed steps.

### Step 1: Add `_count_shared_words` to `src/search/detector.py`

A helper that normalizes Greek text (strip diacritics, lowercase), splits into words, filters words ≤2 chars, and returns the count of shared content words between two texts. Use only `unicodedata` and `re` from stdlib.

### Step 2: Update `_heuristic_classify` in `src/search/detector.py`

Replace threshold-only logic with combined score + word overlap classification:
- input < 4 words → non_biblical
- score ≥ 0.95 AND shared ≥ 5 → exact (confidence 95)
- score ≥ 0.90 AND shared ≥ 3 → close_paraphrase (confidence 85)
- score ≥ 0.85 AND shared ≥ 2 → loose_paraphrase (confidence 70)
- score ≥ 0.80 AND shared ≥ 1 → allusion (confidence 55)
- else → non_biblical (confidence 60)

Include shared word count in explanation string.

### Step 3: Update `chunk_text` in `scripts/test_patristic.py`

Add minimum 4-word filter alongside existing 20-character minimum.

### Step 4: Create `tests/test_word_overlap.py`

Unit tests for `_count_shared_words`: identical texts, disjoint texts, articles-only overlap, diacritics handling, known exact match from 1 Clement data.

### Step 5: Run tests

Run `uv run python -m pytest tests/test_word_overlap.py -v`. Fix any failures.

### Step 6: Re-run 1 Clement detection

Run: `uv run python scripts/test_patristic.py --url "https://jtauber.github.io/apostolic-fathers/001-i_clement.html" --mode heuristic --min-confidence 50 --chunk-size sentence --output results/i_clement/`

### Step 7: Validate results

Analyze the new JSON report. Confirm:
- close_paraphrase count < 100 (was 655)
- The 2 known exact matches preserved (Acts 7:28, Galatians 3:6)
- Chunks with 0 word overlap → non_biblical

Write findings to `results/i_clement/IMPROVEMENT_NOTES.md`.

If all validations pass, output: <promise>HEURISTIC IMPROVED</promise>

If tests fail or distribution is still bad, fix the issue and continue iterating.

## Do NOT

- Modify `src/llm/claude_client.py`, `src/memory/qdrant_manager.py`, `src/models.py`, or `src/api/`
- Change `DetectionResult` or `DetectionSource` dataclass schemas
- Add external dependencies beyond stdlib
- Make network calls in the heuristic classifier
