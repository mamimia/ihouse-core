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
 *
 * ⚠️  GUARDRAILS (from 2026-03-26 staging incident):
 *  1. NEVER put async enrichment (booking cache, property lookups, etc.)
 *     inside loadTasks or any polled/SSE callback. Use a separate useEffect.
 *  2. NEVER import staffApi on admin surfaces. This page uses lib/api (admin
 *     auth via localStorage), NOT lib/staffApi (worker auth via sessionStorage).
 *  Violation of either rule causes infinite request loops that exhaust the
 *  browser connection pool and take down ALL admin pages.
 */

import { useEffect, useState, useCallback } from 'react';
import { api, apiFetch as adminApiFetch, WorkerTask } from '../../../lib/api';
import { getTabToken } from '../../../lib/tokenStore';
import WorkerTaskCard, { computeNights } from '@/components/WorkerTaskCard';
import { useRouter } from 'next/navigation';

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
        case 'canceled': return 'var(--color-text-faint)';
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
    // Normalize: backend returns uppercase (COMPLETED, CANCELED)
    const s = task.status?.toLowerCase();
    return new Date() > due && s !== 'completed' && s !== 'canceled';
}

function getTargetTime(task: WorkerTask): Date {
    const defaultTimes: Record<string, string> = {
        'CHECKOUT_VERIFY': '11:00:00',
        'CHECKOUT_PREP': '11:00:00',
        'CLEANING': '11:00:00',
        'CHECKIN_PREP': '15:00:00',
    };
    const timeStr = task.due_time || defaultTimes[task.kind] || '12:00:00';
    const dateStr = task.due_date || new Date().toISOString().split('T')[0];
    return new Date(`${dateStr}T${timeStr}`);
}

function TaskCountdown({ task }: { task: WorkerTask }) {
    const [now, setNow] = useState(Date.now());
    // Normalize: backend returns uppercase statuses (COMPLETED, CANCELED, PENDING, etc.)
    const normalizedStatus = task.status?.toLowerCase();
    
    useEffect(() => {
        if (normalizedStatus === 'completed' || normalizedStatus === 'canceled') return;
        const timer = setInterval(() => setNow(Date.now()), 1000);
        return () => clearInterval(timer);
    }, [normalizedStatus]);
    
    if (normalizedStatus === 'completed') {
        return <span style={{ color: 'var(--color-ok)', fontSize: 11, fontWeight: 700 }}>✔ DONE</span>;
    }
    if (normalizedStatus === 'canceled') {
        return <span style={{ color: 'var(--color-text-faint)', fontSize: 11, fontWeight: 700 }}>CANCELED</span>;
    }
    
    const target = getTargetTime(task).getTime();
    const diff = target - now;
    
    const isOverdue = diff < 0;
    const absDiff = Math.abs(diff);
    
    const hours = Math.floor(absDiff / 3600000);
    const mins = Math.floor((absDiff % 3600000) / 60000);
    const secs = Math.floor((absDiff % 60000) / 1000);
    
    const display = `${isOverdue ? '-' : ''}${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    
    return (
        <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            fontWeight: 700,
            color: isOverdue ? 'var(--color-danger)' : 'var(--color-text)',
            background: isOverdue ? 'rgba(248,81,73,0.1)' : 'var(--color-surface-2)',
            padding: '4px 8px',
            borderRadius: 4,
            width: '80px',
            textAlign: 'center',
            display: 'inline-block'
        }}>
            {display}
        </span>
    );
}

// ---------------------------------------------------------------------------
function SmallAvatar({ name, photoUrl }: { name: string, photoUrl: string }) {
    const initials = (name || '?').trim().split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
    return (
        <div style={{
            width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
            background: photoUrl ? 'transparent' : 'var(--color-primary)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 9, fontWeight: 700, color: '#fff',
            overflow: 'hidden', border: '1px solid var(--color-border)',
        }}>
            {photoUrl
                ? <img src={photoUrl} alt={name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                : initials}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Admin Task Card — Dense property+day grouped layout (restored from git)
// ---------------------------------------------------------------------------

interface DayPropertyCardProps {
    propertyId: string;
    date: string;
    tasks: WorkerTask[];
    onOpen: (id: string) => void;
    propertyMap: Record<string, string>;
    staffMap: Record<string, { name: string; photo: string }>;
}

function DayPropertyCard({ propertyId, date, tasks, onOpen, propertyMap, staffMap }: DayPropertyCardProps) {
    const router = useRouter();
    const propName = propertyMap[propertyId] || propertyId;
    
    const hasOverdue = tasks.some(t => isOverdue(t));
    const hasCritical = tasks.some(t => t.priority === 'CRITICAL' && t.status === 'pending');
    
    return (
        <div style={{
            background: 'var(--color-surface)',
            borderRadius: 'var(--radius-lg)',
            border: `1px solid ${hasCritical ? 'rgba(239,68,68,0.5)' : hasOverdue ? 'var(--color-danger)' : 'var(--color-border)'}`,
            marginBottom: 'var(--space-4)',
            boxShadow: hasCritical ? '0 0 12px rgba(239,68,68,0.15)' : 'var(--shadow-sm)',
            overflow: 'hidden',
        }}>
             {/* Header */}
             <div style={{
                 background: 'var(--color-surface-2)',
                 padding: 'var(--space-3) var(--space-4)',
                 borderBottom: '1px solid var(--color-border)',
                 display: 'flex',
                 justifyContent: 'space-between',
                 alignItems: 'center'
             }}>
                 <div 
                    onClick={() => router.push(`/admin/properties/${propertyId}`)}
                    style={{ fontWeight: 700, color: 'var(--color-text)', fontSize: 'var(--text-sm)', cursor: 'pointer' }}
                    onMouseEnter={(e) => e.currentTarget.style.textDecoration = 'underline'}
                    onMouseLeave={(e) => e.currentTarget.style.textDecoration = 'none'}
                 >
                    {propName}
                 </div>
                 <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontWeight: 600 }}>
                    {date}
                </div>
            </div>
            
            {/* Task Columns */}
            <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.max(1, tasks.length)}, minmax(0, 1fr))`, gap: '1px', background: 'var(--color-border)' }}>
                {tasks.map((task) => (
                    <div key={task.task_id} 
                         onClick={() => onOpen(task.task_id)}
                         style={{
                             display: 'flex',
                             flexDirection: 'column',
                             padding: '10px 12px',
                             cursor: 'pointer',
                             background: task.status === 'completed' ? 'var(--color-surface-hover)' : 'var(--color-surface)',
                             gap: 8,
                             transition: 'background 0.2s',
                             minWidth: 0,
                         }}
                         onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--color-surface-hover)'; }}
                         onMouseLeave={(e) => { e.currentTarget.style.background = task.status === 'completed' ? 'var(--color-surface-hover)' : 'var(--color-surface)'; }}
                    >
                         {/* Header: Task Kind + Badges */}
                         <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                             <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0, paddingRight: 8 }}>
                                 <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                     {kindLabel(task.kind)}
                                     {(() => { const bk = (task as any)._bookingCache; const n = bk ? computeNights(bk.check_in, bk.check_out) : null; return n ? <span style={{ fontSize: 10, fontWeight: 500, color: 'var(--color-text-faint)', marginLeft: 6 }}>🌙 {n}</span> : null; })()}
                                 </span>
                                 <span 
                                    onClick={(e) => { e.stopPropagation(); router.push(`/bookings/${task.booking_id}`); }}
                                    style={{ fontSize: 10, cursor: 'pointer', color: 'var(--color-text-faint)', textDecoration: 'underline', width: 'fit-content' }}
                                    title="View Booking"
                                 >
                                    #{task.booking_id?.split('-').pop()}
                                 </span>
                             </div>
                             <div style={{ display: 'flex', gap: 4, flexShrink: 0, alignItems: 'center' }}>
                                 {task.priority === 'CRITICAL' && task.status === 'pending' && <span style={{ fontSize: 9, color: '#fff', background: '#f85149', padding: '2px 4px', borderRadius: 4, fontWeight: 700 }}>CRITICAL</span>}
                                 <span style={{ fontSize: 9, color: statusColor(task.status), background: `${statusColor(task.status)}18`, padding: '2px 6px', borderRadius: 4, fontWeight: 600, textTransform: 'uppercase' }}>
                                     {task.status?.replace('_', ' ')}
                                 </span>
                             </div>
                         </div>
                         
                         {/* Footer: Worker + Timer */}
                         <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 'auto' }}>
                             <div 
                                onClick={(e) => {
                                    if (task.assigned_to) {
                                        e.stopPropagation();
                                        router.push(`/admin/staff/${task.assigned_to}`);
                                    }
                                }}
                                style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0, paddingRight: 6, cursor: task.assigned_to ? 'pointer' : 'default' }}
                                onMouseEnter={(e) => { if (task.assigned_to) e.currentTarget.style.opacity = '0.7'; }}
                                onMouseLeave={(e) => { if (task.assigned_to) e.currentTarget.style.opacity = '1'; }}
                             >
                                 <SmallAvatar 
                                    name={task.assigned_to ? (staffMap[task.assigned_to]?.name || task.assigned_to) : '?'} 
                                    photoUrl={task.assigned_to ? (staffMap[task.assigned_to]?.photo || '') : ''} 
                                 />
                                 <span style={{ fontSize: 11, color: task.assigned_to ? 'var(--color-text-dim)' : 'var(--color-text-faint)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                    {task.assigned_to ? (staffMap[task.assigned_to]?.name || task.assigned_to).split(' ')[0] : 'Unassigned'}
                                 </span>
                             </div>
                             
                             <div style={{ flexShrink: 0 }}>
                                 <TaskCountdown task={task} />
                             </div>
                         </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Empty State
// ---------------------------------------------------------------------------

function EmptyState({ filter }: { filter: string }) {
    const isDone = filter === 'COMPLETED';
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

// Admin: full 4-tab filter set — Pending first (default), All last.
// Phase 1027b — canonical task-state model:
// (Touches the admin task filter logic originally introduced in Phase 157/882b/882c.
//  Phase 888 (Task Assignment Backfill) is a different, unrelated feature.)
//   Pending     = all incomplete tasks (PENDING + ACKNOWLEDGED) — the full operational queue.
//                 Backend returns PENDING+ACKNOWLEDGED+IN_PROGRESS when no status filter is sent.
//                 We use '__PENDING_ALL__' as a UI-side sentinel to send no status filter,
//                 which the backend interprets as "all non-CANCELED tasks".
//   In Progress = only tasks where real work has started (IN_PROGRESS). ACKNOWLEDGED ≠ In Progress.
//   Done        = COMPLETED only.
//   All         = no filter, all tasks including CANCELED.
//
// BEFORE this fix: 'In Progress' → ACKNOWLEDGED  (WRONG — just being acknowledged moved task out of Pending)
// AFTER this fix:  'In Progress' → IN_PROGRESS   (CORRECT — only tasks where worker pressed Start)
const ADMIN_FILTERS = [
    { label: 'Pending',     value: '__PENDING_ALL__' },  // sends no status → backend: PENDING+ACKNOWLEDGED+IN_PROGRESS
    { label: 'In Progress', value: 'IN_PROGRESS' },
    { label: 'Done',        value: 'COMPLETED' },
    { label: 'All',         value: '' },
];

// Worker: simplified 2-tab filter set
const WORKER_FILTERS = [
    { label: 'Pending', value: '' },
    { label: 'Done',    value: 'COMPLETED' },
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
    // Check real JWT role — Phase 865: sessionStorage-first via getTabToken
    try {
        const token = getTabToken();
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
    // Default to PENDING so the most actionable tab is shown on load
    const [filter, setFilter] = useState('__PENDING_ALL__');
    const [error, setError] = useState<string | null>(null);
    const [detailId, setDetailId] = useState<string | null>(null);
    // Phase 887c: store both display_name and approval status per property
    const [propertyMap, setPropertyMap] = useState<Record<string, string>>({});
    const [propertyStatusMap, setPropertyStatusMap] = useState<Record<string, string>>({});
    const [staffMap, setStaffMap] = useState<Record<string, { name: string; photo: string }>>({});
    // Phase 889: booking cache for nights computation on stay-linked tasks
    const [bookingCache, setBookingCache] = useState<Record<string, { check_in?: string; check_out?: string; guest_name?: string; guest_count?: number }>>({});

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
                const nameMap: Record<string, string> = {};
                const statusMap: Record<string, string> = {};
                for (const p of pRes.value?.properties || []) {
                    nameMap[p.property_id] = p.display_name || p.property_id;
                    statusMap[p.property_id] = p.status || 'unknown';
                }
                setPropertyMap(nameMap);
                setPropertyStatusMap(statusMap);
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
    // IMPORTANT: This callback is invoked by polling (30s) and SSE events.
    // It must NOT contain booking enrichment — that belongs in a separate
    // one-shot effect to avoid infinite request loops (Phase 889 fix).
    const loadTasks = useCallback(async () => {
        try {
            setError(null);
            const backendRole = getBackendWorkerRole(staffRole);

            // Phase 1027b: __PENDING_ALL__ sentinel — send no status filter so backend
            // returns all non-CANCELED tasks (PENDING + ACKNOWLEDGED + IN_PROGRESS).
            // This ensures acknowledged tasks remain visible in the Pending operational queue.
            const backendStatus = filter === '__PENDING_ALL__' ? undefined : (filter || undefined);

            if (staffRole === 'checkin_checkout') {
                // Special: combined role needs CHECKIN + CHECKOUT tasks merged
                const [checkinResp, checkoutResp] = await Promise.all([
                    api.getWorkerTasks({ status: backendStatus, limit: 50, worker_role: 'CHECKIN' }),
                    api.getWorkerTasks({ status: backendStatus, limit: 50, worker_role: 'CHECKOUT' }),
                ]);
                // Merge and deduplicate by task_id
                const merged = new Map<string, WorkerTask>();
                for (const t of [...(checkinResp.tasks ?? []), ...(checkoutResp.tasks ?? [])]) {
                    merged.set(t.task_id, t);
                }
                setTasks(Array.from(merged.values()));
            } else {
                const resp = await api.getWorkerTasks({
                    status: backendStatus,
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

    // Phase 889 fix: Booking enrichment as a SEPARATE one-shot effect.
    // Fires when tasks change. Uses a ref-based dedup guard to avoid re-fetching
    // the same booking_ids on every render. Uses the ADMIN api client (not staffApi).
    useEffect(() => {
        const stayKinds = new Set(['CHECKIN_PREP', 'CHECKOUT_VERIFY', 'CHECKOUT_PREP', 'CLEANING', 'GUEST_WELCOME']);
        const newIds: string[] = [];
        for (const t of tasks) {
            if (t.booking_id && stayKinds.has(t.kind)) {
                newIds.push(t.booking_id);
            }
        }
        // Dedup: only fetch ids we haven't cached yet
        const toFetch = newIds.filter(id => !bookingCache[id]);
        if (toFetch.length === 0) return;

        let cancelled = false;
        (async () => {
            const patch: Record<string, { check_in?: string; check_out?: string; guest_name?: string; guest_count?: number }> = {};
            await Promise.allSettled(
                [...new Set(toFetch)].map(async (bId) => {
                    try {
                        const bk = await adminApiFetch<any>(`/bookings/${bId}`);
                        if (bk && (bk.booking_id || bk.check_in)) {
                            patch[bId] = {
                                check_in: bk.check_in,
                                check_out: bk.check_out,
                                guest_name: bk.guest_name,
                                guest_count: bk.guest_count,
                            };
                        }
                    } catch { /* best-effort — admin token used */ }
                })
            );
            if (!cancelled && Object.keys(patch).length > 0) {
                setBookingCache(prev => ({ ...prev, ...patch }));
            }
        })();
        return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [tasks]);

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
        // Phase 865: use getTabToken() for tab-aware SSE auth
        const token = typeof window !== 'undefined' ? getTabToken() ?? '' : '';
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
                    {(staffRole === null ? ADMIN_FILTERS : WORKER_FILTERS).map(f => (
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
                {!loading && (() => {
                    // Phase 887c: workers only see tasks for approved properties
                    const approvedSorted = sorted.filter(t =>
                        !propertyStatusMap[t.property_id] ||
                        propertyStatusMap[t.property_id] === 'approved'
                    );

                    // ── Admin view: dense grouped DayPropertyCard board ──
                    if (staffRole === null) {
                        if (sorted.length === 0) return <EmptyState filter={filter} />;
                        const groupedTasks: { key: string; date: string; propertyId: string; tasks: WorkerTask[] }[] = [];
                        const groupMap = new Map<string, WorkerTask[]>();
                        // Phase 889: attach booking data to tasks for nights display
                        const enrichedSorted = sorted.map(t => {
                            const bk = t.booking_id ? bookingCache[t.booking_id] : undefined;
                            return bk ? Object.assign({}, t, { _bookingCache: bk }) : t;
                        });
                        for (const t of enrichedSorted) {
                            const key = `${t.due_date}_${t.property_id}`;
                            if (!groupMap.has(key)) {
                                groupMap.set(key, []);
                                groupedTasks.push({ key, date: t.due_date || 'No Date', propertyId: t.property_id, tasks: groupMap.get(key)! });
                            }
                            groupMap.get(key)!.push(t);
                        }
                        return (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                                {groupedTasks.map((group, idx) => (
                                    <div key={group.key} className="task-card-enter" style={{ animationDelay: `${idx * 40}ms` }}>
                                        <DayPropertyCard
                                            propertyId={group.propertyId}
                                            date={group.date}
                                            tasks={group.tasks}
                                            onOpen={setDetailId}
                                            propertyMap={propertyMap}
                                            staffMap={staffMap}
                                        />
                                    </div>
                                ))}
                            </div>
                        );
                    }

                    // ── Worker/preview view: flat WorkerTaskCard list ──
                    if (approvedSorted.length === 0) return <EmptyState filter={filter} />;
                    return (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                            {approvedSorted.map((t, idx) => {
                                const propName = propertyMap[t.property_id] || t.property_id;
                                const bk = t.booking_id ? bookingCache[t.booking_id] : undefined;

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
                                            guestName={bk?.guest_name || t.title || ''}
                                            guestCount={bk?.guest_count}
                                            checkIn={bk?.check_in}
                                            checkOut={bk?.check_out}
                                            onStart={() => window.location.href = dest}
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
                    );
                })()}

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

