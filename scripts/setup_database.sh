#!/bin/bash
set -e

echo "🚀 Setting up Biblical Quotation Database"
echo "=========================================="

# Step 1: Create database schema
echo ""
echo "Step 1/5: Creating database schema..."
uv run python scripts/create_database.py

# Step 2: Check for data sources
echo ""
echo "Step 2/5: Checking data sources..."

if [ ! -f "data/raw/bible.db" ]; then
    echo "⚠️  bible.db not found"
    echo "Downloading (11 GB - may take a while)..."
    mkdir -p data/raw
    wget https://bible.helloao.org/bible.db -O data/raw/bible.db
fi

if [ ! -d "data/raw/SR" ]; then
    echo "⚠️  SR repository not found"
    echo "Cloning CNTR Statistical Restoration..."
    cd data/raw
    git clone https://github.com/Center-for-New-Testament-Restoration/SR
    cd ../..
fi

# Step 3: Ingest HelloAO data
echo ""
echo "Step 3/5: Ingesting HelloAO Bible data..."
uv run python scripts/ingest_helloao.py

# Step 4: Ingest CNTR data
echo ""
echo "Step 4/5: Ingesting CNTR Statistical Restoration..."
uv run python scripts/ingest_cntr.py

# Step 5: Process Greek text
echo ""
echo "Step 5/5: Processing Greek text (normalize & lemmatize)..."
uv run python scripts/process_greek.py

# Final verification
echo ""
echo "✓ Database setup complete!"
echo ""
echo "📊 Database Statistics:"
sqlite3 data/processed/bible.db "SELECT COUNT(*) || ' total verses' FROM verses;"
sqlite3 data/processed/bible.db "SELECT source, COUNT(*) || ' verses' FROM verses GROUP BY source;"

echo ""
echo "Next steps:"
echo "  1. Test queries: sqlite3 data/processed/bible.db"
echo "  2. Setup Mem0: uv run python scripts/setup_mem0.py"
echo "  3. Start API: uv run uvicorn src.api.main:app"