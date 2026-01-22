#!/usr/bin/env python3
"""
Patristic Text Testing Script

Test the biblical quotation detector with Church Father texts from PDFs or URLs.
Outputs both JSON and Markdown reports.

Usage:
    # From PDF
    uv run python scripts/test_patristic.py --pdf /path/to/clement.pdf --output results/

    # From URL (e.g., Perseus Digital Library)
    uv run python scripts/test_patristic.py --url "https://..." --output results/

    # Options
    --mode llm|heuristic    # Detection mode (default: heuristic for speed)
    --min-confidence 50     # Minimum confidence threshold
    --chunk-size paragraph  # How to split text: paragraph, sentence
"""

import argparse
import json
import logging
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.search.detector import QuotationDetector, DetectionResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def extract_from_pdf(path: str) -> str:
    """
    Extract text from PDF file.

    Args:
        path: Path to PDF file

    Returns:
        Extracted text content
    """
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed. Run: uv pip install pdfplumber")
        sys.exit(1)

    logger.info(f"Extracting text from PDF: {path}")

    text_parts = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
            logger.debug(f"Extracted page {i + 1}/{len(pdf.pages)}")

    full_text = "\n\n".join(text_parts)
    logger.info(f"Extracted {len(full_text)} characters from {len(text_parts)} pages")
    return full_text


def extract_from_url(url: str) -> str:
    """
    Fetch and extract text from URL.

    Args:
        url: URL to fetch

    Returns:
        Extracted text content
    """
    logger.info(f"Fetching URL: {url}")

    try:
        response = httpx.get(url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch URL: {e}")
        sys.exit(1)

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove script and style elements
    for element in soup(["script", "style", "nav", "header", "footer"]):
        element.decompose()

    # Try to find main content area
    main_content = (
        soup.find("main")
        or soup.find("article")
        or soup.find("div", class_=re.compile(r"content|text|body", re.I))
        or soup.find("body")
    )

    if main_content:
        text = main_content.get_text(separator="\n", strip=True)
    else:
        text = soup.get_text(separator="\n", strip=True)

    logger.info(f"Extracted {len(text)} characters from URL")
    return text


def is_greek_text(text: str, threshold: float = 0.3) -> bool:
    """
    Check if text contains significant Greek characters.

    Args:
        text: Text to check
        threshold: Minimum ratio of Greek characters (0.0-1.0)

    Returns:
        True if text is primarily Greek
    """
    if not text.strip():
        return False

    greek_count = 0
    total_alpha = 0

    for char in text:
        if char.isalpha():
            total_alpha += 1
            # Greek Unicode ranges: Basic Greek (0370-03FF), Extended Greek (1F00-1FFF)
            if "\u0370" <= char <= "\u03FF" or "\u1F00" <= char <= "\u1FFF":
                greek_count += 1

    if total_alpha == 0:
        return False

    ratio = greek_count / total_alpha
    return ratio >= threshold


def chunk_text(text: str, method: str = "paragraph") -> List[str]:
    """
    Split text into chunks for analysis.

    Args:
        text: Full text to split
        method: Chunking method - "paragraph" or "sentence"

    Returns:
        List of text chunks
    """
    if method == "paragraph":
        # Split on double newlines or multiple newlines
        chunks = re.split(r"\n\s*\n+", text)
    elif method == "sentence":
        # Split on sentence-ending punctuation (Greek and Latin)
        # Greek period: · (middle dot) or . (full stop)
        # Also handle ; as Greek question mark
        chunks = re.split(r"[.·;!?]\s+", text)
    else:
        raise ValueError(f"Unknown chunking method: {method}")

    # Clean and filter chunks
    cleaned = []
    for chunk in chunks:
        chunk = chunk.strip()
        # Skip very short chunks
        if len(chunk) < 20:
            continue
        # Skip chunks that are just punctuation/numbers
        if not any(c.isalpha() for c in chunk):
            continue
        cleaned.append(chunk)

    logger.info(f"Split text into {len(cleaned)} chunks using '{method}' method")
    return cleaned


def filter_greek_chunks(chunks: List[str]) -> List[str]:
    """
    Filter chunks to keep only those with Greek text.

    Args:
        chunks: List of text chunks

    Returns:
        Filtered list containing only Greek text
    """
    greek_chunks = [c for c in chunks if is_greek_text(c)]
    logger.info(f"Filtered to {len(greek_chunks)} Greek chunks from {len(chunks)} total")
    return greek_chunks


def run_detection(
    chunks: List[str],
    detector: QuotationDetector,
    min_confidence: int = 50,
) -> List[dict]:
    """
    Run detection on all chunks.

    Args:
        chunks: List of text chunks to analyze
        detector: QuotationDetector instance
        min_confidence: Minimum confidence threshold

    Returns:
        List of detection results as dictionaries
    """
    results = []
    total = len(chunks)

    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i + 1}/{total}")

        try:
            result = detector.detect(chunk, min_confidence=min_confidence)
            result_dict = result.to_dict()
            result_dict["chunk_index"] = i
            results.append(result_dict)
        except Exception as e:
            logger.error(f"Detection failed for chunk {i}: {e}")
            results.append({
                "chunk_index": i,
                "input_text": chunk,
                "error": str(e),
                "is_quotation": False,
                "confidence": 0,
                "match_type": "error",
            })

    return results


def write_json_report(
    results: List[dict],
    output_path: str,
    metadata: dict,
) -> str:
    """
    Write JSON report file.

    Args:
        results: Detection results
        output_path: Output directory path
        metadata: Report metadata

    Returns:
        Path to written file
    """
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_{timestamp}.json"
    filepath = output_dir / filename

    report = {
        "metadata": metadata,
        "results": results,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"JSON report written to: {filepath}")
    return str(filepath)


def write_markdown_report(
    results: List[dict],
    output_path: str,
    metadata: dict,
) -> str:
    """
    Write Markdown report with summary statistics.

    Args:
        results: Detection results
        output_path: Output directory path
        metadata: Report metadata

    Returns:
        Path to written file
    """
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_{timestamp}.md"
    filepath = output_dir / filename

    # Calculate statistics
    quotations = [r for r in results if r.get("is_quotation", False)]
    match_types = {}
    total_confidence = 0
    confidence_count = 0

    for r in quotations:
        mt = r.get("match_type", "unknown")
        match_types[mt] = match_types.get(mt, 0) + 1
        if "confidence" in r:
            total_confidence += r["confidence"]
            confidence_count += 1

    avg_confidence = (
        total_confidence / confidence_count if confidence_count > 0 else 0
    )

    # Build report
    lines = [
        "# Patristic Text Analysis Report",
        "",
        f"**Source:** {metadata.get('source', 'Unknown')}",
        f"**Date:** {metadata.get('date', datetime.now().strftime('%Y-%m-%d'))}",
        f"**Mode:** {metadata.get('mode', 'unknown')}",
        f"**Chunks analyzed:** {len(results)}",
        "",
        "## Summary",
        "",
        f"- Total quotations detected: {len(quotations)}",
        f"- Exact matches: {match_types.get('exact', 0)}",
        f"- Close paraphrases: {match_types.get('close_paraphrase', 0)}",
        f"- Loose paraphrases: {match_types.get('loose_paraphrase', 0)}",
        f"- Allusions: {match_types.get('allusion', 0)}",
        f"- Average confidence: {avg_confidence:.0f}%",
        "",
    ]

    # Add quotations table if any found
    if quotations:
        lines.extend([
            "## Detected Quotations",
            "",
            "| # | Text (truncated) | Match Type | Reference | Confidence |",
            "|---|------------------|------------|-----------|------------|",
        ])

        for i, q in enumerate(quotations, 1):
            text = q.get("input_text", "")[:40].replace("\n", " ")
            if len(q.get("input_text", "")) > 40:
                text += "..."

            match_type = q.get("match_type", "unknown")
            confidence = q.get("confidence", 0)

            # Get reference from best match or first source
            reference = "—"
            if q.get("best_match"):
                reference = q["best_match"].get("reference", "—")
            elif q.get("sources") and len(q["sources"]) > 0:
                reference = q["sources"][0].get("reference", "—")

            lines.append(
                f"| {i} | {text} | {match_type} | {reference} | {confidence}% |"
            )

        lines.append("")

    # Add detailed results section
    lines.extend([
        "## Detailed Results",
        "",
    ])

    for i, r in enumerate(results):
        if r.get("is_quotation", False):
            lines.append(f"### Chunk {i + 1}")
            lines.append("")
            lines.append(f"**Text:** {r.get('input_text', '')[:200]}...")
            lines.append("")
            lines.append(f"**Match Type:** {r.get('match_type', 'unknown')}")
            lines.append(f"**Confidence:** {r.get('confidence', 0)}%")

            if r.get("best_match"):
                bm = r["best_match"]
                lines.append(f"**Best Match:** {bm.get('reference', 'Unknown')}")
                lines.append(f"**Biblical Text:** {bm.get('greek_text', '')[:200]}")

            if r.get("explanation"):
                lines.append(f"**Explanation:** {r['explanation']}")

            lines.append("")

    # Write file
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"Markdown report written to: {filepath}")
    return str(filepath)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test biblical quotation detector with Church Father texts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Input source (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--pdf",
        type=str,
        help="Path to PDF file containing Church Father text",
    )
    input_group.add_argument(
        "--url",
        type=str,
        help="URL to fetch Church Father text from",
    )

    # Output
    parser.add_argument(
        "--output",
        type=str,
        default="results/",
        help="Output directory for reports (default: results/)",
    )

    # Detection options
    parser.add_argument(
        "--mode",
        type=str,
        choices=["llm", "heuristic"],
        default="heuristic",
        help="Detection mode: llm (slower, more accurate) or heuristic (faster)",
    )
    parser.add_argument(
        "--min-confidence",
        type=int,
        default=50,
        help="Minimum confidence threshold (0-100, default: 50)",
    )
    parser.add_argument(
        "--chunk-size",
        type=str,
        choices=["paragraph", "sentence"],
        default="paragraph",
        help="How to split text (default: paragraph)",
    )

    # Filtering options
    parser.add_argument(
        "--greek-only",
        action="store_true",
        default=True,
        help="Only analyze chunks containing Greek text (default: True)",
    )
    parser.add_argument(
        "--no-greek-filter",
        action="store_true",
        help="Disable Greek text filtering",
    )

    # Debug options
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract and chunk text without running detection",
    )

    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Extract text from source
    if args.pdf:
        source_name = Path(args.pdf).name
        text = extract_from_pdf(args.pdf)
    else:
        source_name = args.url
        text = extract_from_url(args.url)

    if not text:
        logger.error("No text extracted from source")
        sys.exit(1)

    # Chunk the text
    chunks = chunk_text(text, method=args.chunk_size)

    if not chunks:
        logger.error("No chunks generated from text")
        sys.exit(1)

    # Filter for Greek text
    if args.greek_only and not args.no_greek_filter:
        chunks = filter_greek_chunks(chunks)
        if not chunks:
            logger.warning("No Greek text found in source")
            logger.info("Use --no-greek-filter to analyze all text")
            sys.exit(0)

    # Dry run - just show stats
    if args.dry_run:
        logger.info("=== Dry Run ===")
        logger.info(f"Source: {source_name}")
        logger.info(f"Total text length: {len(text)} characters")
        logger.info(f"Total chunks: {len(chunks)}")
        logger.info(f"Sample chunk: {chunks[0][:200]}...")
        return

    # Initialize detector
    use_llm = args.mode == "llm"
    logger.info(f"Initializing detector (mode={args.mode}, use_llm={use_llm})")

    try:
        detector = QuotationDetector(use_llm=use_llm)
    except Exception as e:
        logger.error(f"Failed to initialize detector: {e}")
        sys.exit(1)

    # Run detection
    logger.info(f"Running detection on {len(chunks)} chunks...")
    results = run_detection(
        chunks=chunks,
        detector=detector,
        min_confidence=args.min_confidence,
    )

    # Prepare metadata
    metadata = {
        "source": source_name,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "mode": args.mode,
        "min_confidence": args.min_confidence,
        "chunk_method": args.chunk_size,
        "total_chunks": len(chunks),
        "greek_filter": args.greek_only and not args.no_greek_filter,
    }

    # Write reports
    json_path = write_json_report(results, args.output, metadata)
    md_path = write_markdown_report(results, args.output, metadata)

    # Summary
    quotations = [r for r in results if r.get("is_quotation", False)]
    logger.info("=== Analysis Complete ===")
    logger.info(f"Chunks analyzed: {len(results)}")
    logger.info(f"Quotations found: {len(quotations)}")
    logger.info(f"JSON report: {json_path}")
    logger.info(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
