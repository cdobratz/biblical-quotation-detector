#!/usr/bin/env python3
"""
Ingest Greek New Testament from HelloAO Bible API
"""
import sqlite3
import json
import httpx
from pathlib import Path
from typing import List, Dict, Optional
import asyncio
from datetime import datetime
import sys

# Book ID mapping (HelloAO uses these IDs)
BOOK_ID_TO_NAME = {
    40: "Matthew", 41: "Mark", 42: "Luke", 43: "John",
    44: "Acts", 45: "Romans", 46: "1 Corinthians", 47: "2 Corinthians",
    48: "Galatians", 49: "Ephesians", 50: "Philippians", 51: "Colossians",
    52: "1 Thessalonians", 53: "2 Thessalonians", 54: "1 Timothy",
    55: "2 Timothy", 56: "Titus", 57: "Philemon", 58: "Hebrews",
    59: "James", 60: "1 Peter", 61: "2 Peter", 62: "1 John",
    63: "2 John", 64: "3 John", 65: "Jude", 66: "Revelation"
}

class HelloAOIngester:
    def __init__(self, db_path: str, use_local_db: bool = True):
        self.db_path = db_path
        self.use_local_db = use_local_db
        self.base_url = "https://bible.helloao.org/api"
        self.local_db_path = "data/raw/bible.db"
        
    def connect(self):
        """Connect to our processed database"""
        return sqlite3.connect(self.db_path)
    
    async def get_greek_translations(self) -> List[str]:
        """Find available Greek translations"""
        print("Finding Greek translations...")
        
        if self.use_local_db and Path(self.local_db_path).exists():
            print("Using local bible.db...")
            return self._get_greek_from_local()
        else:
            print("Fetching from API...")
            return await self._get_greek_from_api()
    
    def _get_greek_from_local(self) -> List[str]:
        """Get Greek translation IDs from local database"""
        conn = sqlite3.connect(self.local_db_path)
        cursor = conn.cursor()
        
        # Query for Greek translations
        cursor.execute("""
        SELECT id, name, englishName FROM Translation
        WHERE language = 'grc'
           OR englishName LIKE '%Greek%'
           OR id LIKE '%greek%'
           OR id LIKE '%GRK%'
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        if results:
            print(f"Found {len(results)} Greek translations:")
            for trans_id, name, eng_name in results:
                print(f"  - {trans_id}: {eng_name or name}")
            return [r[0] for r in results]
        else:
            print("⚠️  No Greek translations found in local DB")
            return []
    
    async def _get_greek_from_api(self) -> List[str]:
        """Get Greek translation IDs from API"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/available_translations.json")
            data = response.json()
            
            greek_trans = [
                t['id'] for t in data['translations']
                if t['language'] == 'grc' or 'Greek' in t.get('englishName', '')
            ]
            
            print(f"Found {len(greek_trans)} Greek translations")
            return greek_trans
    
    async def ingest_translation(self, translation_id: str):
        """Ingest a specific Greek translation"""
        print(f"\n📖 Ingesting {translation_id}...")
        
        conn = self.connect()
        cursor = conn.cursor()
        
        # Log ingestion start
        cursor.execute("""
        INSERT INTO ingestion_log (source_name, status)
        VALUES (?, 'running')
        """, (f"HelloAO-{translation_id}",))
        log_id = cursor.lastrowid
        conn.commit()
        
        verses_added = 0
        verses_skipped = 0
        
        try:
            if self.use_local_db:
                verses = self._load_verses_local(translation_id)
            else:
                verses = await self._load_verses_api(translation_id)
            
            print(f"Found {len(verses)} verses to process")
            
            for verse_data in verses:
                try:
                    # Check if exists
                    cursor.execute("""
                    SELECT id FROM verses 
                    WHERE reference = ? AND source = ?
                    """, (verse_data['reference'], translation_id))
                    
                    if cursor.fetchone():
                        verses_skipped += 1
                        continue
                    
                    # Insert verse
                    cursor.execute("""
                    INSERT INTO verses (
                        reference, book, chapter, verse,
                        greek_text, greek_normalized, 
                        greek_lemmatized, english_text, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        verse_data['reference'],
                        verse_data['book'],
                        verse_data['chapter'],
                        verse_data['verse'],
                        verse_data['text'],
                        verse_data['text'].lower(),  # Basic normalization for now
                        None,  # Will lemmatize later
                        None,  # No English yet
                        translation_id
                    ))
                    verses_added += 1
                    
                    if verses_added % 100 == 0:
                        print(f"  Processed {verses_added} verses...", end='\r')
                        conn.commit()
                
                except Exception as e:
                    print(f"\n⚠️  Error processing verse: {e}")
                    continue
            
            conn.commit()
            
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
            
            print(f"\n✓ Ingestion complete!")
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
            print(f"\n❌ Ingestion failed: {e}")
            raise
        
        finally:
            conn.close()
    
    def _load_verses_local(self, translation_id: str) -> List[Dict]:
        """Load verses from local bible.db"""
        conn = sqlite3.connect(self.local_db_path)
        cursor = conn.cursor()

        verses = []

        # Get translation data
        cursor.execute("""
        SELECT id, name FROM Translation WHERE id = ?
        """, (translation_id,))

        result = cursor.fetchone()
        if not result:
            print(f"⚠️  Translation {translation_id} not found")
            conn.close()
            return verses

        print(f"Loading verses for {result[1]}...")

        # Get all books for this translation (only NT books)
        cursor.execute("""
        SELECT id, name, numberOfChapters, "order"
        FROM Book
        WHERE translationId = ? AND "order" >= 40
        ORDER BY "order"
        """, (translation_id,))

        books = cursor.fetchall()
        print(f"Found {len(books)} NT books")

        # For each book, get all verses
        for book_id, book_name, num_chapters, book_order in books:
            book_display_name = BOOK_ID_TO_NAME.get(book_order, book_name)
            print(f"  Loading {book_display_name}...")

            # Get all verses for this book
            cursor.execute("""
            SELECT chapterNumber, number, text
            FROM ChapterVerse
            WHERE translationId = ? AND bookId = ?
            ORDER BY chapterNumber, number
            """, (translation_id, book_id))

            book_verses = cursor.fetchall()

            for chapter_num, verse_num, text in book_verses:
                verses.append({
                    'reference': f"{book_display_name} {chapter_num}:{verse_num}",
                    'book': book_display_name,
                    'chapter': chapter_num,
                    'verse': verse_num,
                    'text': text
                })

        conn.close()
        return verses
    
    async def _load_verses_api(self, translation_id: str) -> List[Dict]:
        """Load verses from HelloAO API"""
        verses = []
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get books
            books_url = f"{self.base_url}/{translation_id}/books.json"
            books_resp = await client.get(books_url)
            books_data = books_resp.json()
            
            for book in books_data.get('books', []):
                book_id = book['bookId']
                book_name = BOOK_ID_TO_NAME.get(book_id, f"Book{book_id}")
                
                # Only NT (40-66)
                if book_id < 40:
                    continue
                
                print(f"  Loading {book_name}...")
                
                # Get each chapter
                for chapter_num in range(1, book.get('chapters', 0) + 1):
                    try:
                        chapter_url = f"{self.base_url}/{translation_id}/{book_id}/{chapter_num}.json"
                        chapter_resp = await client.get(chapter_url)
                        chapter_data = chapter_resp.json()
                        
                        for verse in chapter_data.get('verses', []):
                            verses.append({
                                'reference': f"{book_name} {chapter_num}:{verse['verse']}",
                                'book': book_name,
                                'chapter': chapter_num,
                                'verse': verse['verse'],
                                'text': verse['text']
                            })
                        
                        await asyncio.sleep(0.1)  # Rate limiting
                    
                    except Exception as e:
                        print(f"    ⚠️  Error loading {book_name} {chapter_num}: {e}")
                        continue
        
        return verses

async def main():
    """Main ingestion workflow"""
    
    # Check if database exists
    db_path = "data/processed/bible.db"
    if not Path(db_path).exists():
        print("❌ Database not found. Run create_database.py first!")
        sys.exit(1)
    
    # Check if raw data exists
    local_db = Path("data/raw/bible.db")
    use_local = local_db.exists()
    
    if use_local:
        print(f"✓ Found local bible.db ({local_db.stat().st_size / 1e9:.1f} GB)")
    else:
        print("⚠️  Local bible.db not found, will use API (slower)")
        download = input("Download bible.db first? (y/n): ")
        if download.lower() == 'y':
            print("Run: wget https://bible.helloao.org/bible.db -O data/raw/bible.db")
            sys.exit(0)
    
    # Initialize ingester
    ingester = HelloAOIngester(db_path, use_local_db=use_local)
    
    # Get Greek translations
    greek_translations = await ingester.get_greek_translations()
    
    if not greek_translations:
        print("❌ No Greek translations found!")
        sys.exit(1)
    
    # Ingest each translation
    for trans_id in greek_translations:
        await ingester.ingest_translation(trans_id)
    
    # Final stats
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM verses")
    total_verses = cursor.fetchone()[0]
    
    cursor.execute("SELECT source, COUNT(*) FROM verses GROUP BY source")
    by_source = cursor.fetchall()
    
    print("\n" + "="*50)
    print("📊 Final Statistics:")
    print(f"   Total verses: {total_verses}")
    print("   By source:")
    for source, count in by_source:
        print(f"     - {source}: {count} verses")
    
    conn.close()

if __name__ == "__main__":
    asyncio.run(main())