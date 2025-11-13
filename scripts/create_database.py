#!/usr/bin/env python3
"""
Create the SQLite database schema for biblical texts
"""
import sqlite3
from pathlib import Path
import sys

def create_database(db_path: str = "data/processed/bible.db"):
    """Create database with all necessary tables"""
    
    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Connect and create tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Creating database schema...")
    
    # Main verses table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS verses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference TEXT NOT NULL,
        book TEXT NOT NULL,
        chapter INTEGER NOT NULL,
        verse INTEGER NOT NULL,
        greek_text TEXT NOT NULL,
        greek_normalized TEXT NOT NULL,
        greek_lemmatized TEXT,
        english_text TEXT,
        source TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        -- Indexes for fast lookup (allows same reference from different sources)
        UNIQUE(book, chapter, verse, source)
    );
    """)
    
    # Create indexes
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_verses_reference 
    ON verses(reference);
    """)
    
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_verses_book_chapter 
    ON verses(book, chapter);
    """)
    
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_verses_source 
    ON verses(source);
    """)
    
    # Full-text search table
    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS verses_fts USING fts5(
        reference,
        book,
        greek_text,
        greek_normalized,
        greek_lemmatized,
        english_text,
        content=verses,
        content_rowid=id
    );
    """)
    
    # Triggers to keep FTS in sync
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS verses_ai AFTER INSERT ON verses BEGIN
      INSERT INTO verses_fts(rowid, reference, book, greek_text, 
                            greek_normalized, greek_lemmatized, english_text)
      VALUES (new.id, new.reference, new.book, new.greek_text,
              new.greek_normalized, new.greek_lemmatized, new.english_text);
    END;
    """)
    
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS verses_ad AFTER DELETE ON verses BEGIN
      DELETE FROM verses_fts WHERE rowid = old.id;
    END;
    """)
    
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS verses_au AFTER UPDATE ON verses BEGIN
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
    
    # Metadata table for tracking ingestion
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ingestion_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_name TEXT NOT NULL,
        verses_added INTEGER DEFAULT 0,
        verses_updated INTEGER DEFAULT 0,
        verses_skipped INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        error_message TEXT,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP
    );
    """)
    
    # Book names reference table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        testament TEXT CHECK(testament IN ('OT', 'NT')),
        book_number INTEGER,
        chapters_count INTEGER,
        verses_count INTEGER
    );
    """)
    
    conn.commit()
    
    print("✓ Database schema created successfully!")
    print(f"✓ Location: {db_path}")
    
    # Insert NT book names
    nt_books = [
        ('Matthew', 'NT', 1, 28, 1071),
        ('Mark', 'NT', 2, 16, 678),
        ('Luke', 'NT', 3, 24, 1151),
        ('John', 'NT', 4, 21, 879),
        ('Acts', 'NT', 5, 28, 1007),
        ('Romans', 'NT', 6, 16, 433),
        ('1 Corinthians', 'NT', 7, 16, 437),
        ('2 Corinthians', 'NT', 8, 13, 257),
        ('Galatians', 'NT', 9, 6, 149),
        ('Ephesians', 'NT', 10, 6, 155),
        ('Philippians', 'NT', 11, 4, 104),
        ('Colossians', 'NT', 12, 4, 95),
        ('1 Thessalonians', 'NT', 13, 5, 89),
        ('2 Thessalonians', 'NT', 14, 3, 47),
        ('1 Timothy', 'NT', 15, 6, 113),
        ('2 Timothy', 'NT', 16, 4, 83),
        ('Titus', 'NT', 17, 3, 46),
        ('Philemon', 'NT', 18, 1, 25),
        ('Hebrews', 'NT', 19, 13, 303),
        ('James', 'NT', 20, 5, 108),
        ('1 Peter', 'NT', 21, 5, 105),
        ('2 Peter', 'NT', 22, 3, 61),
        ('1 John', 'NT', 23, 5, 105),
        ('2 John', 'NT', 24, 1, 13),
        ('3 John', 'NT', 25, 1, 14),
        ('Jude', 'NT', 26, 1, 25),
        ('Revelation', 'NT', 27, 22, 404),
    ]
    
    cursor.executemany("""
    INSERT OR IGNORE INTO books (name, testament, book_number, chapters_count, verses_count)
    VALUES (?, ?, ?, ?, ?)
    """, nt_books)
    
    conn.commit()
    print(f"✓ Inserted {len(nt_books)} NT book references")
    
    # Display stats
    cursor.execute("SELECT COUNT(*) FROM books")
    book_count = cursor.fetchone()[0]
    
    print(f"\n📊 Database Statistics:")
    print(f"   Books: {book_count}")
    print(f"   Tables: verses, verses_fts, ingestion_log, books")
    print(f"   Indexes: 3 created")
    print(f"   Triggers: 3 FTS sync triggers")
    
    conn.close()
    
    return db_path

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/processed/bible.db"
    create_database(db_path)