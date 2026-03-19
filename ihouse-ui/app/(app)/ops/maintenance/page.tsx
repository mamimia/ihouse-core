'use client';

/**
 * Operational Core — Phase F: Mobile Maintenance Flow
 * Architecture source: .agent/architecture/mobile-maintenance.md
 * Scope: Maintenance worker sees MAINTENANCE tasks + problem reports.
 *
 * Wired to existing APIs:
 *   - problem_report_router.py (382 lines) — full CRUD + photo + status
 *   - worker_router.py (598 lines) — task list + acknowledge + complete
 *   - cleaning_task_router.py — supply check reused for parts tracking
 */

import { useEffect, useState, useCallback } from 'react';
import { getToken } from '@/lib/api';
import BottomNav from '@/components/BottomNav';

const BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

// Phase E-4: Extract real worker identity from JWT
function getWorkerId(): string {
    if (typeof window === 'undefined') return '';
    try {
        const token = localStorage.getItem('ihouse_token');
        if (!token) return '';
        const payload = JSON.parse(atob(token.split('.')[1] || '{}'));
        return payload.user_id || payload.sub || payload.tenant_id || '';
    } catch { return ''; }
}

async function apiFetch<T = any>(path: string, init?: RequestInit): Promise<T> {
    const token = getToken();
    const res = await fetch(`${BASE}${path}`, {
        ...init,
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(init?.headers || {}),
        },
    });
    if (!res.ok) throw new Error(`${res.status}`);
    return res.json();
}

type Issue = {
    id?: string; report_id?: string; property_id: string;
    description?: string; category?: string; severity?: string; status?: string;
    created_at?: string; photos?: any[];
};

type Task = {
    task_id: string; property_id: string; kind?: string;
    status: string; priority?: string; title?: string;
    deadline?: string; notes?: string;
};

const SEVERITY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
    CRITICAL: { bg: 'rgba(248,81,73,0.12)', text: '#f85149', border: '#f8514930' },
    HIGH: { bg: 'rgba(210,153,34,0.12)', text: '#d29922', border: '#d2992230' },
    MEDIUM: { bg: 'rgba(88,166,255,0.12)', text: '#58a6ff', border: '#58a6ff30' },
    LOW: { bg: 'rgba(110,118,129,0.12)', text: '#8b949e', border: '#8b949e30' },
};

type ViewMode = 'list' | 'detail' | 'work';

export default function MobileMaintenancePage() {
    const [tasks, setTasks] = useState<Task[]>([]);
    const [issues, setIssues] = useState<Issue[]>([]);
    const [loading, setLoading] = useState(true);
    const [view, setView] = useState<ViewMode>('list');
    const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
    const [selectedTask, setSelectedTask] = useState<Task | null>(null);
    const [notice, setNotice] = useState<string | null>(null);

    // Work log state
    const [workNotes, setWorkNotes] = useState('');
    const [workStarted, setWorkStarted] = useState(false);
    const [workStartTime, setWorkStartTime] = useState<string | null>(null);

    const showNotice = (msg: string) => { setNotice(msg); setTimeout(() => setNotice(null), 3000); };

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const workerId = getWorkerId();
            let rawTasks: Task[] = [];
            let hasExplicitAssignments = false;

            if (workerId) {
                const tasksRes = await apiFetch<any>(`/worker/tasks?worker_role=MAINTENANCE&limit=50&assigned_to=${encodeURIComponent(workerId)}`);
                const assignedList = tasksRes.tasks || tasksRes.data?.tasks || tasksRes.data || [];
                rawTasks = Array.isArray(assignedList) ? assignedList : [];
                hasExplicitAssignments = !!tasksRes.has_assignments;
            }

            if (rawTasks.length === 0 && !hasExplicitAssignments) {
                const allRes = await apiFetch<any>('/worker/tasks?worker_role=MAINTENANCE&limit=50');
                const allList = allRes.tasks || allRes.data?.tasks || allRes.data || [];
                rawTasks = Array.isArray(allList) ? allList : [];
            }

            setTasks(rawTasks);

            // Fetch issues
            const issuesRes = await apiFetch<any>('/problem-reports?limit=50').catch(() => ({}));
            setIssues(issuesRes.reports || issuesRes.data || []);
        } catch { /* graceful */ }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const openIssue = (issue: Issue) => {
        setSelectedIssue(issue);
        // Find matching task
        const match = tasks.find(t => t.property_id === issue.property_id && t.kind === 'MAINTENANCE');
        setSelectedTask(match || null);
        setView('detail');
        setWorkNotes('');
        setWorkStarted(false);
        setWorkStartTime(null);
    };

    const startWork = () => {
        setWorkStarted(true);
        setWorkStartTime(new Date().toISOString());
        setView('work');
    };

    const acknowledgeTask = async () => {
        if (!selectedTask) return;
        try {
            await apiFetch(`/worker/tasks/${selectedTask.task_id}/acknowledge`, { method: 'PATCH' });
            showNotice('✅ Task acknowledged');
            load();
        } catch { showNotice('Acknowledge failed'); }
    };

    const completeTask = async () => {
        if (!selectedTask) return;
        try {
            await apiFetch(`/worker/tasks/${selectedTask.task_id}/complete`, {
                method: 'PATCH',
                body: JSON.stringify({ notes: workNotes || undefined }),
            });
            showNotice('✅ Task completed');
        } catch { showNotice('Complete failed'); }

        // Also update issue status
        if (selectedIssue) {
            const issueId = selectedIssue.id || selectedIssue.report_id;
            if (issueId) {
                try {
                    await apiFetch(`/problem-reports/${issueId}/status`, {
                        method: 'PATCH',
                        body: JSON.stringify({ status: 'resolved', resolution_notes: workNotes }),
                    });
                } catch { /* best-effort */ }
            }
        }

        setView('list');
        setSelectedIssue(null);
        setSelectedTask(null);
        load();
    };

    const today = new Date();
    const dateStr = today.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });

    const openIssues = issues.filter(i => i.status !== 'resolved' && i.status !== 'closed');
    const criticalCount = openIssues.filter(i => i.severity === 'CRITICAL').length;
    const activeTasks = tasks.filter(t => t.status !== 'COMPLETED' && t.status !== 'CANCELED');

    const card = {
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
    };
    const inputStyle = {
        width: '100%', background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-sm)', padding: '10px 14px', color: 'var(--color-text)',
        fontSize: 'var(--text-sm)', outline: 'none',
    };

    return (
        <div style={{ maxWidth: 600, margin: '0 auto', paddingBottom: 80 }}>
            {/* Notice toast */}
            {notice && (
                <div style={{
                    position: 'fixed', top: 20, left: '50%', transform: 'translateX(-50%)', zIndex: 999,
                    background: 'var(--color-surface)', border: '1px solid var(--color-primary)',
                    borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)',
                    fontSize: 'var(--text-sm)', color: 'var(--color-primary)', boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
                }}>{notice}</div>
            )}

            {/* ========== LIST VIEW ========== */}
            {view === 'list' && (
                <>
                    <div style={{ marginBottom: 'var(--space-5)' }}>
                        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                            {dateStr}
                        </p>
                        <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text)', letterSpacing: '-0.03em' }}>
                            Maintenance
                        </h1>
                    </div>

                    {/* Summary strip */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
                        <div style={card}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Open Issues</div>
                            <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: openIssues.length > 0 ? 'var(--color-warn)' : 'var(--color-ok)', marginTop: 4 }}>
                                {openIssues.length}
                            </div>
                        </div>
                        <div style={card}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Critical</div>
                            <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: criticalCount > 0 ? '#f85149' : 'var(--color-ok)', marginTop: 4 }}>
                                {criticalCount}
                            </div>
                        </div>
                        <div style={card}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Tasks</div>
                            <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: 'var(--color-accent)', marginTop: 4 }}>
                                {activeTasks.length}
                            </div>
                        </div>
                    </div>

                    {loading && <div style={{ ...card, textAlign: 'center', color: 'var(--color-text-dim)' }}>Loading…</div>}

                    {!loading && openIssues.length === 0 && (
                        <div style={{ ...card, textAlign: 'center' }}>
                            <div style={{ fontSize: 'var(--text-2xl)', marginBottom: 'var(--space-2)' }}>✅</div>
                            <div style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>No open issues</div>
                        </div>
                    )}

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        {openIssues.map(issue => {
                            const sev = SEVERITY_COLORS[issue.severity || 'MEDIUM'] || SEVERITY_COLORS.MEDIUM;
                            return (
                                <div key={issue.id || issue.report_id} style={{
                                    ...card, cursor: 'pointer', transition: 'border-color 0.2s',
                                    borderLeft: `3px solid ${sev.text}`,
                                }}
                                    onClick={() => openIssue(issue)}
                                    onMouseEnter={e => (e.currentTarget.style.borderColor = sev.text)}
                                    onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                        <div>
                                            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--color-text)' }}>
                                                {issue.description?.substring(0, 50) || 'Issue'}
                                                {(issue.description?.length || 0) > 50 ? '…' : ''}
                                            </div>
                                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                                                {issue.property_id} · {issue.category || '—'}
                                            </div>
                                        </div>
                                        <span style={{
                                            padding: '2px 10px', borderRadius: 12, fontSize: 'var(--text-xs)', fontWeight: 600,
                                            background: sev.bg, color: sev.text, border: `1px solid ${sev.border}`,
                                        }}>{issue.severity || 'MEDIUM'}</span>
                                    </div>
                                    {issue.created_at && (
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-2)', fontFamily: 'var(--font-mono)' }}>
                                            {new Date(issue.created_at).toLocaleString('en-GB', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </>
            )}

            {/* ========== DETAIL VIEW ========== */}
            {view === 'detail' && selectedIssue && (
                <div>
                    <button onClick={() => { setView('list'); setSelectedIssue(null); }} style={{
                        background: 'none', border: 'none', color: 'var(--color-text-dim)',
                        cursor: 'pointer', fontSize: 'var(--text-sm)', padding: 0, marginBottom: 'var(--space-3)',
                    }}>← Back to list</button>

                    <div style={card}>
                        {/* Severity header */}
                        {(() => {
                            const sev = SEVERITY_COLORS[selectedIssue.severity || 'MEDIUM'] || SEVERITY_COLORS.MEDIUM;
                            return (
                                <div style={{
                                    padding: 'var(--space-3)', borderRadius: 'var(--radius-md)',
                                    background: sev.bg, border: `1px solid ${sev.border}`,
                                    marginBottom: 'var(--space-4)', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                }}>
                                    <span style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: sev.text }}>
                                        {selectedIssue.severity || 'MEDIUM'} — {selectedIssue.category || 'General'}
                                    </span>
                                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                                        {selectedIssue.status || 'open'}
                                    </span>
                                </div>
                            );
                        })()}

                        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)', marginBottom: 'var(--space-4)', lineHeight: 1.6 }}>
                            {selectedIssue.description || 'No description'}
                        </div>

                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginBottom: 'var(--space-2)' }}>
                            📍 {selectedIssue.property_id}
                        </div>
                        {selectedIssue.created_at && (
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)' }}>
                                Reported: {new Date(selectedIssue.created_at).toLocaleString()}
                            </div>
                        )}

                        {/* Associated task */}
                        {selectedTask && (
                            <div style={{
                                marginTop: 'var(--space-4)', padding: 'var(--space-3)',
                                background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)',
                                border: '1px solid var(--color-border)',
                            }}>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', marginBottom: 4 }}>
                                    Associated Task
                                </div>
                                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
                                    {selectedTask.title || selectedTask.kind} — <strong>{selectedTask.status}</strong>
                                </div>
                            </div>
                        )}

                        {/* Actions */}
                        <div style={{ marginTop: 'var(--space-5)', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                            {selectedTask?.status === 'PENDING' && (
                                <button onClick={acknowledgeTask} style={{
                                    width: '100%', padding: '14px', borderRadius: 'var(--radius-md)',
                                    background: 'rgba(88,166,255,0.1)', color: '#58a6ff',
                                    border: '1px solid rgba(88,166,255,0.3)',
                                    fontWeight: 700, fontSize: 'var(--text-sm)', cursor: 'pointer',
                                }}>Acknowledge Task</button>
                            )}
                            <button onClick={startWork} style={{
                                width: '100%', padding: '14px', borderRadius: 'var(--radius-md)',
                                background: 'var(--color-primary)', color: '#fff', border: 'none',
                                fontWeight: 700, fontSize: 'var(--text-sm)', cursor: 'pointer',
                            }}>🔧 Start Work</button>

                            {/* Call property manager */}
                            <a href="tel:+66000000000" style={{
                                display: 'block', width: '100%', padding: '14px', borderRadius: 'var(--radius-md)',
                                background: 'transparent', color: 'var(--color-text-dim)',
                                border: '1px solid var(--color-border)', textAlign: 'center',
                                fontWeight: 700, fontSize: 'var(--text-sm)', textDecoration: 'none',
                            }}>📞 Call Manager</a>
                        </div>
                    </div>
                </div>
            )}

            {/* ========== WORK VIEW ========== */}
            {view === 'work' && selectedIssue && (
                <div>
                    <button onClick={() => setView('detail')} style={{
                        background: 'none', border: 'none', color: 'var(--color-text-dim)',
                        cursor: 'pointer', fontSize: 'var(--text-sm)', padding: 0, marginBottom: 'var(--space-3)',
                    }}>← Back to detail</button>

                    <div style={card}>
                        <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)', marginBottom: 'var(--space-4)' }}>
                            🔧 Work Log
                        </h2>

                        {workStartTime && (
                            <div style={{
                                padding: 'var(--space-3)', background: 'rgba(63,185,80,0.05)',
                                border: '1px solid rgba(63,185,80,0.2)', borderRadius: 'var(--radius-sm)',
                                marginBottom: 'var(--space-4)',
                            }}>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>Started at</div>
                                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: '#3fb950' }}>
                                    {new Date(workStartTime).toLocaleTimeString()}
                                </div>
                            </div>
                        )}

                        <div style={{ marginBottom: 'var(--space-3)' }}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 4 }}>
                                📍 {selectedIssue.property_id} · {selectedIssue.category}
                            </div>
                            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                                {selectedIssue.description?.substring(0, 100)}
                            </div>
                        </div>

                        {/* Work notes */}
                        <div style={{ marginBottom: 'var(--space-3)' }}>
                            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
                                Work Notes *
                            </label>
                            <textarea value={workNotes} onChange={e => setWorkNotes(e.target.value)}
                                placeholder="What was done? Parts used? Any follow-up needed?"
                                rows={4} style={{ ...inputStyle, resize: 'vertical' }} />
                        </div>

                        {/* After photo */}
                        <div style={{ marginBottom: 'var(--space-4)' }}>
                            <label style={{
                                display: 'inline-flex', alignItems: 'center', gap: 8,
                                padding: 'var(--space-2) var(--space-4)', borderRadius: 'var(--radius-md)',
                                background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                                fontSize: 'var(--text-sm)', cursor: 'pointer',
                            }}>
                                📷 Upload After Photo
                                <input type="file" accept="image/*" capture="environment" style={{ display: 'none' }}
                                    onChange={async (e) => {
                                        const file = e.target.files?.[0];
                                        if (!file || !selectedIssue) return;
                                        const issueId = selectedIssue.id || selectedIssue.report_id;
                                        if (!issueId) return;
                                        try {
                                            const formData = new FormData();
                                            formData.append('file', file);
                                            formData.append('photo_type', 'after');
                                            const token = getToken();
                                            await fetch(`${BASE}/problem-reports/${issueId}/photos`, {
                                                method: 'POST',
                                                headers: token ? { Authorization: `Bearer ${token}` } : {},
                                                body: formData,
                                            });
                                            showNotice('📷 After photo uploaded');
                                        } catch { showNotice('Photo upload failed'); }
                                    }}
                                />
                            </label>
                        </div>

                        {/* Complete */}
                        <button onClick={completeTask} disabled={!workNotes.trim()} style={{
                            width: '100%', padding: '14px', borderRadius: 'var(--radius-md)',
                            background: workNotes.trim() ? 'var(--color-primary)' : 'var(--color-surface-2)',
                            color: workNotes.trim() ? '#fff' : 'var(--color-text-dim)',
                            border: 'none', fontWeight: 700, fontSize: 'var(--text-sm)',
                            cursor: workNotes.trim() ? 'pointer' : 'not-allowed',
                            opacity: workNotes.trim() ? 1 : 0.5,
                        }}>✅ Complete & Resolve</button>
                    </div>
                </div>
            )}

            <BottomNav items={[
                { href: '/dashboard', label: 'Home', icon: '🏠' },
                { href: '/ops/checkin', label: 'Check-in', icon: '📋' },
                { href: '/ops/checkout', label: 'Check-out', icon: '🚪' },
                { href: '/ops/cleaner', label: 'Cleaning', icon: '🧹' },
                { href: '/ops/maintenance', label: 'Maint.', icon: '🔧' },
            ]} />
        </div>
    );
}
