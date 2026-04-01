'use client';

/**
 * Phase 1034 (OM-1) — ManagerTaskCard
 * Phase 1035 — Reassign UX hardening
 *
 * Manager intervention layer. Read-only timing strip + 3 intervention actions.
 * NOT a worker card. No Acknowledge/Start/Complete buttons.
 *
 * Manager layer:  Monitor · Takeover-Start · Reassign · Note
 * Worker layer:   Acknowledge → Start → Complete  (separate surface, not here)
 *
 * Phase 1035 changes:
 *   - ReassignPanel: compatibility-filtered selector by task_kind → lane
 *   - ReassignPanel: shows current worker name (not UUID)
 *   - ReassignPanel: explicit handoff note field (worker-visible, source="handoff")
 *     vs manager reason (internal only, audit storage)
 *   - Worker info row: resolves display names from task data
 *   - Note semantics: clearly labelled "internal manager note, not visible to workers"
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
  assigned_to_name?: string | null;       // Phase 1035: resolved display name
  original_worker_id?: string | null;
  original_worker_name?: string | null;   // Phase 1035: resolved display name
  taken_over_by?: string | null;
  taken_over_by_name?: string | null;     // Phase 1035: resolved display name
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
  source?: string;         // 'manager_note' | 'handoff' | 'system'
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

// task_kind → lane for compatibility filtering
const KIND_TO_LANE: Record<string, string> = {
  CLEANING:             'CLEANING',
  GENERAL_CLEANING:     'CLEANING',
  CHECKIN_PREP:         'CHECKIN_CHECKOUT',
  GUEST_WELCOME:        'CHECKIN_CHECKOUT',
  SELF_CHECKIN_FOLLOWUP:'CHECKIN_CHECKOUT',
  CHECKOUT_VERIFY:      'CHECKIN_CHECKOUT',
  MAINTENANCE:          'MAINTENANCE',
};

const LANE_LABEL: Record<string, string> = {
  CLEANING: 'Cleaning staff',
  CHECKIN_CHECKOUT: 'Check-in / Check-out staff',
  MAINTENANCE: 'Maintenance staff',
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

/** Short display name: use resolved name, fall back to truncated UUID */
function workerLabel(name?: string | null, uuid?: string | null): string | null {
  if (name && name.trim()) return name;
  if (uuid && uuid.trim()) return uuid.slice(0, 12) + '…';
  return null;
}

// ── Timing Strip ─────────────────────────────────────────────────────────────

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
        The dedicated takeover-start route is the only timing bypass path.
      </div>
      <textarea
        value={reason}
        onChange={e => setReason(e.target.value)}
        placeholder="Reason (optional) — for internal audit trail"
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
// Phase 1035:
//   - Requires /manager/team?task_kind={kind} to get compatibility-filtered workers
//   - Shows current assignee name at top
//   - Worker selector: name first, with designation + load hints
//   - Handoff note: separate from manager reason — written to tasks.notes[], worker-visible
//   - Manager reason: internal only, audit storage only

function ReassignPanel({
  task, onDone, onCancel,
}: { task: ManagerTaskCardTask; onDone: () => void; onCancel: () => void }) {
  const [workers, setWorkers] = useState<PropertyWorker[]>([]);
  const [loadingWorkers, setLoadingWorkers] = useState(true);
  const [workerError, setWorkerError] = useState('');
  const [selectedId, setSelectedId] = useState<string>('');
  const [showManual, setShowManual] = useState(false);
  const [manualId, setManualId] = useState('');
  const [reason, setReason] = useState('');          // internal manager reason (audit only)
  const [handoffNote, setHandoffNote] = useState('');// worker-visible handoff message
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const taskKind = task.task_kind || '';
  const compatLane = KIND_TO_LANE[taskKind] || '';
  const laneLabel = compatLane ? (LANE_LABEL[compatLane] || compatLane) : 'all workers';

  // Current assignee label
  const currentWorker = workerLabel(task.assigned_to_name, task.assigned_to);

  useEffect(() => {
    setLoadingWorkers(true);
    setWorkerError('');
    // Phase 1035: pass task_kind so backend returns only compatible workers
    const qs = taskKind ? `?task_kind=${encodeURIComponent(taskKind)}` : '';
    apiFetch<{ properties: Array<{ property_id: string; workers: PropertyWorker[] }> }>(`/manager/team${qs}`)
      .then(res => {
        const prop = (res.properties || []).find(p => p.property_id === task.property_id);
        const compatible = prop?.workers || [];
        setWorkers(compatible);
      if (!compatible.length) {
          // No property-scoped compatible workers — go straight to manual
          setShowManual(true);
          const propDisplay = task.property_name || task.property_id || 'this property';
          setWorkerError(
            compatLane
              ? `No ${laneLabel} found for ${propDisplay}. Enter the worker ID below or leave blank to unassign.`
              : `No workers found for ${propDisplay}.`
          );
        }
      })
      .catch(() => {
        setShowManual(true);
        setWorkerError('Could not load property workers. Use manual entry.');
      })
      .finally(() => setLoadingWorkers(false));
  }, [task.property_id, taskKind, compatLane, laneLabel]);

  const assigneeId = showManual ? manualId.trim() : selectedId;

  const submit = async () => {
    setBusy(true); setErr('');
    try {
      await apiFetch(`/tasks/${task.id}/reassign`, {
        method: 'POST',
        body: JSON.stringify({
          new_assignee_id: assigneeId || null,
          reason: reason || null,
          handoff_note: handoffNote || null,
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
      <div style={{ fontSize: 11, fontWeight: 700, color: '#a78bfa', marginBottom: 12 }}>
        👤 Reassign Task
      </div>

      {/* Current assignee */}
      <div style={{
        background: 'rgba(139,92,246,0.06)', borderRadius: 6,
        padding: '8px 12px', marginBottom: 14,
        fontSize: 12, color: 'var(--color-text-dim)',
        borderLeft: '3px solid rgba(139,92,246,0.35)',
      }}>
        <span style={{ fontSize: 10, color: 'var(--color-text-faint)', display: 'block', marginBottom: 2 }}>CURRENTLY ASSIGNED TO</span>
        {currentWorker
          ? <strong style={{ color: 'var(--color-text)' }}>{currentWorker}</strong>
          : <span style={{ color: '#f59e0b', fontWeight: 600 }}>⚠ Unassigned (open pool)</span>
        }
      </div>

      {/* Worker selector */}
      {loadingWorkers ? (
        <div style={{ fontSize: 12, color: 'var(--color-text-faint)', marginBottom: 12 }}>
          Loading compatible workers…
        </div>
      ) : !showManual && workers.length > 0 ? (
        <>
          <div style={{ fontSize: 10, color: 'var(--color-text-faint)', marginBottom: 6 }}>
            REASSIGN TO — {laneLabel || 'property workers'} · {task.property_id}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 12 }}>
            {/* Unassign option */}
            <label style={workerRowStyle(selectedId === '')}>
              <input type="radio" name="worker" value="" checked={selectedId === ''}
                onChange={() => setSelectedId('')} style={{ accentColor: '#8b5cf6' }} />
              <span style={{ fontSize: 12, color: 'var(--color-text-dim)', fontStyle: 'italic' }}>
                Return to open pool (unassign)
              </span>
            </label>
            {workers.map(w => (
              <label key={w.user_id} style={workerRowStyle(selectedId === w.user_id)}>
                <input type="radio" name="worker" value={w.user_id}
                  checked={selectedId === w.user_id}
                  onChange={() => setSelectedId(w.user_id)}
                  style={{ accentColor: '#8b5cf6' }} />
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--color-text)' }}>
                    {w.display_name || w.user_id.slice(0, 14) + '…'}
                  </span>
                  <span style={{ fontSize: 10, color: 'var(--color-text-faint)', marginLeft: 8 }}>
                    {w.designation}
                    {w.lane && ` · ${w.lane.replace('_', '/')}`}
                  </span>
                  {(w.open_tasks ?? 0) > 0 && (
                    <span style={{
                      fontSize: 10, marginLeft: 6, fontWeight: 600,
                      color: (w.open_tasks ?? 0) >= 3 ? '#ef4444' : '#f59e0b',
                    }}>
                      {w.open_tasks} open task{(w.open_tasks ?? 0) !== 1 ? 's' : ''}
                    </span>
                  )}
                  {(w.open_tasks ?? 0) === 0 && (
                    <span style={{ fontSize: 10, marginLeft: 6, color: '#10b981', fontWeight: 600 }}>free</span>
                  )}
                </span>
                {!w.is_active && <span style={{ fontSize: 9, color: '#ef4444', fontWeight: 700 }}>INACTIVE</span>}
              </label>
            ))}
          </div>
          <button
            onClick={() => setShowManual(true)}
            style={{ fontSize: 11, color: '#a78bfa', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textDecoration: 'underline', marginBottom: 14 }}
          >
            Not seeing the right worker? Enter ID manually
          </button>
        </>
      ) : (
        <>
          {workerError && (
            <div style={{ fontSize: 11, color: '#f59e0b', marginBottom: 8, lineHeight: 1.4 }}>⚠ {workerError}</div>
          )}
          <div style={{ fontSize: 10, color: 'var(--color-text-faint)', marginBottom: 4 }}>
            Worker user ID (UUID)
          </div>
          <input
            value={manualId}
            onChange={e => setManualId(e.target.value)}
            placeholder="Paste worker user ID, or leave blank to unassign"
            style={inputStyle}
          />
          {workers.length > 0 && (
            <button
              onClick={() => setShowManual(false)}
              style={{ fontSize: 11, color: '#a78bfa', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textDecoration: 'underline', marginBottom: 14 }}
            >
              ← Back to worker list
            </button>
          )}
        </>
      )}

      {/* ── Communication fields ─────────────────────────────────────────── */}
      <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: 12, marginTop: 4 }}>

        {/* Handoff note — worker-visible */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: '#10b981', marginBottom: 4, letterSpacing: '0.04em' }}>
            HANDOFF MESSAGE
            <span style={{ fontWeight: 400, color: 'var(--color-text-faint)', marginLeft: 6 }}>
              — visible to the new worker on their task surface
            </span>
          </div>
          <textarea
            value={handoffNote}
            onChange={e => setHandoffNote(e.target.value)}
            placeholder="Instructions for new worker e.g. Guest arriving 3pm, prioritise check-in prep"
            rows={2}
            style={{
              width: '100%', boxSizing: 'border-box' as const,
              padding: '8px 10px', borderRadius: 6,
              border: '1px solid var(--color-border)',
              background: 'var(--color-bg)', color: 'var(--color-text)',
              fontSize: 12, marginBottom: 10, fontFamily: 'inherit',
              resize: 'vertical' as const,
            }}
          />
        </div>

        {/* Manager reason — internal only */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: '#6b7280', marginBottom: 4, letterSpacing: '0.04em' }}>
            REASON FOR REASSIGNMENT
            <span style={{ fontWeight: 400, color: 'var(--color-text-faint)', marginLeft: 6 }}>
              — internal audit only, not shown to workers
            </span>
          </div>
          <input
            value={reason}
            onChange={e => setReason(e.target.value)}
            placeholder="e.g. Worker unavailable, skill mismatch, schedule conflict"
            style={inputStyle}
          />
        </div>
      </div>

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
// Phase 1035 semantics: this is an INTERNAL manager note.
// It is stored in tasks.notes[] with source="manager_note".
// It is NOT shown on the worker task surface (no handoff intent).
// Use the Reassign panel's Handoff Message field for worker-facing communication.

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
      <div style={{ fontSize: 11, fontWeight: 700, color: '#fbbf24', marginBottom: 4 }}>✎ Internal Manager Note</div>
      <div style={{ fontSize: 10, color: 'var(--color-text-faint)', marginBottom: 10, lineHeight: 1.4 }}>
        Stored in manager audit trail. Not shown to workers.
        To send a message to the new worker during reassignment, use the Handoff Message field in the Reassign panel.
      </div>
      <textarea
        autoFocus
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder="Operational note for manager/admin record…"
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

const NOTE_SOURCE_LABEL: Record<string, { label: string; color: string }> = {
  handoff:      { label: 'Handoff →',  color: '#10b981' },
  manager_note: { label: 'Mgr Note',   color: '#f59e0b' },
  system:       { label: 'System',     color: '#6b7280' },
};

function NotesList({ notes }: { notes: NoteObj[] }) {
  if (!notes.length) return (
    <div style={{ fontSize: 11, color: 'var(--color-text-faint)', padding: '8px 0', fontStyle: 'italic' }}>
      No notes yet
    </div>
  );
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {notes.map((n, i) => {
        const src = n.source ? NOTE_SOURCE_LABEL[n.source] : null;
        return (
          <div key={n.id || i} style={{
            background: 'var(--color-bg)', border: '1px solid var(--color-border)',
            borderRadius: 8, padding: '10px 12px',
            borderLeft: src ? `3px solid ${src.color}44` : '3px solid var(--color-border)',
          }}>
            {src && (
              <div style={{ fontSize: 9, fontWeight: 700, color: src.color, letterSpacing: '0.06em', marginBottom: 4 }}>
                {src.label}
              </div>
            )}
            <div style={{ fontSize: 12, color: 'var(--color-text)', lineHeight: 1.5, marginBottom: 6 }}>
              {n.text}
            </div>
            <div style={{ fontSize: 10, color: 'var(--color-text-faint)', display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {n.author_name && <span>by <strong style={{ color: 'var(--color-text-dim)' }}>{n.author_name}</strong></span>}
              {n.author_role && <span>· {n.author_role}</span>}
              {n.created_at && <span>· {fmtTime(n.created_at)}</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Style helpers ─────────────────────────────────────────────────────────────

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

function workerRowStyle(selected: boolean): React.CSSProperties {
  return {
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '9px 12px', borderRadius: 8,
    background: selected ? 'rgba(139,92,246,0.10)' : 'transparent',
    border: selected ? '1px solid rgba(139,92,246,0.35)' : '1px solid var(--color-border)',
    cursor: 'pointer', transition: 'all 0.12s',
  };
}

const inputStyle: React.CSSProperties = {
  width: '100%', boxSizing: 'border-box',
  padding: '8px 10px', borderRadius: 6,
  border: '1px solid var(--color-border)',
  background: 'var(--color-bg)',
  color: 'var(--color-text)',
  fontSize: 12, marginBottom: 10,
  fontFamily: 'inherit',
};

// ── Action bar ────────────────────────────────────────────────────────────────

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
  onMutated?: () => void;
}) {
  const [task, setTask] = useState<ManagerTaskCardTask>(initialTask);
  const [activePanel, setActivePanel] = useState<ActivePanel>(null);
  const [localNotes, setLocalNotes] = useState<NoteObj[]>(initialTask.notes || []);

  useEffect(() => {
    setTask(initialTask);
    setLocalNotes(initialTask.notes || []);
  }, [initialTask]);

  const sc = STATUS_CHIP[task.status] || STATUS_CHIP['PENDING'];
  const kindLabel = KIND_LABEL[task.task_kind] || task.task_kind;
  const priorityColor = PRIORITY_COLOR[task.priority] || '#6b7280';

  const handleTakeoverDone = useCallback(() => {
    setActivePanel(null);
    setTask(t => ({ ...t, status: 'IN_PROGRESS' }));
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
  }, []);

  return (
    <div style={{
      background: 'var(--color-surface)',
      border: '1px solid var(--color-border)',
      borderRadius: 12,
      overflow: 'hidden',
    }}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={{
        padding: '14px 16px',
        borderBottom: '1px solid var(--color-border)',
        background: 'linear-gradient(135deg, rgba(99,102,241,0.06), rgba(139,92,246,0.03))',
        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
      }}>
        <div style={{ flex: 1, minWidth: 0 }}>
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

      {/* ── Body ──────────────────────────────────────────────────────────── */}
      <div style={{ padding: '14px 16px' }}>

        {/* Worker info row — Phase 1035: display names, not UUIDs */}
        <div style={{
          display: 'flex', gap: 12, flexWrap: 'wrap',
          fontSize: 11, color: 'var(--color-text-dim)',
          marginBottom: 12, paddingBottom: 12,
          borderBottom: '1px solid var(--color-border)',
        }}>
          {(task.assigned_to || task.assigned_to_name) ? (
            <span>
              Worker: <strong style={{ color: 'var(--color-text)' }}>
                {workerLabel(task.assigned_to_name, task.assigned_to)}
              </strong>
            </span>
          ) : null}
          {(task.taken_over_by || task.taken_over_by_name) && (
            <span style={{ color: '#f87171' }}>
              ↩ Taken by: <strong>{workerLabel(task.taken_over_by_name, task.taken_over_by)}</strong>
            </span>
          )}
          {task.taken_over_reason && (
            <span>Reason: <strong>{task.taken_over_reason.replace(/_/g, ' ')}</strong></span>
          )}
          {(task.original_worker_id || task.original_worker_name) && (
            <span>
              Original: <strong>{workerLabel(task.original_worker_name, task.original_worker_id)}</strong>
            </span>
          )}
          {!task.assigned_to && !task.taken_over_by && (
            <span style={{ color: '#f59e0b', fontWeight: 600 }}>⚠ No assigned worker</span>
          )}
        </div>

        {/* Read-only timing strip */}
        <TimingStrip task={task} />

        {/* Action bar */}
        <ActionBar task={task} activePanel={activePanel} onSet={setActivePanel} />

        {/* Active panel */}
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

        {/* Notes — always visible */}
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
