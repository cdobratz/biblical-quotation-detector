#!/usr/bin/env python3
"""
Test Qdrant Semantic Search

Tests the direct Qdrant search functionality with known biblical quotations.

Usage:
    uv run python scripts/test_qdrant_search.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.memory.qdrant_manager import QdrantManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Test queries - known biblical phrases
TEST_QUERIES = [
    {
        "query": "μακαριοι οι πτωχοι τω πνευματι",
        "expected": "Matthew 5:3",
        "description": "Blessed are the poor in spirit (Beatitudes)",
    },
    {
        "query": "εν αρχη ην ο λογος",
        "expected": "John 1:1",
        "description": "In the beginning was the Word",
    },
    {
        "query": "ουτως γαρ ηγαπησεν ο θεος τον κοσμον",
        "expected": "John 3:16",
        "description": "For God so loved the world",
    },
    {
        "query": "πατερ ημων ο εν τοις ουρανοις",
        "expected": "Matthew 6:9",
        "description": "Our Father who art in heaven (Lord's Prayer)",
    },
    {
        "query": "εγω ειμι η οδος και η αληθεια και η ζωη",
        "expected": "John 14:6",
        "description": "I am the way, the truth, and the life",
    },
]


def main():
    logger.info("=" * 60)
    logger.info("QDRANT SEMANTIC SEARCH TEST")
    logger.info("=" * 60)

    # Initialize manager
    logger.info("Initializing Qdrant manager...")
    manager = QdrantManager()

    # Check collection
    info = manager.get_collection_info()
    vectors_count = info.get("vectors_count", 0)
    logger.info(f"Collection has {vectors_count} vectors")

    if not vectors_count:
        logger.warning("No vectors in collection! Run ingestion first.")
        return

    logger.info("")
    logger.info("Running test queries...")
    logger.info("-" * 60)

    success = 0
    total = len(TEST_QUERIES)

    for test in TEST_QUERIES:
        query = test["query"]
        expected = test["expected"]
        desc = test["description"]

        logger.info(f"\nQuery: {desc}")
        logger.info(f"Greek: {query[:50]}...")
        logger.info(f"Expected: {expected}")

        results = manager.search(query=query, limit=5)

        if results:
            top_result = results[0]
            found_ref = top_result.get("reference", "")
            score = top_result.get("score", 0)

            logger.info(f"Top result: {found_ref} (score: {score:.3f})")
            logger.info(f"Text: {top_result.get('text', '')[:60]}...")

            # Check if expected is in top 5
            found_refs = [r.get("reference", "") for r in results]
            if any(expected in ref for ref in found_refs):
                logger.info("✓ PASS - Expected reference found in top 5")
                success += 1
            else:
                logger.warning(f"✗ FAIL - Expected {expected} not in results: {found_refs}")
        else:
            logger.warning("✗ FAIL - No results returned")

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"RESULTS: {success}/{total} tests passed")
    logger.info("=" * 60)

    # Custom query option
    logger.info("\nYou can also test custom queries by running:")
    logger.info("  python -c \"from src.memory.qdrant_manager import QdrantManager; m = QdrantManager(); print(m.search('your query here'))\"")


if __name__ == "__main__":
    main()
