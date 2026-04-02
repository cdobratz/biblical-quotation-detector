#!/usr/bin/env python3
"""
Evaluation Script for Biblical Quotation Detector

Computes precision, recall, and F1 scores against a ground-truth dataset.

Usage:
    uv run python scripts/evaluate.py --report results/i_clement/report_YYYYMMDD_HHMMSS.json
    uv run python scripts/evaluate.py --report results/i_clement/report_YYYYMMDD_HHMMSS.json --verbose
"""

import argparse
import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Set, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default ground-truth path
DEFAULT_GROUND_TRUTH = (
    Path(__file__).parent.parent / "data" / "ground_truth" / "i_clement_quotations.json"
)

# Default cross-references path
DEFAULT_CROSS_REFS = (
    Path(__file__).parent.parent / "data" / "cross_references.json"
)


def load_ground_truth(path: Path) -> Dict:
    """Load ground-truth dataset."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_report(path: Path) -> Dict:
    """Load a detection report."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_biblical_refs_from_result(result: Dict) -> Set[str]:
    """Extract biblical references from a detection result."""
    refs = set()
    if result.get("best_match") and result["best_match"].get("reference"):
        refs.add(normalize_reference(result["best_match"]["reference"]))
    for src in result.get("sources", []):
        if src.get("reference"):
            refs.add(normalize_reference(src["reference"]))
    return refs


def normalize_reference(ref: str) -> str:
    """Normalize a biblical reference for comparison."""
    ref = ref.strip()
    # Normalize spacing around colon
    ref = re.sub(r"\s*:\s*", ":", ref)
    return ref


def expand_verse_range(ref: str) -> Set[str]:
    """Expand a verse range reference into individual verse references.

    Examples:
        "Matthew 7:1-2"       -> {"Matthew 7:1", "Matthew 7:2", "Matthew 7:1-2"}
        "1 Corinthians 13:4-7" -> {"1 Corinthians 13:4", ..., "1 Corinthians 13:7", "1 Corinthians 13:4-7"}
        "Romans 1:29-32"      -> {"Romans 1:29", ..., "Romans 1:32", "Romans 1:29-32"}
        "Matthew 5:3"         -> {"Matthew 5:3"}
    """
    ref = normalize_reference(ref)
    # Match pattern: "Book Chapter:Start-End"
    m = re.match(r"^(.+\s\d+):(\d+)-(\d+)$", ref)
    if not m:
        return {ref}
    prefix = m.group(1)  # e.g. "Matthew 7"
    start = int(m.group(2))
    end = int(m.group(3))
    expanded = {ref}  # keep the original range too
    for v in range(start, end + 1):
        expanded.add(f"{prefix}:{v}")
    return expanded


def load_cross_references(path: Optional[Path] = None) -> Dict[str, Set[str]]:
    """Load cross-reference chains mapping each verse to its parallel passages.

    Returns a dict where each key is a verse reference and the value is the
    set of all parallel references (including itself).
    """
    if path is None:
        path = DEFAULT_CROSS_REFS
    ref_map: Dict[str, Set[str]] = {}

    if not path.exists():
        logger.debug("No cross_references.json found")
        return ref_map

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for group in data.get("parallel_passages", []):
            refs = set(group.get("refs", []))
            for ref in refs:
                if ref not in ref_map:
                    ref_map[ref] = set()
                ref_map[ref].update(refs)
        logger.info(f"Loaded {len(ref_map)} cross-reference entries")
    except Exception as e:
        logger.warning(f"Failed to load cross-references: {e}")

    return ref_map


def build_known_refs(
    ground_truth: Dict,
    cross_refs: Optional[Dict[str, Set[str]]] = None,
) -> Dict[str, Set[str]]:
    """Build sets of known biblical references by match type.

    Verse ranges (e.g. "Matthew 7:1-2") are expanded into individual verses
    so that detecting any verse in the range counts as a match.

    Cross-reference chains: If cross_refs is provided, parallel passages
    are also added so detecting a parallel verse counts as finding the
    ground-truth entry (e.g. detecting Genesis 15:6 counts as finding
    Galatians 3:6 if they are in the same cross-reference group).
    """
    result = {
        "exact": set(),
        "close_paraphrase": set(),
        "allusion": set(),
        "all_quotations": set(),
        "non_biblical": set(),
    }
    # Map each expanded verse back to its original ground-truth entry
    # so we can count recall by entry, not by individual verse
    result["_verse_to_entry"] = {}  # verse -> original ref
    result["_entries"] = {"exact": set(), "close_paraphrase": set(), "allusion": set(), "all": set()}

    if cross_refs is None:
        cross_refs = {}

    for category, key in [
        ("exact_quotations", "exact"),
        ("close_paraphrases", "close_paraphrase"),
        ("allusions", "allusion"),
    ]:
        for entry in ground_truth.get(category, []):
            original_ref = normalize_reference(entry["biblical_ref"])
            result["_entries"][key].add(original_ref)
            result["_entries"]["all"].add(original_ref)
            expanded = expand_verse_range(entry["biblical_ref"])

            # Add cross-reference parallels for each expanded verse
            all_refs = set(expanded)
            for v in expanded:
                if v in cross_refs:
                    all_refs.update(cross_refs[v])

            result[key].update(all_refs)
            result["all_quotations"].update(all_refs)
            for v in all_refs:
                result["_verse_to_entry"][v] = original_ref

    return result


def evaluate_report(
    report: Dict,
    ground_truth: Dict,
    verbose: bool = False,
) -> Dict:
    """
    Evaluate a detection report against ground truth.

    Returns metrics dict with precision, recall, F1 at multiple levels.
    """
    results = report.get("results", [])
    cross_refs = load_cross_references()
    known = build_known_refs(ground_truth, cross_refs)

    # Collect detected references by match type
    detected_refs = {
        "exact": set(),
        "close_paraphrase": set(),
        "loose_paraphrase": set(),
        "allusion": set(),
        "all_quotations": set(),
    }

    true_positives = 0
    false_positives = 0
    match_type_counts = Counter()

    for r in results:
        match_type = r.get("match_type", "non_biblical")
        is_quot = r.get("is_quotation", False)
        match_type_counts[match_type] += 1

        if not is_quot:
            continue

        refs = extract_biblical_refs_from_result(r)
        detected_refs["all_quotations"].update(refs)

        if match_type in detected_refs:
            detected_refs[match_type].update(refs)

        # Check if any detected ref is in ground truth
        is_true_positive = bool(refs & known["all_quotations"])
        if is_true_positive:
            true_positives += 1
        else:
            false_positives += 1

    # Recall: how many ground-truth entries were found?
    # Count by original entry (not expanded verses) so ranges don't inflate denominator
    verse_to_entry = known.get("_verse_to_entry", {})
    all_entries = known.get("_entries", {}).get("all", set())
    all_detected = detected_refs["all_quotations"]

    # Map detected verses back to ground-truth entries
    found_entries = set()
    for v in all_detected:
        if v in verse_to_entry:
            found_entries.add(verse_to_entry[v])
    missed_entries = all_entries - found_entries

    total_detected_quotations = sum(1 for r in results if r.get("is_quotation", False))
    total_non_biblical = sum(1 for r in results if not r.get("is_quotation", False))

    precision = (
        true_positives / total_detected_quotations
        if total_detected_quotations > 0
        else 0.0
    )
    recall = len(found_entries) / len(all_entries) if all_entries else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    metrics = {
        "total_chunks": len(results),
        "total_detected_quotations": total_detected_quotations,
        "total_non_biblical": total_non_biblical,
        "match_type_distribution": dict(match_type_counts),
        "ground_truth_known_quotations": len(all_entries),
        "ground_truth_found": len(found_entries),
        "ground_truth_missed": len(missed_entries),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "found_references": sorted(found_entries),
        "missed_references": sorted(missed_entries),
    }

    if verbose:
        # Per-type breakdown (count by ground-truth entry, not expanded verses)
        entry_sets = known.get("_entries", {})
        for mtype in ["exact", "close_paraphrase", "allusion"]:
            known_entries_for_type = entry_sets.get(mtype, set())
            detected_set = detected_refs.get(mtype, set())
            # Map detected verses back to entries for this type
            found_for_type = set()
            for v in detected_set:
                entry = verse_to_entry.get(v)
                if entry and entry in known_entries_for_type:
                    found_for_type.add(entry)
            metrics[f"{mtype}_known"] = len(known_entries_for_type)
            metrics[f"{mtype}_found"] = len(found_for_type)
            metrics[f"{mtype}_recall"] = (
                round(len(found_for_type) / len(known_entries_for_type), 4)
                if known_entries_for_type
                else 0.0
            )

    return metrics


def print_metrics(metrics: Dict, verbose: bool = False) -> None:
    """Print evaluation metrics in a readable format."""
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)

    print(f"\nTotal chunks analyzed: {metrics['total_chunks']}")
    print(f"Detected as quotation: {metrics['total_detected_quotations']}")
    print(f"Detected as non-biblical: {metrics['total_non_biblical']}")

    print("\nMatch type distribution:")
    for mtype, count in sorted(metrics["match_type_distribution"].items()):
        pct = count / metrics["total_chunks"] * 100
        print(f"  {mtype:20s}: {count:4d} ({pct:.1f}%)")

    print("\n--- Ground Truth Evaluation ---")
    print(f"Known quotations: {metrics['ground_truth_known_quotations']}")
    print(f"Found: {metrics['ground_truth_found']}")
    print(f"Missed: {metrics['ground_truth_missed']}")

    print(f"\nTrue positives:  {metrics['true_positives']}")
    print(f"False positives: {metrics['false_positives']}")

    print(f"\nPrecision: {metrics['precision']:.2%}")
    print(f"Recall:    {metrics['recall']:.2%}")
    print(f"F1 Score:  {metrics['f1']:.2%}")

    if metrics["missed_references"]:
        print("\nMissed references:")
        for ref in metrics["missed_references"]:
            print(f"  - {ref}")

    if verbose:
        print("\n--- Per-Type Recall ---")
        for mtype in ["exact", "close_paraphrase", "allusion"]:
            known = metrics.get(f"{mtype}_known", 0)
            found = metrics.get(f"{mtype}_found", 0)
            recall = metrics.get(f"{mtype}_recall", 0.0)
            print(f"  {mtype:20s}: {found}/{known} ({recall:.2%})")

        if metrics["found_references"]:
            print("\nFound references:")
            for ref in metrics["found_references"]:
                print(f"  + {ref}")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate detection report against ground truth"
    )
    parser.add_argument(
        "--report",
        type=str,
        required=True,
        help="Path to detection report JSON file",
    )
    parser.add_argument(
        "--ground-truth",
        type=str,
        default=str(DEFAULT_GROUND_TRUTH),
        help="Path to ground-truth JSON file",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed per-type breakdown",
    )
    parser.add_argument(
        "--json-output",
        type=str,
        help="Write metrics to JSON file",
    )

    args = parser.parse_args()

    # Load data
    ground_truth = load_ground_truth(Path(args.ground_truth))
    report = load_report(Path(args.report))

    logger.info(f"Report: {args.report}")
    logger.info(f"Ground truth: {args.ground_truth}")

    # Evaluate
    metrics = evaluate_report(report, ground_truth, verbose=args.verbose)

    # Print results
    print_metrics(metrics, verbose=args.verbose)

    # Optionally write JSON
    if args.json_output:
        with open(args.json_output, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        logger.info(f"Metrics written to: {args.json_output}")


if __name__ == "__main__":
    main()
