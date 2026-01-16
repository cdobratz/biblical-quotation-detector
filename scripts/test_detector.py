#!/usr/bin/env python3
"""
Test script for the Biblical Quotation Detector.

Tests both heuristic and LLM-based detection modes.

Usage:
    # Test without LLM (fast, heuristic only)
    uv run python scripts/test_detector.py

    # Test with LLM verification (slower, more accurate)
    uv run python scripts/test_detector.py --use-llm
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.search.detector import QuotationDetector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Test cases with known quotations
TEST_CASES = [
    {
        "text": "μακαριοι οι πτωχοι τω πνευματι οτι αυτων εστιν η βασιλεια των ουρανων",
        "expected_ref": "Matthew 5:3",
        "expected_type": "exact",
        "description": "Beatitudes - Blessed are the poor in spirit",
    },
    {
        "text": "εν αρχη ην ο λογος και ο λογος ην προς τον θεον",
        "expected_ref": "John 1:1",
        "expected_type": "exact",
        "description": "John prologue - In the beginning was the Word",
    },
    {
        "text": "ουτως γαρ ηγαπησεν ο θεος τον κοσμον",
        "expected_ref": "John 3:16",
        "expected_type": "exact",
        "description": "For God so loved the world",
    },
    {
        "text": "πατερ ημων ο εν τοις ουρανοις",
        "expected_ref": "Matthew 6:9",
        "expected_type": "close_paraphrase",
        "description": "Lord's Prayer - Our Father in heaven",
    },
    {
        "text": "αγαπησεις τον πλησιον σου ως σεαυτον",
        "expected_ref": "Matthew 22:39",
        "expected_type": "exact",
        "description": "Love your neighbor as yourself",
    },
    {
        "text": "ο καρπος του πνευματος εστιν αγαπη χαρα ειρηνη",
        "expected_ref": "Galatians 5:22",
        "expected_type": "close_paraphrase",
        "description": "Fruit of the Spirit",
    },
    {
        "text": "τουτο ειναι κειμενο που δεν ειναι βιβλικο",
        "expected_ref": None,
        "expected_type": "non_biblical",
        "description": "Non-biblical modern Greek text",
    },
]


def run_tests(use_llm: bool = False):
    """Run detection tests."""
    logger.info("=" * 60)
    logger.info(f"BIBLICAL QUOTATION DETECTOR TEST")
    logger.info(f"Mode: {'LLM verification' if use_llm else 'Heuristic only'}")
    logger.info("=" * 60)

    # Initialize detector
    logger.info("\nInitializing detector...")
    detector = QuotationDetector(use_llm=use_llm)

    # Run tests
    passed = 0
    failed = 0
    total = len(TEST_CASES)

    for i, test in enumerate(TEST_CASES, 1):
        logger.info(f"\n--- Test {i}/{total}: {test['description']} ---")
        logger.info(f"Input: {test['text'][:50]}...")
        logger.info(f"Expected: {test['expected_ref']} ({test['expected_type']})")

        result = detector.detect(test["text"])

        logger.info(f"Result: is_quotation={result.is_quotation}")
        logger.info(f"Match type: {result.match_type}")
        logger.info(f"Confidence: {result.confidence}%")
        logger.info(f"Time: {result.processing_time_ms}ms")

        if result.best_match:
            logger.info(f"Best match: {result.best_match.reference}")
            logger.info(f"Score: {result.best_match.similarity_score:.3f}")

        logger.info(f"Explanation: {result.explanation}")

        # Check if test passed
        if test["expected_ref"] is None:
            # Non-biblical test
            test_passed = not result.is_quotation or result.match_type == "non_biblical"
        else:
            # Biblical test - check if expected reference is in top results
            found_refs = [s.reference for s in result.sources]
            if result.best_match:
                found_refs.append(result.best_match.reference)

            # Check if any found reference matches expected
            test_passed = any(
                test["expected_ref"] in ref for ref in found_refs
            )

        if test_passed:
            logger.info("✓ PASSED")
            passed += 1
        else:
            logger.warning("✗ FAILED")
            failed += 1

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total: {total}")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Success rate: {passed/total*100:.1f}%")
    logger.info("=" * 60)

    return passed == total


def interactive_test(use_llm: bool = False):
    """Interactive testing mode."""
    logger.info("Interactive detection mode. Enter Greek text to analyze.")
    logger.info("Type 'quit' to exit.\n")

    detector = QuotationDetector(use_llm=use_llm)

    while True:
        text = input("\nEnter Greek text: ").strip()
        if text.lower() == "quit":
            break

        if not text:
            continue

        result = detector.detect(text)

        print(f"\n--- Detection Result ---")
        print(f"Is quotation: {result.is_quotation}")
        print(f"Match type: {result.match_type}")
        print(f"Confidence: {result.confidence}%")
        print(f"Time: {result.processing_time_ms}ms")

        if result.best_match:
            print(f"\nBest match: {result.best_match.reference}")
            print(f"Text: {result.best_match.greek_text}")
            print(f"Score: {result.best_match.similarity_score:.3f}")

        print(f"\nExplanation: {result.explanation}")

        if result.sources:
            print(f"\nTop candidates:")
            for s in result.sources[:3]:
                print(f"  - {s.reference}: {s.greek_text[:40]}... (score: {s.similarity_score:.3f})")


def main():
    parser = argparse.ArgumentParser(description="Test biblical quotation detector")
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use Claude LLM for verification (slower but more accurate)",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Interactive testing mode",
    )

    args = parser.parse_args()

    if args.interactive:
        interactive_test(use_llm=args.use_llm)
    else:
        success = run_tests(use_llm=args.use_llm)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
