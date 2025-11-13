#!/usr/bin/env python3
"""
Quick ingestion of just SBL Greek NT (the scholarly standard)
"""
import sqlite3
from pathlib import Path
from datetime import datetime
import sys

# Book ID mapping
BOOK_ID_TO_NAME = {
    40: "Matthew", 41: "Mark", 42: "Luke", 43: "John",
    44: "Acts", 45: "Romans", 46: "1 Corinthians", 47: "2 Corinthians",
    48: "Galatians", 49: "Ephesians", 50: "Philippians", 51: "Colossians",
    52: "1 Thessalonians", 53: "2 Thessalonians", 54: "1 Timothy",
    55: "2 Timothy", 56: "Titus", 57: "Philemon", 58: "Hebrews",
    59: "James", 60: "1 Peter", 61: "2 Peter", 62: "1 John",
    63: "2 John", 64: "3 John", 65: "Jude", 66: "Revelation"
}

def main():
    # Paths
    db_path = "data/processed/bible.db"
    source_db_path = "data/raw/bible.db"
    translation_id = "grc_sbl"

    # Validate paths
    if not Path(db_path).exists():
        print("❌ Database not found. Run create_database.py first!")
        sys.exit(1)

    if not Path(source_db_path).exists():
        print("❌ Source bible.db not found!")
        sys.exit(1)

    print(f"📖 Ingesting SBL Greek NT...")

    # Connect to both databases
    source_conn = sqlite3.connect(source_db_path)
    dest_conn = sqlite3.connect(db_path)

    source_cursor = source_conn.cursor()
    dest_cursor = dest_conn.cursor()

    # Start ingestion log
    dest_cursor.execute("""
    INSERT INTO ingestion_log (source_name, status)
    VALUES (?, 'running')
    """, (f"HelloAO-{translation_id}",))
    log_id = dest_cursor.lastrowid
    dest_conn.commit()

    verses_added = 0
    verses_skipped = 0

    try:
        # Get all NT books for SBL
        source_cursor.execute("""
        SELECT id, name, numberOfChapters, "order"
        FROM Book
        WHERE translationId = ? AND "order" >= 40 AND "order" <= 66
        ORDER BY "order"
        """, (translation_id,))

        books = source_cursor.fetchall()
        print(f"Found {len(books)} NT books")

        # Process each book
        for book_id, book_name, num_chapters, book_order in books:
            book_display_name = BOOK_ID_TO_NAME.get(book_order, book_name)
            print(f"  Loading {book_display_name}...")

            # Get all verses for this book
            source_cursor.execute("""
            SELECT chapterNumber, number, text
            FROM ChapterVerse
            WHERE translationId = ? AND bookId = ?
            ORDER BY chapterNumber, number
            """, (translation_id, book_id))

            book_verses = source_cursor.fetchall()

            for chapter_num, verse_num, text in book_verses:
                reference = f"{book_display_name} {chapter_num}:{verse_num}"

                # Check if exists
                dest_cursor.execute("""
                SELECT id FROM verses
                WHERE reference = ? AND source = ?
                """, (reference, translation_id))

                if dest_cursor.fetchone():
                    verses_skipped += 1
                    continue

                # Insert verse
                dest_cursor.execute("""
                INSERT INTO verses (
                    reference, book, chapter, verse,
                    greek_text, greek_normalized,
                    greek_lemmatized, english_text, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    reference,
                    book_display_name,
                    chapter_num,
                    verse_num,
                    text,
                    text.lower(),  # Basic normalization
                    None,  # Will lemmatize later
                    None,  # No English
                    translation_id
                ))
                verses_added += 1

                if verses_added % 100 == 0:
                    print(f"    Processed {verses_added} verses...", end='\r')
                    dest_conn.commit()

        dest_conn.commit()

        # Update log
        dest_cursor.execute("""
        UPDATE ingestion_log SET
            verses_added = ?,
            verses_skipped = ?,
            status = 'completed',
            completed_at = ?
        WHERE id = ?
        """, (verses_added, verses_skipped, datetime.now(), log_id))
        dest_conn.commit()

        print(f"\n✅ Ingestion complete!")
        print(f"   Added: {verses_added}")
        print(f"   Skipped: {verses_skipped}")

        # Show sample verses
        print("\n📚 Sample verses:")
        dest_cursor.execute("""
        SELECT reference, greek_text FROM verses
        WHERE source = ?
        LIMIT 3
        """, (translation_id,))

        for ref, text in dest_cursor.fetchall():
            print(f"   {ref}: {text[:60]}...")

    except Exception as e:
        dest_cursor.execute("""
        UPDATE ingestion_log SET
            status = 'failed',
            error_message = ?,
            completed_at = ?
        WHERE id = ?
        """, (str(e), datetime.now(), log_id))
        dest_conn.commit()
        print(f"\n❌ Ingestion failed: {e}")
        raise

    finally:
        source_conn.close()
        dest_conn.close()

if __name__ == "__main__":
    main()
