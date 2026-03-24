'use client';

/**
 * Phase 157 — Worker Task Mobile View
 * Route: /tasks
 *
 * Mobile-first task list for cleaners, check-in staff, maintenance workers.
 * Features:
 *  - Live SLA countdown for CRITICAL tasks (5-min ack window)
 *  - Priority chips with colour coding
 *  - One-tap Acknowledge action
 *  - Overdue indicator
 *  - Tap task card to go to detail view
 */

import { useEffect, useState, useCallback } from 'react';
import { api, WorkerTask } from '../../../lib/api';
import WorkerTaskCard from '@/components/WorkerTaskCard';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function priorityColor(priority: string): string {
    switch (priority?.toUpperCase()) {
        case 'CRITICAL': return 'var(--color-danger)';
        case 'HIGH': return 'var(--color-warn)';
        case 'MEDIUM': return 'var(--color-primary)';
        default: return 'var(--color-muted)';
    }
}

function statusColor(status: string): string {
    switch (status?.toLowerCase()) {
        case 'completed': return 'var(--color-ok)';
        case 'in_progress': return 'var(--color-primary)';
        case 'acknowledged': return 'var(--color-accent)';
        default: return 'var(--color-muted)';
    }
}

function kindLabel(kind: string): string {
    const map: Record<string, string> = {
        CLEANING: '🧹 Cleaning',
        CHECKIN_PREP: '🏠 Check-in Prep',
        CHECKOUT_PREP: '📦 Checkout Prep',
        MAINTENANCE: '🔧 Maintenance',
    };
    return map[kind] ?? kind;
}

function formatTime(iso: string | undefined): string {
    if (!iso) return '—';
    try {
        return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
    } catch { return iso; }
}

function isOverdue(task: WorkerTask): boolean {
    if (!task.due_date) return false;
    const due = new Date(task.due_time ? `${task.due_date}T${task.due_time}` : `${task.due_date}T23:59:59`);
    return new Date() > due && task.status !== 'completed';
}

// Old task rendering components (TaskCountdown, SmallAvatar, DayPropertyCard) removed (Phase 885)

// ---------------------------------------------------------------------------
// Empty State
// ---------------------------------------------------------------------------

function EmptyState({ filter }: { filter: string }) {
    const isDone = filter === 'completed';
    return (
        <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 'var(--space-16)',
            gap: 'var(--space-4)',
            textAlign: 'center',
        }}>
            <div style={{ fontSize: '3rem' }}>{isDone ? '✅' : '🎉'}</div>
            <div style={{ fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text)' }}>
                {isDone ? 'No completed tasks yet' : 'All clear!'}
            </div>
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                {isDone ? 'Tasks you complete will appear here.' : 'No pending tasks assigned to you right now.'}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Status filter tabs
// ---------------------------------------------------------------------------

// Phase 884 fix (E): Simplified to 2 real states.
// - Pending = all active/unfinished tasks (no status filter sent to backend,
//   we rely on the backend default which returns non-completed tasks).
//   In the future this could pass status=pending,acknowledged,in_progress.
// - Done    = completed tasks (status=completed).
// Removed: "All" (was identical to Pending) and "In Progress" (was fake UI
// that passed in_progress to an endpoint that may not filter on it).
const FILTERS = [
    { label: 'Pending', value: '' },
    { label: 'Done',    value: 'completed' },
];

import {
    CHECKIN_BOTTOM_NAV,
    CHECKOUT_BOTTOM_NAV,
    CHECKIN_CHECKOUT_BOTTOM_NAV,
    CLEANER_BOTTOM_NAV,
    MAINTENANCE_BOTTOM_NAV,
} from '@/components/BottomNav';
import MobileStaffShell from '@/components/MobileStaffShell';

/**
 * Phase 882b — Role-aware shell for the tasks page.
 *
 * Problem: `/tasks` was rendering inside AdaptiveShell (admin sidebar) even
 * when a preview-staff or real-staff user navigated here from their role-correct
 * bottom nav. This broke role isolation — the user exited their mobile staff
 * world into the admin dashboard.
 *
 * Fix: detect preview role or real staff role, and wrap tasks content inside
 * MobileStaffShell with the correct role-specific bottom nav. Admin users
 * without preview still get the bare admin-shell tasks view.
 */
function getStaffRoleFromContext(): string | null {
    if (typeof window === 'undefined') return null;
    // Check preview role first (highest priority)
    try {
        const previewRole = sessionStorage.getItem('ihouse_preview_role');
        if (previewRole) return previewRole;
    } catch {}
    // Check real JWT role
    try {
        const token = localStorage.getItem('ihouse_token');
        if (token) {
            const payload = JSON.parse(atob(token.split('.')[1] || '{}'));
            const staffRoles = ['cleaner', 'checkin', 'checkout', 'checkin_checkout', 'maintenance', 'worker'];
            if (staffRoles.includes(payload.role)) return payload.role;
        }
    } catch {}
    return null;
}

/**
 * Phase 882c — Map preview role to backend WorkerRole enum values.
 * 
 * Backend WorkerRole enum (from task_model.py):
 *   CLEANER, CHECKIN, CHECKOUT, MAINTENANCE, PROPERTY_MANAGER,
 *   MAINTENANCE_TECH, INSPECTOR, GENERAL_STAFF
 *
 * The backend accepts worker_role as a query param on GET /worker/tasks
 * and filters tasks at DB level. Admins normally get all tasks (unrestricted),
 * but for Preview As we explicitly pass the role to scope the view.
 */
function getBackendWorkerRole(previewRole: string | null | undefined): string | undefined {
    if (!previewRole) return undefined;
    switch (previewRole) {
        case 'checkin':          return 'CHECKIN';
        case 'checkout':         return 'CHECKOUT';
        case 'cleaner':          return 'CLEANER';
        case 'maintenance':      return 'MAINTENANCE';
        case 'checkin_checkout':  return undefined; // handled specially below
        default:                 return undefined;
    }
}

function getRoleNav(role: string) {
    switch (role) {
        case 'checkin': return CHECKIN_BOTTOM_NAV;
        case 'checkout': return CHECKOUT_BOTTOM_NAV;
        case 'checkin_checkout': return CHECKIN_CHECKOUT_BOTTOM_NAV;
        case 'cleaner': return CLEANER_BOTTOM_NAV;
        case 'maintenance': return MAINTENANCE_BOTTOM_NAV;
        default: return CLEANER_BOTTOM_NAV; // generic staff fallback
    }
}

export default function TasksPage() {
    const [tasks, setTasks] = useState<WorkerTask[]>([]);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState<string | null>(null);
    const [filter, setFilter] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [detailId, setDetailId] = useState<string | null>(null);
    const [propertyMap, setPropertyMap] = useState<Record<string, string>>({});
    const [staffMap, setStaffMap] = useState<Record<string, { name: string; photo: string }>>({});

    // Phase 882b — detect if we should render inside a staff shell
    // Phase 882c fix: undefined = "not yet resolved from sessionStorage"
    //                 null     = "resolved, no preview role (admin view)"
    //                 string   = "resolved, previewing this role"
    // This prevents the timing race where the first loadTasks fires before
    // the sessionStorage read completes, which caused full admin leakage.
    const [staffRole, setStaffRole] = useState<string | null | undefined>(undefined);
    useEffect(() => { setStaffRole(getStaffRoleFromContext()); }, []);

    useEffect(() => {
        Promise.allSettled([
            api.listProperties?.(),
            api.getPermissions?.()
        ]).then(([pRes, sRes]) => {
            if (pRes.status === 'fulfilled') {
                const map: Record<string, string> = {};
                for (const p of pRes.value?.properties || []) {
                    map[p.property_id] = p.display_name || p.property_id;
                }
                setPropertyMap(map);
            }
            if (sRes.status === 'fulfilled') {
                const map: Record<string, { name: string; photo: string }> = {};
                for (const s of sRes.value?.permissions || []) {
                    const anyS = s as any;
                    map[s.user_id] = {
                        name: (anyS.display_name as string) || (s.permissions?.full_name as string) || s.user_id,
                        photo: (anyS.photo_url as string) || ''
                    };
                }
                setStaffMap(map);
            }
        });
    }, []);

    // Phase 882c — Role-scoped task loading
    const loadTasks = useCallback(async () => {
        try {
            setError(null);
            const backendRole = getBackendWorkerRole(staffRole);

            if (staffRole === 'checkin_checkout') {
                // Special: combined role needs CHECKIN + CHECKOUT tasks merged
                const [checkinResp, checkoutResp] = await Promise.all([
                    api.getWorkerTasks({ status: filter || undefined, limit: 50, worker_role: 'CHECKIN' }),
                    api.getWorkerTasks({ status: filter || undefined, limit: 50, worker_role: 'CHECKOUT' }),
                ]);
                // Merge and deduplicate by task_id
                const merged = new Map<string, WorkerTask>();
                for (const t of [...(checkinResp.tasks ?? []), ...(checkoutResp.tasks ?? [])]) {
                    merged.set(t.task_id, t);
                }
                setTasks(Array.from(merged.values()));
            } else {
                const resp = await api.getWorkerTasks({
                    status: filter || undefined,
                    limit: 50,
                    worker_role: backendRole,
                });
                setTasks(resp.tasks ?? []);
            }
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to load tasks');
        } finally {
            setLoading(false);
        }
    }, [filter, staffRole]);

    // Poll every 30s as fallback.
    // IMPORTANT: only start loading after staffRole has been resolved from
    // sessionStorage (i.e. staffRole !== undefined). This prevents the first
    // fetch from firing with staffRole=null (no filter) before the role is set.
    useEffect(() => {
        if (staffRole === undefined) return; // not yet resolved — wait
        setLoading(true);
        loadTasks();
        const interval = setInterval(loadTasks, 30_000);
        return () => clearInterval(interval);
    }, [loadTasks, staffRole]);

    // SSE for real-time task events (Phase 308)
    useEffect(() => {
        const token = typeof window !== 'undefined' ? localStorage.getItem('ihouse_token') ?? '' : '';
        const baseUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';
        const es = new EventSource(`${baseUrl}/events/stream?channels=tasks,alerts&token=${token}`);
        es.onmessage = (e) => {
            try {
                const evt = JSON.parse(e.data);
                if (evt.channel === 'tasks' || evt.channel === 'alerts') {
                    setTimeout(loadTasks, 500);
                }
            } catch { /* ignore */ }
        };
        return () => es.close();
    }, [loadTasks]);

    const handleAcknowledge = async (id: string) => {
        setActionLoading(id);
        try {
            await api.acknowledgeTask(id);
            await loadTasks();
        } catch (err: unknown) {
            console.error('Acknowledge failed:', err);
        } finally {
            setActionLoading(null);
        }
    };

    // Sort: 
    // 1. Primary: Chronological (due_date + due_time)
    // 2. Secondary: Operational order (Checkout -> Cleaning -> Checkin)
    const sorted = [...tasks].sort((a, b) => {
        const dateA = a.due_date || '9999-12-31';
        const dateB = b.due_date || '9999-12-31';
        if (dateA !== dateB) return dateA.localeCompare(dateB);

        const timeA = a.due_time || '23:59:59';
        const timeB = b.due_time || '23:59:59';
        if (timeA !== timeB) return timeA.localeCompare(timeB);

        const opsOrder: Record<string, number> = {
            'CHECKOUT_VERIFY': 1,
            'CHECKOUT_PREP': 1,
            'CLEANING': 2,
            'CHECKIN_PREP': 3,
            'GUEST_WELCOME': 4,
        };
        const orderA = opsOrder[a.kind] ?? 99;
        const orderB = opsOrder[b.kind] ?? 99;
        if (orderA !== orderB) return orderA - orderB;

        return a.task_id.localeCompare(b.task_id);
    });

    const criticalCount = tasks.filter(t => t.priority === 'CRITICAL' && t.status === 'pending').length;
    const overdueCount = tasks.filter(t => isOverdue(t)).length;

    const tasksContent = (
        <>
            <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .task-card-enter {
          animation: slideUp 220ms ease forwards;
        }
        /* Mobile: hide sidebar, full-width */
        @media (max-width: 768px) {
          .tasks-main {
            margin-left: 0 !important;
            padding: var(--space-4) !important;
          }
          .tasks-nav-desktop {
            display: none !important;
          }
        }
      `}</style>

            {/* Mobile-aware outer wrapper */}
            <div className="tasks-main" style={{ maxWidth: 680, margin: '0 auto' }}>

                {/* Header */}
                <div style={{ marginBottom: 'var(--space-6)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                            <h1 style={{
                                fontSize: 'var(--text-2xl)',
                                fontWeight: 700,
                                color: 'var(--color-text)',
                                letterSpacing: '-0.02em',
                                lineHeight: 1.2,
                            }}>
                                My Tasks
                            </h1>
                            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-1)' }}>
                                Today • {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}
                            </p>
                        </div>

                        {/* Badges */}
                        <div style={{ display: 'flex', gap: 'var(--space-2)', flexShrink: 0 }}>
                            {criticalCount > 0 && (
                                <div style={{
                                    background: 'var(--color-danger)',
                                    color: '#fff',
                                    borderRadius: 'var(--radius-full)',
                                    padding: '4px 10px',
                                    fontSize: 'var(--text-xs)',
                                    fontWeight: 700,
                                    animation: 'pulse 2s infinite',
                                    boxShadow: 'var(--shadow-glow-red)',
                                }}>
                                    {criticalCount} CRITICAL
                                </div>
                            )}
                            {overdueCount > 0 && (
                                <div style={{
                                    background: 'rgba(239,68,68,0.15)',
                                    color: 'var(--color-danger)',
                                    border: '1px solid var(--color-danger)',
                                    borderRadius: 'var(--radius-full)',
                                    padding: '4px 10px',
                                    fontSize: 'var(--text-xs)',
                                    fontWeight: 600,
                                }}>
                                    {overdueCount} overdue
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Filter tabs */}
                <div style={{
                    display: 'flex',
                    gap: 'var(--space-2)',
                    marginBottom: 'var(--space-5)',
                    background: 'var(--color-surface)',
                    borderRadius: 'var(--radius-lg)',
                    padding: 'var(--space-1)',
                    border: '1px solid var(--color-border)',
                }}>
                    {FILTERS.map(f => (
                        <button
                            key={f.value}
                            id={`filter-${f.value || 'all'}`}
                            onClick={() => { setFilter(f.value); setLoading(true); }}
                            style={{
                                flex: 1,
                                padding: 'var(--space-2) var(--space-3)',
                                borderRadius: 'var(--radius-md)',
                                border: 'none',
                                background: filter === f.value ? 'var(--color-primary)' : 'transparent',
                                color: filter === f.value ? '#fff' : 'var(--color-text-dim)',
                                fontWeight: filter === f.value ? 600 : 400,
                                fontSize: 'var(--text-sm)',
                                transition: 'all var(--transition-fast)',
                                cursor: 'pointer',
                            }}
                        >
                            {f.label}
                        </button>
                    ))}
                </div>

                {/* Error state */}
                {error && (
                    <div style={{
                        background: 'rgba(239,68,68,0.1)',
                        border: '1px solid rgba(239,68,68,0.3)',
                        borderRadius: 'var(--radius-md)',
                        padding: 'var(--space-4)',
                        marginBottom: 'var(--space-4)',
                        color: 'var(--color-danger)',
                        fontSize: 'var(--text-sm)',
                    }}>
                        ⚠ {error}
                        <button
                            onClick={loadTasks}
                            style={{
                                marginLeft: 'var(--space-3)',
                                background: 'none',
                                border: '1px solid var(--color-danger)',
                                color: 'var(--color-danger)',
                                borderRadius: 'var(--radius-sm)',
                                padding: '2px 8px',
                                fontSize: 'var(--text-xs)',
                                cursor: 'pointer',
                            }}
                        >
                            Retry
                        </button>
                    </div>
                )}

                {/* Loading skeleton */}
                {loading && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        {[1, 2, 3].map(i => (
                            <div key={i} style={{
                                height: 120,
                                background: 'var(--color-surface)',
                                borderRadius: 'var(--radius-lg)',
                                animation: 'pulse 1.5s infinite',
                                border: '1px solid var(--color-border)',
                            }} />
                        ))}
                    </div>
                )}

                {/* Task list */}
                {!loading && sorted.length === 0 && <EmptyState filter={filter} />}

                {!loading && sorted.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                        {sorted.map((t, idx) => {
                            const propName = propertyMap[t.property_id] || t.property_id;
                            
                            // Determine route destination based on task kind
                            let dest = '/tasks';
                            if (t.kind.includes('CLEAN')) dest = `/ops/cleaner`;
                            else if (t.kind.includes('CHECKIN') || t.kind.includes('GUEST')) dest = `/ops/checkin`;
                            else if (t.kind.includes('CHECKOUT')) dest = `/ops/checkout`;
                            else if (t.kind.includes('MAINTENANCE')) dest = `/ops/maintenance`;

                            return (
                                <div key={t.task_id} className="task-card-enter" style={{ animationDelay: `${idx * 40}ms` }}>
                                    <WorkerTaskCard
                                        taskId={t.task_id}
                                        kind={t.kind}
                                        status={t.status}
                                        priority={t.priority}
                                        date={t.due_date || ''}
                                        time={t.due_time || ''}
                                        propertyName={propName}
                                        propertyCode={t.property_id}
                                        guestName={t.title || ''}
                                        onStart={() => window.location.href = dest} // navigate straight to execution page
                                        onAcknowledge={
                                            t.status === 'PENDING' 
                                                ? () => handleAcknowledge(t.task_id) 
                                                : undefined
                                        }
                                        onNavigate={() => {
                                            if (t.property_id) {
                                                window.open(`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(propName + ' ' + t.property_id)}`, '_blank');
                                            }
                                        }}
                                    />
                                </div>
                            );
                        })}
                    </div>
                )}

                {/* Task count footer */}
                {!loading && sorted.length > 0 && (
                    <div style={{
                        textAlign: 'center',
                        fontSize: 'var(--text-xs)',
                        color: 'var(--color-text-faint)',
                        marginTop: 'var(--space-6)',
                    }}>
                        {sorted.length} task{sorted.length !== 1 ? 's' : ''} · refreshes every 30s
                    </div>
                )}
            </div>
        </>
    );

    // Phase 882b — If in staff/preview context, wrap in MobileStaffShell with role-correct nav
    if (staffRole) {
        return (
            <MobileStaffShell title="My Tasks" bottomNavItems={getRoleNav(staffRole)}>
                {tasksContent}
            </MobileStaffShell>
        );
    }

    // Admin context — render bare (AdaptiveShell from layout provides the admin sidebar)
    return tasksContent;
}

