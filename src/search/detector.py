"""
Biblical Quotation Detector

Multi-stage detection pipeline for identifying biblical quotations in Greek texts.

Pipeline:
1. Vector semantic search (Qdrant) - Find candidate matches
2. Multi-signal heuristic scoring - Combine similarity, word overlap,
   lemma overlap, n-gram overlap, and quotation formula signals
3. Selective LLM verification (Claude) - Verify borderline cases only
4. Confidence scoring - Weighted combination of all signals
"""

import json
import logging
import re
import time
import sqlite3
import unicodedata
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Quotation formula patterns (Quick Win 3)
# Church Fathers typically introduce biblical quotations with stock phrases.
# ---------------------------------------------------------------------------
# Patterns use only base Greek characters (no diacritics/breathing marks)
# because _detect_quotation_formula strips combining marks before matching.
_QUOTATION_FORMULAS: List[re.Pattern] = [
    re.compile(r"γεγραπται", re.IGNORECASE),  # "it is written"
    re.compile(r"λεγει\s+(?:ο\s+)?κυριος", re.IGNORECASE),  # "the Lord says"
    re.compile(r"λεγει\s+(?:η\s+)?γραφη", re.IGNORECASE),  # "the Scripture says"
    re.compile(r"φησιν", re.IGNORECASE),  # "he/she says"
    re.compile(
        r"κατα\s+το\s+γεγραμμενον", re.IGNORECASE
    ),  # "according to what is written"
    re.compile(r"ως\s+ειπεν", re.IGNORECASE),  # "as he said"
    re.compile(r"ο\s+προφητης\s+λεγει", re.IGNORECASE),  # "the prophet says"
    re.compile(r"ειπεν\s+(?:ο\s+)?θεος", re.IGNORECASE),  # "God said"
    re.compile(r"λεγων", re.IGNORECASE),  # "saying" (introducing quotation)
    re.compile(r"ουτως\s+λεγει", re.IGNORECASE),  # "thus says"
    re.compile(r"μαρτυρει", re.IGNORECASE),  # "he testifies"
]


def _normalize_greek(text: str) -> str:
    """
    Normalize Greek text by stripping diacritics, punctuation, and lowercasing.

    Uses NFKD normalization to decompose characters, then removes
    combining marks (diacritics), strips punctuation, normalizes
    final sigma (ς → σ), and lowercases the result.
    """
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    lowered = stripped.lower()
    # Strip punctuation (keep only letters, digits, whitespace)
    lowered = re.sub(r"[^\w\s]", "", lowered, flags=re.UNICODE)
    # Normalize final sigma: ς → σ for consistent matching
    lowered = lowered.replace("ς", "σ")
    return lowered


def _count_shared_words(text_a: str, text_b: str) -> int:
    """
    Count meaningful shared words between two Greek texts.

    Normalizes both texts (strip diacritics, lowercase), splits into word
    sets, filters out words with ≤2 characters (articles, particles like
    ο, η, εν, τα), and returns the count of shared content words.

    Args:
        text_a: First text (e.g., input chunk)
        text_b: Second text (e.g., matched biblical verse)

    Returns:
        Number of shared content words (length > 2 characters)
    """
    words_a = set(_normalize_greek(text_a).split())
    words_b = set(_normalize_greek(text_b).split())
    # Only count words with >2 characters (skip articles/particles)
    shared = words_a & words_b
    meaningful = {w for w in shared if len(w) > 2}
    return len(meaningful)


def _count_shared_lemmas(text_a: str, text_b: str) -> int:
    """
    Count shared words using a simple stem-based approach.

    Greek morphology means the same word appears in many inflected forms
    (e.g., θεός, θεοῦ, θεῷ, θεόν all mean 'God'). This function uses a
    lightweight stemming heuristic (truncate to first 4+ characters) to
    catch morphological variants without requiring a full lemmatizer.

    Args:
        text_a: First text
        text_b: Second text

    Returns:
        Number of shared stem groups (words > 3 characters, stems > 3 chars)
    """
    words_a = set(_normalize_greek(text_a).split())
    words_b = set(_normalize_greek(text_b).split())
    # Only consider words long enough to stem meaningfully
    content_a = {w for w in words_a if len(w) > 3}
    content_b = {w for w in words_b if len(w) > 3}

    # Simple Greek stemming: truncate to first 4 characters as a rough stem.
    # This catches inflectional variants like θεος/θεου/θεω → θεοσ/θεου/θεω
    # For longer words, use min(len, 5) to be slightly more discriminating.
    def stem(word: str) -> str:
        cutoff = min(len(word), max(4, len(word) - 2))
        return word[:cutoff]

    stems_a = {stem(w) for w in content_a}
    stems_b = {stem(w) for w in content_b}
    return len(stems_a & stems_b)


def _count_shared_ngrams(text_a: str, text_b: str, n: int = 2) -> int:
    """
    Count shared character n-grams between two texts.

    N-grams capture word-order similarity that bag-of-words approaches miss.

    Args:
        text_a: First text
        text_b: Second text
        n: N-gram size (default: bigrams)

    Returns:
        Number of shared n-grams
    """
    norm_a = _normalize_greek(text_a)
    norm_b = _normalize_greek(text_b)
    words_a = norm_a.split()
    words_b = norm_b.split()

    if len(words_a) < n or len(words_b) < n:
        return 0

    ngrams_a = set()
    for i in range(len(words_a) - n + 1):
        ngrams_a.add(tuple(words_a[i : i + n]))

    ngrams_b = set()
    for i in range(len(words_b) - n + 1):
        ngrams_b.add(tuple(words_b[i : i + n]))

    return len(ngrams_a & ngrams_b)


def _detect_quotation_formula(text: str) -> bool:
    """
    Check if text contains a quotation introductory formula.

    Church Fathers use stock phrases like 'γέγραπται' (it is written) or
    'λέγει κύριος' (the Lord says) to introduce biblical quotations.

    The input is NFKD-decomposed before matching so that precomposed
    characters (e.g. ὕ U+1F55) are broken into base letter + combining
    marks, allowing the regex character classes to match correctly.

    Args:
        text: Greek text to scan

    Returns:
        True if a quotation formula is detected
    """
    # Decompose precomposed Unicode and strip combining marks (diacritics)
    # so that regex character classes match base letters regardless of
    # accent/breathing marks in the source text.
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    for pattern in _QUOTATION_FORMULAS:
        if pattern.search(stripped):
            return True
    return False


def _compute_multi_signal_score(
    similarity_score: float,
    shared_words: int,
    shared_lemmas: int,
    shared_ngrams: int,
    has_formula: bool,
    input_word_count: int,
) -> float:
    """
    Compute a weighted multi-signal confidence score.

    Combines multiple independent signals into a single 0-100 confidence
    score using fixed weights. Each signal is normalized to a 0-1 range
    before weighting.

    Signal weights:
        - Vector similarity:   0.25  (from Qdrant search)
        - Word overlap ratio:  0.25  (shared / max possible)
        - Lemma overlap ratio: 0.20  (stem-based matching)
        - N-gram overlap:      0.15  (word-order similarity)
        - Quotation formula:   0.15  (introductory marker present)

    Args:
        similarity_score: Cosine similarity from vector search (0-1)
        shared_words: Count of shared content words
        shared_lemmas: Count of shared word stems
        shared_ngrams: Count of shared bigrams
        has_formula: Whether a quotation formula was detected
        input_word_count: Number of words in input text

    Returns:
        Weighted confidence score (0-100)
    """
    # Normalize each signal to 0-1 range
    # Similarity: rescale from typical range [0.80, 1.0] to [0, 1]
    sim_norm = max(0.0, min(1.0, (similarity_score - 0.80) / 0.20))

    # Word overlap: cap at 8 shared words for normalization
    word_norm = min(1.0, shared_words / 8.0)

    # Lemma overlap: cap at 10 for normalization
    lemma_norm = min(1.0, shared_lemmas / 10.0)

    # N-gram overlap: cap at 5 shared bigrams
    ngram_norm = min(1.0, shared_ngrams / 5.0)

    # Formula: binary signal
    formula_norm = 1.0 if has_formula else 0.0

    # Weighted combination
    raw_score = (
        0.25 * sim_norm
        + 0.25 * word_norm
        + 0.20 * lemma_norm
        + 0.15 * ngram_norm
        + 0.15 * formula_norm
    )

    return round(raw_score * 100)


def _load_cross_references() -> Dict[str, Set[str]]:
    """Load cross-reference chains from the parallel passage table.

    Returns a mapping from each verse reference to the set of all
    parallel references in its group (including itself). This allows
    the detector and evaluator to recognize that e.g. Genesis 15:6
    and Romans 4:3 are parallel passages quoting the same text.
    """
    cross_ref_path = Path(__file__).parent.parent.parent / "data" / "cross_references.json"
    ref_map: Dict[str, Set[str]] = {}

    if not cross_ref_path.exists():
        logger.debug("No cross_references.json found; skipping cross-ref loading")
        return ref_map

    try:
        with open(cross_ref_path, encoding="utf-8") as f:
            data = json.load(f)

        for group in data.get("parallel_passages", []):
            refs = set(group.get("refs", []))
            for ref in refs:
                if ref not in ref_map:
                    ref_map[ref] = set()
                ref_map[ref].update(refs)

        logger.info(f"Loaded cross-references: {len(ref_map)} entries across "
                     f"{len(data.get('parallel_passages', []))} groups")
    except Exception as e:
        logger.warning(f"Failed to load cross-references: {e}")

    return ref_map


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
            "best_match": (
                {
                    "reference": self.best_match.reference,
                    "greek_text": self.best_match.greek_text,
                    "similarity_score": self.best_match.similarity_score,
                }
                if self.best_match
                else None
            ),
            "explanation": self.explanation,
            "processing_time_ms": self.processing_time_ms,
        }


class QuotationDetector:
    """
    Multi-stage biblical quotation detector.

    Combines vector search and LLM verification for accurate detection.
    """

    # Selective LLM thresholds: chunks scoring between these bounds
    # are sent to Claude for verification; others are decided by heuristic.
    SELECTIVE_LLM_HIGH = 65  # multi-signal score >= this → accept without LLM
    SELECTIVE_LLM_LOW = 20  # multi-signal score < this → reject without LLM

    def __init__(
        self,
        use_llm: bool = True,
        db_path: Optional[str] = None,
        min_similarity: float = 0.7,
        top_k: int = 20,
        selective_llm: bool = False,
        multi_candidate_n: int = 5,
    ):
        """
        Initialize the detector.

        Args:
            use_llm: Whether to use Claude for verification (slower but more accurate)
            db_path: Path to SQLite database for FTS fallback
            min_similarity: Minimum similarity threshold for candidates
            top_k: Number of candidates to retrieve from vector search
            selective_llm: When True and use_llm is True, only send borderline
                          cases to the LLM. High-confidence and low-confidence
                          cases are decided by the heuristic alone, saving
                          ~60-70% of API calls.
            multi_candidate_n: Number of candidates to score in multi-candidate
                              mode (default: 5). Instead of only scoring against
                              the #1 match, the best score across the top N
                              candidates is used.
        """
        self.use_llm = use_llm
        self.selective_llm = selective_llm
        self.min_similarity = min_similarity
        self.top_k = top_k
        self.multi_candidate_n = multi_candidate_n

        # Set database path
        if db_path is None:
            project_root = Path(__file__).parent.parent.parent
            self.db_path = str(project_root / "data" / "processed" / "bible.db")
        else:
            self.db_path = db_path

        # Load cross-reference chains for parallel passage matching
        self._cross_refs = _load_cross_references()

        # Initialize components lazily
        self._qdrant_manager = None
        self._claude_client = None

        logger.info(
            f"QuotationDetector initialized (use_llm={use_llm}, "
            f"selective_llm={selective_llm}, "
            f"min_similarity={min_similarity}, top_k={top_k}, "
            f"multi_candidate_n={multi_candidate_n})"
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
        context_before: str = "",
        context_after: str = "",
    ) -> DetectionResult:
        """
        Detect if text is a biblical quotation.

        Args:
            text: Greek text to analyze
            min_confidence: Minimum confidence threshold (0-100)
            include_all_candidates: Include all candidates in results
            context_before: Text of the preceding chunk (for context-aware scoring)
            context_after: Text of the following chunk (for context-aware scoring)

        Returns:
            DetectionResult with classification and sources
        """
        start_time = time.time()

        logger.info(f"Detecting quotation for: {text[:50]}...")

        # Context-aware scoring: check adjacent chunks for quotation formulas
        context_has_formula = False
        if context_before:
            context_has_formula = _detect_quotation_formula(context_before)
        if not context_has_formula and context_after:
            context_has_formula = _detect_quotation_formula(context_after)

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

        # Stage 2: Classification
        if self.use_llm and self.selective_llm:
            # Selective LLM: heuristic first, only send borderline to Claude
            result = self._selective_llm_classify(
                text, candidates, sources, context_has_formula
            )
        elif self.use_llm:
            # Full LLM: send everything to Claude
            result = self._llm_verify(text, candidates, sources)
        else:
            # Pure heuristic: no LLM at all
            result = self._heuristic_classify(
                text, candidates, sources, context_has_formula
            )

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
        """Perform vector semantic search with FTS fallback.

        Runs Qdrant vector search first, then supplements with SQLite FTS5
        keyword search to catch cases where exact words match but embedding
        similarity is low. Results are merged and deduplicated by reference.
        """
        results = []
        try:
            results = self.qdrant_manager.search(
                query=text,
                limit=self.top_k,
                score_threshold=self.min_similarity,
            )
            logger.debug(f"Vector search returned {len(results)} candidates")
        except Exception as e:
            logger.error(f"Vector search failed: {e}")

        # FTS fallback: supplement with keyword matches
        fts_results = self._fts_search(text, limit=10)
        if fts_results:
            # Deduplicate: skip FTS results whose reference is already in vector results
            seen_refs = {r.get("reference") for r in results}
            for fts_r in fts_results:
                if fts_r.get("reference") not in seen_refs:
                    results.append(fts_r)
                    seen_refs.add(fts_r.get("reference"))
            logger.debug(
                f"After FTS merge: {len(results)} total candidates"
            )

        return results[:self.top_k]

    def _fts_search(self, text: str, limit: int = 10) -> List[Dict]:
        """Search SQLite FTS5 index for keyword matches.

        Extracts content words from input text and runs an OR query against
        the verses_fts table. Returns results formatted like Qdrant output.
        """
        try:
            # Extract content words (>2 chars, normalized)
            normalized = _normalize_greek(text)
            words = [w for w in normalized.split() if len(w) > 2]
            if not words:
                return []

            # Build FTS5 MATCH query with OR
            # Limit to 5 terms to keep query fast
            match_terms = " OR ".join(words[:5])

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT v.reference, v.greek_text, v.book, v.chapter, v.verse, v.source
                FROM verses_fts AS fts
                JOIN verses AS v ON v.rowid = fts.rowid
                WHERE fts.greek_normalized MATCH ?
                LIMIT ?
                """,
                (match_terms, limit),
            )
            rows = cursor.fetchall()
            conn.close()

            results = []
            for row in rows:
                results.append({
                    "reference": row[0],
                    "text": row[1],
                    "book": row[2],
                    "chapter": row[3],
                    "verse": row[4],
                    "source": row[5],
                    "score": 0.80,  # synthetic score for FTS results
                })
            logger.debug(f"FTS search returned {len(results)} results")
            return results
        except Exception as e:
            logger.debug(f"FTS search failed: {e}")
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
        context_has_formula: bool = False,
    ) -> DetectionResult:
        """
        Multi-signal heuristic classification without LLM.

        Combines five independent signals into a weighted confidence score:
        1. Vector similarity score (from Qdrant)
        2. Surface-form word overlap
        3. Lemma/stem-based word overlap
        4. N-gram (bigram) overlap
        5. Quotation formula detection

        Multi-candidate scoring: Instead of only scoring against the #1 match,
        scores against the top N candidates and uses the best result.

        Context-aware scoring: If adjacent chunks contain quotation formulas,
        the formula signal is boosted even when the current chunk lacks one.
        """
        if not candidates:
            return DetectionResult(
                input_text=text,
                is_quotation=False,
                confidence=90,
                match_type="non_biblical",
                explanation="No candidates found.",
            )

        input_word_count = len(text.split())

        # Gate: reject short chunks as unreliable (Option D)
        if input_word_count < 4:
            top_score = candidates[0]["score"]
            best_match = sources[0] if sources else None
            best_match_text = candidates[0].get("text", "")
            shared_words = _count_shared_words(text, best_match_text)
            return DetectionResult(
                input_text=text,
                is_quotation=False,
                confidence=60,
                match_type="non_biblical",
                sources=sources[:3],
                best_match=best_match,
                explanation=(
                    f"Heuristic: score={top_score:.3f}, shared_words={shared_words}, "
                    f"input_words={input_word_count} (<4, too short). "
                    f"Top match: {best_match.reference if best_match else 'none'}."
                ),
            )

        # Multi-candidate scoring: score against top N candidates, keep best
        best_ms_confidence = -1
        best_candidate_idx = 0
        best_signals: Dict = {}
        n_to_score = min(self.multi_candidate_n, len(candidates))

        for idx in range(n_to_score):
            candidate_text = candidates[idx].get("text", "")
            candidate_score = candidates[idx]["score"]

            shared_words = _count_shared_words(text, candidate_text)
            shared_lemmas = _count_shared_lemmas(text, candidate_text)
            shared_ngrams = _count_shared_ngrams(text, candidate_text, n=2)
            has_formula = _detect_quotation_formula(text)

            # Context-aware: boost formula signal if adjacent chunk has formula
            effective_formula = has_formula or context_has_formula

            ms_confidence = _compute_multi_signal_score(
                similarity_score=candidate_score,
                shared_words=shared_words,
                shared_lemmas=shared_lemmas,
                shared_ngrams=shared_ngrams,
                has_formula=effective_formula,
                input_word_count=input_word_count,
            )

            if ms_confidence > best_ms_confidence:
                best_ms_confidence = ms_confidence
                best_candidate_idx = idx
                best_signals = {
                    "score": candidate_score,
                    "shared_words": shared_words,
                    "shared_lemmas": shared_lemmas,
                    "shared_ngrams": shared_ngrams,
                    "has_formula": has_formula,
                    "context_formula": context_has_formula,
                    "effective_formula": effective_formula,
                }

        # Use best candidate's signals for classification
        ms_confidence = best_ms_confidence
        best_match = sources[best_candidate_idx] if best_candidate_idx < len(sources) else sources[0]
        shared_words = best_signals.get("shared_words", 0)
        shared_lemmas = best_signals.get("shared_lemmas", 0)

        # Classify based on multi-signal confidence + word overlap gate
        if ms_confidence >= 70 and shared_words >= 5:
            match_type = "exact"
            is_quotation = True
        elif ms_confidence >= 50 and shared_words >= 3:
            match_type = "close_paraphrase"
            is_quotation = True
        elif ms_confidence >= 35 and shared_words >= 2:
            match_type = "loose_paraphrase"
            is_quotation = True
        elif ms_confidence >= 20 and (shared_words >= 1 or shared_lemmas >= 2):
            match_type = "allusion"
            is_quotation = True
        else:
            match_type = "non_biblical"
            is_quotation = False

        # Build detailed explanation
        formula_note = ""
        if best_signals.get("has_formula"):
            formula_note = ", formula=yes"
        elif best_signals.get("context_formula"):
            formula_note = ", context_formula=yes"
        candidate_note = ""
        if best_candidate_idx > 0:
            candidate_note = f", best_candidate=#{best_candidate_idx + 1}"
        explanation = (
            f"Heuristic: score={best_signals.get('score', 0):.3f}, "
            f"shared_words={shared_words}, "
            f"shared_lemmas={shared_lemmas}, "
            f"shared_ngrams={best_signals.get('shared_ngrams', 0)}, "
            f"multi_signal={ms_confidence}{formula_note}{candidate_note}. "
            f"Top match: {best_match.reference if best_match else 'none'}."
        )

        return DetectionResult(
            input_text=text,
            is_quotation=is_quotation,
            confidence=ms_confidence,
            match_type=match_type,
            sources=sources[:3],
            best_match=best_match,
            explanation=explanation,
        )

    def _selective_llm_classify(
        self,
        text: str,
        candidates: List[Dict],
        sources: List[DetectionSource],
        context_has_formula: bool = False,
    ) -> DetectionResult:
        """
        Selective LLM classification: only send borderline cases to Claude.

        Strategy:
        - High-confidence heuristic (multi_signal >= SELECTIVE_LLM_HIGH):
          Accept without LLM.
        - Low-confidence heuristic (multi_signal < SELECTIVE_LLM_LOW):
          Reject without LLM.
        - Borderline (between the two thresholds): Send to Claude for
          verification.

        This reduces LLM API calls by ~60-70% while maintaining accuracy
        on the cases that actually matter.
        """
        # First, run heuristic classification
        heuristic_result = self._heuristic_classify(
            text, candidates, sources, context_has_formula
        )

        ms_confidence = heuristic_result.confidence

        # High confidence → accept heuristic result
        if ms_confidence >= self.SELECTIVE_LLM_HIGH:
            heuristic_result.explanation += " [selective: accepted by heuristic]"
            return heuristic_result

        # Low confidence → reject without LLM
        if ms_confidence < self.SELECTIVE_LLM_LOW:
            heuristic_result.explanation += " [selective: rejected by heuristic]"
            return heuristic_result

        # Borderline → send to LLM
        logger.info(
            f"Selective LLM: borderline case (ms={ms_confidence}), "
            f"sending to Claude for verification"
        )
        llm_result = self._llm_verify(text, candidates, sources)
        llm_result.explanation += (
            f" [selective: LLM verified, heuristic_ms={ms_confidence}]"
        )
        return llm_result

    def detect_batch(
        self,
        texts: List[str],
        min_confidence: int = 50,
    ) -> List[DetectionResult]:
        """
        Detect quotations in multiple texts with context-aware scoring.

        Each chunk is scored with its preceding and following chunks as
        context, enabling detection of quotation formulas that appear
        in adjacent chunks.

        Args:
            texts: List of Greek texts to analyze
            min_confidence: Minimum confidence threshold

        Returns:
            List of DetectionResults
        """
        results = []
        for i, text in enumerate(texts):
            context_before = texts[i - 1] if i > 0 else ""
            context_after = texts[i + 1] if i < len(texts) - 1 else ""
            result = self.detect(
                text,
                min_confidence,
                context_before=context_before,
                context_after=context_after,
            )
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
                "SELECT * FROM verses WHERE reference = ? LIMIT 1", (reference,)
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None

        except Exception as e:
            logger.error(f"Failed to get verse: {e}")
            return None
