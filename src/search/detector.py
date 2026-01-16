"""
Biblical Quotation Detector

Multi-stage detection pipeline for identifying biblical quotations in Greek texts.

Pipeline:
1. Vector semantic search (Qdrant) - Find candidate matches
2. LLM verification (Claude) - Classify and score matches
3. Confidence scoring - Combine signals for final score
"""

import logging
import time
import sqlite3
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class DetectionSource:
    """A potential biblical source match."""
    reference: str
    book: str
    chapter: int
    verse: int
    greek_text: str
    greek_original: Optional[str] = None
    similarity_score: float = 0.0
    source_edition: str = ""


@dataclass
class DetectionResult:
    """Result of quotation detection."""
    input_text: str
    is_quotation: bool
    confidence: int  # 0-100
    match_type: str  # exact, close_paraphrase, loose_paraphrase, allusion, non_biblical
    sources: List[DetectionSource] = field(default_factory=list)
    best_match: Optional[DetectionSource] = None
    explanation: str = ""
    processing_time_ms: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "input_text": self.input_text,
            "is_quotation": self.is_quotation,
            "confidence": self.confidence,
            "match_type": self.match_type,
            "sources": [
                {
                    "reference": s.reference,
                    "book": s.book,
                    "chapter": s.chapter,
                    "verse": s.verse,
                    "greek_text": s.greek_text,
                    "similarity_score": s.similarity_score,
                    "source_edition": s.source_edition,
                }
                for s in self.sources
            ],
            "best_match": {
                "reference": self.best_match.reference,
                "greek_text": self.best_match.greek_text,
                "similarity_score": self.best_match.similarity_score,
            } if self.best_match else None,
            "explanation": self.explanation,
            "processing_time_ms": self.processing_time_ms,
        }


class QuotationDetector:
    """
    Multi-stage biblical quotation detector.

    Combines vector search and LLM verification for accurate detection.
    """

    def __init__(
        self,
        use_llm: bool = True,
        db_path: Optional[str] = None,
        min_similarity: float = 0.7,
        top_k: int = 10,
    ):
        """
        Initialize the detector.

        Args:
            use_llm: Whether to use Claude for verification (slower but more accurate)
            db_path: Path to SQLite database for FTS fallback
            min_similarity: Minimum similarity threshold for candidates
            top_k: Number of candidates to retrieve from vector search
        """
        self.use_llm = use_llm
        self.min_similarity = min_similarity
        self.top_k = top_k

        # Set database path
        if db_path is None:
            project_root = Path(__file__).parent.parent.parent
            self.db_path = str(project_root / "data" / "processed" / "bible.db")
        else:
            self.db_path = db_path

        # Initialize components lazily
        self._qdrant_manager = None
        self._claude_client = None

        logger.info(
            f"QuotationDetector initialized (use_llm={use_llm}, "
            f"min_similarity={min_similarity}, top_k={top_k})"
        )

    @property
    def qdrant_manager(self):
        """Lazy initialization of Qdrant manager."""
        if self._qdrant_manager is None:
            from src.memory.qdrant_manager import QdrantManager
            self._qdrant_manager = QdrantManager()
        return self._qdrant_manager

    @property
    def claude_client(self):
        """Lazy initialization of Claude client."""
        if self._claude_client is None and self.use_llm:
            from src.llm.claude_client import ClaudeClient
            self._claude_client = ClaudeClient()
        return self._claude_client

    def detect(
        self,
        text: str,
        min_confidence: int = 50,
        include_all_candidates: bool = False,
    ) -> DetectionResult:
        """
        Detect if text is a biblical quotation.

        Args:
            text: Greek text to analyze
            min_confidence: Minimum confidence threshold (0-100)
            include_all_candidates: Include all candidates in results

        Returns:
            DetectionResult with classification and sources
        """
        start_time = time.time()

        logger.info(f"Detecting quotation for: {text[:50]}...")

        # Stage 1: Vector semantic search
        candidates = self._vector_search(text)

        if not candidates:
            return DetectionResult(
                input_text=text,
                is_quotation=False,
                confidence=90,
                match_type="non_biblical",
                explanation="No similar biblical texts found in vector search.",
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

        # Convert to DetectionSource objects
        sources = [
            DetectionSource(
                reference=c["reference"],
                book=c["book"],
                chapter=c["chapter"],
                verse=c["verse"],
                greek_text=c["text"],
                greek_original=c.get("greek_original"),
                similarity_score=c["score"],
                source_edition=c.get("source", ""),
            )
            for c in candidates
        ]

        # Stage 2: LLM verification (if enabled)
        if self.use_llm:
            result = self._llm_verify(text, candidates, sources)
        else:
            # Simple heuristic without LLM
            result = self._heuristic_classify(text, candidates, sources)

        # Filter by confidence
        if result.confidence < min_confidence:
            result.is_quotation = False

        # Include all candidates or just top matches
        if include_all_candidates:
            result.sources = sources
        else:
            result.sources = sources[:3]  # Top 3

        result.processing_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"Detection complete: {result.match_type} "
            f"(confidence: {result.confidence}%, time: {result.processing_time_ms}ms)"
        )

        return result

    def _vector_search(self, text: str) -> List[Dict]:
        """Perform vector semantic search."""
        try:
            results = self.qdrant_manager.search(
                query=text,
                limit=self.top_k,
                score_threshold=self.min_similarity,
            )
            logger.debug(f"Vector search returned {len(results)} candidates")
            return results
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def _llm_verify(
        self,
        text: str,
        candidates: List[Dict],
        sources: List[DetectionSource],
    ) -> DetectionResult:
        """Use Claude LLM for verification."""
        try:
            verification = self.claude_client.verify_quotation(
                input_text=text,
                candidates=candidates,
            )

            # Find best match
            best_match = None
            if verification.best_match_reference:
                for source in sources:
                    if source.reference == verification.best_match_reference:
                        best_match = source
                        break

            # If no best match found but is quotation, use highest similarity
            if best_match is None and verification.is_quotation and sources:
                best_match = sources[0]

            return DetectionResult(
                input_text=text,
                is_quotation=verification.is_quotation,
                confidence=verification.confidence,
                match_type=verification.match_type.value,
                sources=sources[:3],
                best_match=best_match,
                explanation=verification.explanation,
            )

        except Exception as e:
            logger.error(f"LLM verification failed: {e}")
            # Fall back to heuristic
            return self._heuristic_classify(text, candidates, sources)

    def _heuristic_classify(
        self,
        text: str,
        candidates: List[Dict],
        sources: List[DetectionSource],
    ) -> DetectionResult:
        """
        Simple heuristic classification without LLM.

        Uses similarity scores to estimate match type.
        """
        if not candidates:
            return DetectionResult(
                input_text=text,
                is_quotation=False,
                confidence=90,
                match_type="non_biblical",
                explanation="No candidates found.",
            )

        top_score = candidates[0]["score"]
        best_match = sources[0] if sources else None

        # Classify based on similarity score
        if top_score >= 0.95:
            match_type = "exact"
            confidence = 95
            is_quotation = True
        elif top_score >= 0.85:
            match_type = "close_paraphrase"
            confidence = 85
            is_quotation = True
        elif top_score >= 0.75:
            match_type = "loose_paraphrase"
            confidence = 70
            is_quotation = True
        elif top_score >= 0.65:
            match_type = "allusion"
            confidence = 55
            is_quotation = True
        else:
            match_type = "non_biblical"
            confidence = 60
            is_quotation = False

        explanation = (
            f"Heuristic classification based on similarity score ({top_score:.3f}). "
            f"Top match: {best_match.reference if best_match else 'none'}."
        )

        return DetectionResult(
            input_text=text,
            is_quotation=is_quotation,
            confidence=confidence,
            match_type=match_type,
            sources=sources[:3],
            best_match=best_match,
            explanation=explanation,
        )

    def detect_batch(
        self,
        texts: List[str],
        min_confidence: int = 50,
    ) -> List[DetectionResult]:
        """
        Detect quotations in multiple texts.

        Args:
            texts: List of Greek texts to analyze
            min_confidence: Minimum confidence threshold

        Returns:
            List of DetectionResults
        """
        results = []
        for text in texts:
            result = self.detect(text, min_confidence)
            results.append(result)
        return results

    def search_similar(
        self,
        text: str,
        limit: int = 10,
    ) -> List[DetectionSource]:
        """
        Search for similar biblical texts without full detection.

        Useful for exploring the database or getting raw search results.

        Args:
            text: Greek text to search for
            limit: Maximum results

        Returns:
            List of similar biblical sources
        """
        candidates = self.qdrant_manager.search(
            query=text,
            limit=limit,
            score_threshold=0.0,  # Return all
        )

        return [
            DetectionSource(
                reference=c["reference"],
                book=c["book"],
                chapter=c["chapter"],
                verse=c["verse"],
                greek_text=c["text"],
                similarity_score=c["score"],
                source_edition=c.get("source", ""),
            )
            for c in candidates
        ]

    def get_verse(self, reference: str) -> Optional[Dict]:
        """
        Get a specific verse from the database.

        Args:
            reference: Biblical reference (e.g., "Matthew 5:3")

        Returns:
            Verse data or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM verses WHERE reference = ? LIMIT 1",
                (reference,)
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None

        except Exception as e:
            logger.error(f"Failed to get verse: {e}")
            return None
