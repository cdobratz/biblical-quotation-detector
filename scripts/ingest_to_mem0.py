#!/usr/bin/env python3
"""
Ingest Biblical Verses into Mem0 Vector Store

This script loads all biblical verses from the SQLite database and
ingests them into the Mem0 vector store for semantic search.

Usage:
    # Ingest all verses
    uv run python scripts/ingest_to_mem0.py

    # Ingest specific source
    uv run python scripts/ingest_to_mem0.py --source SR

    # Ingest specific book
    uv run python scripts/ingest_to_mem0.py --book Matthew

    # Test with limited verses
    uv run python scripts/ingest_to_mem0.py --limit 100

    # Clear existing data first
    uv run python scripts/ingest_to_mem0.py --clear
"""

import sys
import argparse
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.memory.mem0_manager import Mem0Manager
from src.memory.bulk_ingest import BulkIngester

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Ingest biblical verses into Mem0 vector store"
    )
    parser.add_argument(
        "--database",
        type=str,
        default="./data/processed/bible.db",
        help="Path to SQLite database"
    )
    parser.add_argument(
        "--source",
        type=str,
        help="Ingest only verses from this source (e.g., SR, grc_sbl)"
    )
    parser.add_argument(
        "--book",
        type=str,
        help="Ingest only verses from this book (e.g., Matthew, Romans)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of verses to ingest (for testing)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of verses to process in each batch"
    )
    parser.add_argument(
        "--use-original",
        action="store_true",
        help="Use original Greek text instead of normalized"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing memories before ingesting"
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Show statistics only, don't ingest"
    )

    args = parser.parse_args()

    try:
        # Initialize Mem0Manager
        logger.info("Initializing Mem0Manager...")
        mem0_manager = Mem0Manager()

        # Clear if requested
        if args.clear:
            logger.info("Clearing existing memories...")
            mem0_manager.delete_all()
            logger.info("Memories cleared")

        # Initialize BulkIngester
        logger.info(f"Initializing BulkIngester with database: {args.database}")
        ingester = BulkIngester(
            database_path=args.database,
            mem0_manager=mem0_manager
        )

        # Show stats if requested
        if args.stats_only:
            stats = ingester.get_ingestion_stats()
            logger.info("=== Ingestion Statistics ===")
            logger.info(f"Database:")
            logger.info(f"  Total verses: {stats['database']['total_verses']:,}")
            logger.info(f"  Sources: {stats['database']['sources']}")
            logger.info(f"  Books: {stats['database']['books']}")
            logger.info(f"\nMem0:")
            logger.info(f"  Vector store: {stats['mem0']['vector_store']}")
            logger.info(f"  Embedding model: {stats['mem0']['embedding_model']}")
            logger.info(f"  Total memories: {stats['mem0']['total_memories']}")
            logger.info(f"  Qdrant path: {stats['mem0']['qdrant_path']}")
            return

        # Perform ingestion
        use_normalized = not args.use_original

        if args.source:
            logger.info(f"Ingesting verses from source: {args.source}")
            result = ingester.ingest_by_source(
                source=args.source,
                batch_size=args.batch_size,
                use_normalized=use_normalized
            )
        elif args.book:
            logger.info(f"Ingesting verses from book: {args.book}")
            result = ingester.ingest_by_book(
                book=args.book,
                batch_size=args.batch_size,
                use_normalized=use_normalized
            )
        else:
            logger.info("Ingesting all verses")
            result = ingester.ingest_all(
                batch_size=args.batch_size,
                use_normalized=use_normalized,
                limit=args.limit
            )

        # Print summary
        logger.info("\n" + "=" * 50)
        logger.info("INGESTION COMPLETE")
        logger.info("=" * 50)
        logger.info(f"Total verses processed: {result['total']:,}")
        logger.info(f"Successfully added: {result['added']:,}")
        logger.info(f"Failed: {result['failed']:,}")

        if 'duration_seconds' in result:
            logger.info(f"Duration: {result['duration_seconds']:.2f} seconds")
            logger.info(f"Rate: {result['verses_per_second']:.2f} verses/second")

        logger.info("=" * 50)

        # Show final stats
        stats = ingester.get_ingestion_stats()
        logger.info(f"\nTotal memories in Mem0: {stats['mem0']['total_memories']}")

    except FileNotFoundError as e:
        logger.error(f"Database not found: {e}")
        logger.error("Please ensure the database exists at the specified path")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
