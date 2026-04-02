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

// ── Responsive hooks ──────────────────────────────────────────────────────────

/** Returns true when viewport width < 640px (portrait mobile breakpoint) */
function useIsMobile(): boolean {
  const [mob, setMob] = useState(false);
  useEffect(() => {
    const check = () => setMob(window.innerWidth < 640);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);
  return mob;
}

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
  // Phase 1037: early checkout fields
  early_checkout_status?: string;
  early_checkout_eligible?: boolean;
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

function BookingRow({ booking, onClick, isMobile }: { booking: StreamBooking; onClick: () => void; isMobile: boolean }) {
  const isUrgent = booking.urgency_label.includes('Today');
  const isActive = booking.urgency_label.startsWith('Active Stay');
  const propName = booking.property_name || booking.property_id;
  const propCode = (booking.property_name && booking.property_id !== booking.property_name) ? booking.property_id : null;

  const urgencyColor = booking.urgency_label === 'Departing Today' ? '#ef4444'
    : booking.urgency_label === 'Arriving Today' ? '#10b981'
    : booking.urgency_label === 'Arriving Tomorrow' ? '#f59e0b'
    : isActive ? '#6366f1'
    : '#6b7280';

  const ecStatus = booking.early_checkout_status || 'none';
  const ecApproved = ecStatus === 'approved';
  const ecEligible = booking.early_checkout_eligible;

  // ── Mobile card layout (portrait < 640px) ────────────────────────────────
  if (isMobile) {
    return (
      <div
        onClick={onClick}
        style={{
          padding: '12px 14px',
          borderBottom: '1px solid var(--color-border)',
          background: isUrgent || isActive ? `${urgencyColor}06` : 'transparent',
          cursor: 'pointer',
          display: 'flex', flexDirection: 'column', gap: 6,
          borderLeft: `3px solid ${urgencyColor}`,
        }}
        onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-surface-2)')}
        onMouseLeave={e => (e.currentTarget.style.background = isUrgent || isActive ? `${urgencyColor}06` : 'transparent')}
      >
        {/* Row 1: property name + urgency chip */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--color-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
            {propName}
          </div>
          <span style={{
            fontSize: 10, fontWeight: 700, padding: '3px 8px', borderRadius: 20, flexShrink: 0,
            background: `${urgencyColor}18`, color: urgencyColor,
            border: `1px solid ${urgencyColor}33`, whiteSpace: 'nowrap',
          }}>
            {booking.urgency_label}
          </span>
        </div>
        {/* Row 2: guest + dates */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'space-between' }}>
          <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--color-text-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
            👤 {booking.guest_name}
            {ecApproved && (
              <span style={{ marginLeft: 6, fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 3, background: '#fef3c7', color: '#d97706', border: '1px solid #fde68a' }}>
                EARLY C/O
              </span>
            )}
          </div>
          <div style={{ fontSize: 10, color: 'var(--color-text-faint)', whiteSpace: 'nowrap', flexShrink: 0 }}>
            {fmtDate(booking.start_date)} → {fmtDate(booking.end_date)}
          </div>
        </div>
        {/* Row 3: ref code + action hint */}
        {(propCode || booking.external_ref || ecEligible) && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'space-between' }}>
            <span style={{ fontSize: 10, color: 'var(--color-text-faint)' }}>
              {propCode && <span style={{ marginRight: 6 }}>{propCode}</span>}
              {booking.external_ref && <span>{booking.external_ref}</span>}
            </span>
            {ecEligible && <span style={{ fontSize: 10, color: 'var(--color-primary)', fontWeight: 600 }}>Tap › action</span>}
          </div>
        )}
      </div>
    );
  }

  // ── Desktop table row layout ─────────────────────────────────────────────
  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '12px 20px',
        borderBottom: '1px solid var(--color-border)',
        background: isUrgent || isActive ? `${urgencyColor}06` : 'transparent',
        cursor: 'pointer',
        transition: 'background 120ms ease',
      }}
      onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-surface-2)')}
      onMouseLeave={e => (e.currentTarget.style.background = isUrgent || isActive ? `${urgencyColor}06` : 'transparent')}
    >
      {/* Urgency bar */}
      <div style={{
        width: 3, borderRadius: 2, alignSelf: 'stretch',
        background: urgencyColor, opacity: isActive ? 1.0 : 0.7, flexShrink: 0,
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

      {/* Guest + ref + dates */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--color-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {booking.guest_name}
          {ecApproved && (
            <span style={{ marginLeft: 6, fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 3, background: '#fef3c7', color: '#d97706', border: '1px solid #fde68a' }}>
              EARLY C/O
            </span>
          )}
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

      {ecEligible && (
        <span style={{ fontSize: 10, color: 'var(--color-text-faint)', flexShrink: 0 }}>›</span>
      )}
    </div>
  );
}

// ── Booking Action Panel (slide-in drawer for in-stay bookings) ────────────────
// Reuses EarlyCheckoutPanel logic via a lightweight fetch-and-render approach.
// Does NOT rebuild the early checkout flow — it links to the existing endpoint.

function BookingActionPanel({ booking, onClose }: { booking: StreamBooking; onClose: () => void }) {
  const [ecState, setEcState] = useState<{
    early_checkout_status: string;
    original_checkout_date: string;
    caller_can_approve: boolean;
    request: { recorded: boolean; proposed_date: string | null; source: string | null; note: string | null; at: string };
    approval: { approved: boolean; effective_at: string; effective_date: string; approved_by: string | null; approved_at: string; reason: string | null; approval_note: string | null };
    task: { task_id: string; due_date: string; is_early_checkout: boolean; status: string } | null;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadErr, setLoadErr] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [msg, setMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);

  // Request form
  const [reqSource, setReqSource] = useState('phone');
  const [reqDate, setReqDate] = useState('');
  const [reqNote, setReqNote] = useState('');
  // Approve form
  const [appDate, setAppDate] = useState('');
  const [appTime, setAppTime] = useState('11:00');
  const [appReason, setAppReason] = useState('');

  const loadState = useCallback(async () => {
    setLoading(true);
    setLoadErr('');
    try {
      const res = await apiFetch<{
        early_checkout_status: string;
        original_checkout_date: string;
        caller_can_approve: boolean;
        request: { recorded: boolean; proposed_date: string | null; source: string | null; note: string | null; at: string };
        approval: { approved: boolean; effective_at: string; effective_date: string; approved_by: string | null; approved_at: string; reason: string | null; approval_note: string | null };
        task: { task_id: string; due_date: string; is_early_checkout: boolean; status: string } | null;
      }>(`/admin/bookings/${booking.booking_id}/early-checkout`);
      setEcState(res);
      if (res.request?.proposed_date && !appDate) setAppDate(res.request.proposed_date);
      if (res.approval?.effective_date && !appDate) setAppDate(res.approval.effective_date);
    } catch (e) {
      setLoadErr((e as Error)?.message || 'Failed to load early checkout state.');
    }
    setLoading(false);
  }, [booking.booking_id]);

  useEffect(() => { loadState(); }, [loadState]);

  const flash = (type: 'ok' | 'err', text: string) => {
    setMsg({ type, text });
    setTimeout(() => setMsg(null), 4000);
  };

  const handleRequest = async () => {
    setSubmitting(true);
    try {
      await apiFetch(`/admin/bookings/${booking.booking_id}/early-checkout/request`, {
        method: 'POST',
        body: JSON.stringify({ request_source: reqSource, request_note: reqNote || undefined, proposed_date: reqDate || undefined }),
      });
      flash('ok', 'Request recorded.');
      await loadState();
    } catch (e) { flash('err', (e as Error)?.message || 'Request failed.'); }
    setSubmitting(false);
  };

  const handleApprove = async () => {
    if (!appDate) { flash('err', 'Effective checkout date is required.'); return; }
    setSubmitting(true);
    try {
      await apiFetch(`/admin/bookings/${booking.booking_id}/early-checkout/approve`, {
        method: 'POST',
        body: JSON.stringify({ early_checkout_date: appDate, early_checkout_time: appTime || '11:00', reason: appReason || undefined }),
      });
      flash('ok', `Approved. Checkout task rescheduled to ${appDate}.`);
      await loadState();
    } catch (e) { flash('err', (e as Error)?.message || 'Approval failed.'); }
    setSubmitting(false);
  };

  const propName = booking.property_name || booking.property_id;
  const ecStatus = ecState?.early_checkout_status || 'none';
  const canApprove = ecState?.caller_can_approve || false;
  const isCheckedIn = ['checked_in', 'active'].includes((booking.status || '').toLowerCase());

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 500, display: 'flex', justifyContent: 'flex-end',
    }}>
      {/* Backdrop */}
      <div onClick={onClose} style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.45)' }} />
      {/* Panel */}
      <div style={{
        position: 'relative', width: '100%', maxWidth: 480,
        background: 'var(--color-surface)', boxShadow: '-4px 0 40px rgba(0,0,0,0.25)',
        display: 'flex', flexDirection: 'column', overflowY: 'auto',
      }}>
        {/* Header */}
        <div style={{ padding: '20px 24px 14px', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--color-text)' }}>Booking Actions</div>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-text-dim)', marginTop: 2 }}>{propName}</div>
            <div style={{ fontSize: 11, color: 'var(--color-text-faint)', marginTop: 2 }}>
              {booking.guest_name} · {fmtDate(booking.start_date)} → {fmtDate(booking.end_date)}
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 20, color: 'var(--color-text-faint)', padding: '4px 8px', lineHeight: 1 }}>×</button>
        </div>

        <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Status badge */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 11, color: 'var(--color-text-dim)' }}>Early checkout status:</span>
            <span style={{
              fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 99,
              background: ecStatus === 'approved' ? '#dcfce7' : ecStatus === 'requested' ? '#fef3c7' : 'var(--color-surface-2)',
              color: ecStatus === 'approved' ? '#15803d' : ecStatus === 'requested' ? '#d97706' : 'var(--color-text-dim)',
            }}>
              {ecStatus === 'none' ? 'No early checkout' : ecStatus === 'requested' ? '⏳ Request received' : ecStatus === 'approved' ? '✅ Approved' : ecStatus === 'completed' ? '🏁 Completed' : ecStatus}
            </span>
          </div>

          {/* Feedback */}
          {msg && (
            <div style={{
              padding: '10px 14px', borderRadius: 8, fontSize: 12, fontWeight: 500,
              background: msg.type === 'ok' ? '#dcfce7' : '#fee2e2',
              color: msg.type === 'ok' ? '#15803d' : '#dc2626',
              border: `1px solid ${msg.type === 'ok' ? '#86efac' : '#fca5a5'}`,
            }}>
              {msg.type === 'ok' ? '✅' : '❌'} {msg.text}
            </div>
          )}

          {loading && <div style={{ fontSize: 12, color: 'var(--color-text-faint)' }}>Loading early checkout state…</div>}
          {!loading && loadErr && <div style={{ color: '#ef4444', fontSize: 12 }}>{loadErr}</div>}

          {/* APPROVED: show summary */}
          {!loading && !loadErr && ecStatus === 'approved' && ecState && (
            <div style={{ background: 'var(--color-bg)', border: '2px solid #86efac', borderRadius: 10, padding: '14px 16px', fontSize: 12 }}>
              <div style={{ fontWeight: 700, color: '#15803d', marginBottom: 8, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Approval Details</div>
              <div style={{ color: 'var(--color-text-dim)' }}>Effective date: <strong style={{ color: 'var(--color-text)' }}>{ecState.approval?.effective_date || '—'}</strong></div>
              <div style={{ color: 'var(--color-text-dim)', marginTop: 4 }}>Approved by: <strong style={{ color: 'var(--color-text)' }}>{ecState.approval?.approved_by || '—'}</strong></div>
              {ecState.approval?.reason && <div style={{ color: 'var(--color-text-dim)', marginTop: 4 }}>Reason: {ecState.approval.reason}</div>}
              {ecState.task?.is_early_checkout && (
                <div style={{ marginTop: 8, padding: '6px 10px', background: '#fef3c7', borderRadius: 6, fontSize: 11, color: '#d97706', fontWeight: 600 }}>
                  🔴 Checkout task rescheduled to {fmtDate(ecState.task.due_date)}
                </div>
              )}
            </div>
          )}

          {/* INTAKE FORM: none state, guest is checked in */}
          {!loading && !loadErr && ecStatus === 'none' && isCheckedIn && (
            <div style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', borderRadius: 10, padding: '14px 16px' }}>
              <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--color-text)', marginBottom: 12 }}>🔴 Record Early Departure Request</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Request source *</label>
                  <select value={reqSource} onChange={e => setReqSource(e.target.value)}
                    style={{ width: '100%', padding: '7px 10px', borderRadius: 7, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)', fontSize: 12 }}>
                    <option value="phone">📞 Phone call</option>
                    <option value="message">💬 Message</option>
                    <option value="guest_portal">🌐 Guest portal</option>
                    <option value="ops_escalation">⚡ Ops escalation</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Proposed date (optional)</label>
                  <input type="date" value={reqDate} onChange={e => setReqDate(e.target.value)}
                    style={{ width: '100%', padding: '7px 10px', borderRadius: 7, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)', fontSize: 12, boxSizing: 'border-box' }} />
                </div>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Staff note (optional)</label>
                  <textarea value={reqNote} onChange={e => setReqNote(e.target.value)} rows={2}
                    placeholder="e.g. Guest called, emergency flight change…"
                    style={{ width: '100%', padding: '7px 10px', borderRadius: 7, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)', fontSize: 12, resize: 'vertical', boxSizing: 'border-box' }} />
                </div>
                <button onClick={handleRequest} disabled={submitting || !reqSource}
                  style={{ padding: '9px 18px', borderRadius: 7, border: 'none', background: 'var(--color-primary)', color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer', opacity: submitting ? 0.6 : 1 }}>
                  {submitting ? 'Recording…' : 'Record Request →'}
                </button>
              </div>
            </div>
          )}

          {/* APPROVE FORM: requested state + caller can approve */}
          {!loading && !loadErr && ecStatus === 'requested' && canApprove && (
            <div style={{ background: 'var(--color-bg)', border: '2px solid #fde68a', borderRadius: 10, padding: '14px 16px' }}>
              <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--color-text)', marginBottom: 4 }}>✅ Grant Early Checkout Approval</div>
              <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginBottom: 12 }}>
                Original checkout: {fmtDate(ecState?.original_checkout_date)}.
                This will reschedule the checkout task and cleaning task.
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <div>
                    <label style={{ fontSize: 11, color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Effective date *</label>
                    <input type="date" value={appDate} onChange={e => setAppDate(e.target.value)}
                      max={ecState?.original_checkout_date}
                      style={{ width: '100%', padding: '7px 10px', borderRadius: 7, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)', fontSize: 12, boxSizing: 'border-box' }} />
                  </div>
                  <div>
                    <label style={{ fontSize: 11, color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Effective time</label>
                    <input type="time" value={appTime} onChange={e => setAppTime(e.target.value)}
                      style={{ width: '100%', padding: '7px 10px', borderRadius: 7, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)', fontSize: 12, boxSizing: 'border-box' }} />
                  </div>
                </div>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Reason / guest explanation</label>
                  <input type="text" value={appReason} onChange={e => setAppReason(e.target.value)}
                    placeholder="e.g. Flight change, family emergency…"
                    style={{ width: '100%', padding: '7px 10px', borderRadius: 7, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)', fontSize: 12, boxSizing: 'border-box' }} />
                </div>
                <div style={{ fontSize: 10, color: '#92400e', background: '#fef3c7', border: '1px solid #fde68a', borderRadius: 6, padding: '6px 10px' }}>
                  <strong>Operational scope only.</strong> Financial/refund adjustments must be handled separately through the booking channel.
                </div>
                <button onClick={handleApprove} disabled={submitting || !appDate}
                  style={{ padding: '9px 18px', borderRadius: 7, border: 'none', background: '#d97706', color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer', opacity: submitting || !appDate ? 0.6 : 1 }}>
                  {submitting ? 'Approving…' : '✅ Approve Early Check-out'}
                </button>
              </div>
            </div>
          )}

          {/* REQUEST PENDING, no approve right */}
          {!loading && !loadErr && ecStatus === 'requested' && !canApprove && (
            <div style={{ background: '#fef3c7', border: '1px solid #fde68a', borderRadius: 8, padding: '12px 14px', fontSize: 12, color: '#92400e' }}>
              ⏳ Request recorded. Awaiting approval from Admin or an authorized Operational Manager.
            </div>
          )}

          {/* COMPLETED */}
          {!loading && !loadErr && ecStatus === 'completed' && (
            <div style={{ background: '#dbeafe', border: '1px solid #93c5fd', borderRadius: 8, padding: '12px 14px', fontSize: 12, color: '#1d4ed8' }}>
              🏁 Early checkout completed.
            </div>
          )}

          {/* LATE CHECK-IN coordination note */}
          {!loading && isCheckedIn && (
            <div style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', borderRadius: 10, padding: '14px 16px' }}>
              <div style={{ fontWeight: 700, fontSize: 12, color: 'var(--color-text)', marginBottom: 6 }}>🕐 Late Arrival / Coordination</div>
              <div style={{ fontSize: 11, color: 'var(--color-text-dim)', lineHeight: 1.5 }}>
                Late arrival coordination is a booking-level operation. Use
                {' '}<strong>/manager/bookings</strong> to add coordination notes, update expected ETA,
                or set coordination status for this booking.
              </div>
            </div>
          )}
        </div>
      </div>
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
  // ── Phase 1038: persist activeTab to sessionStorage so orientation change
  // (which triggers a resize but NOT a remount) does NOT reset the tab.
  const [activeTab, setActiveTab] = useState<StreamTab>(() => {
    if (typeof window !== 'undefined') {
      const saved = sessionStorage.getItem('stream_active_tab') as StreamTab | null;
      if (saved === 'tasks' || saved === 'bookings') return saved;
    }
    return 'tasks';
  });

  const switchTab = useCallback((tab: StreamTab) => {
    setActiveTab(tab);
    if (typeof window !== 'undefined') sessionStorage.setItem('stream_active_tab', tab);
  }, []);

  const isMobile = useIsMobile();

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
  // Phase 1037: booking action panel state (early checkout / late arrival)
  const [activeBooking, setActiveBooking] = useState<StreamBooking | null>(null);

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
          <button style={tabBtn('tasks')} onClick={() => switchTab('tasks')}>
            Tasks {tasks.length > 0 && `(${tasks.length})`}
          </button>
          <button style={tabBtn('bookings')} onClick={() => switchTab('bookings')}>
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
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 4 }}>No active or upcoming bookings</div>
                <div style={{ fontSize: 12, color: 'var(--color-text-faint)', maxWidth: 360, margin: '0 auto', lineHeight: 1.5 }}>
                  {scopedPropertyIds.length > 0
                    ? `No checked-in or upcoming bookings in your ${scopedPropertyIds.length === 1 ? `scoped property (${scopedPropertyIds[0]})` : `${scopedPropertyIds.length} scoped properties`} in the next 7 days.`
                    : 'No checked-in or upcoming bookings in your scoped properties in the next 7 days.'
                  }
                </div>
              </div>
            )}
            {bookingsLoaded && !bookingsErr && bookings.length > 0 && (
              // ── Mobile portrait → card list; Desktop → table ──────────────
              isMobile ? (
                <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-xl)', overflow: 'hidden' }}>
                  {bookings.map(b => (
                    <BookingRow
                      key={b.booking_id}
                      booking={b}
                      isMobile={true}
                      onClick={() => b.early_checkout_eligible ? setActiveBooking(b) : undefined}
                    />
                  ))}
                </div>
              ) : (
                <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-xl)', overflow: 'hidden' }}>
                  {/* Column headers — desktop only */}
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
                    <BookingRow
                      key={b.booking_id}
                      booking={b}
                      isMobile={false}
                      onClick={() => b.early_checkout_eligible ? setActiveBooking(b) : undefined}
                    />
                  ))}
                </div>
              )
            )}
            <div style={{ marginTop: 12, fontSize: 11, color: 'var(--color-text-faint)', textAlign: 'center' }}>
              Active in-stay + arrivals/departures: yesterday → next 7 days · confirmed bookings only
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

      {/* ── Booking Action Panel (Phase 1037: early checkout / coordination) ── */}
      {activeBooking && (
        <BookingActionPanel
          booking={activeBooking}
          onClose={() => { setActiveBooking(null); loadBookings(); }}
        />
      )}
    </DraftGuard>
  );
}
