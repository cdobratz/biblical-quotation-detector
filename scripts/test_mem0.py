#!/usr/bin/env python3
"""
Test Mem0 Vector Store Functionality

This script tests the Mem0 setup and semantic search capabilities.

Usage:
    # Test basic functionality with a few verses
    uv run python scripts/test_mem0.py

    # Test with specific search query
    uv run python scripts/test_mem0.py --query "μακαριοι οι πτωχοι"

    # Test search with more results
    uv run python scripts/test_mem0.py --limit 20
"""

import sys
import argparse
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.memory.mem0_manager import Mem0Manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Test queries with known results
TEST_QUERIES = [
    {
        "text": "μακαριοι οι πτωχοι τω πνευματι",
        "description": "Beatitudes - 'Blessed are the poor in spirit'",
        "expected_reference": "Matthew 5:3"
    },
    {
        "text": "εν αρχη ην ο λογος",
        "description": "Gospel of John opening - 'In the beginning was the Word'",
        "expected_reference": "John 1:1"
    },
    {
        "text": "ο θεος αγαπη εστιν",
        "description": "'God is love'",
        "expected_reference": "1 John 4:8"
    },
    {
        "text": "πιστις ελπις αγαπη",
        "description": "Faith, hope, love",
        "expected_reference": "1 Corinthians 13:13"
    },
    {
        "text": "εγω ειμι η οδος η αληθεια η ζωη",
        "description": "'I am the way, the truth, and the life'",
        "expected_reference": "John 14:6"
    }
]


def test_initialization():
    """Test Mem0Manager initialization."""
    logger.info("Testing Mem0Manager initialization...")
    try:
        manager = Mem0Manager()
        logger.info("✓ Mem0Manager initialized successfully")
        return manager
    except Exception as e:
        logger.error(f"✗ Failed to initialize Mem0Manager: {e}")
        raise


def test_stats(manager: Mem0Manager):
    """Test getting statistics."""
    logger.info("\nTesting statistics retrieval...")
    try:
        stats = manager.get_stats()
        logger.info("✓ Successfully retrieved stats:")
        logger.info(f"  Vector store: {stats['vector_store']}")
        logger.info(f"  Embedding model: {stats['embedding_model']}")
        logger.info(f"  Qdrant path: {stats['qdrant_path']}")
        logger.info(f"  Total memories: {stats['total_memories']}")
        return stats
    except Exception as e:
        logger.error(f"✗ Failed to get stats: {e}")
        raise


def test_search(manager: Mem0Manager, query: str, limit: int = 5):
    """Test semantic search."""
    logger.info(f"\nTesting search with query: '{query}'")
    logger.info(f"Retrieving top {limit} results...")

    try:
        results = manager.search(query=query, limit=limit)

        if not results:
            logger.warning("✗ No results returned")
            return []

        logger.info(f"✓ Search successful - found {len(results)} results")

        for i, result in enumerate(results, 1):
            logger.info(f"\n--- Result {i} ---")

            # Handle different result formats from Mem0
            if isinstance(result, dict):
                # Extract metadata
                metadata = result.get('metadata', {})
                memory = result.get('memory', '')

                logger.info(f"Reference: {metadata.get('reference', 'N/A')}")
                logger.info(f"Book: {metadata.get('book', 'N/A')}")
                logger.info(f"Source: {metadata.get('source', 'N/A')}")
                logger.info(f"Text: {memory[:100]}..." if len(memory) > 100 else f"Text: {memory}")

                if 'score' in result:
                    logger.info(f"Score: {result['score']:.4f}")

        return results

    except Exception as e:
        logger.error(f"✗ Search failed: {e}")
        import traceback
        traceback.print_exc()
        raise


def test_known_queries(manager: Mem0Manager, limit: int = 3):
    """Test with known queries."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING WITH KNOWN BIBLICAL QUOTATIONS")
    logger.info("=" * 60)

    results_summary = []

    for i, test_case in enumerate(TEST_QUERIES, 1):
        logger.info(f"\n\nTest Case {i}/{len(TEST_QUERIES)}")
        logger.info(f"Description: {test_case['description']}")
        logger.info(f"Expected: {test_case['expected_reference']}")

        try:
            results = test_search(
                manager,
                query=test_case['text'],
                limit=limit
            )

            # Check if expected reference is in results
            found = False
            if results:
                for result in results:
                    metadata = result.get('metadata', {})
                    if metadata.get('reference', '').startswith(test_case['expected_reference'].split(':')[0]):
                        found = True
                        break

            results_summary.append({
                "description": test_case['description'],
                "expected": test_case['expected_reference'],
                "found": found,
                "results_count": len(results) if results else 0
            })

        except Exception as e:
            logger.error(f"Test case failed: {e}")
            results_summary.append({
                "description": test_case['description'],
                "expected": test_case['expected_reference'],
                "found": False,
                "error": str(e)
            })

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    passed = sum(1 for r in results_summary if r.get('found', False))
    total = len(results_summary)

    for result in results_summary:
        status = "✓ PASS" if result.get('found') else "✗ FAIL"
        logger.info(f"{status} - {result['description']}")
        logger.info(f"       Expected: {result['expected']}")

    logger.info(f"\nTotal: {passed}/{total} tests passed")

    return results_summary


def main():
    parser = argparse.ArgumentParser(
        description="Test Mem0 vector store functionality"
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Custom search query to test"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of search results to return"
    )
    parser.add_argument(
        "--skip-known-tests",
        action="store_true",
        help="Skip testing with known queries"
    )

    args = parser.parse_args()

    try:
        # Test initialization
        manager = test_initialization()

        # Test stats
        stats = test_stats(manager)

        # Check if there are any memories
        if stats['total_memories'] == 0 or stats['total_memories'] == 'unknown':
            logger.warning("\n⚠ Warning: No memories found in vector store!")
            logger.warning("Please run ingestion first:")
            logger.warning("  uv run python scripts/ingest_to_mem0.py --limit 100")
            return

        # Test custom query if provided
        if args.query:
            test_search(manager, query=args.query, limit=args.limit)

        # Test known queries unless skipped
        if not args.skip_known_tests:
            test_known_queries(manager, limit=args.limit)

        logger.info("\n" + "=" * 60)
        logger.info("ALL TESTS COMPLETED")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"\nTest suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
