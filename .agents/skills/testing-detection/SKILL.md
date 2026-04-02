# Testing: Biblical Quotation Detection Functions

## Overview
This skill covers testing the detection pipeline helper functions and evaluation tools in the biblical-quotation-detector project.

## Devin Secrets Needed
- `ANTHROPIC_API_KEY` — required for testing selective LLM verification (Claude calls)

## Environment Setup
```bash
uv sync
uv pip install pytest
```

## Running Tests

### Existing Unit Tests
```bash
uv run pytest tests/ -v
```
Expect 18 tests in `tests/test_word_overlap.py` covering `_normalize_greek` and `_count_shared_words`.

### Testing Detection Helper Functions
Helper functions can be tested directly via Python imports:
```python
import sys
sys.path.insert(0, '.')
from src.search.detector import (
    _detect_quotation_formula,
    _count_shared_lemmas,
    _count_shared_ngrams,
    _compute_multi_signal_score,
)
```

### Evaluation Script
```bash
uv run python scripts/evaluate.py --report results/i_clement/report_YYYYMMDD_HHMMSS.json -v
```
Outputs precision, recall, F1, per-type breakdown, found/missed references.

## Known Issues & Workarounds

### Greek Unicode in Regex Patterns
Koine Greek text contains precomposed Unicode characters (e.g. `ὕ` = U+1F55, upsilon with dasia+oxia). These do NOT match simple regex character classes like `[υὐ]`. 

**Workaround**: Always NFKD-decompose Greek text and strip combining marks before regex matching. Use base-character-only patterns (no diacritics/breathing marks).

```python
import unicodedata
nfkd = unicodedata.normalize('NFKD', text)
stripped = ''.join(c for c in nfkd if not unicodedata.combining(c))
```

### Data Dependencies for Full E2E Testing
- `data/processed/bible.db` — SQLite database of biblical verses (not in repo, must be generated via ingestion)
- `data/processed/qdrant_direct/` — Qdrant vector store (exists but may be empty)
- Both are required for full detection pipeline testing
- Without these, testing is limited to unit-level function verification and evaluation against existing reports in `results/`

### Stem-Based Lemmatization
The `_count_shared_lemmas()` function uses character-truncation (~4 chars) as a rough stemming heuristic, NOT real morphological analysis. This is by design for speed, but may produce false positives on short Greek words sharing prefixes. CLTK's actual lemmatizer is available as a project dependency if more accurate lemmatization is needed.

## Lint & Format
```bash
ruff check src/ scripts/ tests/
black --check --target-version py311 src/ scripts/ tests/
```

## Test Categories
1. **Quotation formula detection**: Test with various Greek introductory phrases (γέγραπται, λέγει κύριος, etc.) — include precomposed Unicode variants
2. **Lemma overlap**: Test with inflected Greek word pairs (θεός/θεοῦ should match)
3. **N-gram overlap**: Test word-order sensitivity (reversed text should return 0)
4. **Multi-signal scoring**: Test with high/medium/low signal inputs, verify ordering and range [0, 100]
5. **Evaluation script**: Run against existing baseline reports in `results/`
6. **Regression**: All 18 existing tests must continue to pass
