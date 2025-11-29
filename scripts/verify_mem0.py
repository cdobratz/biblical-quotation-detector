#!/usr/bin/env python3
"""
Verify Mem0 Vector Store Setup

This script performs comprehensive verification of the Mem0 setup,
including checking configuration, database connectivity, and vector embeddings.

Usage:
    uv run python scripts/verify_mem0.py
"""

import sys
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

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

load_dotenv()


def check_environment():
    """Check environment variables and configuration."""
    logger.info("=" * 60)
    logger.info("CHECKING ENVIRONMENT CONFIGURATION")
    logger.info("=" * 60)

    checks = {
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "MEM0_VECTOR_STORE": os.getenv("MEM0_VECTOR_STORE", "qdrant"),
        "MEM0_EMBEDDING_MODEL": os.getenv("MEM0_EMBEDDING_MODEL", "multilingual-e5-large"),
        "DATABASE_PATH": os.getenv("DATABASE_PATH", "./data/processed/bible.db"),
    }

    all_ok = True

    for key, value in checks.items():
        if value and value != "your_key_here":
            logger.info(f"✓ {key}: {value[:20]}..." if len(str(value)) > 20 else f"✓ {key}: {value}")
        else:
            logger.warning(f"✗ {key}: Not set or invalid")
            if key == "ANTHROPIC_API_KEY":
                logger.warning("  → Please set your Anthropic API key in .env file")
                all_ok = False

    return all_ok


def check_directories():
    """Check required directories exist."""
    logger.info("\n" + "=" * 60)
    logger.info("CHECKING DIRECTORIES")
    logger.info("=" * 60)

    dirs = [
        project_root / "data" / "processed",
        project_root / "data" / "raw",
        project_root / "data" / "processed" / "qdrant_db"
    ]

    all_ok = True

    for dir_path in dirs:
        if dir_path.exists():
            logger.info(f"✓ {dir_path}")
        else:
            logger.warning(f"✗ {dir_path} - Does not exist")
            if "qdrant_db" in str(dir_path):
                logger.info("  → Will be created on first ingestion")
            else:
                all_ok = False

    return all_ok


def check_database():
    """Check SQLite database."""
    logger.info("\n" + "=" * 60)
    logger.info("CHECKING DATABASE")
    logger.info("=" * 60)

    db_path = project_root / "data" / "processed" / "bible.db"

    if not db_path.exists():
        logger.error(f"✗ Database not found: {db_path}")
        return False

    logger.info(f"✓ Database exists: {db_path}")
    logger.info(f"  Size: {db_path.stat().st_size / (1024*1024):.2f} MB")

    # Check database content
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check verse count
        cursor.execute("SELECT COUNT(*) FROM verses")
        verse_count = cursor.fetchone()[0]
        logger.info(f"✓ Total verses: {verse_count:,}")

        # Check sources
        cursor.execute("SELECT DISTINCT source FROM verses")
        sources = [row[0] for row in cursor.fetchall()]
        logger.info(f"✓ Sources: {', '.join(sources)}")

        # Check books
        cursor.execute("SELECT COUNT(DISTINCT book) FROM verses")
        book_count = cursor.fetchone()[0]
        logger.info(f"✓ Books: {book_count}")

        # Check text processing
        cursor.execute("SELECT COUNT(*) FROM verses WHERE greek_normalized IS NOT NULL")
        normalized_count = cursor.fetchone()[0]
        logger.info(f"✓ Normalized verses: {normalized_count:,}")

        cursor.execute("SELECT COUNT(*) FROM verses WHERE greek_lemmatized IS NOT NULL")
        lemmatized_count = cursor.fetchone()[0]
        logger.info(f"✓ Lemmatized verses: {lemmatized_count:,}")

        conn.close()

        if verse_count == 0:
            logger.error("✗ Database is empty!")
            return False

        return True

    except Exception as e:
        logger.error(f"✗ Database check failed: {e}")
        return False


def check_mem0():
    """Check Mem0 initialization and status."""
    logger.info("\n" + "=" * 60)
    logger.info("CHECKING MEM0 VECTOR STORE")
    logger.info("=" * 60)

    try:
        # Try to initialize Mem0Manager
        logger.info("Initializing Mem0Manager...")
        manager = Mem0Manager()
        logger.info("✓ Mem0Manager initialized successfully")

        # Get stats
        stats = manager.get_stats()
        logger.info(f"✓ Vector store: {stats['vector_store']}")
        logger.info(f"✓ Embedding model: {stats['embedding_model']}")
        logger.info(f"✓ Qdrant path: {stats['qdrant_path']}")

        # Check for memories
        total_memories = stats.get('total_memories', 0)
        if total_memories == 'unknown':
            logger.warning("⚠ Cannot determine number of memories")
            logger.info("  → This may be normal if no ingestion has been run yet")
        elif total_memories == 0:
            logger.warning("⚠ No memories in vector store")
            logger.info("  → Run ingestion: uv run python scripts/ingest_to_mem0.py")
        else:
            logger.info(f"✓ Total memories: {total_memories:,}")

        return True, manager

    except Exception as e:
        logger.error(f"✗ Mem0 check failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def check_dependencies():
    """Check Python package dependencies."""
    logger.info("\n" + "=" * 60)
    logger.info("CHECKING DEPENDENCIES")
    logger.info("=" * 60)

    required_packages = [
        "mem0ai",
        "anthropic",
        "pydantic",
        "sqlite_utils",
        "dotenv"
    ]

    all_ok = True

    for package in required_packages:
        try:
            if package == "dotenv":
                import dotenv
                logger.info(f"✓ python-dotenv installed")
            elif package == "sqlite_utils":
                import sqlite_utils
                logger.info(f"✓ {package} installed")
            else:
                __import__(package)
                logger.info(f"✓ {package} installed")
        except ImportError:
            logger.error(f"✗ {package} not installed")
            all_ok = False

    return all_ok


def test_simple_search(manager: Mem0Manager):
    """Test a simple search operation."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING SEARCH FUNCTIONALITY")
    logger.info("=" * 60)

    test_query = "θεος"  # "God" in Greek
    logger.info(f"Testing search with query: '{test_query}'")

    try:
        results = manager.search(query=test_query, limit=3)

        if not results:
            logger.warning("⚠ Search returned no results")
            logger.info("  → This may be normal if no data has been ingested")
            return False

        logger.info(f"✓ Search successful - found {len(results)} results")

        for i, result in enumerate(results, 1):
            metadata = result.get('metadata', {})
            logger.info(f"\n  Result {i}:")
            logger.info(f"    Reference: {metadata.get('reference', 'N/A')}")
            logger.info(f"    Book: {metadata.get('book', 'N/A')}")

        return True

    except Exception as e:
        logger.error(f"✗ Search test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    logger.info("\n" + "=" * 60)
    logger.info("MEM0 VECTOR STORE VERIFICATION")
    logger.info("=" * 60 + "\n")

    results = {}

    # Run checks
    results['environment'] = check_environment()
    results['directories'] = check_directories()
    results['database'] = check_database()
    results['dependencies'] = check_dependencies()
    results['mem0'], manager = check_mem0()

    # Test search if Mem0 is working
    if manager:
        results['search'] = test_simple_search(manager)

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("VERIFICATION SUMMARY")
    logger.info("=" * 60)

    all_passed = True
    for check, passed in results.items():
        if passed:
            logger.info(f"✓ {check.upper()}: PASS")
        else:
            logger.warning(f"✗ {check.upper()}: FAIL")
            all_passed = False

    logger.info("=" * 60)

    if all_passed:
        logger.info("\n✓ ALL CHECKS PASSED - Mem0 is ready to use!")
        logger.info("\nNext steps:")
        logger.info("  1. Ingest data: uv run python scripts/ingest_to_mem0.py")
        logger.info("  2. Test search: uv run python scripts/test_mem0.py")
    else:
        logger.warning("\n⚠ SOME CHECKS FAILED - Please fix the issues above")

        # Provide helpful guidance
        if not results.get('database'):
            logger.info("\nTo create the database:")
            logger.info("  uv run python scripts/create_database.py")
            logger.info("  uv run python scripts/ingest_helloao.py")

        if not results.get('environment'):
            logger.info("\nTo fix environment:")
            logger.info("  1. Copy .env.example to .env (if exists)")
            logger.info("  2. Add your ANTHROPIC_API_KEY to .env")

        if not results.get('dependencies'):
            logger.info("\nTo install dependencies:")
            logger.info("  uv pip install -e .")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
