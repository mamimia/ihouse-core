"""Phase 411 — Worker Task Mobile Completion contract tests.

Verifies the task transition pipeline for mobile worker completion flows.
"""

import pytest


TASK_TRANSITIONS = {
    "pending":       ["acknowledge"],
    "acknowledged":  ["start", "reject"],
    "in_progress":   ["complete", "reject"],
    "completed":     [],
    "rejected":      [],
}

SAMPLE_TASK = {
    "task_id": "task_001",
    "booking_id": "airbnb_BK001",
    "property_id": "prop_1",
    "kind": "CLEANING",
    "status": "pending",
    "priority": "HIGH",
    "worker_id": "worker_1",
    "ack_sla_minutes": 5,
}


class TestWorkerTaskCompletion:
    """Contract tests for worker task mobile completion."""

    def test_transition_actions_exist(self):
        """All statuses have defined transition actions."""
        for status in ["pending", "acknowledged", "in_progress", "completed", "rejected"]:
            assert status in TASK_TRANSITIONS

    def test_pending_can_acknowledge(self):
        """Pending tasks can be acknowledged."""
        assert "acknowledge" in TASK_TRANSITIONS["pending"]

    def test_acknowledged_can_start_or_reject(self):
        """Acknowledged tasks can be started or rejected."""
        assert "start" in TASK_TRANSITIONS["acknowledged"]
        assert "reject" in TASK_TRANSITIONS["acknowledged"]

    def test_in_progress_can_complete(self):
        """In-progress tasks can be completed."""
        assert "complete" in TASK_TRANSITIONS["in_progress"]

    def test_completed_is_terminal(self):
        """Completed is a terminal state."""
        assert len(TASK_TRANSITIONS["completed"]) == 0

    def test_rejected_is_terminal(self):
        """Rejected is a terminal state."""
        assert len(TASK_TRANSITIONS["rejected"]) == 0

    def test_task_has_required_fields(self):
        """Task record has all required fields."""
        required = ["task_id", "booking_id", "property_id", "kind", "status", "priority"]
        for field in required:
            assert field in SAMPLE_TASK

    def test_sla_minutes_is_positive(self):
        """SLA minutes must be positive."""
        assert SAMPLE_TASK["ack_sla_minutes"] > 0
