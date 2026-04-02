# Testing: Biblical Quotation Detection Functions

## Overview
This skill covers testing the detection pipeline helper functions and evaluation tools in the biblical-quotation-detector project.

## Devin Secrets Needed
- `ANTHROPIC_API_KEY` — required for testing selective LLM verification (Claude calls) and LLM-mode detection

## Environment Setup
```bash
uv sync
uv pip install pytest
```

## Running Tests

### Existing Unit Tests
```bash
uv run python -m pytest tests/ -v
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
    _normalize_greek,
    _count_shared_words,
)
```

### Evaluation Script
```bash
uv run python scripts/evaluate.py --report results/i_clement/report_YYYYMMDD_HHMMSS.json -v
```
Outputs precision, recall, F1, per-type breakdown, found/missed references.

The evaluator supports verse-range expansion: ground-truth entries like `Matthew 7:1-2` match detected single verses like `Matthew 7:2`. Recall is counted by ground-truth entry (21 entries), not by individual expanded verses.

### Running the API Server
```bash
uv run uvicorn src.api.main:app --reload
# API: http://localhost:8000
# Swagger docs: http://localhost:8000/docs
# Web app: http://localhost:8000/app
```

### Running Patristic Text Analysis
```bash
uv run python scripts/test_patristic.py \
  --url "https://jtauber.github.io/apostolic-fathers/001-i_clement.html" \
  --mode heuristic \
  --min-confidence 50 \
  --chunk-size sentence \
  --output results/i_clement/
```

### Re-indexing Qdrant Vectors
Required after changing embedding prefixes or model:
```bash
uv run python scripts/ingest_to_qdrant.py --clear
```
Takes ~17 minutes for 77,491 verses at ~77 verses/sec.

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
- `data/processed/bible.db` — SQLite database of biblical verses (not in repo, must be generated via ingestion scripts)
- `data/processed/qdrant_direct/` — Qdrant vector store (exists but may be empty on fresh clone)
- Both are required for full detection pipeline testing (API, detector, search)
- Without these, testing is limited to unit-level function verification and evaluation against existing reports in `results/`
- To regenerate: run `scripts/ingest_to_qdrant.py` (requires bible.db to exist first)

### Embedding Model: e5 Instruction Prefixes
The `intfloat/multilingual-e5-large` model requires `query:` and `passage:` instruction prefixes for optimal performance. After changing prefix behavior, existing Qdrant vectors must be **re-indexed** — old embeddings generated without prefixes will produce degraded similarity scores against new prefixed queries.

### Stem-Based Lemmatization
The `_count_shared_lemmas()` function uses character-truncation (~4 chars) as a rough stemming heuristic, NOT real morphological analysis. This is by design for speed, but may produce false positives on short Greek words sharing prefixes. CLTK's actual lemmatizer is available as a project dependency if more accurate lemmatization is needed.

### Narrow Embedding Score Band
The e5 model compresses all Koine Greek into a narrow similarity band (0.857-0.959, stdev 0.013). Thresholds alone cannot separate true matches from false — the word overlap gate and multi-signal scoring provide the discriminating signals.

### FTS Fallback Search
The detector runs SQLite FTS5 keyword search after Qdrant vector search, merging results deduplicated by reference. FTS results get a synthetic similarity score of 0.80 and only query the `SR` source to avoid duplicates. This catches cases where exact words match but embedding similarity is low.

### Retrieval Ceiling (15/21 Ground-Truth Misses)
15 of 21 ground-truth 1 Clement quotations are unreachable with current retrieval. Root causes:
- Many quotations route through the **Septuagint (OT)**, not the NT directly
- Thematic allusions share no distinctive vocabulary with the source verse
- Embedding model retrieves semantically similar but wrong verses
This is a data coverage problem (NT-only database), not a scoring/threshold problem.

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

## Key Test Values

### Multi-Signal Score Expected Ranges
- High confidence (sim=0.98, 8 words, 10 lemmas, 5 ngrams, formula=True): score >= 80
- Low confidence (sim=0.82, 0 words, 0 lemmas, 0 ngrams, no formula): score <= 20
- Medium (sim=0.90, 3 words, 4 lemmas, 2 ngrams, no formula): score in [25, 70]
- Scores always in [0, 100] range

### Known Exact Matches in 1 Clement
- Acts 7:28 — 1 Clement 4:10 (score=0.959, shared_words=6)
- Galatians 3:6 — 1 Clement 10:6 (score=0.953, shared_words=8)

### Ground Truth Dataset
- 26 entries in `data/ground_truth/i_clement_quotations.json`
- Distribution: 4 exact, 8 close paraphrases, 9 allusions, 5 non-biblical
- Evaluator expands verse ranges (e.g. `Matthew 7:1-2` → `Matthew 7:1`, `Matthew 7:2`)
- Recall denominator = 21 (original entry count, not expanded verse count)

### Current Best Evaluation Results
- **conf=50**: P=10.00%, R=14.29%, F1=11.76% (3/21 found) — best F1
- **conf=20**: P=4.48%, R=28.57%, F1=7.74% (6/21 found) — best recall
- Found: Acts 7:28, Galatians 3:6, 1 Corinthians 2:9, 1 Peter 4:8, 1 Peter 5:5, Matthew 7:1-2

### Tuning Parameters Reference
Key constants in `src/search/detector.py`:
- Signal weights: sim=0.25, word=0.25, lemma=0.20, ngram=0.15, formula=0.15
- Similarity rescale: [0.80, 1.0] → [0, 1]
- Caps: words=8, lemmas=10, ngrams=5
- Classification: exact>=70+5w, close>=50+3w, loose>=35+2w, allusion>=20+1w/2l
- top_k=20, min_similarity=0.7
- Selective LLM: high=65, low=20
