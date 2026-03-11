"""
Phase 258 — i18n Foundation Contract Tests
==========================================

Tests: 15 across 5 groups.
"""
from __future__ import annotations

import pytest

from i18n import get_text, get_supported_languages, is_supported, get_template_variables


# ---------------------------------------------------------------------------
# Group A — Language pack coverage (7 languages × key)
# ---------------------------------------------------------------------------

class TestGroupALanguageCoverage:
    """Every supported language returns a translation for core keys."""

    LANGUAGES = ["en", "th", "ja", "zh", "es", "ko", "he"]
    KEY = "error.not_found"

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_a1_all_languages_have_not_found(self, lang):
        result = get_text(self.KEY, lang=lang)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_a2_english_not_found_text_is_correct(self):
        assert get_text("error.not_found", lang="en") == "Resource not found."

    def test_a3_thai_not_found_returns_thai(self):
        result = get_text("error.not_found", lang="th")
        # Thai text contains Thai Unicode characters
        assert any(0x0E00 <= ord(c) <= 0x0E7F for c in result)


# ---------------------------------------------------------------------------
# Group B — Variable substitution
# ---------------------------------------------------------------------------

class TestGroupBVariableSubstitution:
    """Variables in templates are correctly substituted."""

    def test_b1_task_assigned_en_substitution(self):
        result = get_text(
            "notify.task_assigned", lang="en",
            task_id="T-42", property="Villa Lotus", urgency="CRITICAL",
        )
        assert "T-42" in result
        assert "Villa Lotus" in result
        assert "CRITICAL" in result

    def test_b2_booking_created_es_substitution(self):
        result = get_text(
            "notify.booking_created", lang="es",
            property="Casa Playa", booking_ref="BK-999",
        )
        assert "Casa Playa" in result
        assert "BK-999" in result

    def test_b3_missing_variables_returns_unsubstituted_template(self):
        # If vars are incomplete, return the raw template rather than crashing
        result = get_text("notify.task_assigned", lang="en")
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Group C — Fallback behaviour
# ---------------------------------------------------------------------------

class TestGroupCFallbackBehavior:
    """Unsupported language and missing keys fall back to English."""

    def test_c1_unsupported_language_falls_back_to_en(self):
        result = get_text("error.not_found", lang="xx")
        assert result == get_text("error.not_found", lang="en")

    def test_c2_unknown_key_returns_key_itself(self):
        result = get_text("nonexistent.key", lang="en")
        assert result == "nonexistent.key"

    def test_c3_key_missing_in_lang_falls_back_to_en(self):
        # All keys should be in English; confirm fallback is non-empty
        result = get_text("error.internal", lang="ko")
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Group D — Registry
# ---------------------------------------------------------------------------

class TestGroupDRegistry:
    """Supported language registry."""

    def test_d1_get_supported_languages_returns_7(self):
        langs = get_supported_languages()
        assert len(langs) == 7

    def test_d2_all_expected_languages_present(self):
        langs = set(get_supported_languages())
        assert langs == {"en", "th", "ja", "zh", "es", "ko", "he"}

    def test_d3_is_supported_returns_true_for_valid(self):
        for lang in ["en", "th", "ja", "zh", "es", "ko", "he"]:
            assert is_supported(lang)

    def test_d4_is_supported_returns_false_for_invalid(self):
        assert not is_supported("xx")
        assert not is_supported("")
        assert not is_supported("FR")  # case sensitive


# ---------------------------------------------------------------------------
# Group E — Template introspection
# ---------------------------------------------------------------------------

class TestGroupETemplateIntrospection:
    """get_template_variables extracts template variable names."""

    def test_e1_task_assigned_has_correct_vars(self):
        variables = get_template_variables("notify.task_assigned")
        assert "task_id" in variables
        assert "property" in variables
        assert "urgency" in variables

    def test_e2_booking_created_has_correct_vars(self):
        variables = get_template_variables("notify.booking_created")
        assert "property" in variables
        assert "booking_ref" in variables

    def test_e3_error_keys_have_no_variables(self):
        variables = get_template_variables("error.not_found")
        assert variables == []
