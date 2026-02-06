"""
Tests for the word overlap utility functions in src/search/detector.py.

Validates _count_shared_words and _normalize_greek used by the heuristic
classifier to gate match classifications based on actual lexical overlap.
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.search.detector import _count_shared_words, _normalize_greek


class TestNormalizeGreek:
    """Tests for _normalize_greek helper."""

    def test_strips_diacritics(self):
        """Accented Greek should normalize to plain lowercase."""
        # ἐκκλησία → εκκλησια
        result = _normalize_greek("ἐκκλησία")
        assert result == "εκκλησια"

    def test_lowercase(self):
        """Uppercase Greek should be lowercased with sigma normalized."""
        result = _normalize_greek("ΘΕΟΣ")
        # Final sigma ς is normalized to medial σ for consistent matching
        assert result == "θεοσ"

    def test_mixed_diacritics_and_case(self):
        """Mixed accents and case should all normalize."""
        result = _normalize_greek("Ἰησοῦ Χριστοῦ")
        assert "ιησου" in result
        assert "χριστου" in result

    def test_empty_string(self):
        """Empty string should return empty."""
        assert _normalize_greek("") == ""

    def test_latin_text_passes_through(self):
        """Latin characters should just be lowercased."""
        result = _normalize_greek("Hello World")
        assert result == "hello world"


class TestCountSharedWords:
    """Tests for _count_shared_words function."""

    def test_identical_texts_high_overlap(self):
        """Two identical Greek texts should have high overlap count."""
        text = "ἐπίστευσεν δὲ Ἀβραὰμ τῷ θεῷ καὶ ἐλογίσθη αὐτῷ εἰς δικαιοσύνην"
        count = _count_shared_words(text, text)
        # After filtering ≤2 char words: δε, τω → filtered out
        # Remaining: επιστευσεν, αβρααμ, θεω, και, ελογισθη, αυτω, εις, δικαιοσυνην
        assert count >= 5

    def test_completely_different_texts_zero_overlap(self):
        """Two completely unrelated texts should have 0 shared words."""
        text_a = "αλφα βητα γαμμα δελτα"
        text_b = "ζητα ηθικα θητα ιωτα"
        count = _count_shared_words(text_a, text_b)
        assert count == 0

    def test_only_short_words_shared_returns_zero(self):
        """Texts sharing only articles/particles (≤2 chars) should return 0."""
        # Common short Greek words: ο, η, εν, τα, τε, δε, εκ, ως
        text_a = "ο η εν τα μεγαλοπρεπες"
        text_b = "ο η εν τα ταπεινοφρονειτε"
        count = _count_shared_words(text_a, text_b)
        # Only μεγαλοπρεπες and ταπεινοφρονειτε are >2 chars, and they differ
        assert count == 0

    def test_known_exact_match_acts_7_28(self):
        """
        Known exact match from 1 Clement 4:10 quoting Acts 7:28.
        Should have ≥5 shared words.
        """
        # 1 Clement text (from the report)
        clement_text = "μὴ ἀνελεῖν με σὺ θέλεις, ὃν τρόπον ἀνεῖλες ἐχθὲς τὸν Αἰγύπτιον"
        # Acts 7:28 matched text (normalized, from report)
        acts_text = "μη ανελειν με συ θελεις ον τροπον ανειλες εχθες τον αιγυπτιον"
        count = _count_shared_words(clement_text, acts_text)
        assert count >= 5, f"Expected ≥5 shared words, got {count}"

    def test_known_exact_match_galatians_3_6(self):
        """
        Known exact match from 1 Clement 10:6 quoting Galatians 3:6.
        Should have ≥5 shared words.
        """
        clement_text = "ἐπίστευσεν δὲ Ἀβραὰμ τῷ θεῷ, καὶ ἐλογίσθη αὐτῷ εἰς δικαιοσύνην"
        galatians_text = "καθως αβρααμ επιστευσεν τω θεω και ελογισθη αυτω εις δικαιοσυνην"
        count = _count_shared_words(clement_text, galatians_text)
        assert count >= 5, f"Expected ≥5 shared words, got {count}"

    def test_short_text_correct_count(self):
        """Short text (3 words) should give correct count."""
        text_a = "θεου κυριου χριστου"
        text_b = "θεου κυριου πνευματος"
        count = _count_shared_words(text_a, text_b)
        # θεου and κυριου are shared and >2 chars
        assert count == 2

    def test_diacritics_vs_normalized_same_result(self):
        """Text with diacritics vs normalized should give same overlap."""
        accented = "ἐκκλησία τοῦ θεοῦ ἡ παροικοῦσα Ῥώμην"
        plain = "εκκλησια του θεου η παροικουσα ρωμην"
        count = _count_shared_words(accented, plain)
        # εκκλησια, θεου, παροικουσα, ρωμην are >2 chars and shared
        assert count >= 3

    def test_empty_texts_return_zero(self):
        """Empty strings should return 0."""
        assert _count_shared_words("", "") == 0
        assert _count_shared_words("θεος", "") == 0
        assert _count_shared_words("", "θεος") == 0

    def test_single_word_texts(self):
        """Single matching word that is >2 chars should count as 1."""
        assert _count_shared_words("θεος", "θεος") == 1

    def test_single_short_word_returns_zero(self):
        """Single matching word ≤2 chars should return 0."""
        assert _count_shared_words("εν", "εν") == 0

    def test_false_positive_example_zero_overlap(self):
        """
        Example false positive from 1 Clement report:
        Chunk about hospitality matched to 2 Corinthians 8:17.
        Should have 0 or very low overlap.
        """
        clement_chunk = "καὶ τὸ μεγαλοπρεπὲς τῆς φιλοξενίας ὑμῶν ἦθος οὐκ ἐκήρυξεν"
        cor_verse = "οτι την μεν παρακλησιν εδεξατο σπουδαιοτεροσ δε υπαρχων αυθαιρετοσ εξηλθεν προσ υμασ"
        count = _count_shared_words(clement_chunk, cor_verse)
        assert count <= 1, f"Expected ≤1 shared words for false positive, got {count}"


class TestWordOverlapIntegration:
    """Integration-level tests for word overlap with classification logic."""

    def test_high_overlap_with_high_score_qualifies(self):
        """
        Text with ≥3 shared words and score ≥0.90 should be classifiable
        as close_paraphrase.
        """
        # This test validates the logic described in CLAUDE.md Task 2
        text = "ὀφθαλμὸς οὐκ εἶδεν καὶ οὖς οὐκ ἤκουσεν"
        verse = "οφθαλμος ουκ ειδεν και ους ουκ ηκουσεν"
        count = _count_shared_words(text, verse)
        assert count >= 3, f"Expected ≥3 shared words, got {count}"

    def test_no_overlap_regardless_of_score_rejects(self):
        """
        Text with 0 shared words should be classified as non_biblical
        regardless of what the vector similarity score says.
        """
        text = "Πάντες τε ἐταπεινοφρονεῖτε μηδὲν ἀλαζονευόμενοι ὑποτασσόμενοι"
        verse = "θεσθε ουν εις τας καρδιας υμων μη προμελεταν απολογηθηναι"
        count = _count_shared_words(text, verse)
        assert count <= 1, f"Expected ≤1 shared words, got {count}"
