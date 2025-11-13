#!/usr/bin/env python3
"""
Ingest CNTR Statistical Restoration Greek New Testament
"""
import sqlite3
from pathlib import Path
from datetime import datetime
import re

# CNTR book number to name mapping
CNTR_BOOKS = {
    1: "Matthew", 2: "Mark", 3: "Luke", 4: "John",
    5: "Acts", 6: "Romans", 7: "1 Corinthians", 8: "2 Corinthians",
    9: "Galatians", 10: "Ephesians", 11: "Philippians", 12: "Colossians",
    13: "1 Thessalonians", 14: "2 Thessalonians", 15: "1 Timothy",
    16: "2 Timothy", 17: "Titus", 18: "Philemon", 19: "Hebrews",
    20: "James", 21: "1 Peter", 22: "2 Peter", 23: "1 John",
    24: "2 John", 25: "3 John", 26: "Jude", 27: "Revelation"
}

class CNTRIngester:
    def __init__(self, db_path: str, cntr_path: str = "data/raw/SR"):
        self.db_path = db_path
        self.cntr_path = Path(cntr_path)
        
    def connect(self):
        return sqlite3.connect(self.db_path)
    
    def parse_sr_file(self, file_path: Path) -> list:
        """Parse Statistical Restoration text file"""
        verses = []

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # SR format: BBCCCVVV Full verse text
                # BB = book (40-66 for NT, using 40s numbering)
                # CCC = chapter (001-999)
                # VVV = verse (001-999)

                match = re.match(r'(\d{2})(\d{3})(\d{3})\s+(.+)', line)
                if not match:
                    continue

                book_num, chapter_str, verse_str, greek_text = match.groups()

                # Convert book number (40-66) to 1-27 for NT
                book_num = int(book_num) - 39
                chapter = int(chapter_str)
                verse = int(verse_str)

                # Skip if not NT (books 1-27)
                if book_num < 1 or book_num > 27:
                    continue

                book_name = CNTR_BOOKS.get(book_num, f"Book{book_num}")
                reference = f"{book_name} {chapter}:{verse}"

                # Remove paragraph markers and other special characters
                greek_text = greek_text.replace('¶', '').replace('˚', '').strip()

                verses.append({
                    'reference': reference,
                    'book': book_name,
                    'chapter': chapter,
                    'verse': verse,
                    'text': greek_text
                })

        return verses
    
    def ingest(self):
        """Ingest SR data"""
        print("📖 Ingesting CNTR Statistical Restoration...")
        
        # Find SR text files
        text_files = list(self.cntr_path.glob("*.txt"))
        
        if not text_files:
            print(f"⚠️  No .txt files found in {self.cntr_path}")
            print("   Check if SR repo was cloned correctly")
            return
        
        conn = self.connect()
        cursor = conn.cursor()
        
        # Log start
        cursor.execute("""
        INSERT INTO ingestion_log (source_name, status)
        VALUES ('CNTR-SR', 'running')
        """)
        log_id = cursor.lastrowid
        conn.commit()
        
        verses_added = 0
        verses_skipped = 0
        
        try:
            for text_file in text_files:
                print(f"  Processing {text_file.name}...")
                
                verses = self.parse_sr_file(text_file)
                
                for verse_data in verses:
                    # Check if exists
                    cursor.execute("""
                    SELECT id FROM verses 
                    WHERE reference = ? AND source = 'SR'
                    """, (verse_data['reference'],))
                    
                    if cursor.fetchone():
                        verses_skipped += 1
                        continue
                    
                    # Insert
                    cursor.execute("""
                    INSERT INTO verses (
                        reference, book, chapter, verse,
                        greek_text, greek_normalized,
                        source
                    ) VALUES (?, ?, ?, ?, ?, ?, 'SR')
                    """, (
                        verse_data['reference'],
                        verse_data['book'],
                        verse_data['chapter'],
                        verse_data['verse'],
                        verse_data['text'],
                        verse_data['text'].lower()
                    ))
                    verses_added += 1
                
                conn.commit()
                print(f"    Added {verses_added}, skipped {verses_skipped}")
            
            # Update log
            cursor.execute("""
            UPDATE ingestion_log SET
                verses_added = ?,
                verses_skipped = ?,
                status = 'completed',
                completed_at = ?
            WHERE id = ?
            """, (verses_added, verses_skipped, datetime.now(), log_id))
            conn.commit()
            
            print(f"✓ SR ingestion complete!")
            print(f"  Added: {verses_added}")
            print(f"  Skipped: {verses_skipped}")
        
        except Exception as e:
            cursor.execute("""
            UPDATE ingestion_log SET
                status = 'failed',
                error_message = ?,
                completed_at = ?
            WHERE id = ?
            """, (str(e), datetime.now(), log_id))
            conn.commit()
            print(f"❌ Ingestion failed: {e}")
            raise
        
        finally:
            conn.close()

if __name__ == "__main__":
    ingester = CNTRIngester("data/processed/bible.db")
    ingester.ingest()