'use client';

/**
 * Phase 1033 — /manager/tasks
 * Operational Manager scoped task board.
 *
 * Calls GET /manager/tasks (property-scoped) — NOT /tasks (unscoped).
 * Includes lane filter, status filter, takeover, reassign, note, ad-hoc task.
 * Reuses TakeoverModal and ManagerExecutionDrawer from /manager/page.tsx via API.
 */

import { useState, useEffect, useCallback } from 'react';
import { api } from '../../../../lib/api';
import { useRouter } from 'next/navigation';
import DraftGuard from '../../../../components/DraftGuard';

// ── Types ────────────────────────────────────────────────────────────────────

type Task = {
  id: string;
  task_kind: string;
  status: string;
  priority: string;
  property_id: string;
  assigned_to?: string | null;
  taken_over_by?: string | null;
  taken_over_reason?: string | null;
  due_date?: string | null;
  title?: string | null;
};

type Groups = {
  manager_executing: Task[];
  pending: Task[];
  acknowledged: Task[];
  in_progress: Task[];
};

type Lane = 'ALL' | 'CLEANING' | 'CHECKIN_PREP' | 'GUEST_WELCOME' | 'CHECKOUT_VERIFY' | 'MAINTENANCE' | 'GENERAL';
const LANES: Lane[] = ['ALL', 'CLEANING', 'CHECKIN_PREP', 'GUEST_WELCOME', 'CHECKOUT_VERIFY', 'MAINTENANCE'];
const LANE_LABELS: Record<Lane, string> = {
  ALL: 'All',
  CLEANING: 'Cleaning',
  CHECKIN_PREP: 'Check-in',
  GUEST_WELCOME: 'Welcome',
  CHECKOUT_VERIFY: 'Check-out',
  MAINTENANCE: 'Maintenance',
  GENERAL: 'General',
};

const STATUS_COLORS: Record<string, string> = {
  PENDING: '#f59e0b',
  ACKNOWLEDGED: '#3b82f6',
  IN_PROGRESS: '#10b981',
  MANAGER_EXECUTING: '#8b5cf6',
  COMPLETED: '#6b7280',
  CANCELED: '#ef4444',
};

const PRIORITY_DOT: Record<string, string> = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  NORMAL: '#6b7280',
  LOW: '#9ca3af',
};

function fmtDate(d?: string | null) {
  if (!d) return '—';
  try { return new Date(d).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
  catch { return d; }
}

// ── Note Modal ───────────────────────────────────────────────────────────────

function NoteModal({ taskId, onClose }: { taskId: string; onClose: () => void }) {
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    if (!note.trim()) return;
    setSaving(true);
    try {
      await api.post<{ status: string }>(`/tasks/${taskId}/notes`, { note });
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to add note');
      setSaving(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60,
    }}>
      <div style={{
        background: 'var(--color-surface)', borderRadius: 12, padding: 28,
        width: '100%', maxWidth: 440, boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
      }}>
        <h3 style={{ margin: '0 0 16px', fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--color-text)' }}>
          Add Operational Note
        </h3>
        <textarea
          autoFocus
          value={note}
          onChange={e => setNote(e.target.value)}
          placeholder="Enter operational note…"
          rows={4}
          style={{
            width: '100%', padding: '10px 12px', borderRadius: 8,
            border: '1px solid var(--color-border)', background: 'var(--color-bg)',
            color: 'var(--color-text)', fontSize: 'var(--text-sm)', resize: 'vertical',
            boxSizing: 'border-box',
          }}
        />
        {error && <p style={{ color: 'var(--color-error, #ef4444)', fontSize: 'var(--text-xs)', margin: '8px 0 0' }}>{error}</p>}
        <div style={{ display: 'flex', gap: 10, marginTop: 16, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{
            padding: '8px 18px', borderRadius: 8, border: '1px solid var(--color-border)',
            background: 'transparent', cursor: 'pointer', color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)',
          }}>Cancel</button>
          <button onClick={submit} disabled={saving || !note.trim()} style={{
            padding: '8px 18px', borderRadius: 8, border: 'none',
            background: 'var(--color-primary)', color: '#fff', cursor: 'pointer',
            fontSize: 'var(--text-sm)', fontWeight: 600, opacity: saving ? 0.7 : 1,
          }}>{saving ? 'Saving…' : 'Save Note'}</button>
        </div>
      </div>
    </div>
  );
}

// ── Reassign Modal ────────────────────────────────────────────────────────────

function ReassignModal({ task, onClose, onDone }: { task: Task; onClose: () => void; onDone: () => void }) {
  const [assigneeId, setAssigneeId] = useState('');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    setSaving(true);
    try {
      await api.post<{ status: string }>(`/tasks/${task.id}/reassign`, {
        new_assignee_id: assigneeId || null,
        reason: reason || null,
      });
      onDone();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to reassign');
      setSaving(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60,
    }}>
      <div style={{
        background: 'var(--color-surface)', borderRadius: 12, padding: 28,
        width: '100%', maxWidth: 440, boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
      }}>
        <h3 style={{ margin: '0 0 6px', fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--color-text)' }}>
          Reassign Task
        </h3>
        <p style={{ margin: '0 0 16px', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
          {task.title || task.task_kind} · {task.property_id}
        </p>
        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
          Worker ID (leave blank to return to open pool)
        </label>
        <input
          autoFocus
          value={assigneeId}
          onChange={e => setAssigneeId(e.target.value)}
          placeholder="Worker user ID or leave blank"
          style={{
            width: '100%', padding: '8px 12px', borderRadius: 8,
            border: '1px solid var(--color-border)', background: 'var(--color-bg)',
            color: 'var(--color-text)', fontSize: 'var(--text-sm)', boxSizing: 'border-box', marginBottom: 12,
          }}
        />
        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
          Reason (optional)
        </label>
        <input
          value={reason}
          onChange={e => setReason(e.target.value)}
          placeholder="Reason for reassignment"
          style={{
            width: '100%', padding: '8px 12px', borderRadius: 8,
            border: '1px solid var(--color-border)', background: 'var(--color-bg)',
            color: 'var(--color-text)', fontSize: 'var(--text-sm)', boxSizing: 'border-box',
          }}
        />
        {error && <p style={{ color: 'var(--color-error, #ef4444)', fontSize: 'var(--text-xs)', margin: '8px 0 0' }}>{error}</p>}
        <div style={{ display: 'flex', gap: 10, marginTop: 16, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{
            padding: '8px 18px', borderRadius: 8, border: '1px solid var(--color-border)',
            background: 'transparent', cursor: 'pointer', color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)',
          }}>Cancel</button>
          <button onClick={submit} disabled={saving} style={{
            padding: '8px 18px', borderRadius: 8, border: 'none',
            background: '#8b5cf6', color: '#fff', cursor: 'pointer',
            fontSize: 'var(--text-sm)', fontWeight: 600, opacity: saving ? 0.7 : 1,
          }}>{saving ? 'Reassigning…' : 'Reassign'}</button>
        </div>
      </div>
    </div>
  );
}

// ── Task Row ─────────────────────────────────────────────────────────────────

function TaskRow({
  task,
  onTakeOver,
  onNote,
  onReassign,
}: {
  task: Task;
  onTakeOver: (t: Task) => void;
  onNote: (t: Task) => void;
  onReassign: (t: Task) => void;
}) {
  const isExec = task.status === 'MANAGER_EXECUTING';

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '8px 1fr auto',
      gap: 12,
      padding: '11px 14px',
      borderRadius: 8,
      background: 'var(--color-bg)',
      border: '1px solid var(--color-border)',
      alignItems: 'center',
    }}>
      {/* Priority dot */}
      <div style={{
        width: 8, height: 8, borderRadius: '50%',
        background: PRIORITY_DOT[task.priority] || '#9ca3af',
        flexShrink: 0,
      }} />

      {/* Content */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
            {task.title || task.task_kind}
          </span>
          <span style={{
            fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 4,
            background: (STATUS_COLORS[task.status] || '#6b7280') + '22',
            color: STATUS_COLORS[task.status] || '#6b7280',
            letterSpacing: '0.03em',
          }}>{task.status.replace('_', ' ')}</span>
        </div>
        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 3, display: 'flex', gap: 12 }}>
          <span>{task.property_id}</span>
          <span>Due: {fmtDate(task.due_date)}</span>
          {task.assigned_to && <span>Worker: {task.assigned_to.slice(0, 8)}…</span>}
        </div>
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
        <button onClick={() => onNote(task)} title="Add note" style={actionBtn('#f59e0b')}>📝</button>
        <button onClick={() => onReassign(task)} title="Reassign" style={actionBtn('#8b5cf6')}>⇄</button>
        {isExec ? (
          <button onClick={() => onTakeOver(task)} title="Execute" style={actionBtn('#10b981')}>▶</button>
        ) : (
          <button onClick={() => onTakeOver(task)} title="Take over" style={actionBtn('#ef4444')}>⚡</button>
        )}
      </div>
    </div>
  );
}

function actionBtn(color: string) {
  return {
    width: 32, height: 32, borderRadius: 8, border: 'none',
    background: color + '18', color, cursor: 'pointer',
    fontSize: '0.95em', display: 'flex', alignItems: 'center', justifyContent: 'center',
    transition: 'background 0.15s',
  } as React.CSSProperties;
}

// ── Ad-hoc Task Modal ─────────────────────────────────────────────────────────

function AdHocModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [propertyId, setPropertyId] = useState('');
  const [kind, setKind] = useState('GENERAL');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    if (!propertyId.trim()) { setError('Property ID is required'); return; }
    setSaving(true);
    try {
      await api.post<{ task_id: string }>('/tasks/adhoc', { property_id: propertyId, task_kind: kind, note });
      onDone();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to create task');
      setSaving(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60,
    }}>
      <div style={{
        background: 'var(--color-surface)', borderRadius: 12, padding: 28,
        width: '100%', maxWidth: 440, boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
      }}>
        <h3 style={{ margin: '0 0 16px', fontWeight: 700, color: 'var(--color-text)', fontSize: 'var(--text-base)' }}>
          ➕ Create Ad-hoc Task
        </h3>
        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Property ID</label>
        <input autoFocus value={propertyId} onChange={e => setPropertyId(e.target.value)} placeholder="e.g. KPG-500"
          style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', boxSizing: 'border-box', marginBottom: 12 }} />
        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Task Kind</label>
        <select value={kind} onChange={e => setKind(e.target.value)}
          style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', marginBottom: 12 }}>
          {['CLEANING', 'MAINTENANCE', 'GENERAL'].map(k => <option key={k} value={k}>{k}</option>)}
        </select>
        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Note (optional)</label>
        <textarea value={note} onChange={e => setNote(e.target.value)} rows={2} placeholder="Operational note"
          style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', resize: 'none', boxSizing: 'border-box' }} />
        {error && <p style={{ color: '#ef4444', fontSize: 'var(--text-xs)', margin: '8px 0 0' }}>{error}</p>}
        <div style={{ display: 'flex', gap: 10, marginTop: 16, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid var(--color-border)', background: 'transparent', cursor: 'pointer', color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Cancel</button>
          <button onClick={submit} disabled={saving} style={{ padding: '8px 18px', borderRadius: 8, border: 'none', background: 'var(--color-primary)', color: '#fff', cursor: 'pointer', fontSize: 'var(--text-sm)', fontWeight: 600, opacity: saving ? 0.7 : 1 }}>{saving ? 'Creating…' : 'Create Task'}</button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function ManagerTasksPage() {
  const router = useRouter();
  const [groups, setGroups] = useState<Groups>({ manager_executing: [], pending: [], acknowledged: [], in_progress: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lane, setLane] = useState<Lane>('ALL');
  const [noteTask, setNoteTask] = useState<Task | null>(null);
  const [reassignTask, setReassignTask] = useState<Task | null>(null);
  const [showAdHoc, setShowAdHoc] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<{ groups: Groups }>('/manager/tasks');
      setGroups(res.groups || { manager_executing: [], pending: [], acknowledged: [], in_progress: [] });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load tasks');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleTakeOver = (task: Task) => {
    // Navigate to hub which has the full TakeoverModal + ExecutionDrawer
    router.push(`/manager?takeover=${task.id}`);
  };

  const allTasks = [
    ...groups.manager_executing,
    ...groups.pending,
    ...groups.acknowledged,
    ...groups.in_progress,
  ];

  const filtered = lane === 'ALL' ? allTasks : allTasks.filter(t => t.task_kind === lane);

  const statusOrder: Record<string, number> = {
    MANAGER_EXECUTING: 0, PENDING: 1, ACKNOWLEDGED: 2, IN_PROGRESS: 3,
  };
  filtered.sort((a, b) => (statusOrder[a.status] ?? 9) - (statusOrder[b.status] ?? 9));

  if (loading) return (
    <DraftGuard>
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-dim)' }}>
        Loading tasks…
      </div>
    </DraftGuard>
  );

  return (
    <DraftGuard>
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '24px 20px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 'var(--text-xl)', fontWeight: 800, color: 'var(--color-text)', fontFamily: "'Manrope', sans-serif" }}>
            Task Board
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
            {allTasks.length} active task{allTasks.length !== 1 ? 's' : ''} across supervised properties
          </p>
        </div>
        <button onClick={() => setShowAdHoc(true)} style={{
          padding: '9px 18px', borderRadius: 10, border: 'none',
          background: 'var(--color-primary)', color: '#fff', cursor: 'pointer',
          fontSize: 'var(--text-sm)', fontWeight: 700,
        }}>
          ➕ Ad-hoc Task
        </button>
      </div>

      {/* Lane filter */}
      <div style={{ display: 'flex', gap: 8, overflowX: 'auto', marginBottom: 20, paddingBottom: 4 }}>
        {LANES.map(l => (
          <button key={l} onClick={() => setLane(l)} style={{
            padding: '6px 14px', borderRadius: 20, border: '1px solid var(--color-border)',
            background: lane === l ? 'var(--color-primary)' : 'var(--color-bg)',
            color: lane === l ? '#fff' : 'var(--color-text-dim)',
            cursor: 'pointer', fontSize: 'var(--text-xs)', fontWeight: lane === l ? 700 : 400,
            whiteSpace: 'nowrap', transition: 'all 0.15s',
          }}>
            {LANE_LABELS[l]}
            {l !== 'ALL' && (
              <span style={{ marginLeft: 6, opacity: 0.75 }}>
                {allTasks.filter(t => t.task_kind === l).length}
              </span>
            )}
          </button>
        ))}
      </div>

      {error && (
        <div style={{ padding: 16, borderRadius: 8, background: '#ef444414', color: '#ef4444', marginBottom: 16, fontSize: 'var(--text-sm)' }}>
          {error}
        </div>
      )}

      {/* Task list */}
      {filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--color-text-faint)' }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>✅</div>
          <div style={{ fontSize: 'var(--text-sm)' }}>No {lane !== 'ALL' ? `${LANE_LABELS[lane]} ` : ''}tasks in the queue</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {filtered.map(task => (
            <TaskRow
              key={task.id}
              task={task}
              onTakeOver={handleTakeOver}
              onNote={() => setNoteTask(task)}
              onReassign={() => setReassignTask(task)}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      {noteTask && (
        <NoteModal taskId={noteTask.id} onClose={() => setNoteTask(null)} />
      )}
      {reassignTask && (
        <ReassignModal
          task={reassignTask}
          onClose={() => setReassignTask(null)}
          onDone={() => { setReassignTask(null); load(); }}
        />
      )}
      {showAdHoc && (
        <AdHocModal
          onClose={() => setShowAdHoc(false)}
          onDone={() => { setShowAdHoc(false); load(); }}
        />
      )}
    </div>
    </DraftGuard>
  );
}
