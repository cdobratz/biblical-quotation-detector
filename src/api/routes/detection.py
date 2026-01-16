"""
Detection API routes.

Endpoints for detecting biblical quotations in Greek texts.
"""

import time
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.models import (
    DetectRequest,
    DetectResponse,
    BatchDetectRequest,
    BatchDetectResponse,
    SearchRequest,
    SearchResponse,
    SourceMatch,
    SearchResultItem,
    DetectionMode,
    MatchType,
)
from src.search.detector import QuotationDetector, DetectionResult

logger = logging.getLogger(__name__)

router = APIRouter()

# Lazy initialization of detector
_detector_llm: Optional[QuotationDetector] = None
_detector_heuristic: Optional[QuotationDetector] = None


def get_detector(use_llm: bool = True) -> QuotationDetector:
    """Get or create a detector instance."""
    global _detector_llm, _detector_heuristic

    if use_llm:
        if _detector_llm is None:
            logger.info("Initializing LLM detector...")
            _detector_llm = QuotationDetector(use_llm=True)
        return _detector_llm
    else:
        if _detector_heuristic is None:
            logger.info("Initializing heuristic detector...")
            _detector_heuristic = QuotationDetector(use_llm=False)
        return _detector_heuristic


def result_to_response(result: DetectionResult) -> DetectResponse:
    """Convert DetectionResult to API response."""
    sources = [
        SourceMatch(
            reference=s.reference,
            book=s.book,
            chapter=s.chapter,
            verse=s.verse,
            greek_text=s.greek_text,
            similarity_score=s.similarity_score,
            source_edition=s.source_edition or None,
        )
        for s in result.sources
    ]

    best_match = None
    if result.best_match:
        best_match = SourceMatch(
            reference=result.best_match.reference,
            book=result.best_match.book,
            chapter=result.best_match.chapter,
            verse=result.best_match.verse,
            greek_text=result.best_match.greek_text,
            similarity_score=result.best_match.similarity_score,
            source_edition=result.best_match.source_edition or None,
        )

    return DetectResponse(
        input_text=result.input_text,
        is_quotation=result.is_quotation,
        confidence=result.confidence,
        match_type=MatchType(result.match_type),
        sources=sources,
        best_match=best_match,
        explanation=result.explanation,
        processing_time_ms=result.processing_time_ms,
    )


@router.post(
    "/detect",
    response_model=DetectResponse,
    summary="Detect biblical quotation",
    description="""
    Analyze Greek text to detect if it contains a biblical quotation.

    **Detection Modes:**
    - `llm`: Uses Claude for accurate verification (slower, ~3-5 seconds)
    - `heuristic`: Uses similarity scores only (faster, ~100-200ms)

    **Match Types:**
    - `exact`: Word-for-word or near word-for-word match
    - `close_paraphrase`: Same meaning with minor word changes
    - `loose_paraphrase`: Same core idea, significantly reworded
    - `allusion`: Reference to biblical concepts
    - `non_biblical`: Not a biblical quotation
    """,
    responses={
        200: {"description": "Detection result"},
        400: {"description": "Invalid input"},
        500: {"description": "Server error"},
    },
)
async def detect_quotation(request: DetectRequest):
    """Detect if text is a biblical quotation."""
    try:
        use_llm = request.mode == DetectionMode.llm
        detector = get_detector(use_llm=use_llm)

        result = detector.detect(
            text=request.text,
            min_confidence=request.min_confidence,
            include_all_candidates=request.include_all_candidates,
        )

        return result_to_response(result)

    except Exception as e:
        logger.error(f"Detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/detect/batch",
    response_model=BatchDetectResponse,
    summary="Batch detect biblical quotations",
    description="""
    Analyze multiple Greek texts for biblical quotations.

    **Note:** Heuristic mode is recommended for batch processing to avoid
    API rate limits and reduce processing time.

    Maximum 50 texts per request.
    """,
    responses={
        200: {"description": "Batch detection results"},
        400: {"description": "Invalid input"},
        500: {"description": "Server error"},
    },
)
async def batch_detect_quotations(request: BatchDetectRequest):
    """Detect quotations in multiple texts."""
    try:
        start_time = time.time()
        use_llm = request.mode == DetectionMode.llm
        detector = get_detector(use_llm=use_llm)

        results = []
        quotation_count = 0

        for text in request.texts:
            result = detector.detect(
                text=text,
                min_confidence=request.min_confidence,
            )
            response = result_to_response(result)
            results.append(response)
            if response.is_quotation:
                quotation_count += 1

        total_time = int((time.time() - start_time) * 1000)

        return BatchDetectResponse(
            results=results,
            total_processed=len(request.texts),
            total_quotations=quotation_count,
            total_time_ms=total_time,
        )

    except Exception as e:
        logger.error(f"Batch detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Semantic search",
    description="""
    Search for semantically similar biblical passages.

    Uses vector embeddings to find verses with similar meaning,
    regardless of exact wording.
    """,
    responses={
        200: {"description": "Search results"},
        400: {"description": "Invalid input"},
        500: {"description": "Server error"},
    },
)
async def semantic_search(request: SearchRequest):
    """Search for similar biblical passages."""
    try:
        start_time = time.time()
        detector = get_detector(use_llm=False)

        sources = detector.search_similar(
            text=request.query,
            limit=request.limit,
        )

        # Filter by minimum similarity
        if request.min_similarity > 0:
            sources = [s for s in sources if s.similarity_score >= request.min_similarity]

        results = [
            SearchResultItem(
                reference=s.reference,
                book=s.book,
                chapter=s.chapter,
                verse=s.verse,
                greek_text=s.greek_text,
                similarity_score=s.similarity_score,
                source_edition=s.source_edition or None,
            )
            for s in sources
        ]

        processing_time = int((time.time() - start_time) * 1000)

        return SearchResponse(
            query=request.query,
            results=results,
            total_results=len(results),
            processing_time_ms=processing_time,
        )

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Semantic search (GET)",
    description="Search for similar biblical passages using query parameters.",
    responses={
        200: {"description": "Search results"},
        400: {"description": "Invalid input"},
        500: {"description": "Server error"},
    },
)
async def semantic_search_get(
    query: str = Query(..., description="Greek text to search for", min_length=1),
    limit: int = Query(10, ge=1, le=100, description="Maximum results"),
    min_similarity: float = Query(0.0, ge=0.0, le=1.0, description="Minimum similarity"),
):
    """Search for similar biblical passages (GET version)."""
    request = SearchRequest(query=query, limit=limit, min_similarity=min_similarity)
    return await semantic_search(request)
