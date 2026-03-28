'use client';

/**
 * Phase 290 / 850 — Worker Mobile UI
 * Phase 884 — Role-aware Home layer
 * Phase 865 — Uses getTabToken for Act As tab isolation
 * Route: /worker
 *
 * Shared Home page for all field worker roles.
 * Role is resolved from:
 *   1. sessionStorage.ihouse_preview_role  (Preview As)
 *   2. JWT payload.role                    (real worker login or Act As)
 * Each role sees role-correct stats + a CTA linking to /ops/[role].
 * Admin/unknown roles are redirected to /dashboard.
 */

import { useEffect, useState, useCallback } from 'react';
import type { WorkerTask } from '../../../lib/api';
import { apiFetch } from '../../../lib/staffApi';
import { getTabToken } from '../../../lib/tokenStore';

import { useLanguage } from '../../../lib/LanguageContext';
import CompactLangSwitcher from '../../../components/CompactLangSwitcher';
import MobileStaffShell from '../../../components/MobileStaffShell';
import { LiveCountdown } from '../../../components/WorkerTaskCard';
import { useRouter } from 'next/navigation';

// ---------------------------------------------------------------------------
// Phase 884 — Role Config
// ---------------------------------------------------------------------------

type WorkerRoleKey = 'cleaner' | 'checkin' | 'checkout' | 'maintenance';
// Note: 'checkin_checkout' combined role uses /ops/checkin-checkout as its own hub/home
// and does NOT use /worker as home. Those workers are handled by the hub page.

interface WorkerRoleConfig {
    key:         WorkerRoleKey;
    displayName: string;   // shown in role badge
    workHref:    string;   // /ops/[role] — the work/execution page
    workLabel:   string;   // button label for the CTA
    workIcon:    string;   // emoji
    taskRole:    string;   // backend worker_role= filter for stats query
}

const ROLE_CONFIGS: Record<WorkerRoleKey, WorkerRoleConfig> = {
    cleaner: {
        key: 'cleaner', displayName: 'Cleaner',
        workHref: '/ops/cleaner', workLabel: 'Go to Cleaning', workIcon: '🧹',
        taskRole: 'CLEANER',
    },
    checkin: {
        key: 'checkin', displayName: 'Check-in Staff',
        workHref: '/ops/checkin', workLabel: 'Go to Check-ins', workIcon: '📋',
        taskRole: 'CHECKIN',
    },
    checkout: {
        key: 'checkout', displayName: 'Check-out Staff',
        workHref: '/ops/checkout', workLabel: 'Go to Check-outs', workIcon: '🚪',
        taskRole: 'CHECKOUT',
    },
    maintenance: {
        key: 'maintenance', displayName: 'Maintenance',
        workHref: '/ops/maintenance', workLabel: 'Go to Maintenance', workIcon: '🔧',
        taskRole: 'MAINTENANCE',
    },
};

/**
 * Phase 948g — Canonical Worker Role Resolution
 *
 * Routing Rules:
 *   1. Preview As override  → returns exact preview role
 *   2. JWT worker_role      → primary sub-role (set by admin, e.g. "cleaner")
 *   3. JWT worker_roles[0]  → first entry if worker_role is null
 *   4. JWT role == "admin"  → redirect to /dashboard
 *   5. JWT role == "checkin_checkout" → explicit combined role (NOT a fallback)
 *   6. No sub-role found & role == "worker" → returns null (generic home)
 *      This is NOT 'checkin_checkout'. The generic worker home shows
 *      a "no role assigned" state, not the combined check-in/check-out surface.
 *
 * INVARIANT: A worker NEVER enters the 'checkin_checkout' surface unless their
 * explicit stored worker_role or worker_roles includes 'checkin_checkout'.
 */
function resolveWorkerRole(): WorkerRoleKey | 'admin' | 'checkin_checkout' | null {
    if (typeof window === 'undefined') return null;
    // 1. Preview As (sessionStorage override — read-only inspection)
    const preview = sessionStorage.getItem('ihouse_preview_role');
    if (preview) return preview as WorkerRoleKey | 'admin' | 'checkin_checkout';
    // 2. JWT — handles both Act As (token_type=act_as) and normal login
    // Phase 865: use getTabToken() for sessionStorage-first isolation
    const token = getTabToken();
    if (!token) return null;
    try {
        const p = JSON.parse(atob(token.split('.')[1]));
        const outerRole = (p.role as string || '').toLowerCase();

        // Admin/manager → redirect out
        if (outerRole === 'admin' || outerRole === 'manager') return 'admin';

        // Explicit combined role (only if stored as such — never a fallback)
        if (outerRole === 'checkin_checkout') return 'checkin_checkout';

        // For role=worker, resolve from the real stored sub-role
        if (outerRole === 'worker') {
            // Phase 989: Check for combined checkin+checkout first
            const workerRolesArr: string[] = (p.worker_roles as string[] | undefined) ?? [];
            const rolesSet = new Set(workerRolesArr.map((r: string) => r.toLowerCase()));
            if (rolesSet.has('checkin') && rolesSet.has('checkout')) {
                return 'checkin_checkout';
            }

            const subRole = (
                (p.worker_role as string) ||
                (workerRolesArr[0]) ||
                ''
            ).toLowerCase();

            // Only accept recognized configs or explicit 'checkin_checkout'
            if (subRole && (ROLE_CONFIGS[subRole as WorkerRoleKey] || subRole === 'checkin_checkout')) {
                return subRole as WorkerRoleKey | 'checkin_checkout';
            }
            // No recognized sub-role → null (generic home, NOT combined view)
            return null;
        }

        // Direct sub-role login (e.g., role=cleaner directly in JWT)
        if (ROLE_CONFIGS[outerRole as WorkerRoleKey]) {
            return outerRole as WorkerRoleKey;
        }

        return null;
    } catch { return null; }
}


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
                    <span style={{ fontSize: 12 }}>
                        <LiveCountdown
                            targetDate={task.due_date}
                            targetTime={task.due_time || undefined}
                            status={task.status || 'PENDING'}
                        />
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

// DetailSheet removed — Phase 979i:
// Generic modal was wrong for role-specific task flows and leaked untranslated
// i18n tokens (worker.btn_complete). Next Up taps now navigate directly to the
// real task flow surface for each role.

// ---------------------------------------------------------------------------
// Phase 884 — Role-Aware Worker Home Bottom Nav
// Tab pattern: Home (active) · Work → /ops/[role] · Tasks → /tasks · Profile (in-page)
// ---------------------------------------------------------------------------

type Tab = 'dashboard' | 'settings';
// 'todo' and 'done' tabs removed — Tasks routes to /tasks (role-filtered, Phase 883)

function WorkerHomeNav({
    tab, setTab, roleConfig,
}: {
    tab: Tab; setTab: (t: Tab) => void; roleConfig: WorkerRoleConfig | null;
}) {
    const { t } = useLanguage();
    const navStyle: React.CSSProperties = {
        position: 'fixed', bottom: 0, left: 0, right: 0,
        background: 'rgba(23,26,31,0.95)',
        backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        display: 'flex', justifyContent: 'space-around', alignItems: 'center',
        paddingBottom: 'env(safe-area-inset-bottom, 0)',
        zIndex: 50,
    };
    const btnStyle = (active: boolean): React.CSSProperties => ({
        flex: 1, background: 'none', border: 'none',
        padding: '12px 0 8px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
        color: active ? 'var(--color-accent)' : 'var(--color-text-faint)',
        transition: 'color 0.15s', cursor: 'pointer',
        fontSize: 10, fontWeight: active ? 700 : 500,
    });
    const iconStyle: React.CSSProperties = { fontSize: 20, lineHeight: 1 };

    return (
        <div style={navStyle}>
            {/* Home — always active on this page */}
            <button style={btnStyle(tab === 'dashboard')} onClick={() => setTab('dashboard')}>
                <span style={iconStyle}>🏠</span>{t('worker.home' as any)}
            </button>

            {/* Work — routes out to /ops/[role] */}
            {roleConfig && (
                <a href={roleConfig.workHref} style={{ ...btnStyle(false), textDecoration: 'none' }}>
                    <span style={iconStyle}>{roleConfig.workIcon}</span>
                    {t('worker.work' as any)}
                </a>
            )}

            {/* Tasks — routes to role-filtered /tasks */}
            <a href="/tasks" style={{ ...btnStyle(false), textDecoration: 'none' }}>
                <span style={iconStyle}>✓</span>{t('nav.tasks' as any)}
            </a>

            {/* Profile — in-page tab */}
            <button style={btnStyle(tab === 'settings')} onClick={() => setTab('settings')}>
                <span style={iconStyle}>⚙️</span>Profile
            </button>
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
                {t('worker.sign_out' as any)}
            </button>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main Page — Phase 884 Role-Aware
// ---------------------------------------------------------------------------

export default function WorkerPage() {
    const [tasks, setTasks] = useState<WorkerTask[]>([]);
    const [propMap, setPropMap] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(true);
    const [tab, setTab] = useState<Tab>('dashboard');
    const [error, setError] = useState<string | null>(null);
    const [toast, setToast] = useState<string | null>(null);
    const [userName, setUserName] = useState('');
    const [roleConfig, setRoleConfig] = useState<WorkerRoleConfig | null>(null);
    // Phase 948g: Explicit flag — true ONLY for workers whose stored role is 'checkin_checkout'.
    // Prevents accidental combined-view rendering for workers with missing sub-roles.
    const [isCombinedRole, setIsCombinedRole] = useState(false);
    const { lang, t } = useLanguage();
    const l = getLocale(lang);
    const router = useRouter();

    const showToast = (msg: string) => {
        setToast(msg);
        setTimeout(() => setToast(null), 2500);
    };

    // Phase 884 — role-scoped task query
    const load = useCallback(async (taskRole?: string) => {
        try {
            setError(null);
            const url = taskRole
                ? `/worker/tasks?worker_role=${taskRole}&limit=100`
                : '/worker/tasks?limit=100';
            const res = await apiFetch<any>(url);
            const list = res.tasks || res.data?.tasks || res.data || [];
            setTasks(Array.isArray(list) ? list : []);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        // Phase 884 — resolve role, guard admin
        const resolved = resolveWorkerRole();

        // Phase 887: Combined-role workers CAN access /worker as their profile/home layer.
        // Previously we bounced them back to /ops/checkin-checkout immediately, which
        // made the Profile & Settings link a dead end. Now we detect the combined role
        // and render a minimal profile view instead of redirecting.
        if (resolved === 'admin') {
            router.replace('/dashboard');
            return;
        }
        if (resolved === 'checkin_checkout') {
            // Stay on /worker — render combined profile view (only for explicit checkin_checkout)
            setRoleConfig(null);
            setIsCombinedRole(true);
            const token = typeof window !== 'undefined' ? getTabToken() : null;
            if (token) {
                const p = parseJwt(token);
                if (p.email) setUserName(p.email.split('@')[0]);
            }
            setLoading(false);
            return;
        }

        const config = resolved ? ROLE_CONFIGS[resolved as WorkerRoleKey] ?? null : null;
        setRoleConfig(config);

        setLoading(true);
        load(config?.taskRole);

        // Load properties for task cards
        apiFetch<any>('/properties').then((res: any) => {
            const m: Record<string, string> = {};
            (res.properties || []).forEach((p: any) => m[p.property_id] = p.display_name);
            setPropMap(m);
        }).catch(() => {});

        // Phase 865: use getTabToken() for tab-aware greeting (act_as or real login)
        const token = typeof window !== 'undefined' ? getTabToken() : null;
        if (token) {
            const p = parseJwt(token);
            if (p.email) setUserName(p.email.split('@')[0]);
        }
    }, [load, router]);

    // Role-scoped task stats
    const activeTasks = tasks.filter(t => t.status?.toUpperCase() !== 'COMPLETED' && t.status?.toUpperCase() !== 'CANCELED');
    const openCount    = activeTasks.filter(t => t.status?.toUpperCase() === 'PENDING').length;
    const overdueCount = activeTasks.filter(t => isOverdue(t)).length;
    const dueTodayCount = activeTasks.filter(t => t.due_date === new Date().toISOString().split('T')[0]).length;

    const todo = activeTasks.sort((a, b) => {
        const pm: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
        return (pm[a.priority] ?? 9) - (pm[b.priority] ?? 9);
    });

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
                                Profile
                            </h1>
                            <p style={{ fontSize: 13, color: 'var(--color-sage)', margin: '2px 0 0' }}>
                                {new Date().toLocaleDateString(getLocale(lang), { weekday: 'long', month: 'short', day: 'numeric' })}
                            </p>
                        </div>
                    </div>
                )}

                {/* ===== HOME / DASHBOARD TAB ===== */}
                {tab === 'dashboard' && (
                    <div style={{ padding: '0', animation: 'fadeIn 200ms ease' }}>

                        {/* Top bar */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px' }}>
                            <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.02em' }}>{t('worker.home' as any)}</div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                                <CompactLangSwitcher theme="dark" position="inline" />
                                <button
                                    onClick={() => { localStorage.removeItem('ihouse_token'); router.push('/login'); }}
                                    style={{ background: 'none', border: 'none', color: 'var(--color-sage)', fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
                                >
                                    ➔ {t('worker.sign_out' as any)}
                                </button>
                            </div>
                        </div>

                        <div style={{ padding: '0 20px' }}>

                            {/* Welcome card */}
                            <div style={{ background: 'var(--color-surface-2)', borderRadius: 16, padding: 20, marginBottom: 24 }}>
                                <div style={{ fontSize: 11, color: 'var(--color-sage)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>{t('worker.welcome_label' as any)}</div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                    <div style={{ fontSize: 24, color: 'var(--color-text)' }}>
                                        Hello, <span style={{ fontWeight: 700 }}>{userName || 'Staff'}</span>
                                    </div>
                                    {roleConfig ? (
                                        <span style={{ background: 'var(--color-surface-3)', color: 'var(--color-text-dim)', fontSize: 11, fontWeight: 700, padding: '2px 10px', borderRadius: 99 }}>
                                            {roleConfig.displayName}
                                        </span>
                                    ) : isCombinedRole ? (
                                        <span style={{ background: 'var(--color-surface-3)', color: 'var(--color-sage)', fontSize: 11, fontWeight: 700, padding: '2px 10px', borderRadius: 99 }}>
                                            Check-in &amp; Check-out
                                        </span>
                                    ) : null}
                                </div>
                            </div>

                            {/* Phase 887: Combined-role workers get a direct Work link back to their hub */}
                            {isCombinedRole && (
                                <div style={{ marginBottom: 24 }}>
                                    <div style={{ fontSize: 12, color: 'var(--color-sage)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>{t('worker.work' as any)}</div>
                                    <a href="/ops/checkin-checkout" style={{ textDecoration: 'none' }}>
                                        <div style={{
                                            background: 'var(--color-surface-2)', borderRadius: 16, padding: '20px',
                                            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                            border: '1px solid var(--color-border)',
                                        }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                                                <span style={{ fontSize: 32 }}>🏠🚪</span>
                                                <div>
                                                    <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--color-text)' }}>{t('worker.combined_hub' as any)}</div>
                                                    <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginTop: 2 }}>{t('worker.combined_hub_sub' as any)}</div>
                                                </div>
                                            </div>
                                            <span style={{ fontSize: 20, color: 'var(--color-text-faint)' }}>›</span>
                                        </div>
                                    </a>
                                </div>
                            )}

                            {/* Role-specific stats */}
                            <div style={{ marginBottom: 24 }}>
                                <div style={{ fontSize: 12, color: 'var(--color-sage)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>{t('worker.my_status' as any)}</div>
                                <div style={{ display: 'flex', gap: 12 }}>
                                    <div style={{ flex: 1, background: 'var(--color-surface-2)', borderRadius: 12, padding: 16 }}>
                                        <div style={{ fontSize: 11, color: 'var(--color-sage)', marginBottom: 8 }}>📋 {t('worker.stat_open' as any)}</div>
                                        <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--color-text)' }}>{openCount}</div>
                                    </div>
                                    <div style={{ flex: 1, background: 'var(--color-surface-2)', borderRadius: 12, padding: 16 }}>
                                        <div style={{ fontSize: 11, color: 'var(--color-sage)', marginBottom: 8 }}>🕒 {t('worker.stat_overdue' as any)}</div>
                                        <div style={{ fontSize: 28, fontWeight: 700, color: overdueCount > 0 ? 'var(--color-alert)' : 'var(--color-text)' }}>{overdueCount}</div>
                                    </div>
                                    <div style={{ flex: 1, background: 'var(--color-surface-2)', borderRadius: 12, padding: 16 }}>
                                        <div style={{ fontSize: 11, color: 'var(--color-sage)', marginBottom: 8 }}>📅 {t('worker.stat_today' as any)}</div>
                                        <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--color-text)' }}>{dueTodayCount}</div>
                                    </div>
                                </div>
                            </div>

                            {/* Role Work CTA — links to /ops/[role] */}
                            {roleConfig && (
                                <div style={{ marginBottom: 24 }}>
                                    <div style={{ fontSize: 12, color: 'var(--color-sage)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>{t('worker.work' as any)}</div>
                                    <a href={roleConfig.workHref} style={{ textDecoration: 'none' }}>
                                        <div style={{
                                            background: 'var(--color-surface-2)', borderRadius: 16, padding: '20px',
                                            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                            border: '1px solid var(--color-border)',
                                            transition: 'border-color 0.15s',
                                        }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                                                <span style={{ fontSize: 32 }}>{roleConfig.workIcon}</span>
                                                <div>
                                                    <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--color-text)' }}>{roleConfig.workLabel}</div>
                                                    <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginTop: 2 }}>
                                                        {openCount > 0 ? `${openCount} task${openCount > 1 ? 's' : ''} waiting` : 'No open tasks'}
                                                    </div>
                                                </div>
                                            </div>
                                            <span style={{ fontSize: 20, color: 'var(--color-text-faint)' }}>›</span>
                                        </div>
                                    </a>
                                </div>
                            )}

                            {/* Upcoming tasks summary — Phase 979i: taps navigate to real task flow */}
                            {todo.length > 0 && roleConfig && (
                                <div style={{ marginBottom: 24 }}>
                                    <div style={{ fontSize: 12, color: 'var(--color-sage)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>Next Up</div>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                        {todo.slice(0, 3).map(task => (
                                            <TaskCard
                                                key={task.task_id}
                                                task={task}
                                                propName={propMap[task.property_id]}
                                                onTap={() => router.push(roleConfig.workHref)}
                                            />
                                        ))}
                                        {todo.length > 3 && (
                                            <a href="/tasks" style={{
                                                display: 'block', textAlign: 'center', padding: '12px',
                                                background: 'var(--color-surface-2)', borderRadius: 12,
                                                color: 'var(--color-sage)', fontSize: 13, fontWeight: 600,
                                                textDecoration: 'none',
                                            }}>
                                                View all {todo.length} tasks →
                                            </a>
                                        )}
                                    </div>
                                </div>
                            )}

                        </div>
                    </div>
                )}

                {/* ===== PROFILE TAB ===== */}
                {tab === 'settings' && <SettingsTab showToast={showToast} userName={userName} />}

                {/* DetailSheet removed — Phase 979i: taps now navigate to real task flow */}
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

            <WorkerHomeNav tab={tab} setTab={setTab} roleConfig={roleConfig} />
        </MobileStaffShell>
    );
}
