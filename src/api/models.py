"""API request and response models."""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class MatchType(str, Enum):
    """Types of biblical text matches."""
    exact = "exact"
    close_paraphrase = "close_paraphrase"
    loose_paraphrase = "loose_paraphrase"
    allusion = "allusion"
    non_biblical = "non_biblical"


class DetectionMode(str, Enum):
    """Detection modes for the API."""
    llm = "llm"
    heuristic = "heuristic"


# Request Models


class DetectRequest(BaseModel):
    """Request body for quotation detection."""
    text: str = Field(
        ...,
        description="Greek text to analyze for biblical quotations",
        min_length=1,
        max_length=5000,
    )
    min_confidence: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Minimum confidence threshold (0-100)",
    )
    mode: DetectionMode = Field(
        default=DetectionMode.llm,
        description="Detection mode: 'llm' for accurate results, 'heuristic' for speed",
    )
    include_all_candidates: bool = Field(
        default=False,
        description="Include all candidate matches in response",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "text": "Μακάριοι οἱ πτωχοὶ τῷ πνεύματι",
                    "min_confidence": 70,
                    "mode": "llm",
                    "include_all_candidates": False,
                }
            ]
        }
    }


class BatchDetectRequest(BaseModel):
    """Request body for batch detection."""
    texts: List[str] = Field(
        ...,
        description="List of Greek texts to analyze",
        min_length=1,
        max_length=50,
    )
    min_confidence: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Minimum confidence threshold (0-100)",
    )
    mode: DetectionMode = Field(
        default=DetectionMode.heuristic,
        description="Detection mode (heuristic recommended for batch)",
    )


class SearchRequest(BaseModel):
    """Request body for semantic search."""
    query: str = Field(
        ...,
        description="Greek text to search for",
        min_length=1,
        max_length=2000,
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results",
    )
    min_similarity: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score (0.0 to 1.0)",
    )


# Response Models


class SourceMatch(BaseModel):
    """A biblical source that matches the input."""
    reference: str = Field(..., description="Biblical reference (e.g., 'Matthew 5:3')")
    book: str = Field(..., description="Book name")
    chapter: int = Field(..., description="Chapter number")
    verse: int = Field(..., description="Verse number")
    greek_text: str = Field(..., description="Greek text of the verse")
    similarity_score: float = Field(..., description="Semantic similarity score (0-1)")
    source_edition: Optional[str] = Field(None, description="Source edition")


class DetectResponse(BaseModel):
    """Response from quotation detection."""
    input_text: str = Field(..., description="Original input text")
    is_quotation: bool = Field(..., description="Whether text is a biblical quotation")
    confidence: int = Field(..., ge=0, le=100, description="Confidence score (0-100)")
    match_type: MatchType = Field(..., description="Type of match found")
    sources: List[SourceMatch] = Field(default=[], description="Matching biblical sources")
    best_match: Optional[SourceMatch] = Field(None, description="Best matching source")
    explanation: str = Field(..., description="Explanation of the classification")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")


class BatchDetectResponse(BaseModel):
    """Response from batch detection."""
    results: List[DetectResponse] = Field(..., description="Detection results for each text")
    total_processed: int = Field(..., description="Total texts processed")
    total_quotations: int = Field(..., description="Number of quotations detected")
    total_time_ms: int = Field(..., description="Total processing time in milliseconds")


class VerseResponse(BaseModel):
    """Response for verse lookup."""
    reference: str = Field(..., description="Biblical reference")
    book: str = Field(..., description="Book name")
    chapter: int = Field(..., description="Chapter number")
    verse: int = Field(..., description="Verse number")
    greek_text: str = Field(..., description="Original Greek text with diacritics")
    greek_normalized: Optional[str] = Field(None, description="Normalized Greek text")
    greek_lemmatized: Optional[str] = Field(None, description="Lemmatized Greek text")
    english_text: Optional[str] = Field(None, description="English translation")
    source: str = Field(..., description="Source edition")


class SearchResultItem(BaseModel):
    """Single search result item."""
    reference: str
    book: str
    chapter: int
    verse: int
    greek_text: str
    similarity_score: float
    source_edition: Optional[str] = None


class SearchResponse(BaseModel):
    """Response for semantic search."""
    query: str = Field(..., description="Original query text")
    results: List[SearchResultItem] = Field(..., description="Search results")
    total_results: int = Field(..., description="Number of results returned")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    database_connected: bool = Field(..., description="Database connection status")
    vector_store_connected: bool = Field(..., description="Vector store connection status")


class ErrorResponse(BaseModel):
    """Error response."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional details")
