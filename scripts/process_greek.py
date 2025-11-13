#!/usr/bin/env python3
"""
Process Greek text: normalize and lemmatize all verses
"""
import sqlite3
import re
from tqdm import tqdm

class GreekProcessor:
    """Basic Greek text processing"""
    
    def __init__(self):
        # Greek Unicode ranges
        self.greek_pattern = re.compile(r'[\u0370-\u03FF\u1F00-\u1FFF]+')
        
    def normalize(self, text: str) -> str:
        """
        Remove diacritics and convert to lowercase
        Basic version - CLTK would be better but this works for MVP
        """
        # Remove diacritics (combining characters)
        import unicodedata
        
        # Decompose and remove combining marks
        nfd = unicodedata.normalize('NFD', text)
        text = ''.join(char for char in nfd 
                      if not unicodedata.combining(char))
        
        # Lowercase
        text = text.lower()
        
        # Remove punctuation but keep spaces
        text = re.sub(r'[^\w\s]', '', text)
        
        return text.strip()
    
    def simple_lemmatize(self, text: str) -> str:
        """
        Very basic lemmatization - just remove common endings
        For MVP - replace with CLTK later
        """
        words = text.split()
        lemmatized = []
        
        # Common Greek endings to strip (very simplified)
        endings = ['ος', 'ον', 'ου', 'ων', 'ας', 'αι', 'ης', 'ει']
        
        for word in words:
            if len(word) > 4:
                for ending in endings:
                    if word.endswith(ending):
                        word = word[:-len(ending)]
                        break
            lemmatized.append(word)
        
        return ' '.join(lemmatized)

def process_all_verses(db_path: str):
    """Process all verses in database"""

    print("🔄 Processing Greek text...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Temporarily disable FTS triggers to avoid corruption
    print("Disabling FTS triggers temporarily...")
    cursor.execute("DROP TRIGGER IF EXISTS verses_au")
    conn.commit()

    # Get all verses that need processing
    cursor.execute("""
    SELECT id, greek_text FROM verses
    WHERE greek_lemmatized IS NULL
    """)

    verses = cursor.fetchall()
    print(f"Found {len(verses)} verses to process")

    processor = GreekProcessor()
    processed = 0

    for verse_id, greek_text in tqdm(verses, desc="Processing"):
        try:
            normalized = processor.normalize(greek_text)
            lemmatized = processor.simple_lemmatize(normalized)

            cursor.execute("""
            UPDATE verses SET
                greek_normalized = ?,
                greek_lemmatized = ?
            WHERE id = ?
            """, (normalized, lemmatized, verse_id))

            processed += 1

            if processed % 1000 == 0:
                conn.commit()

        except Exception as e:
            print(f"\n⚠️  Error processing verse {verse_id}: {e}")
            continue

    conn.commit()

    # Recreate the FTS update trigger
    print("\nRecreating FTS triggers...")
    cursor.execute("""
    CREATE TRIGGER verses_au AFTER UPDATE ON verses BEGIN
      UPDATE verses_fts SET
        reference = new.reference,
        book = new.book,
        greek_text = new.greek_text,
        greek_normalized = new.greek_normalized,
        greek_lemmatized = new.greek_lemmatized,
        english_text = new.english_text
      WHERE rowid = new.id;
    END;
    """)
    conn.commit()

    # Rebuild FTS index with new data
    print("Rebuilding FTS index...")
    cursor.execute("INSERT INTO verses_fts(verses_fts) VALUES('rebuild')")
    conn.commit()

    conn.close()

    print(f"✓ Processed {processed} verses")
    print(f"✓ FTS index rebuilt")

if __name__ == "__main__":
    process_all_verses("data/processed/bible.db")