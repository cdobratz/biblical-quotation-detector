#!/usr/bin/env python3
"""
Septuagint (LXX) Ingestion Script

Downloads and ingests the Rahlfs 1935 LXX text into the SQLite database
and Qdrant vector store. Uses the eliranwong/LXX-Rahlfs-1935 dataset
which provides word-by-word Greek text with verse references.

Usage:
    # Download LXX data and ingest into database
    uv run python scripts/ingest_lxx.py

    # Ingest only (data already downloaded)
    uv run python scripts/ingest_lxx.py --skip-download

    # Ingest specific books only
    uv run python scripts/ingest_lxx.py --books Gen,Exod,Isa,Ps

    # Limit verses for testing
    uv run python scripts/ingest_lxx.py --limit 100
"""

import argparse
import logging
import re
import sqlite3
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# LXX repository URL
LXX_REPO_URL = "https://github.com/eliranwong/LXX-Rahlfs-1935.git"

# Map LXX abbreviated book names to standard full names
LXX_BOOK_NAMES: Dict[str, str] = {
    "Gen": "Genesis",
    "Exod": "Exodus",
    "Lev": "Leviticus",
    "Num": "Numbers",
    "Deut": "Deuteronomy",
    "JoshA": "Joshua",
    "JoshB": "Joshua",
    "JudgA": "Judges",
    "JudgB": "Judges",
    "Ruth": "Ruth",
    "1Sam/K": "1 Samuel",
    "2Sam/K": "2 Samuel",
    "1/3Kgs": "1 Kings",
    "2/4Kgs": "2 Kings",
    "1Chr": "1 Chronicles",
    "2Chr": "2 Chronicles",
    "1Esdr": "1 Esdras",
    "2Esdr": "Ezra-Nehemiah",
    "Esth": "Esther",
    "Jdt": "Judith",
    "TobBA": "Tobit",
    "TobS": "Tobit",
    "1Mac": "1 Maccabees",
    "2Mac": "2 Maccabees",
    "3Mac": "3 Maccabees",
    "4Mac": "4 Maccabees",
    "Ps": "Psalms",
    "Od": "Odes",
    "PsSol": "Psalms of Solomon",
    "Prov": "Proverbs",
    "Qoh": "Ecclesiastes",
    "Cant": "Song of Solomon",
    "Job": "Job",
    "Wis": "Wisdom of Solomon",
    "Sir": "Sirach",
    "Hos": "Hosea",
    "Amos": "Amos",
    "Mic": "Micah",
    "Joel": "Joel",
    "Jonah": "Jonah",
    "Hab": "Habakkuk",
    "Zeph": "Zephaniah",
    "Hag": "Haggai",
    "Zech": "Zechariah",
    "Mal": "Malachi",
    "Nah": "Nahum",
    "Isa": "Isaiah",
    "Jer": "Jeremiah",
    "Bar": "Baruch",
    "Lam": "Lamentations",
    "Ezek": "Ezekiel",
    "Dan": "Daniel",
    "DanTh": "Daniel (Theodotion)",
    "SusTh": "Susanna (Theodotion)",
}

# Books most relevant to 1 Clement quotations (prioritized for ingestion)
PRIORITY_BOOKS: Set[str] = {
    "Gen",
    "Exod",
    "Deut",
    "Ps",
    "Prov",
    "Isa",
    "Jer",
    "Ezek",
    "Job",
    "Dan",
    "DanTh",
}


def normalize_greek(text: str) -> str:
    """Normalize Greek text for storage (lowercase, strip diacritics)."""
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    lowered = stripped.lower()
    lowered = re.sub(r"[^\w\s]", "", lowered, flags=re.UNICODE)
    lowered = lowered.replace("ς", "σ")
    return lowered


def download_lxx_data(data_dir: Path) -> Path:
    """Clone the LXX-Rahlfs-1935 repository."""
    lxx_dir = data_dir / "LXX-Rahlfs-1935"

    if lxx_dir.exists():
        logger.info(f"LXX data already exists at {lxx_dir}")
        return lxx_dir

    logger.info("Downloading LXX-Rahlfs-1935 data...")
    data_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["git", "clone", "--depth", "1", LXX_REPO_URL, str(lxx_dir)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        logger.error(f"Git clone failed: {result.stderr}")
        raise RuntimeError(f"Failed to download LXX data: {result.stderr}")

    logger.info(f"LXX data downloaded to {lxx_dir}")
    return lxx_dir


def load_lxx_words(lxx_dir: Path) -> Dict[int, str]:
    """Load word list from text_accented.csv."""
    words_file = lxx_dir / "01_wordlist_unicode" / "text_accented.csv"

    if not words_file.exists():
        raise FileNotFoundError(f"Word list not found: {words_file}")

    words: Dict[int, str] = {}
    with open(words_file, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                words[int(parts[0])] = parts[2]

    logger.info(f"Loaded {len(words)} words from LXX text")
    return words


def load_lxx_verses(lxx_dir: Path) -> List[Tuple[int, str]]:
    """Load verse boundaries from E-verse.csv."""
    verse_file = lxx_dir / "08_versification" / "ccat" / "E-verse.csv"

    if not verse_file.exists():
        raise FileNotFoundError(f"Versification file not found: {verse_file}")

    verses: List[Tuple[int, str]] = []
    with open(verse_file, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                word_idx = int(parts[0])
                ref_match = re.search(r"「(.+)」", parts[2])
                if ref_match:
                    verses.append((word_idx, ref_match.group(1)))

    logger.info(f"Loaded {len(verses)} verse boundaries")
    return verses


def reconstruct_verses(
    words: Dict[int, str],
    verse_boundaries: List[Tuple[int, str]],
    book_filter: Optional[Set[str]] = None,
) -> List[Dict]:
    """Reconstruct verse-level text from word list and verse boundaries.

    Args:
        words: Word index -> word text mapping
        verse_boundaries: List of (word_index, reference_string) tuples
        book_filter: Optional set of LXX book abbreviations to include

    Returns:
        List of verse dicts with reference, book, chapter, verse, text fields
    """
    verses: List[Dict] = []
    max_word_idx = max(words.keys()) if words else 0

    for i, (start_idx, ref_str) in enumerate(verse_boundaries):
        # Parse reference: "Gen 1:1" -> book="Gen", chapter=1, verse=1
        ref_match = re.match(r"^(.+?)\s+(\d+):(\d+)$", ref_str)
        if not ref_match:
            logger.debug(f"Skipping unparseable reference: {ref_str}")
            continue

        lxx_book = ref_match.group(1)
        chapter = int(ref_match.group(2))
        verse_num = int(ref_match.group(3))

        # Apply book filter
        if book_filter and lxx_book not in book_filter:
            continue

        # Map to standard book name
        book_name = LXX_BOOK_NAMES.get(lxx_book, lxx_book)

        # Determine end index (start of next verse or end of words)
        end_idx = (
            verse_boundaries[i + 1][0]
            if i + 1 < len(verse_boundaries)
            else max_word_idx + 1
        )

        # Reconstruct verse text
        verse_words = [words.get(j, "") for j in range(start_idx, end_idx)]
        verse_words = [w for w in verse_words if w]  # filter empty
        greek_text = " ".join(verse_words)

        if not greek_text.strip():
            continue

        # Build reference string
        reference = f"{book_name} {chapter}:{verse_num}"

        verses.append(
            {
                "reference": reference,
                "book": book_name,
                "chapter": chapter,
                "verse": verse_num,
                "greek_text": greek_text,
                "greek_normalized": normalize_greek(greek_text),
                "source": "LXX",
                "lxx_book": lxx_book,
            }
        )

    logger.info(f"Reconstructed {len(verses)} verses")
    return verses


def insert_ot_books(conn: sqlite3.Connection) -> None:
    """Insert OT book entries into the books table."""
    ot_books = [
        ("Genesis", "OT", 1, 50, 1533),
        ("Exodus", "OT", 2, 40, 1213),
        ("Leviticus", "OT", 3, 27, 859),
        ("Numbers", "OT", 4, 36, 1288),
        ("Deuteronomy", "OT", 5, 34, 959),
        ("Joshua", "OT", 6, 24, 658),
        ("Judges", "OT", 7, 21, 618),
        ("Ruth", "OT", 8, 4, 85),
        ("1 Samuel", "OT", 9, 31, 810),
        ("2 Samuel", "OT", 10, 24, 695),
        ("1 Kings", "OT", 11, 22, 816),
        ("2 Kings", "OT", 12, 25, 719),
        ("1 Chronicles", "OT", 13, 29, 942),
        ("2 Chronicles", "OT", 14, 36, 822),
        ("Ezra-Nehemiah", "OT", 15, 23, 688),
        ("Esther", "OT", 16, 10, 167),
        ("Job", "OT", 17, 42, 1070),
        ("Psalms", "OT", 18, 150, 2461),
        ("Proverbs", "OT", 19, 31, 915),
        ("Ecclesiastes", "OT", 20, 12, 222),
        ("Song of Solomon", "OT", 21, 8, 117),
        ("Isaiah", "OT", 22, 66, 1292),
        ("Jeremiah", "OT", 23, 52, 1364),
        ("Lamentations", "OT", 24, 5, 154),
        ("Ezekiel", "OT", 25, 48, 1273),
        ("Daniel", "OT", 26, 12, 357),
        ("Hosea", "OT", 27, 14, 197),
        ("Joel", "OT", 28, 3, 73),
        ("Amos", "OT", 29, 9, 146),
        ("Jonah", "OT", 30, 4, 48),
        ("Micah", "OT", 31, 7, 105),
        ("Nahum", "OT", 32, 3, 47),
        ("Habakkuk", "OT", 33, 3, 56),
        ("Zephaniah", "OT", 34, 3, 53),
        ("Haggai", "OT", 35, 2, 38),
        ("Zechariah", "OT", 36, 14, 211),
        ("Malachi", "OT", 37, 4, 55),
        # Deuterocanonical / Apocrypha
        ("Tobit", "OT", 38, 14, 244),
        ("Judith", "OT", 39, 16, 339),
        ("Wisdom of Solomon", "OT", 40, 19, 435),
        ("Sirach", "OT", 41, 51, 1388),
        ("Baruch", "OT", 42, 5, 213),
        ("1 Maccabees", "OT", 43, 16, 924),
        ("2 Maccabees", "OT", 44, 15, 555),
        ("3 Maccabees", "OT", 45, 7, 229),
        ("4 Maccabees", "OT", 46, 18, 459),
        ("1 Esdras", "OT", 47, 9, 436),
        ("Odes", "OT", 48, 14, 179),
        ("Psalms of Solomon", "OT", 49, 18, 253),
        ("Daniel (Theodotion)", "OT", 50, 12, 357),
        ("Susanna (Theodotion)", "OT", 51, 1, 64),
    ]

    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT OR IGNORE INTO books (name, testament, book_number, chapters_count, verses_count)
        VALUES (?, ?, ?, ?, ?)
        """,
        ot_books,
    )
    conn.commit()
    logger.info(f"Inserted {len(ot_books)} OT book entries")


def ingest_to_sqlite(
    verses: List[Dict],
    db_path: str,
) -> int:
    """Ingest LXX verses into SQLite database.

    Returns:
        Number of verses successfully inserted
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Insert OT books first
    insert_ot_books(conn)

    added = 0
    skipped = 0

    for verse in verses:
        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO verses (
                    reference, book, chapter, verse,
                    greek_text, greek_normalized,
                    greek_lemmatized, english_text, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    verse["reference"],
                    verse["book"],
                    verse["chapter"],
                    verse["verse"],
                    verse["greek_text"],
                    verse["greek_normalized"],
                    None,  # lemmatized - not available
                    None,  # english - not available
                    verse["source"],
                ),
            )

            if cursor.rowcount > 0:
                added += 1
            else:
                skipped += 1

            if added % 500 == 0 and added > 0:
                conn.commit()
                logger.info(f"  Progress: {added} verses inserted...")

        except Exception as e:
            logger.warning(f"Failed to insert {verse['reference']}: {e}")
            skipped += 1

    conn.commit()
    conn.close()

    logger.info(f"SQLite ingestion: {added} added, {skipped} skipped")
    return added


def main():
    parser = argparse.ArgumentParser(
        description="Download and ingest LXX Septuagint into the database"
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip downloading LXX data (use existing)",
    )
    parser.add_argument(
        "--books",
        type=str,
        help="Comma-separated list of LXX book abbreviations to ingest "
        "(e.g., Gen,Exod,Isa,Ps). Default: all books.",
    )
    parser.add_argument(
        "--priority-only",
        action="store_true",
        help="Only ingest priority books most relevant to 1 Clement",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of verses to ingest (for testing)",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="./data/processed/bible.db",
        help="Path to SQLite database",
    )
    parser.add_argument(
        "--skip-qdrant",
        action="store_true",
        help="Skip Qdrant vector ingestion (SQLite only)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for Qdrant ingestion",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("SEPTUAGINT (LXX) INGESTION")
    logger.info("=" * 60)

    # Determine data directory
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data" / "raw"

    # Step 1: Download LXX data
    if args.skip_download:
        lxx_dir = data_dir / "LXX-Rahlfs-1935"
        if not lxx_dir.exists():
            logger.error(f"LXX data not found at {lxx_dir}")
            sys.exit(1)
    else:
        lxx_dir = download_lxx_data(data_dir)

    # Step 2: Load word list and verse boundaries
    logger.info("Loading LXX word list...")
    start_time = time.time()
    words = load_lxx_words(lxx_dir)
    verse_boundaries = load_lxx_verses(lxx_dir)
    load_time = time.time() - start_time
    logger.info(f"Data loaded in {load_time:.1f}s")

    # Step 3: Determine book filter
    book_filter: Optional[Set[str]] = None
    if args.books:
        book_filter = set(args.books.split(","))
        logger.info(f"Filtering to books: {book_filter}")
    elif args.priority_only:
        book_filter = PRIORITY_BOOKS
        logger.info(f"Using priority books: {book_filter}")

    # Step 4: Reconstruct verses
    logger.info("Reconstructing verses from word list...")
    verses = reconstruct_verses(words, verse_boundaries, book_filter)

    if args.limit:
        verses = verses[: args.limit]
        logger.info(f"Limited to {len(verses)} verses")

    if not verses:
        logger.warning("No verses to ingest!")
        return

    # Show book distribution
    book_counts: Dict[str, int] = {}
    for v in verses:
        book_counts[v["book"]] = book_counts.get(v["book"], 0) + 1
    logger.info(f"Total verses to ingest: {len(verses)}")
    logger.info(f"Books: {len(book_counts)}")
    for book, count in sorted(book_counts.items(), key=lambda x: -x[1])[:10]:
        logger.info(f"  {book}: {count} verses")

    # Step 5: Ingest into SQLite
    logger.info("Ingesting into SQLite...")
    db_path = args.db_path
    if not Path(db_path).exists():
        logger.error(f"Database not found: {db_path}. Run create_database.py first.")
        sys.exit(1)

    sqlite_start = time.time()
    added = ingest_to_sqlite(verses, db_path)
    sqlite_time = time.time() - sqlite_start
    logger.info(f"SQLite ingestion complete in {sqlite_time:.1f}s")

    # Step 6: Ingest into Qdrant (optional)
    if not args.skip_qdrant:
        logger.info("Ingesting into Qdrant...")
        try:
            from src.memory.qdrant_manager import QdrantManager

            manager = QdrantManager()

            # Format for Qdrant ingestion
            qdrant_verses = []
            # Use ID offset to avoid conflicts with NT verses
            # NT verses use IDs from the SQLite autoincrement
            # We'll query the max existing ID and start from there
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            # Get the actual IDs of newly inserted LXX verses
            cursor.execute(
                "SELECT id, reference, greek_normalized, greek_text, book, "
                "chapter, verse, source FROM verses WHERE source = 'LXX'"
            )
            lxx_rows = cursor.fetchall()
            conn.close()

            for row in lxx_rows:
                qdrant_verses.append(
                    {
                        "id": row[0],
                        "text": row[2] or row[3],  # normalized or original
                        "metadata": {
                            "reference": row[1],
                            "book": row[4],
                            "chapter": row[5],
                            "verse": row[6],
                            "source": row[7],
                            "greek_original": row[3],
                        },
                    }
                )

            if qdrant_verses:
                qdrant_start = time.time()
                result = manager.add_verses_batch(
                    verses=qdrant_verses,
                    batch_size=args.batch_size,
                )
                qdrant_time = time.time() - qdrant_start
                logger.info(
                    f"Qdrant ingestion: {result['added']} added, "
                    f"{result['failed']} failed in {qdrant_time:.1f}s"
                )
            else:
                logger.info("No new LXX verses to add to Qdrant")

        except Exception as e:
            logger.error(f"Qdrant ingestion failed: {e}")
            logger.info("You can re-run with --skip-qdrant to skip vector ingestion")
    else:
        logger.info("Skipping Qdrant ingestion (--skip-qdrant)")

    # Final report
    logger.info("")
    logger.info("=" * 60)
    logger.info("LXX INGESTION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Verses added to SQLite: {added}")
    logger.info(f"Books covered: {len(book_counts)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
