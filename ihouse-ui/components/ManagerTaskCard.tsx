'use client';

/**
 * Phase 1034 (OM-1) — ManagerTaskCard
 *
 * Manager intervention layer. Read-only timing strip + 3 intervention actions.
 * NOT a worker card. No Acknowledge/Start/Complete buttons.
 *
 * Manager layer:  Monitor · Takeover-Start · Reassign · Note
 * Worker layer:   Acknowledge → Start → Complete  (separate surface, not here)
 *
 * Used as a drill-down panel from:
 *   - Stream page (task event expand)
 *   - Alert rail (alert task_id link)
 *   - Task Board (row → expand instead of navigate)
 *
 * Receives the task object from the parent — no internal data fetching.
 * Parent responsible for load/refresh after mutations.
 */

import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from '@/lib/api';

// ── Types ─────────────────────────────────────────────────────────────────────

export type ManagerTaskCardTask = {
  id: string;
  task_kind: string;
  status: string;
  priority: string;
  property_id: string;
  property_name?: string;
  title?: string | null;
  due_date?: string | null;
  assigned_to?: string | null;
  original_worker_id?: string | null;
  taken_over_by?: string | null;
  taken_over_reason?: string | null;
  taken_over_at?: string | null;
  // Timing fields (from worker API, read-only for manager)
  ack_allowed_at?: string | null;
  ack_is_open?: boolean;
  start_allowed_at?: string | null;
  start_is_open?: boolean;
  // Notes (tasks.notes[] JSONB)
  notes?: NoteObj[] | null;
};

export type NoteObj = {
  id?: string;
  text: string;
  author_id?: string;
  author_name?: string;
  author_role?: string;
  created_at?: string;
  source?: string;
};

export type PropertyWorker = {
  user_id: string;
  display_name: string;
  role?: string;
  lane?: string;
  priority?: number;
  designation?: string;
  open_tasks?: number;
  is_active?: boolean;
};

// ── Constants ─────────────────────────────────────────────────────────────────

const STATUS_CHIP: Record<string, { color: string; bg: string; label: string }> = {
  PENDING:          { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)',  label: 'Pending' },
  ACKNOWLEDGED:     { color: '#3b82f6', bg: 'rgba(59,130,246,0.12)',  label: 'Acknowledged' },
  IN_PROGRESS:      { color: '#10b981', bg: 'rgba(16,185,129,0.12)',  label: 'In Progress' },
  MANAGER_EXECUTING:{ color: '#8b5cf6', bg: 'rgba(139,92,246,0.12)', label: 'Manager Executing' },
  COMPLETED:        { color: '#6b7280', bg: 'rgba(107,114,128,0.1)',  label: 'Completed' },
  CANCELED:         { color: '#ef4444', bg: 'rgba(239,68,68,0.1)',    label: 'Canceled' },
};

const PRIORITY_COLOR: Record<string, string> = {
  CRITICAL: '#ef4444', HIGH: '#f97316', NORMAL: '#6b7280', LOW: '#9ca3af',
};

const KIND_LABEL: Record<string, string> = {
  CLEANING: 'Cleaning', MAINTENANCE: 'Maintenance',
  CHECKIN_PREP: 'Check-in Prep', GUEST_WELCOME: 'Guest Welcome',
  CHECKOUT_VERIFY: 'Check-out', SELF_CHECKIN_FOLLOWUP: 'Self Check-in',
  GENERAL: 'General',
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function chip(color: string, bg: string, label: string) {
  return (
    <span style={{
      display: 'inline-block', fontSize: 10, fontWeight: 700,
      padding: '2px 8px', borderRadius: 20,
      background: bg, color,
      letterSpacing: '0.04em', whiteSpace: 'nowrap',
    }}>{label}</span>
  );
}

function fmtTime(iso?: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

function opensIn(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return 'now';
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

// ── Timing Strip ─────────────────────────────────────────────────────────────
// Read-only informational strip. No action buttons tied to worker gates.

function TimingStrip({ task }: { task: ManagerTaskCardTask }) {
  const hasGates = task.ack_allowed_at || task.start_allowed_at;
  if (!hasGates) return null;

  return (
    <div style={{
      background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.15)',
      borderRadius: 8, padding: '10px 14px', marginBottom: 12,
    }}>
      <div style={{ fontSize: 9, fontWeight: 700, color: '#818cf8', letterSpacing: '0.08em', marginBottom: 8 }}>
        WORKER TIMING GATES · Read-only — manager view
      </div>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        {task.ack_allowed_at && (
          <div>
            <div style={{ fontSize: 10, color: 'var(--color-text-faint)', marginBottom: 2 }}>ACK window opens</div>
            <div style={{ fontSize: 12, fontWeight: 600, color: task.ack_is_open ? '#10b981' : '#f59e0b' }}>
              {task.ack_is_open ? '✓ Open' : `In ${opensIn(task.ack_allowed_at)}`}
            </div>
            <div style={{ fontSize: 10, color: 'var(--color-text-faint)' }}>{fmtTime(task.ack_allowed_at)}</div>
          </div>
        )}
        {task.start_allowed_at && (
          <div>
            <div style={{ fontSize: 10, color: 'var(--color-text-faint)', marginBottom: 2 }}>START window opens</div>
            <div style={{ fontSize: 12, fontWeight: 600, color: task.start_is_open ? '#10b981' : '#f59e0b' }}>
              {task.start_is_open ? '✓ Open' : `In ${opensIn(task.start_allowed_at)}`}
            </div>
            <div style={{ fontSize: 10, color: 'var(--color-text-faint)' }}>{fmtTime(task.start_allowed_at)}</div>
          </div>
        )}
      </div>
      <div style={{ fontSize: 10, color: 'var(--color-text-faint)', marginTop: 8, lineHeight: 1.4 }}>
        Takeover bypasses these gates via the dedicated takeover-start route.
      </div>
    </div>
  );
}

// ── Takeover Start Panel ──────────────────────────────────────────────────────
// Uses POST /tasks/{id}/takeover-start — timing bypass route.
// Not the old /take-over (MANAGER_EXECUTING) path.

function TakeoverStartPanel({
  task, onDone, onCancel,
}: { task: ManagerTaskCardTask; onDone: () => void; onCancel: () => void }) {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const ineligible = ['COMPLETED', 'CANCELED', 'MANAGER_EXECUTING'].includes(task.status);

  const submit = async () => {
    setBusy(true); setErr('');
    try {
      await apiFetch(`/tasks/${task.id}/takeover-start`, {
        method: 'POST',
        body: JSON.stringify({ reason: reason || undefined }),
      });
      onDone();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Takeover failed');
      setBusy(false);
    }
  };

  if (ineligible) {
    return (
      <div style={{ padding: '12px 14px', background: 'rgba(107,114,128,0.08)', borderRadius: 8, fontSize: 12, color: 'var(--color-text-dim)' }}>
        Task is in <strong>{task.status}</strong> — takeover-start not applicable.
      </div>
    );
  }

  return (
    <div style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: '14px 16px' }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: '#f87171', marginBottom: 10 }}>
        ⚡ Takeover Start — bypasses worker timing gates
      </div>
      <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginBottom: 12, lineHeight: 1.5 }}>
        Task walks atomically: {task.status} → IN_PROGRESS. You become the assigned executor.
        The dedicated takeover-start route is the only timing bypass path — no global role bypass.
      </div>
      <textarea
        value={reason}
        onChange={e => setReason(e.target.value)}
        placeholder="Reason (optional)"
        rows={2}
        style={{
          width: '100%', boxSizing: 'border-box',
          padding: '8px 10px', borderRadius: 6, fontSize: 12,
          border: '1px solid var(--color-border)', background: 'var(--color-bg)',
          color: 'var(--color-text)', resize: 'none', fontFamily: 'inherit', marginBottom: 10,
        }}
      />
      {err && <div style={{ fontSize: 11, color: '#ef4444', marginBottom: 8 }}>⚠ {err}</div>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={onCancel} style={btnStyle('#6b7280')}>Cancel</button>
        <button onClick={submit} disabled={busy} style={btnStyle('#ef4444', busy)}>
          {busy ? 'Starting…' : '⚡ Confirm Takeover Start'}
        </button>
      </div>
    </div>
  );
}

// ── Reassign Panel ────────────────────────────────────────────────────────────
// Tier 1: property-scoped pool from /manager/team.
// Tier 2: manual ID input (explicit opt-in).

function ReassignPanel({
  task, onDone, onCancel,
}: { task: ManagerTaskCardTask; onDone: () => void; onCancel: () => void }) {
  const [workers, setWorkers] = useState<PropertyWorker[]>([]);
  const [loadingWorkers, setLoadingWorkers] = useState(true);
  const [selectedId, setSelectedId] = useState<string>('');
  const [manualId, setManualId] = useState('');
  const [showManual, setShowManual] = useState(false);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    setLoadingWorkers(true);
    apiFetch<{ properties: Array<{ property_id: string; workers: PropertyWorker[] }> }>('/manager/team')
      .then(res => {
        const prop = (res.properties || []).find(p => p.property_id === task.property_id);
        setWorkers(prop?.workers || []);
        if (!prop?.workers?.length) setShowManual(true);
      })
      .catch(() => setShowManual(true))
      .finally(() => setLoadingWorkers(false));
  }, [task.property_id]);

  const assigneeId = showManual ? manualId.trim() : selectedId;

  const submit = async () => {
    setBusy(true); setErr('');
    try {
      await apiFetch(`/tasks/${task.id}/reassign`, {
        method: 'POST',
        body: JSON.stringify({
          new_assignee_id: assigneeId || null,
          reason: reason || null,
        }),
      });
      onDone();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Reassign failed');
      setBusy(false);
    }
  };

  return (
    <div style={{ background: 'rgba(139,92,246,0.06)', border: '1px solid rgba(139,92,246,0.2)', borderRadius: 8, padding: '14px 16px' }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: '#a78bfa', marginBottom: 10 }}>
        👤 Reassign Task
      </div>

      {loadingWorkers ? (
        <div style={{ fontSize: 12, color: 'var(--color-text-faint)', marginBottom: 10 }}>Loading property workers…</div>
      ) : !showManual && workers.length > 0 ? (
        <>
          <div style={{ fontSize: 10, color: 'var(--color-text-faint)', marginBottom: 6 }}>
            PROPERTY WORKERS — {task.property_id} (Tier 1 scope)
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 10 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 6, background: selectedId === '' ? 'rgba(139,92,246,0.06)' : 'transparent', border: '1px solid var(--color-border)', cursor: 'pointer', fontSize: 12, color: 'var(--color-text-dim)' }}>
              <input type="radio" name="worker" value="" checked={selectedId === ''} onChange={() => setSelectedId('')} style={{ accentColor: '#8b5cf6' }} />
              Return to open pool (unassign)
            </label>
            {workers.map(w => (
              <label key={w.user_id} style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '8px 10px', borderRadius: 6,
                background: selectedId === w.user_id ? 'rgba(139,92,246,0.1)' : 'transparent',
                border: selectedId === w.user_id ? '1px solid rgba(139,92,246,0.35)' : '1px solid var(--color-border)',
                cursor: 'pointer', transition: 'all 0.12s',
              }}>
                <input type="radio" name="worker" value={w.user_id} checked={selectedId === w.user_id} onChange={() => setSelectedId(w.user_id)} style={{ accentColor: '#8b5cf6' }} />
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span style={{ fontWeight: 600, fontSize: 12, color: 'var(--color-text)' }}>{w.display_name}</span>
                  <span style={{ fontSize: 10, color: 'var(--color-text-faint)', marginLeft: 8 }}>{w.designation} · {w.lane}</span>
                  {(w.open_tasks ?? 0) > 0 && <span style={{ fontSize: 10, color: '#f59e0b', marginLeft: 6 }}>{w.open_tasks} tasks</span>}
                </span>
                {!w.is_active && <span style={{ fontSize: 9, color: '#ef4444' }}>INACTIVE</span>}
              </label>
            ))}
          </div>
          <button onClick={() => setShowManual(true)} style={{ fontSize: 11, color: '#a78bfa', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textDecoration: 'underline', marginBottom: 10 }}>
            Show all eligible workers (Tier 2)
          </button>
        </>
      ) : (
        <>
          <div style={{ fontSize: 10, color: 'var(--color-text-faint)', marginBottom: 4 }}>
            {showManual && !loadingWorkers && workers.length > 0
              ? 'Tier 2: Enter any worker ID'
              : 'Enter worker ID (leave blank for open pool)'}
          </div>
          <input
            value={manualId}
            onChange={e => setManualId(e.target.value)}
            placeholder="Worker user ID or leave blank"
            style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', borderRadius: 6, border: '1px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)', fontSize: 12, marginBottom: 10 }}
          />
          {workers.length > 0 && (
            <button onClick={() => setShowManual(false)} style={{ fontSize: 11, color: '#a78bfa', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textDecoration: 'underline', marginBottom: 10 }}>
              ← Back to property workers
            </button>
          )}
        </>
      )}

      <input
        value={reason}
        onChange={e => setReason(e.target.value)}
        placeholder="Reason for reassignment (optional)"
        style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', borderRadius: 6, border: '1px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)', fontSize: 12, marginBottom: 10 }}
      />
      {err && <div style={{ fontSize: 11, color: '#ef4444', marginBottom: 8 }}>⚠ {err}</div>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={onCancel} style={btnStyle('#6b7280')}>Cancel</button>
        <button onClick={submit} disabled={busy} style={btnStyle('#8b5cf6', busy)}>
          {busy ? 'Reassigning…' : '👤 Confirm Reassign'}
        </button>
      </div>
    </div>
  );
}

// ── Note Panel ────────────────────────────────────────────────────────────────

function NotePanel({
  taskId, onDone, onCancel,
}: { taskId: string; onDone: (note: NoteObj) => void; onCancel: () => void }) {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const submit = async () => {
    if (!text.trim()) return;
    setBusy(true); setErr('');
    try {
      const res = await apiFetch<{ note: NoteObj }>(`/tasks/${taskId}/notes`, {
        method: 'POST',
        body: JSON.stringify({ note: text.trim() }),
      });
      onDone(res.note);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Failed to add note');
      setBusy(false);
    }
  };

  return (
    <div style={{ background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 8, padding: '14px 16px' }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: '#fbbf24', marginBottom: 10 }}>✎ Add Operational Note</div>
      <textarea
        autoFocus
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder="Operational note — visible in manager surface, not visible to workers"
        rows={3}
        style={{
          width: '100%', boxSizing: 'border-box',
          padding: '8px 10px', borderRadius: 6, fontSize: 12,
          border: '1px solid var(--color-border)', background: 'var(--color-bg)',
          color: 'var(--color-text)', resize: 'vertical', fontFamily: 'inherit', marginBottom: 10,
        }}
      />
      {err && <div style={{ fontSize: 11, color: '#ef4444', marginBottom: 8 }}>⚠ {err}</div>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={onCancel} style={btnStyle('#6b7280')}>Cancel</button>
        <button onClick={submit} disabled={busy || !text.trim()} style={btnStyle('#f59e0b', busy || !text.trim())}>
          {busy ? 'Saving…' : '✎ Save Note'}
        </button>
      </div>
    </div>
  );
}

// ── Notes List ────────────────────────────────────────────────────────────────

function NotesList({ notes }: { notes: NoteObj[] }) {
  if (!notes.length) return (
    <div style={{ fontSize: 11, color: 'var(--color-text-faint)', padding: '8px 0', fontStyle: 'italic' }}>
      No notes yet
    </div>
  );
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {notes.map((n, i) => (
        <div key={n.id || i} style={{
          background: 'var(--color-bg)', border: '1px solid var(--color-border)',
          borderRadius: 8, padding: '10px 12px',
        }}>
          <div style={{ fontSize: 12, color: 'var(--color-text)', lineHeight: 1.5, marginBottom: 6 }}>
            {n.text}
          </div>
          <div style={{ fontSize: 10, color: 'var(--color-text-faint)', display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {n.author_name && <span>by <strong style={{ color: 'var(--color-text-dim)' }}>{n.author_name}</strong></span>}
            {n.author_role && <span>· {n.author_role}</span>}
            {n.source && <span>· {n.source}</span>}
            {n.created_at && <span>· {fmtTime(n.created_at)}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Button helper ─────────────────────────────────────────────────────────────

function btnStyle(color: string, disabled?: boolean): React.CSSProperties {
  return {
    padding: '7px 14px', borderRadius: 6, border: 'none',
    background: disabled ? 'var(--color-surface-3)' : `${color}22`,
    color: disabled ? 'var(--color-text-faint)' : color,
    fontSize: 12, fontWeight: 600, cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'background 0.12s',
    outline: `1px solid ${disabled ? 'transparent' : color}44`,
  };
}

// ── Action button in the main action bar ──────────────────────────────────────

type ActivePanel = null | 'takeover' | 'reassign' | 'note';

function ActionBar({
  task, activePanel, onSet,
}: { task: ManagerTaskCardTask; activePanel: ActivePanel; onSet: (p: ActivePanel) => void }) {
  const canTakeoverStart = !['COMPLETED', 'CANCELED', 'MANAGER_EXECUTING'].includes(task.status);

  const ab = (panel: ActivePanel, label: string, color: string, disabled?: boolean) => (
    <button
      onClick={() => onSet(activePanel === panel ? null : panel)}
      disabled={disabled}
      style={{
        padding: '8px 14px', borderRadius: 8, border: `1px solid ${color}44`,
        background: activePanel === panel ? `${color}22` : 'transparent',
        color: disabled ? 'var(--color-text-faint)' : color,
        fontSize: 12, fontWeight: 700,
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'all 0.12s', opacity: disabled ? 0.5 : 1,
        outline: activePanel === panel ? `1px solid ${color}66` : 'none',
      }}
    >{label}</button>
  );

  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', padding: '10px 0', borderTop: '1px solid var(--color-border)', borderBottom: '1px solid var(--color-border)', marginBottom: 12 }}>
      {ab('takeover', '⚡ Takeover', '#ef4444', !canTakeoverStart)}
      {ab('reassign', '👤 Reassign', '#8b5cf6')}
      {ab('note', '✎ Note', '#f59e0b')}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function ManagerTaskCard({
  task: initialTask,
  onClose,
  onMutated,
}: {
  task: ManagerTaskCardTask;
  onClose?: () => void;
  onMutated?: () => void;   // parent reload callback
}) {
  const [task, setTask] = useState<ManagerTaskCardTask>(initialTask);
  const [activePanel, setActivePanel] = useState<ActivePanel>(null);
  const [localNotes, setLocalNotes] = useState<NoteObj[]>(initialTask.notes || []);

  // Sync if parent passes updated task
  useEffect(() => {
    setTask(initialTask);
    setLocalNotes(initialTask.notes || []);
  }, [initialTask]);

  const sc = STATUS_CHIP[task.status] || STATUS_CHIP['PENDING'];
  const kindLabel = KIND_LABEL[task.task_kind] || task.task_kind;
  const priorityColor = PRIORITY_COLOR[task.priority] || '#6b7280';

  const handleTakeoverDone = useCallback(() => {
    setActivePanel(null);
    // Optimistically update status
    setTask(t => ({ ...t, status: 'IN_PROGRESS', assigned_to: 'you' }));
    onMutated?.();
  }, [onMutated]);

  const handleReassignDone = useCallback(() => {
    setActivePanel(null);
    setTask(t => ({ ...t, status: 'PENDING' }));
    onMutated?.();
  }, [onMutated]);

  const handleNoteDone = useCallback((newNote: NoteObj) => {
    setActivePanel(null);
    setLocalNotes(n => [...n, newNote]);
    // Don't reload parent — note is appended in-place
  }, []);

  return (
    <div style={{
      background: 'var(--color-surface)',
      border: '1px solid var(--color-border)',
      borderRadius: 12,
      overflow: 'hidden',
    }}>
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div style={{
        padding: '14px 16px',
        borderBottom: '1px solid var(--color-border)',
        background: 'linear-gradient(135deg, rgba(99,102,241,0.06), rgba(139,92,246,0.03))',
        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
      }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Manager layer badge — makes explicit this is oversight, not execution */}
          <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', color: '#818cf8', marginBottom: 6 }}>
            MANAGER INTERVENTION LAYER
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: priorityColor, display: 'inline-block', flexShrink: 0,
            }} />
            <span style={{ fontWeight: 700, fontSize: 15, color: 'var(--color-text)', lineHeight: 1.2 }}>
              {task.title || kindLabel}
            </span>
            {chip(sc.color, sc.bg, sc.label)}
          </div>
          <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--color-text-faint)', flexWrap: 'wrap', paddingLeft: 16 }}>
            <span>📍 {task.property_name || task.property_id}</span>
            <span>{kindLabel}</span>
            {task.due_date && <span>Due {fmtTime(task.due_date)}</span>}
            {task.priority !== 'NORMAL' && (
              <span style={{ color: priorityColor, fontWeight: 700 }}>{task.priority}</span>
            )}
          </div>
        </div>
        {onClose && (
          <button onClick={onClose} style={{
            background: 'none', border: 'none', fontSize: 18, cursor: 'pointer',
            color: 'var(--color-text-dim)', padding: '0 0 0 8px', lineHeight: 1, flexShrink: 0,
          }}>✕</button>
        )}
      </div>

      {/* ── Body ─────────────────────────────────────────────────────────── */}
      <div style={{ padding: '14px 16px' }}>

        {/* Worker info row */}
        <div style={{
          display: 'flex', gap: 16, flexWrap: 'wrap',
          fontSize: 11, color: 'var(--color-text-dim)',
          marginBottom: 12, paddingBottom: 12,
          borderBottom: '1px solid var(--color-border)',
        }}>
          {task.assigned_to && (
            <span>Worker: <strong style={{ color: 'var(--color-text)', fontFamily: 'var(--font-mono)' }}>{task.assigned_to.slice(0, 14)}…</strong></span>
          )}
          {task.taken_over_by && (
            <span style={{ color: '#f87171' }}>↩ Taken by: <strong>{task.taken_over_by.slice(0, 14)}…</strong></span>
          )}
          {task.taken_over_reason && (
            <span>Reason: <strong>{task.taken_over_reason.replace(/_/g, ' ')}</strong></span>
          )}
          {task.original_worker_id && (
            <span>Original: <strong style={{ fontFamily: 'var(--font-mono)' }}>{task.original_worker_id.slice(0, 14)}…</strong></span>
          )}
          {!task.assigned_to && !task.taken_over_by && (
            <span style={{ color: '#f59e0b', fontWeight: 600 }}>⚠ No assigned worker</span>
          )}
        </div>

        {/* Read-only timing strip */}
        <TimingStrip task={task} />

        {/* Action bar — manager-only actions, no worker buttons */}
        <ActionBar task={task} activePanel={activePanel} onSet={setActivePanel} />

        {/* Active intervention panel */}
        {activePanel === 'takeover' && (
          <div style={{ marginBottom: 12 }}>
            <TakeoverStartPanel
              task={task}
              onDone={handleTakeoverDone}
              onCancel={() => setActivePanel(null)}
            />
          </div>
        )}
        {activePanel === 'reassign' && (
          <div style={{ marginBottom: 12 }}>
            <ReassignPanel
              task={task}
              onDone={handleReassignDone}
              onCancel={() => setActivePanel(null)}
            />
          </div>
        )}
        {activePanel === 'note' && (
          <div style={{ marginBottom: 12 }}>
            <NotePanel
              taskId={task.id}
              onDone={handleNoteDone}
              onCancel={() => setActivePanel(null)}
            />
          </div>
        )}

        {/* Notes section — always visible, shows after panel actions */}
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-text-faint)', letterSpacing: '0.06em', marginBottom: 8 }}>
            OPERATIONAL NOTES ({localNotes.length})
          </div>
          <NotesList notes={localNotes} />
        </div>
      </div>
    </div>
  );
}

// ── Slide-in Drawer Wrapper ───────────────────────────────────────────────────
// Used by Stream page and Alert rail — slides in from right on task expand.

export function ManagerTaskDrawer({
  task,
  onClose,
  onMutated,
}: {
  task: ManagerTaskCardTask;
  onClose: () => void;
  onMutated?: () => void;
}) {
  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(2px)',
          zIndex: 490,
        }}
      />
      {/* Panel */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0,
        width: 'min(480px, 92vw)',
        background: 'var(--color-surface)',
        borderLeft: '1px solid var(--color-border)',
        boxShadow: '-10px 0 40px rgba(0,0,0,0.3)',
        zIndex: 500,
        overflowY: 'auto',
        animation: 'mtcSlideIn 0.2s ease-out',
      }}>
        <ManagerTaskCard task={task} onClose={onClose} onMutated={onMutated} />
      </div>
      <style>{`
        @keyframes mtcSlideIn {
          from { transform: translateX(100%); opacity: 0.7; }
          to   { transform: translateX(0);    opacity: 1; }
        }
      `}</style>
    </>
  );
}
