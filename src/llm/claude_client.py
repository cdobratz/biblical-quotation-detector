"""
Claude LLM Client for Biblical Quotation Verification

This module provides Claude API integration for intelligent verification
of potential biblical quotations, including match classification and
confidence scoring.
"""

import os
import logging
from typing import List, Dict, Optional
from enum import Enum
from dataclasses import dataclass

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class MatchType(str, Enum):
    """Classification of quotation match types."""
    EXACT = "exact"
    CLOSE_PARAPHRASE = "close_paraphrase"
    LOOSE_PARAPHRASE = "loose_paraphrase"
    ALLUSION = "allusion"
    NON_BIBLICAL = "non_biblical"
    UNCERTAIN = "uncertain"


@dataclass
class VerificationResult:
    """Result of LLM verification."""
    is_quotation: bool
    match_type: MatchType
    confidence: int  # 0-100
    explanation: str
    best_match_reference: Optional[str] = None
    best_match_text: Optional[str] = None


class ClaudeClient:
    """
    Claude API client for biblical quotation verification.

    Uses Claude to analyze candidate matches from vector search and determine:
    - Whether the input is actually a biblical quotation
    - The type of match (exact, paraphrase, allusion, etc.)
    - Confidence level
    - Explanation of the match
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ):
        """
        Initialize Claude client.

        Args:
            model: Claude model to use
            max_tokens: Maximum response tokens
            temperature: Sampling temperature (low for consistency)
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key or self.api_key == "your_key_here":
            raise ValueError("ANTHROPIC_API_KEY not set in environment")

        self.client = Anthropic(api_key=self.api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        logger.info(f"ClaudeClient initialized with model: {self.model}")

    def verify_quotation(
        self,
        input_text: str,
        candidates: List[Dict],
        include_explanation: bool = True,
    ) -> VerificationResult:
        """
        Verify if input text is a biblical quotation using Claude.

        Args:
            input_text: The Greek text to analyze
            candidates: List of candidate matches from vector search
                       Each dict should have: reference, text, score
            include_explanation: Whether to include detailed explanation

        Returns:
            VerificationResult with classification and confidence
        """
        if not candidates:
            return VerificationResult(
                is_quotation=False,
                match_type=MatchType.NON_BIBLICAL,
                confidence=90,
                explanation="No candidate matches found in vector search.",
            )

        # Build prompt
        prompt = self._build_verification_prompt(input_text, candidates)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            result = self._parse_verification_response(
                response.content[0].text,
                candidates,
            )

            logger.info(
                f"Verification complete: {result.match_type.value} "
                f"(confidence: {result.confidence}%)"
            )
            return result

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            # Return uncertain result on error
            return VerificationResult(
                is_quotation=False,
                match_type=MatchType.UNCERTAIN,
                confidence=0,
                explanation=f"Error during verification: {str(e)}",
            )

    def _build_verification_prompt(
        self,
        input_text: str,
        candidates: List[Dict],
    ) -> str:
        """Build the verification prompt for Claude."""

        # Format candidates
        candidates_text = ""
        for i, c in enumerate(candidates[:5], 1):  # Top 5 candidates
            candidates_text += f"""
Candidate {i}:
- Reference: {c.get('reference', 'Unknown')}
- Greek Text: {c.get('text', '')}
- Similarity Score: {c.get('score', 0):.3f}
"""

        prompt = f"""You are an expert in biblical Greek and textual analysis. Your task is to determine if a given Greek text is a quotation from the New Testament.

## Input Text to Analyze
{input_text}

## Candidate Biblical Matches (from semantic search)
{candidates_text}

## Your Task
Analyze the input text and determine:
1. Is this a biblical quotation? (yes/no)
2. What type of match is it?
   - exact: Word-for-word or near word-for-word match
   - close_paraphrase: Same meaning with minor word changes or reordering
   - loose_paraphrase: Same core idea but significantly reworded
   - allusion: Reference to biblical concepts without direct quotation
   - non_biblical: Not a biblical quotation
3. Confidence level (0-100%)
4. Best matching reference (if applicable)

## Response Format
Respond in exactly this format:

IS_QUOTATION: [yes/no]
MATCH_TYPE: [exact/close_paraphrase/loose_paraphrase/allusion/non_biblical]
CONFIDENCE: [0-100]
BEST_REFERENCE: [reference or "none"]
EXPLANATION: [1-2 sentence explanation of your analysis]

Consider:
- Greek word forms and inflections (same lemma = similar meaning)
- Word order flexibility in Greek
- Common textual variants between manuscripts
- Whether the semantic content matches, not just surface words"""

        return prompt

    def _parse_verification_response(
        self,
        response_text: str,
        candidates: List[Dict],
    ) -> VerificationResult:
        """Parse Claude's response into a VerificationResult."""

        lines = response_text.strip().split("\n")
        result_dict = {}

        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                result_dict[key.strip().upper()] = value.strip()

        # Parse values with defaults
        is_quotation = result_dict.get("IS_QUOTATION", "no").lower() == "yes"

        match_type_str = result_dict.get("MATCH_TYPE", "non_biblical").lower()
        try:
            match_type = MatchType(match_type_str)
        except ValueError:
            match_type = MatchType.UNCERTAIN

        try:
            confidence = int(result_dict.get("CONFIDENCE", "50"))
            confidence = max(0, min(100, confidence))  # Clamp to 0-100
        except ValueError:
            confidence = 50

        explanation = result_dict.get("EXPLANATION", "No explanation provided.")
        best_reference = result_dict.get("BEST_REFERENCE", "none")

        if best_reference.lower() == "none":
            best_reference = None

        # Find the matching candidate text if we have a reference
        best_match_text = None
        if best_reference:
            for c in candidates:
                if c.get("reference") == best_reference:
                    best_match_text = c.get("text")
                    break

        return VerificationResult(
            is_quotation=is_quotation,
            match_type=match_type,
            confidence=confidence,
            explanation=explanation,
            best_match_reference=best_reference,
            best_match_text=best_match_text,
        )

    def analyze_match_quality(
        self,
        input_text: str,
        biblical_text: str,
        reference: str,
    ) -> Dict:
        """
        Detailed analysis of match quality between two texts.

        Args:
            input_text: The text being analyzed
            biblical_text: The candidate biblical text
            reference: Biblical reference

        Returns:
            Dict with detailed analysis
        """
        prompt = f"""Analyze the similarity between these two Greek texts:

INPUT TEXT: {input_text}
BIBLICAL TEXT ({reference}): {biblical_text}

Provide a detailed analysis including:
1. Word-level matches (identical words)
2. Lemma-level matches (same dictionary form, different inflection)
3. Semantic similarity (same meaning, different words)
4. Key differences
5. Overall assessment

Format your response as:
WORD_MATCHES: [list of matching words]
LEMMA_MATCHES: [list of lemma matches]
SEMANTIC_SIMILARITY: [high/medium/low]
KEY_DIFFERENCES: [brief description]
ASSESSMENT: [1-2 sentence summary]"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            return {
                "analysis": response.content[0].text,
                "input_text": input_text,
                "biblical_text": biblical_text,
                "reference": reference,
            }

        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return {"error": str(e)}
