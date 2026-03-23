'use client';

/**
 * Phase 290 / 850 — Worker Mobile UI
 * Route: /worker
 *
 * Dedicated mobile-first app for field workers.
 * Fully polished Dashboard UI.
 */

import { useEffect, useState, useCallback } from 'react';
import { api, apiFetch, WorkerTask, WorkerChannel } from '../../../lib/api';
import { useLanguage } from '../../../lib/LanguageContext';
import CompactLangSwitcher from '../../../components/CompactLangSwitcher';
import MobileStaffShell from '../../../components/MobileStaffShell';
import { useRouter } from 'next/navigation';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function priorityBg(p: string) {
    switch (p?.toUpperCase()) {
        case 'CRITICAL': return 'var(--color-alert)'; // Warm Alert
        case 'HIGH': return 'var(--color-accent)'; // Signal Copper
        case 'MEDIUM': return 'var(--color-primary)'; // Deep Moss
        default: return 'var(--color-muted)'; // Quiet Olive
    }
}

function statusLabelEn(s: string) {
    const m: Record<string, string> = {
        pending: 'Pending',
        acknowledged: 'Acknowledged',
        in_progress: 'In Progress',
        completed: 'Completed',
        canceled: 'Canceled',
    };
    return m[s?.toLowerCase()] ?? s;
}

function kindLabelEn(k: string) {
    const m: Record<string, string> = {
        CLEANING: 'Cleaning',
        CHECKIN_PREP: 'Check-in Prep',
        CHECKOUT_VERIFY: 'Checkout Verification',
        MAINTENANCE: 'Maintenance',
        GENERAL: 'General Task',
        GUEST_WELCOME: 'Guest Welcome',
    };
    return m[k?.toUpperCase()] ?? k;
}

function kindEmoji(k: string) {
    const m: Record<string, string> = {
        CLEANING: '🧹',
        CHECKIN_PREP: '🏠',
        CHECKOUT_PREP: '📦',
        MAINTENANCE: '🔧',
        INSPECTION: '🔍',
    };
    return m[k?.toUpperCase()] ?? '📋';
}

function isOverdue(task: WorkerTask): boolean {
    if (!task.due_date || task.status?.toUpperCase() === 'COMPLETED' || task.status?.toUpperCase() === 'CANCELED') return false;
    const due = new Date(task.due_time
        ? `${task.due_date}T${task.due_time}`
        : `${task.due_date}T23:59:59`);
    return new Date() > due;
}

function fmtTime(iso: string, locale: string = 'en-US') {
    try { return new Date(iso).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', hour12: false }); }
    catch { return iso; }
}

function fmtDate(d: string, locale: string = 'en-US') {
    try {
        return new Date(d).toLocaleDateString(locale, { weekday: 'short', month: 'short', day: 'numeric' });
    } catch { return d; }
}

function getLocale(lang: string) {
    return lang === 'th' ? 'th-TH' : lang === 'he' ? 'he-IL' : 'en-US';
}

function parseJwt(token: string) {
    try { return JSON.parse(atob(token.split('.')[1])); }
    catch { return {}; }
}

// ---------------------------------------------------------------------------
// SLA Countdown
// ---------------------------------------------------------------------------

function SlaCountdown({ task }: { task: WorkerTask }) {
    const [ms, setMs] = useState<number | null>(null);

    useEffect(() => {
        if (task.priority !== 'CRITICAL' || task.status?.toUpperCase() !== 'PENDING') return;
        const calc = () => {
            const deadline = new Date(task.created_at).getTime() + (task.ack_sla_minutes ?? 5) * 60_000;
            return Math.max(0, deadline - Date.now());
        };
        setMs(calc());
        const t = setInterval(() => setMs(calc()), 1000);
        return () => clearInterval(t);
    }, [task]);

    if (ms === null) return null;
    const secs = Math.floor(ms / 1000);
    const mins = Math.floor(secs / 60);
    const s = secs % 60;
    const hot = ms < 60_000;
    const gone = ms === 0;

    return (
        <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            fontSize: 13, fontFamily: 'monospace',
            color: gone ? 'var(--color-sage)' : hot ? 'var(--color-alert)' : 'var(--color-accent)',
            animation: hot && !gone ? 'pulse 1s infinite' : 'none',
            marginTop: 6,
        }}>
            <span>⏱</span>
            <span>{gone ? 'SLA EXPIRED' : `${mins}:${String(s).padStart(2, '0')} to ack`}</span>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Task Card
// ---------------------------------------------------------------------------

interface CardProps { task: WorkerTask; propName?: string; onTap: () => void; }

function TaskCard({ task, propName, onTap }: CardProps) {
    const { lang, t } = useLanguage();
    const l = getLocale(lang);
    const overdue = isOverdue(task);
    const isCrit = task.priority === 'CRITICAL';
    const displayName = propName || task.property_id;

    return (
        <div
            id={`worker-task-${task.task_id}`}
            onClick={onTap}
            style={{
                background: 'var(--color-surface, #1F2329)',
                border: `1px solid ${overdue ? 'var(--color-alert)' : isCrit ? 'rgba(196,91,74,0.3)' : 'rgba(248,246,242,0.07)'}`,
                borderRadius: 16,
                padding: '16px 16px 16px 20px',
                position: 'relative',
                overflow: 'hidden',
                cursor: 'pointer',
                boxShadow: overdue
                    ? '0 0 18px rgba(196,91,74,0.2)'
                    : isCrit ? '0 0 10px rgba(196,91,74,0.1)' : '0 4px 12px rgba(0,0,0,0.25)',
                transition: 'transform 0.1s ease, box-shadow 0.15s ease',
            }}
        >
            <div style={{
                position: 'absolute', left: 0, top: 0, bottom: 0, width: 4,
                background: priorityBg(task.priority),
                borderRadius: '16px 0 0 16px',
            }} />

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                <div style={{ paddingRight: 10 }}>
                    <div style={{ fontSize: 11, color: 'var(--color-sage)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                        <span style={{ fontSize: 13 }}>{kindEmoji(task.kind)}</span>
                        <span style={{ fontWeight: 600 }}>{task.worker_role?.replace('_', ' ')}</span>
                    </div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--color-text)', lineHeight: 1.3 }}>
                        {kindLabelEn(task.kind)}
                    </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
                    <span style={{
                        fontSize: 10, fontWeight: 800, letterSpacing: '0.05em',
                        color: task.priority === 'CRITICAL' || task.priority === 'HIGH' ? 'var(--color-text)' : 'var(--color-text-dim)',
                        background: priorityBg(task.priority),
                        borderRadius: 4, padding: '3px 8px',
                    }}>{task.priority}</span>
                    <span style={{
                        fontSize: 11, fontWeight: 500, color: task.status?.toUpperCase() === 'COMPLETED' ? 'var(--color-muted)' : 'var(--color-sage)',
                    }}>{t(`status.${(task.status || '').toLowerCase()}` as Parameters<typeof t>[0]) || statusLabelEn(task.status)}</span>
                </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginTop: 12 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--color-text-dim)' }}>
                        🏡 <span style={{ fontWeight: 600, fontSize: 13 }}>{displayName}</span>
                    </span>
                    <span style={{ color: overdue ? 'var(--color-alert)' : 'var(--color-sage)', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                        🕒 {overdue && <span style={{ fontWeight: 700 }}>{t('worker.overdue') || 'Overdue'} - </span>}
                        {task.due_time ? fmtTime(`${task.due_date}T${task.due_time}`, l) : fmtDate(task.due_date, l)}
                    </span>
                </div>
                
                <button
                    onClick={async (e) => {
                        e.stopPropagation();
                        try {
                            const res = await apiFetch<any>(`/properties/${task.property_id}/location`);
                            const lat = res.latitude;
                            const lng = res.longitude;
                            if (lat != null && lng != null) {
                                const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
                                const url = isMobile
                                    ? `https://waze.com/ul?ll=${lat},${lng}&navigate=yes`
                                    : `https://maps.google.com/maps?daddr=${lat},${lng}`;
                                window.open(url, '_blank');
                            } else {
                                // Fallback: search by name
                                window.open(`https://www.waze.com/ul?q=${encodeURIComponent(displayName)}`, '_blank');
                            }
                        } catch {
                            // GPS API unavailable — fallback to name search
                            window.open(`https://www.waze.com/ul?q=${encodeURIComponent(displayName)}`, '_blank');
                        }
                    }}
                    style={{
                        background: 'var(--color-primary)',
                        color: 'var(--color-text)',
                        border: '1px solid var(--color-muted)',
                        padding: '6px 12px',
                        borderRadius: 8,
                        fontSize: 12,
                        fontWeight: 600,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        cursor: 'pointer',
                        transition: 'background 0.2s',
                    }}
                >
                    📍 Navigate
                </button>
            </div>

            {task.priority === 'CRITICAL' && task.status?.toUpperCase() === 'PENDING' && (
                <div style={{ marginTop: 8 }}><SlaCountdown task={task} /></div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Detail Bottom Sheet
// ---------------------------------------------------------------------------

interface SheetProps {
    task: WorkerTask;
    propName?: string;
    onClose: () => void;
    onAck: (id: string) => Promise<void>;
    onComplete: (id: string, notes: string) => Promise<void>;
    loading: boolean;
}

function DetailSheet({ task, propName, onClose, onAck, onComplete, loading }: SheetProps) {
    const { lang, t } = useLanguage();
    const l = getLocale(lang);
    const [notes, setNotes] = useState('');
    const [view, setView] = useState<'detail' | 'complete'>('detail');
    const overdue = isOverdue(task);
    const isPending = task.status?.toUpperCase() === 'PENDING';
    const isAcked = task.status?.toUpperCase() === 'ACKNOWLEDGED' || task.status?.toUpperCase() === 'IN_PROGRESS';
    const isDone = task.status?.toUpperCase() === 'COMPLETED' || task.status?.toUpperCase() === 'CANCELED';

    return (
        <>
            <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 100, backdropFilter: 'blur(4px)' }} />
            <div style={{
                position: 'fixed', bottom: 0, left: 0, right: 0,
                background: 'var(--color-bg)', borderRadius: '24px 24px 0 0', zIndex: 101,
                padding: '0 0 env(safe-area-inset-bottom,24px)', maxHeight: '85vh', overflowY: 'auto',
                animation: 'slideUp 240ms cubic-bezier(0.32,0.72,0,1)',
            }}>
                <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 12, paddingBottom: 4 }}>
                    <div style={{ width: 40, height: 4, background: 'var(--color-surface-3)', borderRadius: 99 }} />
                </div>

                <div style={{ padding: '12px 20px 28px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                        <div>
                            <div style={{ fontSize: 12, color: 'var(--color-sage)', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                                {kindEmoji(task.kind)} {task.worker_role?.replace('_', ' ')}
                            </div>
                            <h2 style={{ fontSize: 20, fontWeight: 700, margin: 0, color: 'var(--color-text)', lineHeight: 1.2 }}>
                                {kindLabelEn(task.kind)}
                            </h2>
                        </div>
                        <button onClick={onClose} style={{
                            background: 'var(--color-surface-2)', border: 'none', color: 'var(--color-sage)',
                            width: 32, height: 32, borderRadius: 16, fontSize: 16, cursor: 'pointer'
                        }}>✕</button>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
                        <div style={{ background: 'var(--color-surface-2)', padding: 12, borderRadius: 12 }}>
                            <div style={{ fontSize: 11, color: 'var(--color-sage)', marginBottom: 2 }}>Property</div>
                            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text)' }}>{propName || task.property_id}</div>
                        </div>
                        <div style={{ background: 'var(--color-surface-2)', padding: 12, borderRadius: 12 }}>
                            <div style={{ fontSize: 11, color: 'var(--color-sage)', marginBottom: 2 }}>Due</div>
                            <div style={{ fontSize: 14, fontWeight: 600, color: overdue ? 'var(--color-alert)' : 'var(--color-text)' }}>
                                {task.due_time ? fmtTime(`${task.due_date}T${task.due_time}`, l) : fmtDate(task.due_date, l)}
                            </div>
                        </div>
                        <div style={{ background: 'var(--color-surface-2)', padding: 12, borderRadius: 12 }}>
                            <div style={{ fontSize: 11, color: 'var(--color-sage)', marginBottom: 2 }}>Priority</div>
                            <div style={{ fontSize: 14, fontWeight: 600, color: priorityBg(task.priority) }}>{task.priority}</div>
                        </div>
                        <div style={{ background: 'var(--color-surface-2)', padding: 12, borderRadius: 12 }}>
                            <div style={{ fontSize: 11, color: 'var(--color-sage)', marginBottom: 2 }}>Status</div>
                            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text)' }}>{statusLabelEn(task.status)}</div>
                        </div>
                    </div>

                    {task.priority === 'CRITICAL' && task.status?.toUpperCase() === 'PENDING' && (
                        <div style={{ marginBottom: 16 }}><SlaCountdown task={task} /></div>
                    )}

                    {view === 'detail' && (
                        <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
                            {isPending && (
                                <button
                                    disabled={loading}
                                    onClick={() => onAck(task.task_id)}
                                    style={{
                                        flex: 1, padding: 16, borderRadius: 12, border: 'none',
                                        background: 'var(--color-primary)', color: 'var(--color-text)', fontSize: 16, fontWeight: 700,
                                        opacity: loading ? 0.5 : 1, cursor: 'pointer',
                                    }}
                                >
                                    {loading ? '...' : (t('worker.btn_ack' as any) || 'Acknowledge')}
                                </button>
                            )}

                            {isAcked && (
                                <button
                                    onClick={() => setView('complete')}
                                    style={{
                                        flex: 1, padding: 16, borderRadius: 12, border: 'none',
                                        background: 'var(--color-muted)', color: 'var(--color-text)', fontSize: 16, fontWeight: 700, cursor: 'pointer',
                                    }}
                                >
                                    {(t('worker.btn_complete' as any) || 'Mark Complete')}
                                </button>
                            )}

                            {isDone && (
                                <div style={{ flex: 1, textAlign: 'center', padding: 16, color: 'var(--color-sage)', background: 'var(--color-surface-2)', borderRadius: 12 }}>
                                    Task completed or canceled.
                                </div>
                            )}
                        </div>
                    )}

                    {view === 'complete' && (
                        <div style={{ animation: 'fadeIn 200ms ease' }}>
                            <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text)', marginBottom: 8, marginTop: 0 }}>Add Notes (Optional)</h3>
                            <textarea
                                value={notes}
                                onChange={e => setNotes(e.target.value)}
                                placeholder="Any issues or details?"
                                style={{
                                    width: '100%', height: 100, background: 'var(--color-surface-2)', color: 'var(--color-text)',
                                    border: '1px solid var(--color-border)', borderRadius: 12, padding: 12,
                                    fontSize: 14, resize: 'none', marginBottom: 16,
                                }}
                            />
                            <div style={{ display: 'flex', gap: 12 }}>
                                <button
                                    onClick={() => setView('detail')}
                                    style={{ flex: 1, padding: 14, borderRadius: 12, border: 'none', background: 'var(--color-surface-3)', color: 'var(--color-text)', fontSize: 15, fontWeight: 600, cursor: 'pointer' }}
                                >Cancel</button>
                                <button
                                    disabled={loading}
                                    onClick={() => onComplete(task.task_id, notes)}
                                    style={{ flex: 2, padding: 14, borderRadius: 12, border: 'none', background: 'var(--color-muted)', color: 'var(--color-text)', fontSize: 15, fontWeight: 700, opacity: loading ? 0.5 : 1, cursor: 'pointer' }}
                                >{loading ? '...' : 'Confirm Complete'}</button>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}

// ---------------------------------------------------------------------------
// Worker Tab Bottom Navigation
// ---------------------------------------------------------------------------

type Tab = 'dashboard' | 'todo' | 'done' | 'settings';

function BottomNav({ tab, setTab, counts }: { tab: Tab; setTab: (t: Tab) => void; counts: Record<'todo' | 'done', number> }) {
    const { t } = useLanguage();
    const tabs = [
        { id: 'dashboard', label: 'Home', icon: 'N' },
        { id: 'todo', label: 'Tasks', icon: '📋' },
        { id: 'done', label: 'Done', icon: '✅' },
        { id: 'settings', label: 'Profile', icon: '⚙️' },
    ];

    return (
        <div style={{
            position: 'fixed', bottom: 0, left: 0, right: 0,
            background: 'rgba(23,26,31,0.85)',
            backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)',
            borderTop: '1px solid rgba(255,255,255,0.05)',
            display: 'flex', justifyContent: 'space-around', alignItems: 'center',
            paddingBottom: 'env(safe-area-inset-bottom, 0)',
            zIndex: 50,
        }}>
            {tabs.map(item => {
                const active = tab === item.id;
                const showBadge = item.id === 'todo' && counts.todo > 0;
                
                return (
                    <button
                        key={item.id}
                        onClick={() => setTab(item.id as Tab)}
                        style={{
                            flex: 1, background: 'none', border: 'none',
                            padding: '12px 0 8px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
                            color: active ? 'var(--color-accent)' : 'var(--color-text-faint)',
                            transition: 'color 0.2s', cursor: 'pointer', position: 'relative',
                        }}
                    >
                        <div style={{ position: 'relative' }}>
                            <div style={{ fontSize: 22, height: 24, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: active ? 1 : 0.7 }}>
                                {item.icon === 'N' ? (
                                    <div style={{ width: 24, height: 24, borderRadius: 12, background: active ? 'var(--color-accent)' : 'var(--color-surface-3)', color: 'var(--color-bg)', fontWeight: 800, fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>N</div>
                                ) : item.icon}
                            </div>
                            {showBadge && (
                                <div style={{
                                    position: 'absolute', top: -6, right: -10,
                                    background: 'var(--color-alert)', color: 'var(--color-text)',
                                    fontSize: 10, fontWeight: 700,
                                    padding: '2px 6px', borderRadius: 99,
                                    border: '2px solid var(--color-bg)',
                                }}>{counts.todo > 99 ? '99+' : counts.todo}</div>
                            )}
                        </div>
                        <span style={{ fontSize: 10, fontWeight: active ? 600 : 500 }}>{item.label}</span>
                    </button>
                );
            })}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Settings Tab
// ---------------------------------------------------------------------------

function SettingsTab({ showToast, userName }: { showToast: (msg: string) => void; userName?: string }) {
    const { lang, t } = useLanguage();
    const l = getLocale(lang);
    const router = useRouter();
    const initial = (userName || 'S').charAt(0).toUpperCase();

    return (
        <div style={{ padding: '20px', animation: 'fadeIn 200ms ease' }}>
            <h2 style={{ fontSize: 24, fontWeight: 800, color: 'var(--color-text)', marginBottom: 24 }}>My Profile</h2>
            
            <div style={{ background: 'var(--color-surface-2)', borderRadius: 16, overflow: 'hidden', marginBottom: 24 }}>
                <div style={{ padding: 20, borderBottom: '1px solid var(--color-border)', display: 'flex', alignItems: 'center', gap: 16 }}>
                    <div style={{ width: 60, height: 60, borderRadius: 30, background: 'var(--color-primary)', color: 'var(--color-text)', fontSize: 24, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {initial}
                    </div>
                    <div>
                        <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text)' }}>My Profile</div>
                        <div style={{ fontSize: 14, color: 'var(--color-sage)' }}>Domaniqo Staff</div>
                    </div>
                </div>
            </div>

            <button 
                onClick={() => {
                    localStorage.removeItem('ihouse_token');
                    router.push('/login');
                }}
                style={{
                    width: '100%', padding: 16, background: 'rgba(196,91,74,0.12)', color: 'var(--color-alert)',
                    border: '1px solid rgba(196,91,74,0.3)', borderRadius: 12, fontSize: 16, fontWeight: 700,
                    cursor: 'pointer'
                }}
            >
                Sign Out
            </button>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function WorkerPage() {
    const [tasks, setTasks] = useState<WorkerTask[]>([]);
    const [propMap, setPropMap] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState(false);
    const [selected, setSelected] = useState<WorkerTask | null>(null);
    const [tab, setTab] = useState<Tab>('dashboard');
    const [error, setError] = useState<string | null>(null);
    const [toast, setToast] = useState<string | null>(null);
    const [userName, setUserName] = useState('');
    const [userRole, setUserRole] = useState('Staff Member');
    const { lang, t } = useLanguage();
    const l = getLocale(lang);
    const router = useRouter();

    const showToast = (msg: string) => {
        setToast(msg);
        setTimeout(() => setToast(null), 2500);
    };

    const load = useCallback(async () => {
        try {
            setError(null);
            const resp = await api.getWorkerTasks({ limit: 100 });
            setTasks(resp.tasks ?? []);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        setLoading(true);
        load();
        
        // Load properties
        api.listProperties().then((res: any) => {
            const m: Record<string, string> = {};
            res.properties?.forEach((p: any) => m[p.property_id] = p.display_name);
            setPropMap(m);
        }).catch(() => {});

        // Parse token for greeting
        const ROLE_DISPLAY_LABELS: Record<string, string> = {
            admin: 'Admin', manager: 'Ops Manager', owner: 'Owner',
            worker: 'Staff Member', cleaner: 'Cleaner',
            checkin: 'Check-in', checkin_staff: 'Check-in',
            checkout: 'Check-out', maintenance: 'Maintenance',
            ops: 'Operations',
        };
        const token = typeof window !== 'undefined' ? localStorage.getItem('ihouse_token') : null;
        if (token) {
            const p = parseJwt(token);
            if (p.email) setUserName(p.email.split('@')[0]);
            if (p.role) setUserRole(ROLE_DISPLAY_LABELS[p.role] || 'Staff Member');
        }
    }, [load]);

    const handleAck = async (id: string) => {
        setActionLoading(true);
        try {
            await api.acknowledgeTask(id);
            showToast('✓ Task acknowledged');
            setSelected(null);
            await load();
        } catch {
            showToast('⚠ Acknowledge failed');
        } finally {
            setActionLoading(false);
        }
    };

    const handleComplete = async (id: string, notes: string) => {
        setActionLoading(true);
        try {
            await api.completeTask(id, notes || undefined);
            showToast('✅ Task completed!');
            setSelected(null);
            await load();
        } catch {
            showToast('⚠ Complete failed');
        } finally {
            setActionLoading(false);
        }
    };

    // Tab filters
    const todo = tasks
        .filter(t => t.status?.toUpperCase() !== 'COMPLETED' && t.status?.toUpperCase() !== 'CANCELED')
        .sort((a, b) => {
            const pm: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
            const pa = pm[a.priority] ?? 9;
            const pb = pm[b.priority] ?? 9;
            if (pa !== pb) return pa - pb;
            return (a.due_time ?? '').localeCompare(b.due_time ?? '');
        });

    const done = tasks
        .filter(t => t.status?.toUpperCase() === 'COMPLETED' || t.status?.toUpperCase() === 'CANCELED')
        .slice(0, 30);

    const openCount = tasks.filter(t => t.status?.toUpperCase() === 'PENDING').length;
    const overdueCount = tasks.filter(t => isOverdue(t) && t.status?.toUpperCase() !== 'COMPLETED').length;
    const dueTodayCount = todo.filter(t => t.due_date === new Date().toISOString().split('T')[0]).length;

    const visible = tab === 'todo' ? todo : done;

    return (
        <MobileStaffShell hideHeader>
            <style>{`
        @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:.5 } }
        @keyframes slideUp { from { opacity:0; transform:translateY(24px) } to { opacity:1; transform:translateY(0) } }
        @keyframes fadeIn { from { opacity:0 } to { opacity:1 } }
        @keyframes toastIn { from { opacity:0; transform:translateX(-50%) translateY(12px) } to { opacity:1; transform:translateX(-50%) translateY(0) } }
        * { box-sizing:border-box }
      `}</style>

            <div style={{
                minHeight: '100vh',
                color: 'var(--color-text)', fontFamily: "'Inter', -apple-system, sans-serif",
                paddingBottom: 80,
            }}>
                {/* Header (Hidden on Dashboard because Dasboard has its own header) */}
                {tab !== 'dashboard' && (
                    <div style={{
                        padding: '20px 20px 12px',
                        background: 'linear-gradient(180deg, var(--color-bg, #171A1F) 60%, transparent 100%)',
                        position: 'sticky', top: 0, zIndex: 30,
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                    }}>
                        <div>
                            <h1 style={{ fontSize: 24, fontWeight: 800, color: 'var(--color-text)', margin: 0, letterSpacing: '-0.03em' }}>
                                {tab === 'todo' ? 'Tasks' : tab === 'done' ? 'Done' : 'Profile'}
                            </h1>
                            <p style={{ fontSize: 13, color: 'var(--color-sage)', margin: '2px 0 0' }}>
                                {new Date().toLocaleDateString(getLocale(lang), { weekday: 'long', month: 'short', day: 'numeric' })}
                            </p>
                        </div>
                    </div>
                )}

                {/* Dashboard Tab */}
                {tab === 'dashboard' && (
                    <div style={{ padding: '0', animation: 'fadeIn 200ms ease' }}>
                        
                        {/* Top Navbar */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px' }}>
                            <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.02em' }}>Dashboard</div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                                <CompactLangSwitcher theme="dark" position="inline" />
                                <button
                                    onClick={() => { localStorage.removeItem('ihouse_token'); router.push('/login'); }}
                                    style={{ background: 'none', border: 'none', color: 'var(--color-sage)', fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
                                >
                                    ➔ Sign Out
                                </button>
                            </div>
                        </div>

                        <div style={{ padding: '0 20px' }}>

                            {/* Welcome Card */}
                            <div style={{ background: 'var(--color-surface-2)', borderRadius: 16, padding: 20, marginBottom: 24 }}>
                                <div style={{ fontSize: 11, color: 'var(--color-sage)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>Welcome</div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                    <div style={{ fontSize: 24, color: 'var(--color-text)' }}>
                                        Hello, <span style={{ fontWeight: 700 }}>{userName || 'Staff'}</span>
                                    </div>
                                    <span style={{ background: 'var(--color-surface-3)', color: 'var(--color-text-dim)', fontSize: 11, fontWeight: 700, padding: '2px 10px', borderRadius: 99 }}>
                                        {userRole}
                                    </span>
                                </div>
                            </div>

                            {/* Quick Actions */}
                            <div style={{ marginBottom: 24 }}>
                                <div style={{ fontSize: 12, color: 'var(--color-sage)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>Quick Actions</div>
                                <div style={{ display: 'flex', gap: 12 }}>
                                    <button onClick={() => setTab('todo')} style={{ flex: 1, background: 'var(--color-surface-2)', border: 'none', borderRadius: 12, padding: '16px', color: 'var(--color-text)', fontSize: 14, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                                        📋 My Tasks
                                    </button>
                                    <button onClick={() => setTab('settings')} style={{ flex: 1, background: 'var(--color-surface-2)', border: 'none', borderRadius: 12, padding: '16px', color: 'var(--color-text)', fontSize: 14, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                                        ⚙️ My Profile
                                    </button>
                                </div>
                            </div>

                            {/* My Status */}
                            <div style={{ marginBottom: 32 }}>
                                <div style={{ fontSize: 12, color: 'var(--color-sage)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>My Status</div>
                                <div style={{ display: 'flex', gap: 12 }}>
                                    <div style={{ flex: 1, background: 'var(--color-surface-2)', borderRadius: 12, padding: 16 }}>
                                        <div style={{ fontSize: 11, color: 'var(--color-sage)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 4 }}>📋 Open Tasks</div>
                                        <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--color-text)' }}>{openCount}</div>
                                    </div>
                                    <div style={{ flex: 1, background: 'var(--color-surface-2)', borderRadius: 12, padding: 16 }}>
                                        <div style={{ fontSize: 11, color: 'var(--color-sage)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 4 }}>🕒 Overdue</div>
                                        <div style={{ fontSize: 28, fontWeight: 700, color: overdueCount > 0 ? 'var(--color-alert)' : 'var(--color-text)' }}>{overdueCount}</div>
                                    </div>
                                    <div style={{ flex: 1, background: 'var(--color-surface-2)', borderRadius: 12, padding: 16 }}>
                                        <div style={{ fontSize: 11, color: 'var(--color-sage)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 4 }}>📅 Due Today</div>
                                        <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--color-text)' }}>{dueTodayCount}</div>
                                    </div>
                                </div>
                            </div>

                            {/* Next Tasks */}
                            <div>
                                <div style={{ fontSize: 12, color: 'var(--color-sage)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>Next Tasks</div>
                                <div style={{ background: 'var(--color-surface-2)', borderRadius: 16, padding: '32px 20px', textAlign: 'center' }}>
                                    {todo.length === 0 ? (
                                        <div style={{ color: 'var(--color-sage)', fontSize: 14 }}>No tasks yet.</div>
                                    ) : (
                                        <>
                                            <div style={{ color: 'var(--color-text)', fontSize: 15, fontWeight: 600, marginBottom: 16 }}>You have {todo.length} tasks in your queue.</div>
                                            <button onClick={() => setTab('todo')} style={{ background: 'var(--color-primary)', color: 'var(--color-text)', border: 'none', padding: '10px 20px', borderRadius: 99, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
                                                View My Tasks ➔
                                            </button>
                                        </>
                                    )}
                                </div>
                            </div>

                        </div>
                    </div>
                )}

                {/* Task list */}
                {!loading && (tab === 'todo' || tab === 'done') && (
                    <div style={{ padding: '0 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                        {visible.length === 0 && (
                            <div style={{
                                textAlign: 'center', padding: '60px 20px',
                                color: 'var(--color-muted)',
                            }}>
                                <div style={{ fontSize: 48, marginBottom: 12 }}>
                                    {tab === 'done' ? '✅' : '🎉'}
                                </div>
                                <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--color-sage)' }}>
                                    {tab === 'done' ? 'No completed tasks yet' : 'All clear!'}
                                </div>
                            </div>
                        )}
                        {visible.map(task => (
                            <div key={task.task_id} style={{ animation: 'fadeIn 200ms ease' }}>
                                <TaskCard task={task} propName={propMap[task.property_id]} onTap={() => setSelected(task)} />
                            </div>
                        ))}
                    </div>
                )}

                {/* Settings tab */}
                {tab === 'settings' && <SettingsTab showToast={showToast} userName={userName} />}

                {/* Detail Sheet */}
                {selected && (
                    <DetailSheet
                        task={selected}
                        propName={propMap[selected.property_id]}
                        loading={actionLoading}
                        onClose={() => setSelected(null)}
                        onAck={handleAck}
                        onComplete={handleComplete}
                    />
                )}
            </div>

            {/* Error Toast */}
            {error && (
                <div style={{ position: 'fixed', top: 20, left: '50%', transform: 'translateX(-50%)', background: 'var(--color-alert)', color: 'var(--color-text)', padding: '12px 24px', borderRadius: 12, zIndex: 200, boxShadow: '0 4px 12px rgba(239,68,68,0.3)' }}>
                    {error}
                </div>
            )}

            {/* Success Toast */}
            {toast && (
                <div style={{ position: 'fixed', bottom: 100, left: '50%', transform: 'translateX(-50%)', background: 'var(--color-muted)', color: 'var(--color-text)', padding: '12px 24px', borderRadius: 99, zIndex: 100, fontWeight: 600, animation: 'toastIn 300ms cubic-bezier(0.34,1.56,0.64,1)', boxShadow: '0 4px 12px rgba(16,185,129,0.3)' }}>
                    {toast}
                </div>
            )}

            <BottomNav tab={tab} setTab={setTab} counts={{ todo: todo.length, done: done.length }} />
        </MobileStaffShell>
    );
}
