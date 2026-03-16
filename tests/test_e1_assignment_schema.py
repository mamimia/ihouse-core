"""
Phase E-1 — Task Assignment Schema Contract Tests

Verifies:
  A. Task model dataclass includes assigned_to field (nullable)
  B. Task.build() accepts and passes assigned_to
  C. _task_to_row() serialization includes assigned_to
  D. with_status preserves assigned_to
"""

import pytest


# ============================================================================
# A. Task model has assigned_to field
# ============================================================================

class TestA_TaskModelField:

    def test_a1_task_dataclass_has_assigned_to(self):
        """Task dataclass includes assigned_to as an optional field."""
        from tasks.task_model import Task
        import dataclasses
        field_names = [f.name for f in dataclasses.fields(Task)]
        assert "assigned_to" in field_names, "Task dataclass missing 'assigned_to' field"

    def test_a2_assigned_to_defaults_none(self):
        """assigned_to defaults to None when not explicitly set."""
        from tasks.task_model import Task, TaskKind, TaskStatus, TaskPriority, WorkerRole
        t = Task(
            task_id="abc123",
            kind=TaskKind.CLEANING,
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM,
            urgency="normal",
            worker_role=WorkerRole.CLEANER,
            ack_sla_minutes=60,
            tenant_id="T1",
            booking_id="B1",
            property_id="P1",
            due_date="2026-01-01",
            title="Clean",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        assert t.assigned_to is None

    def test_a3_assigned_to_accepts_string(self):
        """assigned_to accepts a worker user_id string."""
        from tasks.task_model import Task, TaskKind, TaskStatus, TaskPriority, WorkerRole
        t = Task(
            task_id="abc123",
            kind=TaskKind.CLEANING,
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM,
            urgency="normal",
            worker_role=WorkerRole.CLEANER,
            ack_sla_minutes=60,
            tenant_id="T1",
            booking_id="B1",
            property_id="P1",
            due_date="2026-01-01",
            title="Clean",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            assigned_to="WRK-001",
        )
        assert t.assigned_to == "WRK-001"


# ============================================================================
# B. Task.build() includes assigned_to
# ============================================================================

class TestB_TaskBuild:

    def test_b1_build_without_assigned_to(self):
        """Task.build() produces assigned_to=None when not specified."""
        from tasks.task_model import Task, TaskKind
        t = Task.build(
            kind=TaskKind.CLEANING,
            tenant_id="T1",
            booking_id="B1",
            property_id="P1",
            due_date="2026-01-01",
            title="Clean unit",
            created_at="2026-01-01T00:00:00Z",
        )
        assert t.assigned_to is None

    def test_b2_build_with_assigned_to(self):
        """Task.build() stores assigned_to when provided."""
        from tasks.task_model import Task, TaskKind
        t = Task.build(
            kind=TaskKind.CLEANING,
            tenant_id="T1",
            booking_id="B1",
            property_id="P1",
            due_date="2026-01-01",
            title="Clean unit",
            created_at="2026-01-01T00:00:00Z",
            assigned_to="WRK-007",
        )
        assert t.assigned_to == "WRK-007"

    def test_b3_build_assigned_to_does_not_affect_task_id(self):
        """assigned_to has no influence on task_id (deterministic from kind+booking+property)."""
        from tasks.task_model import Task, TaskKind
        t1 = Task.build(
            kind=TaskKind.CLEANING, tenant_id="T1", booking_id="B1",
            property_id="P1", due_date="2026-01-01", title="Clean",
            created_at="2026-01-01T00:00:00Z", assigned_to=None,
        )
        t2 = Task.build(
            kind=TaskKind.CLEANING, tenant_id="T1", booking_id="B1",
            property_id="P1", due_date="2026-01-01", title="Clean",
            created_at="2026-01-01T00:00:00Z", assigned_to="WRK-001",
        )
        assert t1.task_id == t2.task_id, "assigned_to must not influence task_id"


# ============================================================================
# C. Serialization includes assigned_to
# ============================================================================

class TestC_Serialization:

    def test_c1_task_to_row_includes_assigned_to(self):
        """_task_to_row() includes assigned_to in output dict."""
        from tasks.task_model import Task, TaskKind
        from tasks.task_writer import _task_to_row
        t = Task.build(
            kind=TaskKind.CLEANING, tenant_id="T1", booking_id="B1",
            property_id="P1", due_date="2026-01-01", title="Clean",
            created_at="2026-01-01T00:00:00Z", assigned_to="WRK-002",
        )
        row = _task_to_row(t)
        assert "assigned_to" in row, "_task_to_row() missing assigned_to key"
        assert row["assigned_to"] == "WRK-002"

    def test_c2_task_to_row_null_assigned_to(self):
        """_task_to_row() outputs None for unassigned tasks."""
        from tasks.task_model import Task, TaskKind
        from tasks.task_writer import _task_to_row
        t = Task.build(
            kind=TaskKind.CLEANING, tenant_id="T1", booking_id="B1",
            property_id="P1", due_date="2026-01-01", title="Clean",
            created_at="2026-01-01T00:00:00Z",
        )
        row = _task_to_row(t)
        assert row["assigned_to"] is None


# ============================================================================
# D. with_status preserves assigned_to
# ============================================================================

class TestD_StatusTransition:

    def test_d1_with_status_preserves_assigned_to(self):
        """Task.with_status() preserves assigned_to field."""
        from tasks.task_model import Task, TaskKind, TaskStatus
        t = Task.build(
            kind=TaskKind.CLEANING, tenant_id="T1", booking_id="B1",
            property_id="P1", due_date="2026-01-01", title="Clean",
            created_at="2026-01-01T00:00:00Z", assigned_to="WRK-003",
        )
        t2 = t.with_status(TaskStatus.ACKNOWLEDGED, "2026-01-01T01:00:00Z")
        assert t2.assigned_to == "WRK-003"
        assert t2.status == TaskStatus.ACKNOWLEDGED
