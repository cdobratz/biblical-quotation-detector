# Services Overview

This document provides an overview of all Python modules in the Biblical Quotation Detector project, organized by their `__init__.py` package structure.

---

## Package Structure

```
src/
├── __init__.py              # Root package
├── models.py                # Shared data models
├── memory/
│   ├── __init__.py          # Memory/vector storage package
│   ├── mem0_manager.py      # Mem0-based memory management
│   ├── bulk_ingest.py       # Bulk data ingestion
│   └── qdrant_manager.py    # Direct Qdrant vector operations
├── llm/
│   ├── __init__.py          # LLM integration package
│   └── claude_client.py     # Claude API client
└── search/
    ├── __init__.py          # Search/detection package
    └── detector.py          # Quotation detection engine
```

---

## src/__init__.py

**Purpose**: Root package marker for the Biblical Quotation Detector.

**Contents**:
- Package version number (`__version__ = "0.1.0"`)
- Module-level docstring describing the project

**Why Needed**: Required for Python to recognize `src/` as an importable package. Enables imports like `from src.memory import Mem0Manager`.

---

## src/memory/__init__.py

**Purpose**: Memory and vector storage services package.

**Contents**:
```python
from .mem0_manager import Mem0Manager
from .bulk_ingest import BulkIngester

__all__ = ["Mem0Manager", "BulkIngester"]
```

**Why Needed**:
- Marks `memory/` as a package
- Provides convenient imports at the package level
- Defines the public API via `__all__`

### Services in this Package

| Module | Class | Description |
|--------|-------|-------------|
| `mem0_manager.py` | `Mem0Manager` | High-level Mem0 integration for semantic memory storage. Handles configuration, verse addition, and semantic search using the Mem0 framework. |
| `bulk_ingest.py` | `BulkIngester` | Batch processing pipeline for loading verses from SQLite into the vector store. Supports filtering by source or book. |
| `qdrant_manager.py` | `QdrantManager` | Direct Qdrant vector database operations, bypassing Mem0's LLM layer for ~130x faster ingestion. Uses sentence-transformers for local embeddings. |

### Usage Example
```python
from src.memory import Mem0Manager, BulkIngester

# Or for fast operations
from src.memory.qdrant_manager import QdrantManager
```

---

## src/llm/__init__.py

**Purpose**: LLM (Large Language Model) integration services package.

**Contents**:
```python
# LLM module for biblical quotation detection
```

**Why Needed**:
- Marks `llm/` as a package
- Currently minimal; ready for expansion with additional LLM providers

### Services in this Package

| Module | Class | Description |
|--------|-------|-------------|
| `claude_client.py` | `ClaudeClient` | Anthropic Claude API client for intelligent quotation verification. Classifies matches (exact, paraphrase, allusion) and provides confidence scores with scholarly explanations. |

### Key Features
- **Match Classification**: Categorizes matches as exact, close_paraphrase, loose_paraphrase, allusion, or non_biblical
- **Confidence Scoring**: 0-100% confidence assessment
- **Greek Text Analysis**: Expert-level analysis of biblical Greek texts
- **Verification Pipeline**: Analyzes vector search candidates for accuracy

### Usage Example
```python
from src.llm.claude_client import ClaudeClient

client = ClaudeClient()
result = client.verify_quotation(
    input_text="Μακάριοι οἱ πτωχοὶ τῷ πνεύματι",
    candidates=[...],
)
```

---

## src/search/__init__.py

**Purpose**: Search and quotation detection services package.

**Contents**:
```python
# Search module for biblical quotation detection
```

**Why Needed**:
- Marks `search/` as a package
- Contains the core detection engine

### Services in this Package

| Module | Class | Description |
|--------|-------|-------------|
| `detector.py` | `QuotationDetector` | Multi-stage quotation detection pipeline combining vector search with LLM verification. The main entry point for detection operations. |

### Key Features
- **Multi-Stage Pipeline**:
  1. Vector semantic search (Qdrant) for candidate retrieval
  2. LLM verification (Claude) for accurate classification
- **Dual Modes**:
  - `use_llm=True`: Full verification with Claude (accurate, ~3-5s)
  - `use_llm=False`: Heuristic-only mode (fast, ~100-200ms)
- **Batch Processing**: Process multiple texts efficiently
- **Configurable Thresholds**: Adjustable similarity and confidence settings

### Usage Example
```python
from src.search.detector import QuotationDetector

detector = QuotationDetector(use_llm=True)
result = detector.detect("Μακάριοι οἱ πτωχοὶ τῷ πνεύματι")

print(f"Is quotation: {result.is_quotation}")
print(f"Match type: {result.match_type}")
print(f"Confidence: {result.confidence}%")
print(f"Best match: {result.best_match.reference}")
```

---

## Data Flow Diagram

```
                    ┌─────────────────────────────────┐
                    │       User Input (Greek)         │
                    └─────────────────┬───────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────┐
                    │    src/search/detector.py       │
                    │      QuotationDetector          │
                    └─────────────────┬───────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│  src/memory/        │  │  src/llm/           │  │   SQLite DB         │
│  qdrant_manager.py  │  │  claude_client.py   │  │   (verses table)    │
│                     │  │                     │  │                     │
│  - Vector search    │  │  - Classification   │  │  - Verse lookup     │
│  - Embeddings       │  │  - Verification     │  │  - FTS search       │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
              │                       │                       │
              │                       │                       │
              ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           DetectionResult                                │
│  - is_quotation, confidence, match_type, sources, explanation           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Dependencies Between Packages

| Package | Depends On | Purpose |
|---------|------------|---------|
| `src.search` | `src.memory`, `src.llm` | Detection combines vector search and LLM verification |
| `src.memory` | External: `qdrant-client`, `sentence-transformers`, `mem0ai` | Vector operations |
| `src.llm` | External: `anthropic` | Claude API access |

---

## Configuration

All packages use environment variables from `.env`:

| Variable | Used By | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | `llm`, `memory` | Claude API authentication |
| `MEM0_VECTOR_STORE` | `memory` | Vector store backend (default: qdrant) |
| `MEM0_EMBEDDING_MODEL` | `memory` | Embedding model (default: multilingual-e5-large) |
| `DATABASE_PATH` | `search` | Path to SQLite database |

---

## Adding New Services

To add a new service:

1. Create the module in the appropriate package
2. Update the package's `__init__.py` to export key classes
3. Add to `__all__` for explicit public API
4. Update this documentation

Example:
```python
# src/memory/__init__.py
from .mem0_manager import Mem0Manager
from .bulk_ingest import BulkIngester
from .new_service import NewService  # Add new import

__all__ = ["Mem0Manager", "BulkIngester", "NewService"]
```

---

**Last Updated**: January 16, 2026
