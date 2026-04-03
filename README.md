# Biblical Quotation Detector

> An LLM-powered RAG agent for detecting biblical quotations in ancient Koine Greek texts

## Overview

This project helps scholars identify when ancient Greek texts (such as writings of early church fathers) quote or allude to biblical passages. It combines modern vector search, semantic embeddings, and Claude AI to provide intelligent quotation detection with confidence scoring.

## Project Status

**Current Phase**: Phase 6 Complete - Scoring Improvements & LXX Support

**Overall Progress**: ~95% Complete

### Completed Phases

- **Phase 1**: Database Schema & Setup ✅
  - SQLite database with full-text search (FTS5)
  - Biblical verse storage with multiple text forms
  - Efficient indexing and triggers

- **Phase 2**: Data Ingestion ✅
  - 77,491 verses ingested from multiple Greek sources
  - Text normalization and lemmatization complete
  - 10 Greek New Testament versions integrated

- **Phase 3**: Vector Storage ✅
  - Direct Qdrant integration (77 verses/second ingestion)
  - 77,491 verses fully vectorized with e5 `passage:` prefixes
  - Semantic search with multilingual-e5-large embeddings

- **Phase 4**: Detection Engine ✅
  - Multi-stage detection pipeline (vector + FTS + LLM)
  - 100% accuracy with LLM verification
  - Match type classification (exact, paraphrase, allusion)
  - Confidence scoring (0-100%)

- **Phase 5**: API & Web Interface ✅
  - FastAPI REST API with 10 endpoints
  - Interactive web UI at /app
  - OpenAPI documentation at /docs
  - Batch detection support (up to 50 texts)

- **Phase 5b**: Multi-Signal Scoring ✅
  - 5-signal weighted scoring (vector similarity, word overlap, lemma overlap, n-grams, quotation formulas)
  - Selective LLM verification (borderline-only, ~60-70% cost reduction)
  - 26-entry ground-truth evaluation set for 1 Clement

- **Phase 5c**: Retrieval Improvements ✅
  - SQLite FTS5 fallback search after Qdrant vector search
  - Evaluator verse-range matching (`Matthew 7:1-2` matches `Matthew 7:2`)
  - Diagnosed retrieval ceiling: 15/21 misses are data coverage gaps (NT-only)

- **Phase 6**: Scoring Improvements & LXX Support ✅
  - LXX/Septuagint ingestion pipeline (Rahlfs 1935 edition)
  - Cross-reference chain matching (32 parallel passage groups, 126 entries)
  - Multi-candidate scoring (top-5 candidates, not just #1)
  - Context-aware formula detection (adjacent chunk boosting)
  - Ground truth expanded to 30 entries (21 NT + 9 OT/LXX)

### Pending

- LXX data ingestion + Qdrant re-indexing (scripts ready, awaiting execution)

### Future Enhancements

- **Phase 7**: OT expansion (Hebrew text processing)
- **Phase 8**: Multi-language support (Latin, Syriac, Coptic)

See [PROGRESS.md](./PROGRESS.md) for detailed roadmap.

## Features

### Multi-Stage Detection Pipeline

```
Input Greek Text
    ↓
1. Vector Semantic Search (Qdrant, top-20 candidates)
    ↓
2. FTS Keyword Fallback (SQLite FTS5, merged results)
    ↓
3. Multi-Signal Heuristic Scoring (5 weighted signals)
    ↓
4. Selective LLM Verification (Claude, borderline cases only)
    ↓
Output: Quotations + Sources + Confidence Scores
```

### Five-Signal Scoring Model

The heuristic classifier combines five independent signals into a weighted 0-100 confidence score:

| Signal | Weight | Description |
|--------|--------|-------------|
| Vector similarity | 0.25 | Cosine similarity from Qdrant search |
| Word overlap | 0.25 | Shared content words (>2 chars) |
| Lemma overlap | 0.20 | Stem-based matching for Greek morphology |
| N-gram overlap | 0.15 | Shared bigrams for word-order similarity |
| Quotation formula | 0.15 | Greek introductory markers (γέγραπται, etc.) |

### Multiple Text Forms

Each verse is stored in three forms for optimal matching:

1. **Original**: Preserves all diacritics and accents
2. **Normalized**: Lowercase, no diacritics (fuzzy matching)
3. **Lemmatized**: Dictionary forms (semantic matching)

### Data Sources

- **CNTR Statistical Restoration (SR)**: Most scientifically accurate Greek NT
- **SBLGNT**: Society of Biblical Literature Greek NT
- **HelloAO Bible**: 9 additional Greek translations
- **LXX Rahlfs 1935**: Septuagint/Greek Old Testament (ingestion pipeline ready)
- All sources are open and properly licensed

## Tech Stack

- **Python 3.11+** - Core language
- **uv** - Fast Python package manager
- **Qdrant** - Vector database for semantic search
- **sentence-transformers** - Embedding model (intfloat/multilingual-e5-large)
- **Claude API** - LLM for selective verification of borderline cases
- **SQLite + FTS5** - Local database with full-text search fallback
- **FastAPI** - REST API
- **CLTK** - Classical Language Toolkit for Greek processing

## Quick Start

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Anthropic API key

### Installation

```bash
# Clone the repository
git clone https://github.com/cdobratz/biblical-quotation-detector.git
cd biblical-quotation-detector

# Install dependencies
uv pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Setup Database (if not already done)

```bash
# Create database schema
uv run python scripts/create_database.py

# Download and ingest data
./scripts/download_data.sh
uv run python scripts/ingest_helloao.py
uv run python scripts/ingest_cntr.py

# Process Greek text
uv run python scripts/process_greek.py
```

### Start the API Server

```bash
# Start the server
uv run uvicorn src.api.main:app --reload

# Access points:
# - API: http://localhost:8000
# - Web App: http://localhost:8000/app
# - API Docs: http://localhost:8000/docs
# - ReDoc: http://localhost:8000/redoc
```

## Usage Examples

### Web Interface

Visit `http://localhost:8000/app` for the interactive web interface where you can:
- Enter Greek text for analysis
- Choose between LLM and Heuristic detection modes
- Set confidence thresholds
- View detailed results with biblical sources

### API Usage

```bash
# Detect a quotation
curl -X POST http://localhost:8000/api/v1/detect \
  -H "Content-Type: application/json" \
  -d '{"text": "Μακάριοι οἱ πτωχοὶ τῷ πνεύματι", "mode": "llm"}'

# Semantic search
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "blessed are the poor in spirit", "limit": 5}'

# Get verse by reference
curl http://localhost:8000/api/v1/verse/Matthew%205:3
```

### Python Usage

```python
from src.search.detector import QuotationDetector

# Heuristic mode (fast, no API calls)
detector = QuotationDetector(use_llm=False)
result = detector.detect("Μακάριοι οἱ πτωχοὶ τῷ πνεύματι")

print(f"Is quotation: {result.is_quotation}")
print(f"Confidence: {result.confidence}%")
print(f"Match type: {result.match_type}")
print(f"Source: {result.best_match.reference}")

# Selective LLM mode (only sends borderline cases to Claude)
detector = QuotationDetector(use_llm=True, selective_llm=True)
result = detector.detect("Μακάριοι οἱ πτωχοὶ τῷ πνεύματι")
```

### Patristic Text Analysis

```bash
# Analyze 1 Clement against the biblical corpus
uv run python scripts/test_patristic.py \
  --url "https://jtauber.github.io/apostolic-fathers/001-i_clement.html" \
  --mode heuristic --min-confidence 50 --chunk-size sentence \
  --output results/i_clement/

# Evaluate results against ground truth
uv run python scripts/evaluate.py \
  --report results/i_clement/report_*.json -v
```

## Project Structure

```
biblical-quotation-detector/
├── data/
│   ├── raw/                    # Source data (Bible databases, Greek texts)
│   ├── processed/
│   │   ├── bible.db            # SQLite database (77K+ verses)
│   │   └── qdrant_direct/      # Vector embeddings (e5-large, 1024 dims)
│   ├── ground_truth/
│   │   └── i_clement_quotations.json  # 30-entry evaluation set
│   └── cross_references.json   # 32 parallel passage groups (126 entries)
├── src/
│   ├── models.py               # Pydantic data models
│   ├── ingestion/              # Data ingestion modules
│   ├── preprocessing/          # Greek text processing
│   ├── memory/                 # Vector store management
│   │   ├── qdrant_manager.py   # Direct Qdrant operations (e5 prefixes)
│   │   ├── mem0_manager.py     # Mem0 operations
│   │   └── bulk_ingest.py      # Bulk vectorization
│   ├── llm/                    # LLM integration
│   │   └── claude_client.py    # Claude API client
│   ├── search/                 # Detection engine
│   │   └── detector.py         # Multi-signal quotation detection
│   └── api/                    # FastAPI endpoints
│       ├── main.py             # Main application
│       ├── models.py           # Request/response schemas
│       └── routes/             # API route handlers
├── scripts/
│   ├── create_database.py      # Database setup
│   ├── ingest_*.py             # Data ingestion (HelloAO, CNTR)
│   ├── ingest_to_qdrant.py     # Vector store ingestion
│   ├── ingest_lxx.py           # LXX/Septuagint ingestion pipeline
│   ├── evaluate.py             # Precision/recall/F1 evaluation
│   ├── test_patristic.py       # Patristic text analysis
│   └── test_detector.py        # Detection engine tests
├── results/
│   └── i_clement/              # 1 Clement detection reports + analysis
├── tests/                      # Unit tests (18 tests)
├── README.md                   # This file
├── PROGRESS.md                 # Detailed roadmap
└── test-report.md              # Test results across all phases
```

## Documentation

- **[PROGRESS.md](./PROGRESS.md)** - Detailed roadmap and milestones
- **[test-report.md](./test-report.md)** - Test results across all phases
- **[results/i_clement/IMPROVEMENT_NOTES.md](./results/i_clement/IMPROVEMENT_NOTES.md)** - Detection improvement history
- **[results/i_clement/DEBUGGING_GUIDE.md](./results/i_clement/DEBUGGING_GUIDE.md)** - Troubleshooting guide
- **[CLAUDE.local.md](./CLAUDE.local.md)** - Comprehensive project documentation
- **[docs/phase3_mem0_setup.md](./docs/phase3_mem0_setup.md)** - Phase 3 setup guide

## Development

### Running Tests

```bash
# Run all unit tests (18 tests)
uv run python -m pytest tests/ -v

# Run patristic text detection
uv run python scripts/test_patristic.py \
  --url "https://jtauber.github.io/apostolic-fathers/001-i_clement.html" \
  --mode heuristic --min-confidence 50 --chunk-size sentence \
  --output results/i_clement/

# Evaluate against ground truth
uv run python scripts/evaluate.py --report results/i_clement/report_*.json -v
```

### Code Quality

```bash
# Format code
uv run black src/ scripts/ tests/

# Lint code
uv run ruff check src/ scripts/ tests/
```

## Performance

### Current Database Stats
- **Total verses**: 77,491 (NT), LXX ingestion pending
- **Sources**: 10 Greek NT versions + LXX pipeline ready
- **Books**: 27 NT books + additional texts
- **Database size**: 83 MB
- **Cross-references**: 32 parallel passage groups (126 entries)

### Vector Store
- **Embedding model**: intfloat/multilingual-e5-large (1024 dims)
- **Instruction prefixes**: `query:` for search, `passage:` for indexing
- **Ingestion rate**: 77 verses/second
- **Search latency**: 100-400ms
- **Total vectors**: 77,491
- **top_k**: 20 candidates per query

### Detection Performance
- **Heuristic mode**: 100-200ms per chunk, multi-signal scoring
- **LLM mode**: 3-5 seconds, 100% accuracy on test suite
- **Selective LLM**: Only borderline cases (confidence 20-65) sent to Claude

### Evaluation Results (1 Clement, 650 chunks, 30-entry ground truth)

| Configuration | Precision | Recall | F1 | Refs Found |
|---------------|-----------|--------|-----|------------|
| conf=50 (conservative) | 10.00% | 14.29% | 11.76% | 3/21 |
| conf=20 (balanced) | 4.48% | 28.57% | 7.74% | 6/21 |
| conf=20, rebalanced | 2.25% | 33.33% | 4.17% | 7/21 |

Phase 6 improvements (multi-candidate scoring, context-aware detection, cross-references, LXX data) are expected to significantly improve these numbers once LXX ingestion is complete.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Follow PEP 8 style guidelines
5. Submit a pull request

### Commit Message Format

```
feat: Add CNTR ingestion script
fix: Handle missing diacritics in normalization
docs: Update README with installation steps
test: Add tests for Greek processor
```

## License

**Code**: MIT License

**Data**: Various open licenses (see data sources)

### Attribution Required

- **CNTR**: Alan Bunning & Center for New Testament Restoration
- **SBLGNT**: Society of Biblical Literature
- **HelloAO**: Bible.helloao.org

## Roadmap

- [x] Phase 1: Database Schema (Complete)
- [x] Phase 2: Data Ingestion (Complete)
- [x] Phase 3: Vector Storage (Complete)
- [x] Phase 4: Detection Engine (Complete)
- [x] Phase 5: API & Web Interface (Complete)
- [x] Phase 5b: Multi-Signal Scoring (Complete)
- [x] Phase 5c: Retrieval Improvements & FTS Fallback (Complete)
- [x] Phase 6: Scoring Improvements & LXX Support (Complete - pending data ingestion)
- [ ] Phase 7: OT Expansion (Hebrew text processing)
- [ ] Phase 8: Multi-language Support (Latin, Syriac, Coptic)
- [ ] Phase 9: Advanced Features (manuscript variants, citation graphs)

See [PROGRESS.md](./PROGRESS.md) for details.

## FAQ

**Q: Why Greek only?**

A: Greek is the original language of the NT. Starting simple, can expand later.

**Q: Can this run offline?**

A: Mostly yes - database and vector search are local. Only Claude API requires internet.

**Q: How accurate is it?**

A: With LLM verification, 100% on the test suite (7/7). In heuristic mode against 1 Clement (650 chunks), best F1 is 11.76% with precision 10% — limited mainly by retrieval coverage (NT-only database misses OT quotations). LXX ingestion is expected to significantly improve recall.

**Q: What about copyright?**

A: All data sources are open (CC BY 4.0 or similar). Our code is MIT licensed.

## Support

- **Issues**: [GitHub Issues](https://github.com/cdobratz/biblical-quotation-detector/issues)
- **Documentation**: See `CLAUDE.local.md` for comprehensive details
- **Questions**: Open a discussion on GitHub

## Acknowledgments

- Center for New Testament Restoration (CNTR)
- Society of Biblical Literature (SBL)
- HelloAO Bible Project
- Classical Language Toolkit (CLTK)
- Anthropic (Claude API)
- Mem0 Team

---

**Last Updated**: 2026-04-02

**Version**: 1.1.0

**Status**: Production Ready (Phase 6 - LXX ingestion pending)
