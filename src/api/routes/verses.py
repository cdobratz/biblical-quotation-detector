"""
Verses API routes.

Endpoints for looking up biblical verses.
"""

import os
import sqlite3
import logging
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query

from src.api.models import VerseResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Database path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATABASE_PATH = os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "data" / "processed" / "bible.db"))


def get_db_connection():
    """Get a database connection."""
    if not Path(DATABASE_PATH).exists():
        raise HTTPException(status_code=503, detail="Database not available")
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get(
    "/verse/{reference:path}",
    response_model=VerseResponse,
    summary="Get verse by reference",
    description="""
    Retrieve a specific biblical verse by its reference.

    **Reference format:** `Book Chapter:Verse`

    Examples:
    - `Matthew 5:3`
    - `John 3:16`
    - `1 Corinthians 13:4`
    - `Romans 8:28`

    **Note:** References are case-sensitive and should match the format
    used in the database (e.g., "Matthew" not "matthew").
    """,
    responses={
        200: {"description": "Verse found"},
        404: {"description": "Verse not found"},
        503: {"description": "Database unavailable"},
    },
)
async def get_verse(reference: str):
    """Get a verse by its reference."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT reference, book, chapter, verse, greek_text,
                   greek_normalized, greek_lemmatized, english_text, source
            FROM verses
            WHERE reference = ?
            LIMIT 1
            """,
            (reference,),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Verse not found: {reference}"
            )

        return VerseResponse(
            reference=row["reference"],
            book=row["book"],
            chapter=row["chapter"],
            verse=row["verse"],
            greek_text=row["greek_text"],
            greek_normalized=row["greek_normalized"],
            greek_lemmatized=row["greek_lemmatized"],
            english_text=row["english_text"],
            source=row["source"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching verse: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/verses",
    response_model=List[VerseResponse],
    summary="List verses",
    description="""
    List verses with optional filtering by book, chapter, or source.

    Use query parameters to filter results.
    """,
    responses={
        200: {"description": "List of verses"},
        503: {"description": "Database unavailable"},
    },
)
async def list_verses(
    book: Optional[str] = Query(None, description="Filter by book name (e.g., 'Matthew')"),
    chapter: Optional[int] = Query(None, ge=1, description="Filter by chapter number"),
    source: Optional[str] = Query(None, description="Filter by source edition"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Skip first N results"),
):
    """List verses with optional filters."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT reference, book, chapter, verse, greek_text,
                   greek_normalized, greek_lemmatized, english_text, source
            FROM verses
            WHERE 1=1
        """
        params = []

        if book:
            query += " AND book = ?"
            params.append(book)

        if chapter:
            query += " AND chapter = ?"
            params.append(chapter)

        if source:
            query += " AND source = ?"
            params.append(source)

        query += " ORDER BY book, chapter, verse LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            VerseResponse(
                reference=row["reference"],
                book=row["book"],
                chapter=row["chapter"],
                verse=row["verse"],
                greek_text=row["greek_text"],
                greek_normalized=row["greek_normalized"],
                greek_lemmatized=row["greek_lemmatized"],
                english_text=row["english_text"],
                source=row["source"],
            )
            for row in rows
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing verses: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/books",
    summary="List available books",
    description="Get a list of all available biblical books in the database.",
    responses={
        200: {"description": "List of books"},
        503: {"description": "Database unavailable"},
    },
)
async def list_books():
    """List all available books."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT name, testament, book_number, chapters_count, verses_count
            FROM books
            ORDER BY book_number
            """
        )

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "name": row["name"],
                "testament": row["testament"],
                "book_number": row["book_number"],
                "chapters_count": row["chapters_count"],
                "verses_count": row["verses_count"],
            }
            for row in rows
        ]

    except Exception as e:
        logger.error(f"Error listing books: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/sources",
    summary="List available sources",
    description="Get a list of all available text sources/editions.",
    responses={
        200: {"description": "List of sources with verse counts"},
        503: {"description": "Database unavailable"},
    },
)
async def list_sources():
    """List all available text sources."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT source, COUNT(*) as verse_count
            FROM verses
            GROUP BY source
            ORDER BY verse_count DESC
            """
        )

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "source": row["source"],
                "verse_count": row["verse_count"],
            }
            for row in rows
        ]

    except Exception as e:
        logger.error(f"Error listing sources: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/stats",
    summary="Database statistics",
    description="Get statistics about the biblical text database.",
    responses={
        200: {"description": "Database statistics"},
        503: {"description": "Database unavailable"},
    },
)
async def get_stats():
    """Get database statistics."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Total verses
        cursor.execute("SELECT COUNT(*) FROM verses")
        total_verses = cursor.fetchone()[0]

        # Unique verses (by reference)
        cursor.execute("SELECT COUNT(DISTINCT reference) FROM verses")
        unique_references = cursor.fetchone()[0]

        # Sources count
        cursor.execute("SELECT COUNT(DISTINCT source) FROM verses")
        sources_count = cursor.fetchone()[0]

        # Books count
        cursor.execute("SELECT COUNT(DISTINCT book) FROM verses")
        books_count = cursor.fetchone()[0]

        # Verses with lemmatization
        cursor.execute("SELECT COUNT(*) FROM verses WHERE greek_lemmatized IS NOT NULL AND greek_lemmatized != ''")
        lemmatized_count = cursor.fetchone()[0]

        conn.close()

        return {
            "total_verses": total_verses,
            "unique_references": unique_references,
            "sources_count": sources_count,
            "books_count": books_count,
            "lemmatized_verses": lemmatized_count,
            "lemmatization_coverage": round(lemmatized_count / total_verses * 100, 2) if total_verses > 0 else 0,
        }

    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
