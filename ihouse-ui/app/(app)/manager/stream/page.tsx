'use client';

/**
 * Phase 1035 — /manager/stream  (REDESIGNED)
 *
 * Product spec: docs/core/stream-product-spec.md
 *
 * This is an OPERATIONAL COMMAND SURFACE, not an audit log.
 * - Tasks tab: live tasks table (PENDING/ACKNOWLEDGED/IN_PROGRESS/MANAGER_EXECUTING)
 *   sorted by urgency (overdue → today → upcoming → future)
 * - Bookings tab: operational booking runway (yesterday → +7d) from bookings table
 * - Sessions tab: REMOVED (belongs in /admin/audit)
 *
 * Data sources:
 *   Tasks   → GET /manager/tasks  (tasks table, property-scoped)
 *   Bookings → GET /manager/stream/bookings  (bookings table, operational window)
 *
 * NOT audit_events. Never.
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
  // Within 7 days
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

function TaskRow({
  task, isNew, onClick,
}: { task: StreamTask; isNew: boolean; onClick: () => void }) {
  const urgency = getUrgency(task);
  const sc = STATUS_CHIP[task.status] || STATUS_CHIP['PENDING'];
  const kindLabel = KIND_LABEL[task.task_kind || task.kind || ''] || task.task_kind || '';
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
        <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginTop: 1 }}>{kindLabel}</div>
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

  // Drawer state
  const [drawerTask, setDrawerTask] = useState<ManagerTaskCardTask | null>(null);
  const [loadingTask, setLoadingTask] = useState(false);

  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Load tasks (from /manager/tasks — tasks table, not audit_events) ────────
  const loadTasks = useCallback(async (isAuto = false) => {
    if (!isAuto) setTasksLoading(true);
    setTasksErr('');
    try {
      const res = await apiFetch<{ groups: Record<string, StreamTask[]> }>('/manager/tasks');
      const groups = res.groups || {};
      // Flatten all groups into one list; urgency sort applied client-side
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
      // Sort by urgency
      all.sort((a, b) => {
        const ua = URGENCY_ORDER[getUrgency(a)];
        const ub = URGENCY_ORDER[getUrgency(b)];
        if (ua !== ub) return ua - ub;
        const da = a.due_date || '9999';
        const db2 = b.due_date || '9999';
        return da.localeCompare(db2);
      });
      setTasks(all);
      setLastRefresh(new Date());
    } catch (e: unknown) {
      setTasksErr((e as Error)?.message || 'Failed to load tasks');
    } finally {
      setTasksLoading(false);
    }
  }, []);

  // ── Load bookings (from /manager/stream/bookings — bookings table) ──────────
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
      // Drawer still opens with what we know from the stream row
      // Find task in current list for minimal shell — avoids empty property_id
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

  // Load bookings only when tab is first opened
  useEffect(() => {
    if (activeTab === 'bookings' && !bookingsLoaded) {
      loadBookings();
    }
  }, [activeTab, bookingsLoaded, loadBookings]);

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

  // ── Stats for header ─────────────────────────────────────────────────────────
  const overdueCount = tasks.filter(t => getUrgency(t) === 'overdue').length;
  const todayCount = tasks.filter(t => getUrgency(t) === 'today').length;
  const unassignedCount = tasks.filter(t => !t.assigned_to && !t.taken_over_by).length;

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
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 11, color: 'var(--color-text-faint)' }}>
                {lastRefresh.toLocaleTimeString()}
              </span>
              <button
                onClick={() => activeTab === 'tasks' ? loadTasks() : loadBookings()}
                style={{ background: 'transparent', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: '7px 14px', fontSize: 12, fontWeight: 600, color: 'var(--color-text-dim)', cursor: 'pointer' }}
              >
                ↻ Refresh
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

        {/* ── Tabs: Tasks | Bookings (Sessions removed) ────────────────────── */}
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
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 4 }}>No upcoming bookings</div>
                <div style={{ fontSize: 12, color: 'var(--color-text-faint)' }}>No arrivals or departures in the next 7 days</div>
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
    </DraftGuard>
  );
}
