'use client';

/**
 * Phase 1036 — /manager/stream  (HARDENED)
 *
 * Product spec: docs/core/stream-product-spec.md
 *
 * Phase 1035: Stream redesigned as operational command surface (live tables).
 * Phase 1036 additions:
 *   - Canonical task ordering: Checkout → Cleaning → Check-in within same property+day
 *   - Add Task quick action (reuses POST /tasks/adhoc — no parallel creation system)
 *   - Duplicate guardrail: warns if conflicting open task exists, allows force-override
 *   - Scope-aware booking empty state
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import DraftGuard from '@/components/DraftGuard';
import { apiFetch } from '@/lib/api';
import { ManagerTaskDrawer, type ManagerTaskCardTask } from '@/components/ManagerTaskCard';

// ── Types ─────────────────────────────────────────────────────────────────────

type TaskStatus = 'PENDING' | 'ACKNOWLEDGED' | 'IN_PROGRESS' | 'MANAGER_EXECUTING';

type StreamTask = {
  id: string;
  task_id?: string;
  task_kind: string;
  kind?: string;
  status: TaskStatus;
  priority: string;
  property_id: string;
  property_name?: string;
  title?: string | null;
  due_date?: string | null;
  assigned_to?: string | null;
  assigned_to_name?: string | null;
  taken_over_by?: string | null;
  taken_over_by_name?: string | null;
  original_worker_id?: string | null;
  original_worker_name?: string | null;
  created_at?: string;
};

type StreamBooking = {
  booking_id: string;
  property_id: string;
  property_name: string;
  guest_name: string;
  start_date: string;
  end_date: string;
  status: string;
  external_ref?: string;
  urgency_label: string;
};

type StreamTab = 'tasks' | 'bookings';

type ConflictTask = { task_id: string; kind: string; status: string; due_date: string };

// ── Constants ─────────────────────────────────────────────────────────────────

const KIND_LABEL: Record<string, string> = {
  CLEANING: 'Cleaning',
  MAINTENANCE: 'Maintenance',
  CHECKIN_PREP: 'Check-in',
  GUEST_WELCOME: 'Guest Welcome',
  CHECKOUT_VERIFY: 'Check-out',
  SELF_CHECKIN_FOLLOWUP: 'Self Check-in',
  GENERAL: 'General',
};

const STATUS_CHIP: Record<string, { color: string; bg: string; label: string }> = {
  PENDING:            { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)',  label: 'Pending' },
  ACKNOWLEDGED:       { color: '#3b82f6', bg: 'rgba(59,130,246,0.12)',  label: 'Acknowledged' },
  IN_PROGRESS:        { color: '#10b981', bg: 'rgba(16,185,129,0.12)',  label: 'In Progress' },
  MANAGER_EXECUTING:  { color: '#8b5cf6', bg: 'rgba(139,92,246,0.12)', label: 'Manager Executing' },
};

// ── Canonical task kind ordering within same property + due_date ──────────────
// Operational sequence: Check-out (turnover starts) → Cleaning → Check-in
// This matches the real workflow: guest leaves → property cleaned → new guest arrives.
const CANONICAL_KIND_ORDER: Record<string, number> = {
  CHECKOUT_VERIFY:     1,
  CLEANING:            2,
  CHECKIN_PREP:        3,
  MAINTENANCE:         4,
  GUEST_WELCOME:       5,
  SELF_CHECKIN_FOLLOWUP: 6,
  GENERAL:             7,
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

type UrgencyLevel = 'overdue' | 'today' | 'upcoming' | 'future';

function getUrgency(task: StreamTask): UrgencyLevel {
  if (!task.due_date) return 'future';
  const due = task.due_date.slice(0, 10);
  const today = todayStr();
  if (due < today) return 'overdue';
  if (due === today) return 'today';
  const daysOut = (new Date(due).getTime() - Date.now()) / 86400000;
  if (daysOut <= 7) return 'upcoming';
  return 'future';
}

const URGENCY_ORDER: Record<UrgencyLevel, number> = {
  overdue: 0, today: 1, upcoming: 2, future: 3,
};

const URGENCY_BADGE: Record<UrgencyLevel, { label: string; color: string; bg: string }> = {
  overdue:  { label: 'OVERDUE',  color: '#ef4444', bg: 'rgba(239,68,68,0.12)' },
  today:    { label: 'TODAY',    color: '#f59e0b', bg: 'rgba(245,158,11,0.10)' },
  upcoming: { label: 'UPCOMING', color: '#6366f1', bg: 'rgba(99,102,241,0.10)' },
  future:   { label: '',         color: '#6b7280', bg: 'transparent' },
};

/**
 * Sort tasks by:
 *   1. Urgency (overdue → today → upcoming → future)
 *   2. Due date ascending (earlier first within same urgency band)
 *   3. Property ID (group same-property tasks together within same day)
 *   4. Canonical kind order (Checkout → Cleaning → Checkin within same property+date)
 */
function sortTasks(tasks: StreamTask[]): StreamTask[] {
  return [...tasks].sort((a, b) => {
    const ua = URGENCY_ORDER[getUrgency(a)];
    const ub = URGENCY_ORDER[getUrgency(b)];
    if (ua !== ub) return ua - ub;

    const da = a.due_date || '9999';
    const db = b.due_date || '9999';
    if (da !== db) return da.localeCompare(db);

    // Same urgency + same due date → group by property, then canonical kind order
    const pa = a.property_id || '';
    const pb = b.property_id || '';
    if (pa !== pb) return pa.localeCompare(pb);

    const ka = CANONICAL_KIND_ORDER[a.task_kind || a.kind || ''] ?? 99;
    const kb = CANONICAL_KIND_ORDER[b.task_kind || b.kind || ''] ?? 99;
    return ka - kb;
  });
}

function fmtDate(iso?: string | null): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch { return iso; }
}

function workerDisplay(name?: string | null, id?: string | null): string {
  if (name?.trim()) return name;
  if (id?.trim()) return id.slice(0, 12) + '…';
  return '—';
}

// ── Sub-components ────────────────────────────────────────────────────────────

function UrgencyBadge({ level }: { level: UrgencyLevel }) {
  const b = URGENCY_BADGE[level];
  if (!b.label) return null;
  return (
    <span style={{
      fontSize: 9, fontWeight: 800, letterSpacing: '0.06em',
      padding: '2px 6px', borderRadius: 4,
      color: b.color, background: b.bg,
      border: `1px solid ${b.color}33`,
      userSelect: 'none',
    }}>
      {b.label}
    </span>
  );
}

/** Tiny canonical sequence badge shown within same property+day group */
function KindSequenceBadge({ kind }: { kind: string }) {
  const seq = CANONICAL_KIND_ORDER[kind];
  if (!seq) return null;
  const color = kind === 'CHECKOUT_VERIFY' ? '#ef4444'
    : kind === 'CLEANING' ? '#f59e0b'
    : kind === 'CHECKIN_PREP' ? '#10b981'
    : 'transparent';
  if (color === 'transparent') return null;
  return (
    <span title="Operational sequence" style={{
      fontSize: 8, fontWeight: 800, padding: '1px 5px', borderRadius: 3,
      background: `${color}15`, color, border: `1px solid ${color}30`,
      marginLeft: 4, letterSpacing: '0.05em', userSelect: 'none',
    }}>
      {seq === 1 ? 'CHECKOUT' : seq === 2 ? 'CLEAN' : seq === 3 ? 'CHECK-IN' : ''}
    </span>
  );
}

function TaskRow({
  task, isNew, onClick,
}: { task: StreamTask; isNew: boolean; onClick: () => void }) {
  const urgency = getUrgency(task);
  const sc = STATUS_CHIP[task.status] || STATUS_CHIP['PENDING'];
  const kind = task.task_kind || task.kind || '';
  const kindLabel = KIND_LABEL[kind] || kind;
  const propName = task.property_name || task.property_id;
  const propCode = (task.property_name && task.property_id !== task.property_name) ? task.property_id : null;
  const workerName = workerDisplay(task.assigned_to_name || task.taken_over_by_name, task.assigned_to || task.taken_over_by);

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '12px 20px',
        background: isNew ? 'rgba(99,102,241,0.05)' : 'transparent',
        cursor: 'pointer',
        transition: 'background 120ms ease',
        borderBottom: '1px solid var(--color-border)',
      }}
      onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-surface-2)')}
      onMouseLeave={e => (e.currentTarget.style.background = isNew ? 'rgba(99,102,241,0.05)' : 'transparent')}
    >
      {/* Urgency indicator bar */}
      <div style={{
        width: 3, borderRadius: 2, alignSelf: 'stretch',
        background: URGENCY_BADGE[urgency].color,
        opacity: urgency === 'future' ? 0.2 : 0.7,
        flexShrink: 0,
      }} />

      {/* Property + task kind */}
      <div style={{ flex: '0 0 200px', minWidth: 0 }}>
        <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--color-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {propName}
        </div>
        {propCode && (
          <div style={{ fontSize: 10, color: 'var(--color-text-faint)' }}>{propCode}</div>
        )}
        <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginTop: 1, display: 'flex', alignItems: 'center' }}>
          {kindLabel}
          <KindSequenceBadge kind={kind} />
        </div>
      </div>

      {/* Status + urgency */}
      <div style={{ flex: '0 0 130px', display: 'flex', flexDirection: 'column', gap: 4 }}>
        <span style={{
          display: 'inline-block', fontSize: 10, fontWeight: 700,
          padding: '2px 7px', borderRadius: 20,
          background: sc.bg, color: sc.color,
          letterSpacing: '0.03em', whiteSpace: 'nowrap', alignSelf: 'flex-start',
        }}>
          {sc.label}
        </span>
        <UrgencyBadge level={urgency} />
      </div>

      {/* Worker */}
      <div style={{ flex: 1, fontSize: 11, color: 'var(--color-text-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {workerName !== '—'
          ? <><span style={{ color: 'var(--color-text-faint)' }}>Worker: </span>{workerName}</>
          : <span style={{ color: '#f59e0b', fontWeight: 600 }}>⚠ Unassigned</span>
        }
      </div>

      {/* Due date */}
      <div style={{ flex: '0 0 70px', fontSize: 11, color: urgency === 'overdue' ? '#ef4444' : 'var(--color-text-faint)', textAlign: 'right', fontWeight: urgency === 'overdue' ? 700 : 400 }}>
        {task.due_date ? fmtDate(task.due_date) : '—'}
      </div>

      {/* Chevron */}
      <div style={{ fontSize: 14, color: 'var(--color-text-faint)', flexShrink: 0 }}>›</div>
    </div>
  );
}

function BookingRow({ booking }: { booking: StreamBooking }) {
  const isUrgent = booking.urgency_label.includes('Today');
  const propName = booking.property_name || booking.property_id;
  const propCode = (booking.property_name && booking.property_id !== booking.property_name) ? booking.property_id : null;

  const urgencyColor = booking.urgency_label === 'Departing Today' ? '#ef4444'
    : booking.urgency_label === 'Arriving Today' ? '#10b981'
    : booking.urgency_label === 'Arriving Tomorrow' ? '#f59e0b'
    : booking.urgency_label === 'Active Stay' ? '#6366f1'
    : '#6b7280';

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '12px 20px',
      borderBottom: '1px solid var(--color-border)',
      background: isUrgent ? `${urgencyColor}06` : 'transparent',
    }}>
      {/* Urgency bar */}
      <div style={{
        width: 3, borderRadius: 2, alignSelf: 'stretch',
        background: urgencyColor, opacity: 0.7, flexShrink: 0,
      }} />

      {/* Property */}
      <div style={{ flex: '0 0 200px', minWidth: 0 }}>
        <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--color-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {propName}
        </div>
        {propCode && (
          <div style={{ fontSize: 10, color: 'var(--color-text-faint)' }}>{propCode}</div>
        )}
      </div>

      {/* Guest + urgency */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--color-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {booking.guest_name}
        </div>
        <div style={{ fontSize: 10, color: 'var(--color-text-faint)', marginTop: 2 }}>
          {booking.external_ref && `${booking.external_ref} · `}{fmtDate(booking.start_date)} → {fmtDate(booking.end_date)}
        </div>
      </div>

      {/* Label */}
      <span style={{
        fontSize: 10, fontWeight: 700, padding: '3px 8px', borderRadius: 20,
        background: `${urgencyColor}18`, color: urgencyColor,
        border: `1px solid ${urgencyColor}33`, whiteSpace: 'nowrap', flexShrink: 0,
      }}>
        {booking.urgency_label}
      </span>
    </div>
  );
}

// ── Add Task Modal ────────────────────────────────────────────────────────────
// Reuses POST /tasks/adhoc — NOT a second task creation system.
// Allowed kinds: CLEANING | MAINTENANCE | GENERAL
// CHECKIN_PREP / CHECKOUT_VERIFY are booking-generated and blocked here.

const ADHOC_KINDS = ['CLEANING', 'MAINTENANCE', 'GENERAL'] as const;
type AdhocKind = typeof ADHOC_KINDS[number];

const ADHOC_KIND_LABEL: Record<AdhocKind, string> = {
  CLEANING: 'Extra Cleaning',
  MAINTENANCE: 'Maintenance',
  GENERAL: 'General Operational Task',
};

type ConflictState = {
  message: string;
  conflicts: ConflictTask[];
  propertyName: string;
};

function AddTaskModal({
  onClose,
  onDone,
  scopedPropertyIds,
}: {
  onClose: () => void;
  onDone: () => void;
  scopedPropertyIds?: string[];
}) {
  const [propertyId, setPropertyId] = useState(scopedPropertyIds?.[0] || '');
  const [kind, setKind] = useState<AdhocKind>('CLEANING');
  const [dueDate, setDueDate] = useState(todayStr());
  const [note, setNote] = useState('');
  const [priority, setPriority] = useState<'MEDIUM' | 'HIGH' | 'CRITICAL'>('MEDIUM');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState<ConflictState | null>(null);

  const submit = async (force = false) => {
    if (!propertyId.trim()) { setError('Select a property.'); return; }
    if (!dueDate) { setError('Due date is required.'); return; }
    setSaving(true);
    setError('');
    setConflict(null);
    try {
      const url = `/tasks/adhoc${force ? '?force=true' : ''}`;
      await apiFetch(url, {
        method: 'POST',
        body: JSON.stringify({ property_id: propertyId, task_kind: kind, due_date: dueDate, note: note || undefined, priority }),
      });
      onDone();
    } catch (e: unknown) {
      // Try to parse conflict response (409)
      const msg = (e as Error)?.message || '';
      if (msg.includes('DUPLICATE_TASK_CONFLICT') || msg.includes('already exists')) {
        // Parse conflict details from error if available
        setConflict({
          message: msg,
          conflicts: [],
          propertyName: propertyId,
        });
      } else {
        setError(msg || 'Failed to create task');
      }
      setSaving(false);
    }
  };

  const PRIORITIES = ['MEDIUM', 'HIGH', 'CRITICAL'] as const;

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60,
    }}>
      <div style={{
        background: 'var(--color-surface)', borderRadius: 14, padding: 28,
        width: '100%', maxWidth: 460, boxShadow: '0 24px 80px rgba(0,0,0,0.35)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div style={{ fontWeight: 800, fontSize: 16, color: 'var(--color-text)' }}>Add Operational Task</div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, cursor: 'pointer', color: 'var(--color-text-faint)' }}>✕</button>
        </div>

        {/* Property selector */}
        <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text-faint)', display: 'block', marginBottom: 4, letterSpacing: '0.06em' }}>PROPERTY</label>
        {scopedPropertyIds && scopedPropertyIds.length > 1 ? (
          <select value={propertyId} onChange={e => setPropertyId(e.target.value)}
            style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)', fontSize: 13, marginBottom: 14 }}>
            {scopedPropertyIds.map(pid => <option key={pid} value={pid}>{pid}</option>)}
          </select>
        ) : (
          <input autoFocus value={propertyId} onChange={e => setPropertyId(e.target.value)} placeholder="e.g. KPG-500"
            style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)', fontSize: 13, boxSizing: 'border-box', marginBottom: 14 }} />
        )}

        {/* Task kind */}
        <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text-faint)', display: 'block', marginBottom: 6, letterSpacing: '0.06em' }}>TASK TYPE</label>
        <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
          {ADHOC_KINDS.map(k => (
            <button key={k} onClick={() => setKind(k)} style={{
              padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer',
              border: `1.5px solid ${kind === k ? 'var(--color-primary)' : 'var(--color-border)'}`,
              background: kind === k ? 'rgba(var(--color-primary-rgb),0.08)' : 'transparent',
              color: kind === k ? 'var(--color-primary)' : 'var(--color-text-dim)',
            }}>
              {ADHOC_KIND_LABEL[k]}
            </button>
          ))}
        </div>

        {/* Note: check-in / check-out are not available */}
        <div style={{ fontSize: 11, color: 'var(--color-text-faint)', marginBottom: 14, padding: '8px 12px', background: 'var(--color-bg)', borderRadius: 8, border: '1px solid var(--color-border)' }}>
          ℹ Check-in and check-out tasks are generated automatically from bookings.
        </div>

        {/* Due date */}
        <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text-faint)', display: 'block', marginBottom: 4, letterSpacing: '0.06em' }}>DUE DATE</label>
        <input type="date" value={dueDate} onChange={e => setDueDate(e.target.value)}
          style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)', fontSize: 13, boxSizing: 'border-box', marginBottom: 14 }} />

        {/* Priority */}
        <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text-faint)', display: 'block', marginBottom: 6, letterSpacing: '0.06em' }}>PRIORITY</label>
        <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
          {PRIORITIES.map(p => {
            const col = p === 'CRITICAL' ? '#ef4444' : p === 'HIGH' ? '#f59e0b' : 'var(--color-primary)';
            return (
              <button key={p} onClick={() => setPriority(p)} style={{
                flex: 1, padding: '7px 0', borderRadius: 8, fontSize: 11, fontWeight: 600, cursor: 'pointer',
                border: `1.5px solid ${priority === p ? col : 'var(--color-border)'}`,
                background: priority === p ? `${col}15` : 'transparent',
                color: priority === p ? col : 'var(--color-text-dim)',
              }}>
                {p}
              </button>
            );
          })}
        </div>

        {/* Note */}
        <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text-faint)', display: 'block', marginBottom: 4, letterSpacing: '0.06em' }}>NOTE FOR WORKER (optional)</label>
        <textarea value={note} onChange={e => setNote(e.target.value)} rows={2}
          placeholder="e.g. Extra cleaning — guest complaint, focus on kitchen"
          style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)', fontSize: 13, resize: 'none', boxSizing: 'border-box' }} />

        {/* Conflict warning */}
        {conflict && (
          <div style={{ marginTop: 14, padding: '12px 14px', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 10 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#f59e0b', marginBottom: 4 }}>⚠ Existing task conflict detected</div>
            <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginBottom: 10 }}>
              An open {kind} task already exists near this date for {conflict.propertyName}.
              Creating another is still valid — e.g. for an extra cleaning between stays.
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => { setConflict(null); setSaving(false); }}
                style={{ flex: 1, padding: '7px 0', borderRadius: 8, border: '1px solid var(--color-border)', background: 'transparent', cursor: 'pointer', fontSize: 12, color: 'var(--color-text-dim)' }}
              >Cancel</button>
              <button
                onClick={() => submit(true)}
                disabled={saving}
                style={{ flex: 2, padding: '7px 0', borderRadius: 8, border: 'none', background: '#f59e0b', color: '#fff', cursor: 'pointer', fontSize: 12, fontWeight: 700, opacity: saving ? 0.7 : 1 }}
              >{saving ? 'Creating…' : 'Create Anyway (Extra Task)'}</button>
            </div>
          </div>
        )}

        {error && <p style={{ color: '#ef4444', fontSize: 12, margin: '10px 0 0' }}>⚠ {error}</p>}

        {!conflict && (
          <div style={{ display: 'flex', gap: 10, marginTop: 18, justifyContent: 'flex-end' }}>
            <button onClick={onClose}
              style={{ padding: '9px 20px', borderRadius: 8, border: '1px solid var(--color-border)', background: 'transparent', cursor: 'pointer', color: 'var(--color-text-dim)', fontSize: 13 }}>
              Cancel
            </button>
            <button onClick={() => submit(false)} disabled={saving}
              style={{ padding: '9px 20px', borderRadius: 8, border: 'none', background: 'var(--color-primary)', color: '#fff', cursor: 'pointer', fontSize: 13, fontWeight: 700, opacity: saving ? 0.7 : 1 }}>
              {saving ? 'Creating…' : 'Create Task'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function StreamPage() {
  const [activeTab, setActiveTab] = useState<StreamTab>('tasks');

  // Tasks state
  const [tasks, setTasks] = useState<StreamTask[]>([]);
  const [tasksLoading, setTasksLoading] = useState(true);
  const [tasksErr, setTasksErr] = useState('');
  const [newTaskIds, setNewTaskIds] = useState<Set<string>>(new Set());
  const prevTaskIdsRef = useRef<Set<string>>(new Set());

  // Bookings state
  const [bookings, setBookings] = useState<StreamBooking[]>([]);
  const [bookingsLoading, setBookingsLoading] = useState(false);
  const [bookingsErr, setBookingsErr] = useState('');
  const [bookingsLoaded, setBookingsLoaded] = useState(false);

  // Drawer + modal state
  const [drawerTask, setDrawerTask] = useState<ManagerTaskCardTask | null>(null);
  const [loadingTask, setLoadingTask] = useState(false);
  const [showAddTask, setShowAddTask] = useState(false);

  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Load tasks ───────────────────────────────────────────────────────────────
  const loadTasks = useCallback(async (isAuto = false) => {
    if (!isAuto) setTasksLoading(true);
    setTasksErr('');
    try {
      const res = await apiFetch<{ groups: Record<string, StreamTask[]> }>('/manager/tasks');
      const groups = res.groups || {};
      const all: StreamTask[] = [
        ...(groups.manager_executing || []),
        ...(groups.pending || []),
        ...(groups.acknowledged || []),
        ...(groups.in_progress || []),
      ];
      if (isAuto) {
        const oldIds = prevTaskIdsRef.current;
        const fresh = new Set(all.filter(t => !oldIds.has(t.id)).map(t => t.id));
        setNewTaskIds(fresh);
        setTimeout(() => setNewTaskIds(new Set()), 3000);
      }
      prevTaskIdsRef.current = new Set(all.map(t => t.id));
      setTasks(sortTasks(all));
      setLastRefresh(new Date());
    } catch (e: unknown) {
      setTasksErr((e as Error)?.message || 'Failed to load tasks');
    } finally {
      setTasksLoading(false);
    }
  }, []);

  // ── Load bookings ────────────────────────────────────────────────────────────
  const loadBookings = useCallback(async () => {
    setBookingsLoading(true);
    setBookingsErr('');
    try {
      const res = await apiFetch<{ bookings: StreamBooking[] }>('/manager/stream/bookings');
      setBookings(res.bookings || []);
      setBookingsLoaded(true);
    } catch (e: unknown) {
      setBookingsErr((e as Error)?.message || 'Failed to load bookings');
      setBookingsLoaded(true);
    } finally {
      setBookingsLoading(false);
    }
  }, []);

  // ── Open task drawer ─────────────────────────────────────────────────────────
  const openTaskDrawer = useCallback(async (taskId: string) => {
    if (!taskId) return;
    setLoadingTask(true);
    try {
      const res = await apiFetch<{ task: ManagerTaskCardTask }>(`/tasks/detail/${taskId}`);
      setDrawerTask(res.task);
    } catch {
      const known = tasks.find(t => t.id === taskId);
      if (known) {
        setDrawerTask({
          id: known.id,
          task_kind: known.task_kind || known.kind || 'GENERAL',
          status: known.status,
          priority: known.priority,
          property_id: known.property_id,
          property_name: known.property_name,
          assigned_to: known.assigned_to,
          assigned_to_name: known.assigned_to_name,
        });
      }
    } finally {
      setLoadingTask(false);
    }
  }, [tasks]);

  // ── Auto-refresh ─────────────────────────────────────────────────────────────
  useEffect(() => {
    loadTasks();
    timerRef.current = setInterval(() => loadTasks(true), 20_000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [loadTasks]);

  useEffect(() => {
    if (activeTab === 'bookings' && !bookingsLoaded) {
      loadBookings();
    }
  }, [activeTab, bookingsLoaded, loadBookings]);

  // ── Derived values ────────────────────────────────────────────────────────────
  const overdueCount = tasks.filter(t => getUrgency(t) === 'overdue').length;
  const todayCount = tasks.filter(t => getUrgency(t) === 'today').length;
  const unassignedCount = tasks.filter(t => !t.assigned_to && !t.taken_over_by).length;
  const scopedPropertyIds = [...new Set(tasks.map(t => t.property_id).filter(Boolean))];

  // ── Tab button style ─────────────────────────────────────────────────────────
  const tabBtn = (tab: StreamTab): React.CSSProperties => ({
    padding: '6px 16px',
    borderRadius: 'var(--radius-full)',
    border: activeTab === tab ? '1px solid var(--color-primary)' : '1px solid var(--color-border)',
    background: activeTab === tab ? 'var(--color-primary)15' : 'transparent',
    color: activeTab === tab ? 'var(--color-primary)' : 'var(--color-text-dim)',
    fontWeight: activeTab === tab ? 700 : 500,
    fontSize: 12,
    cursor: 'pointer',
    transition: 'all 120ms ease',
  });

  return (
    <DraftGuard>
      <div style={{ maxWidth: 960 }}>

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-text-faint)', letterSpacing: '0.1em', marginBottom: 4 }}>
                OPERATIONAL MANAGER
              </div>
              <h1 style={{ fontSize: 28, fontWeight: 800, color: 'var(--color-text)', letterSpacing: '-0.04em', marginBottom: 4 }}>
                Live Stream
              </h1>
              <div style={{ fontSize: 13, color: 'var(--color-text-dim)' }}>
                Active tasks · Booking runway · Updated every 20s
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 11, color: 'var(--color-text-faint)' }}>
                {lastRefresh.toLocaleTimeString()}
              </span>
              <button
                onClick={() => activeTab === 'tasks' ? loadTasks() : loadBookings()}
                style={{ background: 'transparent', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: '7px 14px', fontSize: 12, fontWeight: 600, color: 'var(--color-text-dim)', cursor: 'pointer' }}
              >
                ↻ Refresh
              </button>
              {/* Add Task — reuses POST /tasks/adhoc, not a new creation system */}
              <button
                id="stream-add-task-btn"
                onClick={() => setShowAddTask(true)}
                style={{
                  background: 'var(--color-primary)', border: 'none',
                  borderRadius: 'var(--radius-md)', padding: '7px 16px',
                  fontSize: 12, fontWeight: 700, color: '#fff', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 6,
                }}
              >
                <span style={{ fontSize: 14, lineHeight: 1 }}>+</span> Add Task
              </button>
            </div>
          </div>

          {/* Quick stats */}
          {activeTab === 'tasks' && !tasksLoading && (
            <div style={{ display: 'flex', gap: 16, marginTop: 12, flexWrap: 'wrap' }}>
              {overdueCount > 0 && (
                <div style={{ fontSize: 11, fontWeight: 700, color: '#ef4444', background: 'rgba(239,68,68,0.10)', padding: '3px 10px', borderRadius: 20, border: '1px solid rgba(239,68,68,0.25)' }}>
                  ⚠ {overdueCount} overdue
                </div>
              )}
              {todayCount > 0 && (
                <div style={{ fontSize: 11, fontWeight: 700, color: '#f59e0b', background: 'rgba(245,158,11,0.10)', padding: '3px 10px', borderRadius: 20, border: '1px solid rgba(245,158,11,0.25)' }}>
                  ● {todayCount} due today
                </div>
              )}
              {unassignedCount > 0 && (
                <div style={{ fontSize: 11, fontWeight: 700, color: '#f59e0b', background: 'rgba(245,158,11,0.08)', padding: '3px 10px', borderRadius: 20, border: '1px solid rgba(245,158,11,0.2)' }}>
                  ⬡ {unassignedCount} unassigned
                </div>
              )}
              {overdueCount === 0 && todayCount === 0 && tasks.length > 0 && (
                <div style={{ fontSize: 11, color: '#10b981', fontWeight: 600 }}>✓ No urgent tasks</div>
              )}
            </div>
          )}
        </div>

        {/* ── Tabs ─────────────────────────────────────────────────────────── */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
          <button style={tabBtn('tasks')} onClick={() => setActiveTab('tasks')}>
            Tasks {tasks.length > 0 && `(${tasks.length})`}
          </button>
          <button style={tabBtn('bookings')} onClick={() => setActiveTab('bookings')}>
            Bookings {activeTab === 'bookings' && bookings.length > 0 ? `(${bookings.length})` : ''}
          </button>
        </div>

        {/* ── Tasks tab ────────────────────────────────────────────────────── */}
        {activeTab === 'tasks' && (
          <>
            {tasksLoading && (
              <div style={{ padding: '32px 0', textAlign: 'center', fontSize: 13, color: 'var(--color-text-faint)' }}>
                Loading active tasks…
              </div>
            )}
            {!tasksLoading && tasksErr && (
              <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--radius-lg)', padding: '16px 20px', color: '#ef4444', fontSize: 13 }}>
                ⚠ {tasksErr}
              </div>
            )}
            {!tasksLoading && !tasksErr && tasks.length === 0 && (
              <div style={{ padding: '48px 0', textAlign: 'center' }}>
                <div style={{ fontSize: 24, marginBottom: 8 }}>✓</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 4 }}>All caught up</div>
                <div style={{ fontSize: 12, color: 'var(--color-text-faint)' }}>No active tasks in your supervised properties</div>
              </div>
            )}
            {!tasksLoading && !tasksErr && tasks.length > 0 && (
              <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-xl)', overflow: 'hidden' }}>
                {/* Column headers */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '9px 20px', borderBottom: '1px solid var(--color-border)', background: 'var(--color-bg)' }}>
                  <div style={{ width: 3, flexShrink: 0 }} />
                  {[
                    { label: 'PROPERTY / KIND', flex: '0 0 200px' },
                    { label: 'STATUS', flex: '0 0 130px' },
                    { label: 'WORKER', flex: 1 },
                    { label: 'DUE', flex: '0 0 70px', align: 'right' as const },
                  ].map(h => (
                    <div key={h.label} style={{ flex: h.flex, fontSize: 9, fontWeight: 700, color: 'var(--color-text-faint)', letterSpacing: '0.1em', textAlign: h.align }}>
                      {h.label}
                    </div>
                  ))}
                  <div style={{ width: 14, flexShrink: 0 }} />
                </div>
                {tasks.map(task => (
                  <TaskRow
                    key={task.id}
                    task={task}
                    isNew={newTaskIds.has(task.id)}
                    onClick={() => openTaskDrawer(task.id)}
                  />
                ))}
              </div>
            )}
          </>
        )}

        {/* ── Bookings tab ─────────────────────────────────────────────────── */}
        {activeTab === 'bookings' && (
          <>
            {bookingsLoading && (
              <div style={{ padding: '32px 0', textAlign: 'center', fontSize: 13, color: 'var(--color-text-faint)' }}>
                Loading booking runway…
              </div>
            )}
            {!bookingsLoading && bookingsErr && (
              <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--radius-lg)', padding: '16px 20px', color: '#ef4444', fontSize: 13 }}>
                ⚠ {bookingsErr}
              </div>
            )}
            {bookingsLoaded && !bookingsErr && bookings.length === 0 && (
              <div style={{ padding: '48px 0', textAlign: 'center' }}>
                <div style={{ fontSize: 24, marginBottom: 8 }}>📅</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 4 }}>No upcoming arrivals or departures</div>
                <div style={{ fontSize: 12, color: 'var(--color-text-faint)', maxWidth: 340, margin: '0 auto', lineHeight: 1.5 }}>
                  {scopedPropertyIds.length > 0
                    ? `No confirmed arrivals or departures in your ${scopedPropertyIds.length === 1 ? `scoped property (${scopedPropertyIds[0]})` : `${scopedPropertyIds.length} scoped properties`} in the next 7 days.`
                    : 'No confirmed arrivals or departures in your scoped properties in the next 7 days.'
                  }
                </div>
              </div>
            )}
            {bookingsLoaded && !bookingsErr && bookings.length > 0 && (
              <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-xl)', overflow: 'hidden' }}>
                {/* Column headers */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '9px 20px', borderBottom: '1px solid var(--color-border)', background: 'var(--color-bg)' }}>
                  <div style={{ width: 3, flexShrink: 0 }} />
                  {[
                    { label: 'PROPERTY', flex: '0 0 200px' },
                    { label: 'GUEST', flex: 1 },
                    { label: 'STATUS', flex: '0 0 130px', align: 'right' as const },
                  ].map(h => (
                    <div key={h.label} style={{ flex: h.flex, fontSize: 9, fontWeight: 700, color: 'var(--color-text-faint)', letterSpacing: '0.1em', textAlign: h.align }}>
                      {h.label}
                    </div>
                  ))}
                </div>
                {bookings.map(b => (
                  <BookingRow key={b.booking_id} booking={b} />
                ))}
              </div>
            )}
            <div style={{ marginTop: 12, fontSize: 11, color: 'var(--color-text-faint)', textAlign: 'center' }}>
              Showing arrivals + departures: yesterday → next 7 days · confirmed bookings only
              {scopedPropertyIds.length > 0 && ` · ${scopedPropertyIds.length} propert${scopedPropertyIds.length === 1 ? 'y' : 'ies'} in scope`}
            </div>
          </>
        )}

      </div>

      {/* ── Task Drawer ─────────────────────────────────────────────────────── */}
      {drawerTask && (
        <ManagerTaskDrawer
          task={drawerTask}
          onClose={() => setDrawerTask(null)}
          onMutated={() => { setDrawerTask(null); loadTasks(); }}
        />
      )}
      {loadingTask && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24,
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 8, padding: '10px 16px', fontSize: 12, color: 'var(--color-text-dim)',
          zIndex: 400, boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
        }}>
          Opening task…
        </div>
      )}

      {/* ── Add Task Modal ───────────────────────────────────────────────────── */}
      {showAddTask && (
        <AddTaskModal
          onClose={() => setShowAddTask(false)}
          onDone={() => { setShowAddTask(false); loadTasks(); }}
          scopedPropertyIds={scopedPropertyIds.length > 0 ? scopedPropertyIds : undefined}
        />
      )}
    </DraftGuard>
  );
}
