/**
 * Phase 1033 — Operational Manager Baseline v1
 * lib/manager/types.ts
 *
 * Canonical shared type definitions for the OM cockpit module.
 * These types are used across Hub, Alert, Stream, Team, and supporting
 * coordination layers. No runtime code here — types only.
 *
 * SCAFFOLD — not yet wired into live surfaces.
 */

// ---------------------------------------------------------------------------
// Alert types
// ---------------------------------------------------------------------------

export type AlertSeverity = 'CRITICAL' | 'HIGH' | 'NORMAL' | 'LOW';
export type AlertStatus   = 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED';

export type ManagerAlert = {
  id: string;
  severity: AlertSeverity;
  status: AlertStatus;
  title: string;
  body?: string | null;
  property_id?: string | null;
  task_id?: string | null;
  booking_id?: string | null;
  created_at: string;
  acknowledged_at?: string | null;
  resolved_at?: string | null;
  actor?: string | null;
};

// ---------------------------------------------------------------------------
// Stream / activity feed types
// ---------------------------------------------------------------------------

export type StreamEventKind =
  | 'TASK_CREATED'
  | 'TASK_ACKNOWLEDGED'
  | 'TASK_IN_PROGRESS'
  | 'TASK_COMPLETED'
  | 'TASK_CANCELED'
  | 'MANAGER_TAKEOVER_INITIATED'
  | 'MANAGER_TASK_COMPLETED'
  | 'BOOKING_FLAGS_UPDATED'
  | 'BOOKING_CREATED'
  | 'BOOKING_CANCELED'
  | 'WORKER_ASSIGNED'
  | 'BATON_TRANSFER'
  | string; // extensible — new event kinds must not break the stream

export type StreamEvent = {
  id: string;
  kind: StreamEventKind;
  property_id?: string | null;
  task_id?: string | null;
  booking_id?: string | null;
  actor?: string | null;
  actor_role?: string | null;
  description?: string | null;
  created_at: string;
  meta?: Record<string, unknown>;
};

// ---------------------------------------------------------------------------
// Team / coverage types
// ---------------------------------------------------------------------------

export type WorkerDesignation = 'PRIMARY' | 'BACKUP' | 'ON_CALL' | string;

export type CoverageStatus = {
  has_primary: boolean;
  primary_user_id?: string | null;
  backup_user_id?: string | null;
};

export type OperationalWorker = {
  user_id: string;
  display_name: string;
  role: string;
  is_active: boolean;
  lane: string;
  priority: number;
  designation: WorkerDesignation;
  open_tasks_on_property: number;
  contact: {
    line?: string | null;
    phone?: string | null;
    email?: string | null;
  };
};

export type PropertyTeamView = {
  property_id: string;
  workers: OperationalWorker[];
  lane_coverage: Record<string, CoverageStatus>;
  coverage_gaps: string[];
};

export type TeamSummary = {
  properties: PropertyTeamView[];
  total_workers: number;
};

// ---------------------------------------------------------------------------
// Task types (manager view — not worker queue view)
// ---------------------------------------------------------------------------

export type TaskStatus =
  | 'PENDING'
  | 'ACKNOWLEDGED'
  | 'IN_PROGRESS'
  | 'MANAGER_EXECUTING'
  | 'COMPLETED'
  | 'CANCELED';

export type TaskPriority = 'CRITICAL' | 'HIGH' | 'NORMAL' | 'LOW';

export type TaskKind =
  | 'CLEANING'
  | 'CHECKIN_PREP'
  | 'GUEST_WELCOME'
  | 'CHECKOUT_VERIFY'
  | 'MAINTENANCE'
  | 'GENERAL'
  | string;

export type ManagerTask = {
  id: string;
  task_kind: TaskKind;
  status: TaskStatus;
  priority: TaskPriority;
  property_id: string;
  assigned_to?: string | null;
  taken_over_by?: string | null;
  taken_over_reason?: string | null;
  due_date?: string | null;
  title?: string | null;
  completed_at?: string | null;
};

export type TaskGroups = {
  manager_executing: ManagerTask[];
  pending: ManagerTask[];
  acknowledged: ManagerTask[];
  in_progress: ManagerTask[];
};

// ---------------------------------------------------------------------------
// Booking coordination types (manager view — operational overlay only)
// No financial columns. No full guest PII.
// ---------------------------------------------------------------------------

export type BookingCoordStatus =
  | 'ARRIVING'
  | 'IN_HOUSE'
  | 'DEPARTING'
  | 'READY'
  | string;

export type ManagerBooking = {
  id: string;
  booking_id?: string;
  property_id?: string;
  reservation_ref?: string;
  source?: string;
  check_in?: string;
  check_out?: string;
  status?: string;
  guest_first_name?: string;
  // Operational overlay (may not exist yet — graceful fallback)
  expected_arrival_eta?: string | null;
  coordination_status?: BookingCoordStatus | null;
  operational_notes?: string | null;
  priority_flags?: string[] | null;
  last_operational_update?: string | null;
};

// ---------------------------------------------------------------------------
// Hub / cockpit summary types
// ---------------------------------------------------------------------------

export type HubSummary = {
  open_alerts: number;
  critical_alerts: number;
  active_tasks: number;
  manager_executing: number;
  coverage_gaps: number;
  arriving_today: number;
  departing_today: number;
};
