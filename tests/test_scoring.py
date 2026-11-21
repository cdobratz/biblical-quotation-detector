"""
Tests for core scoring functions in src/search/detector.py.

Covers:
- _compute_multi_signal_score (weighted confidence computation)
- _count_shared_lemmas (stem-based overlap)
- _count_shared_ngrams (bigram overlap)
- _detect_quotation_formula (introductory marker detection)
- Classification thresholds (exact, close_paraphrase, allusion boundaries)
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.search.detector import (
    _compute_multi_signal_score,
    _count_shared_lemmas,
    _count_shared_ngrams,
    _count_shared_words,
    _detect_quotation_formula,
    _normalize_greek,
)


class TestComputeMultiSignalScore:
    """Tests for _compute_multi_signal_score."""

    def test_perfect_signals_give_100(self):
        score = _compute_multi_signal_score(
            similarity_score=1.0,
            shared_words=8,
            shared_lemmas=10,
            shared_ngrams=5,
            has_formula=True,
            input_word_count=10,
        )
        assert score == 100

    def test_zero_signals_give_zero(self):
        score = _compute_multi_signal_score(
            similarity_score=0.80,
            shared_words=0,
            shared_lemmas=0,
            shared_ngrams=0,
            has_formula=False,
            input_word_count=10,
        )
        assert score == 0

    def test_similarity_below_080_clamps_to_zero(self):
        score = _compute_multi_signal_score(
            similarity_score=0.75,
            shared_words=0,
            shared_lemmas=0,
            shared_ngrams=0,
            has_formula=False,
            input_word_count=10,
        )
        assert score == 0

    def test_formula_alone_gives_15(self):
        score = _compute_multi_signal_score(
            similarity_score=0.80,
            shared_words=0,
            shared_lemmas=0,
            shared_ngrams=0,
            has_formula=True,
            input_word_count=10,
        )
        assert score == 15

    def test_high_similarity_alone_gives_25(self):
        score = _compute_multi_signal_score(
            similarity_score=1.0,
            shared_words=0,
            shared_lemmas=0,
            shared_ngrams=0,
            has_formula=False,
            input_word_count=10,
        )
        assert score == 25

    def test_word_overlap_caps_at_8(self):
        score_8 = _compute_multi_signal_score(
            similarity_score=0.80,
            shared_words=8,
            shared_lemmas=0,
            shared_ngrams=0,
            has_formula=False,
            input_word_count=10,
        )
        score_20 = _compute_multi_signal_score(
            similarity_score=0.80,
            shared_words=20,
            shared_lemmas=0,
            shared_ngrams=0,
            has_formula=False,
            input_word_count=10,
        )
        assert score_8 == score_20

    def test_typical_exact_match_scores_above_70(self):
        score = _compute_multi_signal_score(
            similarity_score=0.95,
            shared_words=7,
            shared_lemmas=8,
            shared_ngrams=4,
            has_formula=True,
            input_word_count=10,
        )
        assert score >= 70

    def test_typical_allusion_scores_between_20_and_50(self):
        score = _compute_multi_signal_score(
            similarity_score=0.87,
            shared_words=1,
            shared_lemmas=2,
            shared_ngrams=0,
            has_formula=False,
            input_word_count=10,
        )
        assert 10 <= score <= 50

    def test_known_acts_7_28_signals(self):
        """Acts 7:28 known exact: score ~0.92, 7+ shared words."""
        score = _compute_multi_signal_score(
            similarity_score=0.92,
            shared_words=7,
            shared_lemmas=7,
            shared_ngrams=5,
            has_formula=False,
            input_word_count=11,
        )
        assert score >= 60


class TestCountSharedLemmas:
    """Tests for _count_shared_lemmas (stem-based overlap)."""

    def test_identical_texts(self):
        text = "ἐπίστευσεν δὲ Ἀβραὰμ τῷ θεῷ"
        count = _count_shared_lemmas(text, text)
        assert count >= 2

    def test_morphological_variants_match(self):
        """Different inflections of the same word should share stems."""
        text_a = "θεός κύριος χριστός"
        text_b = "θεοῦ κυρίου χριστοῦ"
        count = _count_shared_lemmas(text_a, text_b)
        assert count >= 2

    def test_completely_different_texts_zero(self):
        text_a = "αλφαβητα γαμμαδελτα"
        text_b = "ζηταηθικα θηταιωτα"
        count = _count_shared_lemmas(text_a, text_b)
        assert count == 0

    def test_short_words_excluded(self):
        """Words with ≤3 characters are excluded from lemma comparison."""
        text_a = "και εις δια θεος"
        text_b = "και εις δια λογος"
        count = _count_shared_lemmas(text_a, text_b)
        assert count == 0

    def test_stem_varies_with_word_length(self):
        """Longer words should keep more characters in stems."""
        text_a = "δικαιοσυνην"
        text_b = "δικαιοσυνης"
        count = _count_shared_lemmas(text_a, text_b)
        assert count == 1

    def test_stem_does_not_falsely_collide_short_words(self):
        """4-char words with different stems should not collide."""
        text_a = "λογοσ"
        text_b = "λογικ"
        count = _count_shared_lemmas(text_a, text_b)
        assert count <= 1


class TestCountSharedNgrams:
    """Tests for _count_shared_ngrams."""

    def test_identical_texts_high_ngrams(self):
        text = "ἐπίστευσεν δὲ Ἀβραὰμ τῷ θεῷ"
        count = _count_shared_ngrams(text, text, n=2)
        assert count >= 3

    def test_different_texts_zero_ngrams(self):
        text_a = "αλφα βητα γαμμα"
        text_b = "δελτα ζητα ηθικα"
        count = _count_shared_ngrams(text_a, text_b, n=2)
        assert count == 0

    def test_short_text_below_n_returns_zero(self):
        """Single word can't form bigrams."""
        count = _count_shared_ngrams("θεος", "θεος", n=2)
        assert count == 0

    def test_shared_word_pair_in_different_order(self):
        """Bigrams are ordered, so reversed pairs don't match."""
        text_a = "θεος κυριος χριστος"
        text_b = "κυριος θεος πνευμα"
        count = _count_shared_ngrams(text_a, text_b, n=2)
        assert count == 0

    def test_trigrams(self):
        text = "αλφα βητα γαμμα δελτα"
        count = _count_shared_ngrams(text, text, n=3)
        assert count == 2

    def test_known_exact_match_high_ngrams(self):
        """Acts 7:28 exact match should have high bigram overlap."""
        clement = "μὴ ἀνελεῖν με σὺ θέλεις ὃν τρόπον ἀνεῖλες ἐχθὲς τὸν Αἰγύπτιον"
        acts = "μη ανελειν με συ θελεις ον τροπον ανειλες εχθες τον αιγυπτιον"
        count = _count_shared_ngrams(clement, acts, n=2)
        assert count >= 5


class TestDetectQuotationFormula:
    """Tests for _detect_quotation_formula."""

    def test_gegraphtai(self):
        assert _detect_quotation_formula("γέγραπται γάρ") is True

    def test_legei_kurios(self):
        assert _detect_quotation_formula("λέγει ὁ κύριος") is True

    def test_legei_graphe(self):
        assert _detect_quotation_formula("λέγει ἡ γραφή") is True

    def test_phēsin(self):
        assert _detect_quotation_formula("φησίν ὁ προφήτης") is True

    def test_kata_to_gegrammenon(self):
        assert _detect_quotation_formula("κατὰ τὸ γεγραμμένον") is True

    def test_hōs_eipen(self):
        assert _detect_quotation_formula("ὡς εἶπεν ὁ θεός") is True

    def test_no_formula(self):
        assert _detect_quotation_formula("ἐπίστευσεν δὲ Ἀβραὰμ τῷ θεῷ") is False

    def test_empty_string(self):
        assert _detect_quotation_formula("") is False

    def test_legōn(self):
        assert _detect_quotation_formula("εἶπεν λέγων") is True

    def test_marturei(self):
        assert _detect_quotation_formula("μαρτυρεῖ γὰρ αὐτῷ") is True

    def test_eipen_theos(self):
        assert _detect_quotation_formula("εἶπεν ὁ θεός") is True

    def test_outōs_legei(self):
        assert _detect_quotation_formula("οὕτως λέγει") is True

    def test_mixed_diacritics(self):
        """Formula detection should work regardless of diacritics."""
        assert _detect_quotation_formula("ΓΕΓΡΑΠΤΑΙ") is True


class TestClassificationThresholds:
    """Tests for the classification boundary conditions."""

    def test_exact_bypass_on_high_word_overlap(self):
        """shared_words >= 7 should classify as exact regardless of ms_confidence."""
        assert _count_shared_words(
            "μὴ ἀνελεῖν με σὺ θέλεις ὃν τρόπον ἀνεῖλες ἐχθὲς τὸν Αἰγύπτιον",
            "μη ανελειν με συ θελεις ον τροπον ανειλες εχθες τον αιγυπτιον",
        ) >= 7

    def test_allusion_requires_minimum_two_words(self):
        """Single shared word should NOT qualify as allusion anymore."""
        text_a = "θεος αλφα βητα γαμμα"
        text_b = "θεος δελτα ζητα ηθικα"
        words = _count_shared_words(text_a, text_b)
        lemmas = _count_shared_lemmas(text_a, text_b)
        assert words < 2 and lemmas < 3

    def test_close_paraphrase_needs_3_words_and_ms50(self):
        """Verifies the threshold boundary for close_paraphrase."""
        text = "ὀφθαλμὸς οὐκ εἶδεν καὶ οὖς οὐκ ἤκουσεν"
        verse = "οφθαλμος ουκ ειδεν και ους ουκ ηκουσεν"
        words = _count_shared_words(text, verse)
        assert words >= 3
