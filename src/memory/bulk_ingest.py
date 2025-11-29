"""
Bulk Ingestion Module for Mem0 Vector Store

This module handles the bulk loading of biblical verses from SQLite
into the Mem0 vector store for semantic search.
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from .mem0_manager import Mem0Manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BulkIngester:
    """
    Handles bulk ingestion of biblical verses into Mem0 vector store.
    """

    def __init__(
        self,
        database_path: str,
        mem0_manager: Optional[Mem0Manager] = None
    ):
        """
        Initialize the bulk ingester.

        Args:
            database_path: Path to the SQLite database
            mem0_manager: Optional Mem0Manager instance (creates new if None)
        """
        self.database_path = Path(database_path)

        if not self.database_path.exists():
            raise FileNotFoundError(f"Database not found: {database_path}")

        self.mem0_manager = mem0_manager or Mem0Manager()
        logger.info(f"BulkIngester initialized with database: {database_path}")

    def _fetch_verses(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        source: Optional[str] = None,
        book: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch verses from the database.

        Args:
            limit: Maximum number of verses to fetch
            offset: Number of verses to skip
            source: Filter by source (e.g., 'SR', 'grc_sbl')
            book: Filter by book name

        Returns:
            List of verse dictionaries
        """
        query = """
        SELECT
            id,
            reference,
            book,
            chapter,
            verse,
            greek_text,
            greek_normalized,
            greek_lemmatized,
            english_text,
            source
        FROM verses
        WHERE 1=1
        """

        params = []

        if source:
            query += " AND source = ?"
            params.append(source)

        if book:
            query += " AND book = ?"
            params.append(book)

        query += " ORDER BY id"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        if offset:
            query += " OFFSET ?"
            params.append(offset)

        try:
            conn = sqlite3.connect(self.database_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(query, params)
            rows = cursor.fetchall()

            verses = []
            for row in rows:
                verses.append({
                    "id": row["id"],
                    "reference": row["reference"],
                    "book": row["book"],
                    "chapter": row["chapter"],
                    "verse": row["verse"],
                    "greek_text": row["greek_text"],
                    "greek_normalized": row["greek_normalized"],
                    "greek_lemmatized": row["greek_lemmatized"],
                    "english_text": row["english_text"],
                    "source": row["source"]
                })

            conn.close()
            logger.info(f"Fetched {len(verses)} verses from database")
            return verses

        except Exception as e:
            logger.error(f"Failed to fetch verses: {e}")
            raise

    def ingest_all(
        self,
        batch_size: int = 100,
        use_normalized: bool = True,
        limit: Optional[int] = None
    ) -> Dict:
        """
        Ingest all verses from the database into Mem0.

        Args:
            batch_size: Number of verses to process in each batch
            use_normalized: Use normalized text (True) or original (False)
            limit: Optional limit on number of verses to ingest

        Returns:
            Summary statistics
        """
        start_time = datetime.now()
        logger.info("Starting bulk ingestion of all verses")

        # Fetch all verses
        verses = self._fetch_verses(limit=limit)
        total = len(verses)

        logger.info(f"Preparing to ingest {total} verses")

        # Prepare data for Mem0
        mem0_verses = []
        for verse in verses:
            # Choose which text version to use
            text = verse["greek_normalized"] if use_normalized else verse["greek_text"]

            mem0_verses.append({
                "id": str(verse["id"]),
                "text": text,
                "metadata": {
                    "reference": verse["reference"],
                    "book": verse["book"],
                    "chapter": verse["chapter"],
                    "verse": verse["verse"],
                    "source": verse["source"],
                    "greek_text": verse["greek_text"],
                    "greek_normalized": verse["greek_normalized"],
                    "greek_lemmatized": verse["greek_lemmatized"],
                    "english_text": verse["english_text"] or ""
                }
            })

        # Ingest in batches
        result = self.mem0_manager.add_verses_batch(
            verses=mem0_verses,
            batch_size=batch_size
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info(f"Bulk ingestion complete in {duration:.2f} seconds")

        return {
            **result,
            "duration_seconds": duration,
            "verses_per_second": result["added"] / duration if duration > 0 else 0
        }

    def ingest_by_source(
        self,
        source: str,
        batch_size: int = 100,
        use_normalized: bool = True
    ) -> Dict:
        """
        Ingest verses from a specific source.

        Args:
            source: Source identifier (e.g., 'SR', 'grc_sbl')
            batch_size: Number of verses to process in each batch
            use_normalized: Use normalized text (True) or original (False)

        Returns:
            Summary statistics
        """
        logger.info(f"Starting ingestion for source: {source}")

        verses = self._fetch_verses(source=source)

        if not verses:
            logger.warning(f"No verses found for source: {source}")
            return {"total": 0, "added": 0, "failed": 0}

        mem0_verses = []
        for verse in verses:
            text = verse["greek_normalized"] if use_normalized else verse["greek_text"]

            mem0_verses.append({
                "id": str(verse["id"]),
                "text": text,
                "metadata": {
                    "reference": verse["reference"],
                    "book": verse["book"],
                    "chapter": verse["chapter"],
                    "verse": verse["verse"],
                    "source": verse["source"],
                    "greek_text": verse["greek_text"],
                    "greek_normalized": verse["greek_normalized"],
                    "greek_lemmatized": verse["greek_lemmatized"]
                }
            })

        result = self.mem0_manager.add_verses_batch(
            verses=mem0_verses,
            batch_size=batch_size
        )

        logger.info(f"Completed ingestion for source {source}: {result}")
        return result

    def ingest_by_book(
        self,
        book: str,
        batch_size: int = 100,
        use_normalized: bool = True
    ) -> Dict:
        """
        Ingest verses from a specific book.

        Args:
            book: Book name (e.g., 'Matthew', 'Romans')
            batch_size: Number of verses to process in each batch
            use_normalized: Use normalized text (True) or original (False)

        Returns:
            Summary statistics
        """
        logger.info(f"Starting ingestion for book: {book}")

        verses = self._fetch_verses(book=book)

        if not verses:
            logger.warning(f"No verses found for book: {book}")
            return {"total": 0, "added": 0, "failed": 0}

        mem0_verses = []
        for verse in verses:
            text = verse["greek_normalized"] if use_normalized else verse["greek_text"]

            mem0_verses.append({
                "id": str(verse["id"]),
                "text": text,
                "metadata": {
                    "reference": verse["reference"],
                    "book": verse["book"],
                    "chapter": verse["chapter"],
                    "verse": verse["verse"],
                    "source": verse["source"],
                    "greek_text": verse["greek_text"],
                    "greek_normalized": verse["greek_normalized"],
                    "greek_lemmatized": verse["greek_lemmatized"]
                }
            })

        result = self.mem0_manager.add_verses_batch(
            verses=mem0_verses,
            batch_size=batch_size
        )

        logger.info(f"Completed ingestion for book {book}: {result}")
        return result

    def get_ingestion_stats(self) -> Dict:
        """
        Get statistics about the current state of ingestion.

        Returns:
            Dictionary with statistics
        """
        # Get database stats
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM verses")
        db_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT source) FROM verses")
        source_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT book) FROM verses")
        book_count = cursor.fetchone()[0]

        conn.close()

        # Get Mem0 stats
        mem0_stats = self.mem0_manager.get_stats()

        return {
            "database": {
                "total_verses": db_count,
                "sources": source_count,
                "books": book_count
            },
            "mem0": mem0_stats
        }
