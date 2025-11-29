# Phase 3: Mem0 Vector Store Setup

## Overview

Phase 3 implements the vector store integration using Mem0 and Qdrant for semantic search of biblical verses.

## What's Been Created

### 1. Core Modules

**`src/memory/mem0_manager.py`**
- Manages Mem0 configuration and initialization
- Handles vector store operations (add, search, delete)
- Configured for Qdrant with multilingual embeddings
- Supports both single verse and batch operations

**`src/memory/bulk_ingest.py`**
- Bulk ingestion of verses from SQLite to Mem0
- Supports filtering by source or book
- Batch processing for efficiency
- Progress tracking and error handling

### 2. Scripts

**`scripts/ingest_to_mem0.py`** - Main ingestion script
```bash
# Ingest all verses
uv run python scripts/ingest_to_mem0.py

# Test with limited data
uv run python scripts/ingest_to_mem0.py --limit 100

# Ingest specific source
uv run python scripts/ingest_to_mem0.py --source SR

# Clear and re-ingest
uv run python scripts/ingest_to_mem0.py --clear
```

**`scripts/test_mem0.py`** - Test semantic search
```bash
# Run all tests
uv run python scripts/test_mem0.py

# Test custom query
uv run python scripts/test_mem0.py --query "μακαριοι οι πτωχοι"

# Get more results
uv run python scripts/test_mem0.py --limit 20
```

**`scripts/verify_mem0.py`** - Comprehensive verification
```bash
# Verify entire setup
uv run python scripts/verify_mem0.py
```

## Step-by-Step Setup

### Step 1: Verify Prerequisites

```bash
cd /Users/myone/biblical-quotation-detector
uv run python scripts/verify_mem0.py
```

This checks:
- Environment variables (.env file)
- Database existence and content
- Required directories
- Python dependencies
- Mem0 initialization

### Step 2: Set API Key

Ensure your `.env` file has:
```bash
ANTHROPIC_API_KEY=sk-ant-...  # Your actual API key
```

### Step 3: Test Ingestion (Small Sample)

Start with a small test to verify everything works:

```bash
# Ingest first 100 verses only
uv run python scripts/ingest_to_mem0.py --limit 100
```

Expected output:
- Progress messages for batches
- Summary showing 100 verses added
- No errors

### Step 4: Test Search

```bash
uv run python scripts/test_mem0.py
```

This runs 5 test queries with known biblical quotations:
- Beatitudes (Matthew 5:3)
- Gospel of John opening (John 1:1)
- "God is love" (1 John 4:8)
- Faith, hope, love (1 Corinthians 13:13)
- "I am the way..." (John 14:6)

### Step 5: Full Ingestion

Once testing is successful, ingest all verses:

```bash
# This will take several minutes for ~77,000 verses
uv run python scripts/ingest_to_mem0.py
```

**Performance expectations:**
- ~77,491 total verses
- Processing time: 20-60 minutes (depends on hardware)
- Rate: 20-60 verses/second
- Final size: ~500MB-1GB for vector database

### Step 6: Verify Complete Setup

```bash
uv run python scripts/verify_mem0.py
```

Should show all checks passing.

## Configuration

### Mem0 Settings (in `.env`)

```bash
MEM0_VECTOR_STORE=qdrant
MEM0_EMBEDDING_MODEL=multilingual-e5-large
MEM0_LLM_PROVIDER=anthropic
MEM0_LLM_MODEL=claude-sonnet-4-20250514
```

### Embedding Model

**Model**: `intfloat/multilingual-e5-large`
- Dimensions: 1024
- Supports Greek and English
- High quality semantic embeddings
- Good for biblical text similarity

### Vector Store

**Backend**: Qdrant (local)
- Location: `./data/processed/qdrant_db/`
- No external server needed
- Fast local search
- Persistent storage

## Features

### Text Normalization

Ingestion uses **normalized Greek text** by default:
- Lowercase
- Diacritics removed
- Better for fuzzy matching

To use original text with diacritics:
```bash
uv run python scripts/ingest_to_mem0.py --use-original
```

### Metadata Stored

Each verse embedding includes:
- `reference` (e.g., "Matthew 5:3")
- `book`, `chapter`, `verse`
- `source` (e.g., "SR", "grc_sbl")
- `greek_text` (original with diacritics)
- `greek_normalized` (no diacritics)
- `greek_lemmatized` (dictionary forms)
- `english_text` (if available)

### Search Capabilities

```python
from src.memory.mem0_manager import Mem0Manager

manager = Mem0Manager()

# Semantic search
results = manager.search(
    query="μακαριοι οι πτωχοι",
    limit=10
)

# Each result contains:
# - similarity score
# - verse metadata
# - original text
```

## Troubleshooting

### "No module named 'mem0'"

```bash
uv pip install mem0ai
```

### "ANTHROPIC_API_KEY not set"

Edit `.env` file and add your API key:
```bash
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
```

### "Database not found"

Run data ingestion first:
```bash
cd /Users/myone/biblical-quotation-detector
uv run python scripts/create_database.py
uv run python scripts/ingest_helloao.py
```

### Slow ingestion

Normal! Processing 77K verses with embeddings takes time:
- Reduce batch size: `--batch-size 50`
- Test with subset first: `--limit 1000`
- Check CPU usage (embedding model runs locally)

### Search returns no results

1. Check if data was ingested:
```bash
uv run python scripts/verify_mem0.py
```

2. Clear and re-ingest:
```bash
uv run python scripts/ingest_to_mem0.py --clear --limit 100
```

## Performance Tips

### Speed up ingestion:
1. Use SSD storage
2. Increase batch size: `--batch-size 200`
3. Close other applications
4. Use specific source: `--source SR` (smaller dataset)

### Optimize search:
1. Lower limit: `--limit 5` (fewer results)
2. Use normalized text (default)
3. Keep queries concise

## Next Steps (Phase 4)

After Mem0 is working, you can:

1. **Build Detection Engine** (`src/search/detector.py`)
   - Combine vector search with LLM verification
   - Multi-stage matching (exact → fuzzy → semantic)
   - Confidence scoring

2. **Create API** (`src/api/main.py`)
   - FastAPI endpoints
   - POST /api/v1/detect
   - Return quotation matches with sources

3. **Add Web UI**
   - Simple interface for testing
   - Paste Greek text, get results
   - Show confidence scores

## Files Created

```
src/memory/
├── __init__.py
├── mem0_manager.py       # Core Mem0 management
└── bulk_ingest.py        # Bulk ingestion logic

scripts/
├── ingest_to_mem0.py     # Main ingestion script
├── test_mem0.py          # Test semantic search
└── verify_mem0.py        # Verification script

docs/
└── phase3_mem0_setup.md  # This file
```

## Success Criteria

Phase 3 is complete when:

✅ `verify_mem0.py` passes all checks
✅ All ~77K verses ingested successfully
✅ Semantic search returns relevant results
✅ Test queries find expected biblical references
✅ No errors in search operations

---

**Status**: Implementation complete, ready for testing and ingestion
**Next**: Run verification and begin ingestion
