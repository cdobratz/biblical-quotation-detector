#!/usr/bin/env python3
"""
Direct Qdrant Ingestion Script

Ingests biblical verses directly into Qdrant using local embeddings.
Much faster than Mem0 approach (no API calls per verse).

Usage:
    # Test with 100 verses
    uv run python scripts/ingest_to_qdrant.py --limit 100

    # Full ingestion
    uv run python scripts/ingest_to_qdrant.py

    # Clear and re-ingest
    uv run python scripts/ingest_to_qdrant.py --clear

    # Filter by source
    uv run python scripts/ingest_to_qdrant.py --source SR
"""

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.memory.qdrant_manager import QdrantManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def fetch_verses(
    db_path: str,
    limit: int = None,
    source: str = None,
    book: str = None,
) -> list:
    """Fetch verses from SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Build query
    query = """
        SELECT
            id,
            reference,
            book,
            chapter,
            verse,
            greek_text,
            greek_normalized,
            source
        FROM verses
        WHERE greek_text IS NOT NULL
    """
    params = []

    if source:
        query += " AND source = ?"
        params.append(source)

    if book:
        query += " AND book = ?"
        params.append(book)

    query += " ORDER BY id"

    if limit:
        query += " LIMIT ?"
        params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    # Format for ingestion
    verses = []
    for row in rows:
        verses.append({
            "id": row["id"],
            "text": row["greek_normalized"] or row["greek_text"],  # Use normalized for embedding
            "metadata": {
                "reference": row["reference"],
                "book": row["book"],
                "chapter": row["chapter"],
                "verse": row["verse"],
                "source": row["source"],
                "greek_original": row["greek_text"],  # Keep original for display
            },
        })

    return verses


def main():
    parser = argparse.ArgumentParser(description="Ingest verses into Qdrant")
    parser.add_argument("--limit", type=int, help="Limit number of verses")
    parser.add_argument("--source", type=str, help="Filter by source (e.g., SR, grc_sbl)")
    parser.add_argument("--book", type=str, help="Filter by book (e.g., Matthew)")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size")
    parser.add_argument("--clear", action="store_true", help="Clear collection first")
    parser.add_argument(
        "--db-path",
        type=str,
        default="./data/processed/bible.db",
        help="Path to SQLite database",
    )

    args = parser.parse_args()

    # Check database exists
    if not Path(args.db_path).exists():
        logger.error(f"Database not found: {args.db_path}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("DIRECT QDRANT INGESTION")
    logger.info("=" * 60)

    # Initialize Qdrant manager
    logger.info("Initializing Qdrant manager...")
    start_time = time.time()

    manager = QdrantManager()
    init_time = time.time() - start_time
    logger.info(f"Initialization complete in {init_time:.1f}s")

    # Clear if requested
    if args.clear:
        logger.info("Clearing existing collection...")
        manager.clear_collection()

    # Show collection info
    info = manager.get_collection_info()
    logger.info(f"Collection: {info.get('name', 'N/A')}")
    logger.info(f"Current vectors: {info.get('vectors_count', 0)}")

    # Fetch verses
    logger.info("Fetching verses from database...")
    verses = fetch_verses(
        db_path=args.db_path,
        limit=args.limit,
        source=args.source,
        book=args.book,
    )
    logger.info(f"Fetched {len(verses)} verses")

    if not verses:
        logger.warning("No verses to ingest!")
        return

    # Ingest
    logger.info("Starting ingestion...")
    ingest_start = time.time()

    result = manager.add_verses_batch(
        verses=verses,
        batch_size=args.batch_size,
    )

    ingest_time = time.time() - ingest_start

    # Report results
    logger.info("")
    logger.info("=" * 60)
    logger.info("INGESTION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total verses: {result['total']}")
    logger.info(f"Successfully added: {result['added']}")
    logger.info(f"Failed: {result['failed']}")
    logger.info(f"Duration: {ingest_time:.1f} seconds")
    logger.info(f"Rate: {result['added'] / ingest_time:.1f} verses/second")
    logger.info("=" * 60)

    # Final collection info
    info = manager.get_collection_info()
    logger.info(f"Total vectors in collection: {info.get('vectors_count', 'N/A')}")


if __name__ == "__main__":
    main()
