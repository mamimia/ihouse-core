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
    
    useEffect(() => {
        if (task.status === 'completed' || task.status === 'canceled') return;
        const timer = setInterval(() => setNow(Date.now()), 1000);
        return () => clearInterval(timer);
    }, [task.status]);
    
    if (task.status === 'completed') {
        return <span style={{ color: 'var(--color-ok)', fontSize: 11, fontWeight: 700 }}>✔ DONE</span>;
    }
    if (task.status === 'canceled') {
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
// Task Card
// ---------------------------------------------------------------------------

interface DayPropertyCardProps {
    propertyId: string;
    date: string;
    tasks: WorkerTask[];
    onOpen: (id: string) => void;
    propertyMap: Record<string, string>;
    staffMap: Record<string, { name: string; photo: string }>;
}

import { useRouter } from 'next/navigation';

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
                {tasks.map((task, idx) => (
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
                                 </span>
                                 <span 
                                    onClick={(e) => { e.stopPropagation(); router.push(`/bookings/${task.booking_id}`); }}
                                    style={{ fontSize: 10, cursor: 'pointer', color: 'var(--color-text-faint)', textDecoration: 'underline', width: 'fit-content' }}
                                    title="View Booking"
                                 >
                                    #{task.booking_id.split('-').pop()}
                                 </span>
                             </div>
                             <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                                 {task.priority === 'CRITICAL' && task.status === 'pending' && <span style={{ fontSize: 9, color: '#fff', background: '#f85149', padding: '2px 4px', borderRadius: 4, fontWeight: 700 }}>CRITICAL</span>}
                                 {task.status !== 'completed' && task.status !== 'pending' && (
                                    <span style={{ fontSize: 9, color: 'var(--color-primary)', background: 'rgba(88,166,255,0.1)', padding: '2px 4px', borderRadius: 4, fontWeight: 600 }}>
                                        {task.status.replace('_', ' ')}
                                    </span>
                                 )}
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

function EmptyState() {
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
            <div style={{ fontSize: '3rem' }}>✅</div>
            <div style={{ fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text)' }}>
                All clear!
            </div>
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                No tasks assigned to you right now.
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Status filter tabs
// ---------------------------------------------------------------------------

const FILTERS = [
    { label: 'All', value: '' },
    { label: 'Pending', value: 'pending' },
    { label: 'In Progress', value: 'in_progress' },
    { label: 'Done', value: 'completed' },
];

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function TasksPage() {
    const [tasks, setTasks] = useState<WorkerTask[]>([]);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState<string | null>(null);
    const [filter, setFilter] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [detailId, setDetailId] = useState<string | null>(null);
    const [propertyMap, setPropertyMap] = useState<Record<string, string>>({});
    const [staffMap, setStaffMap] = useState<Record<string, { name: string; photo: string }>>({});

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

    const loadTasks = useCallback(async () => {
        try {
            setError(null);
            const resp = await api.getWorkerTasks({ status: filter || undefined, limit: 50 });
            setTasks(resp.tasks ?? []);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to load tasks');
        } finally {
            setLoading(false);
        }
    }, [filter]);

    // Poll every 30s as fallback
    useEffect(() => {
        setLoading(true);
        loadTasks();
        const interval = setInterval(loadTasks, 30_000);
        return () => clearInterval(interval);
    }, [loadTasks]);

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

    return (
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
                {!loading && sorted.length === 0 && <EmptyState />}

                {!loading && sorted.length > 0 && (() => {
                    const groupedTasks: { key: string; date: string; propertyId: string; tasks: WorkerTask[] }[] = [];
                    const groupMap = new Map<string, WorkerTask[]>();
                    for (const t of sorted) {
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
}
