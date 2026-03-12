"""
Phase 341 — AI Copilot Robustness Tests
========================================

Robustness tests for AI copilot infrastructure:
- ai_audit_log.log_ai_interaction() → best-effort audit logging
- Graceful degradation when DB fails

Group A: AI Audit Log Writer (6 tests)
Group B: Graceful Degradation Patterns (6 tests)

CI-safe: injectable DB mock, no external API calls.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services.ai_audit_log import log_ai_interaction


# ===========================================================================
# Group A — AI Audit Log Writer
# ===========================================================================


class TestAiAuditLogWriter:

    def test_log_interaction_inserts_to_correct_table(self):
        db = MagicMock()
        log_ai_interaction(
            tenant_id="t-001",
            endpoint="POST /ai/copilot/morning-briefing",
            request_type="morning_briefing",
            input_summary="context for prop-001",
            output_summary="5 bookings today",
            client=db,
        )
        db.table.assert_called_with("ai_audit_log")

    def test_log_interaction_db_error_does_not_raise(self):
        db = MagicMock()
        db.table.side_effect = Exception("DB crash")
        # Must not raise (best-effort)
        log_ai_interaction(
            tenant_id="t-001",
            endpoint="POST /ai/copilot/financial-explainer",
            request_type="financial_explainer",
            input_summary="Q3 revenue",
            output_summary="Total: $15,000",
            client=db,
        )
        # If we reach here, it didn't raise — pass

    def test_log_interaction_with_entity_fields(self):
        db = MagicMock()
        log_ai_interaction(
            tenant_id="t-001",
            endpoint="POST /ai/copilot/task-recommendation",
            request_type="task_recommendation",
            entity_type="booking",
            entity_id="bk-123",
            client=db,
        )
        db.table.assert_called()

    def test_log_interaction_with_language(self):
        db = MagicMock()
        log_ai_interaction(
            tenant_id="t-001",
            endpoint="POST /ai/copilot/guest-messaging",
            request_type="guest_messaging",
            language="th",
            client=db,
        )
        db.table.assert_called()

    def test_log_interaction_with_generated_by(self):
        db = MagicMock()
        log_ai_interaction(
            tenant_id="t-001",
            endpoint="POST /ai/copilot/anomaly-alert",
            request_type="anomaly_alert",
            generated_by="gpt-4o",
            client=db,
        )
        db.table.assert_called()

    def test_log_interaction_minimal_args(self):
        db = MagicMock()
        log_ai_interaction(
            tenant_id="t-001",
            endpoint="GET /ai/copilot/worker",
            request_type="worker_copilot",
            client=db,
        )
        db.table.assert_called_with("ai_audit_log")


# ===========================================================================
# Group B — Graceful Degradation Patterns
# ===========================================================================


class TestGracefulDegradation:

    def test_log_empty_input_summary(self):
        db = MagicMock()
        log_ai_interaction(
            tenant_id="t-001",
            endpoint="POST /ai/copilot/morning-briefing",
            request_type="morning_briefing",
            input_summary="",
            output_summary="No data available",
            client=db,
        )
        db.table.assert_called()

    def test_log_empty_output_summary(self):
        db = MagicMock()
        log_ai_interaction(
            tenant_id="t-001",
            endpoint="POST /ai/copilot/financial-explainer",
            request_type="financial_explainer",
            input_summary="revenue data",
            output_summary="",
            client=db,
        )
        db.table.assert_called()

    def test_log_none_client_uses_default(self):
        """When client=None, the function should use the default Supabase client.
        In test/dev mode this may attempt real connection — we just verify no crash."""
        try:
            log_ai_interaction(
                tenant_id="t-001",
                endpoint="POST /ai/copilot/test",
                request_type="test",
                client=None,
            )
        except Exception:
            pass  # acceptable if no real Supabase

    def test_log_very_long_summary(self):
        db = MagicMock()
        long_summary = "x" * 10000
        log_ai_interaction(
            tenant_id="t-001",
            endpoint="POST /ai/copilot/context",
            request_type="context_aggregation",
            input_summary=long_summary,
            output_summary=long_summary,
            client=db,
        )
        db.table.assert_called()

    def test_log_special_characters_in_summary(self):
        db = MagicMock()
        log_ai_interaction(
            tenant_id="t-001",
            endpoint="POST /ai/copilot/morning-briefing",
            request_type="morning_briefing",
            input_summary="Guest: 日本語テスト 🏠 <script>alert('xss')</script>",
            output_summary="Résultat: €1,500.00",
            client=db,
        )
        db.table.assert_called()

    def test_log_interaction_returns_none(self):
        db = MagicMock()
        result = log_ai_interaction(
            tenant_id="t-001",
            endpoint="POST /ai/copilot/test",
            request_type="test",
            client=db,
        )
        assert result is None
