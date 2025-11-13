# src/models.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class BiblicalVerse(BaseModel):
    """Model for a single biblical verse"""
    reference: str  # "Matthew 5:3"
    book: str
    chapter: int
    verse: int
    greek_text: str
    greek_normalized: str  # lowercase, no diacritics
    greek_lemmatized: str  # lemmatized forms
    english_text: Optional[str] = None
    source: str  # SR, SBLGNT, etc.
    
class QuotationMatch(BaseModel):
    """Model for a detected quotation"""
    input_text: str
    is_quotation: bool
    confidence: float  # 0-100
    match_type: str  # exact, paraphrase, allusion, none
    sources: List[dict]
    explanation: str
    processed_at: datetime = datetime.now()

class BiblicalContext(BaseModel):
    """Extended context for better matching"""
    reference: str
    verse_text: str
    previous_verse: Optional[str] = None
    next_verse: Optional[str] = None
    chapter_theme: Optional[str] = None