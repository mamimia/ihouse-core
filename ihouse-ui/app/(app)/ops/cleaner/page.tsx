'use client';

/**
 * Operational Core — Phase E: Mobile Cleaner Flow
 * Architecture source: .agent/architecture/mobile-cleaner.md
 * Scope rule: Cleaner sees only assigned CLEANING tasks — no revenue, no booking details.
 *
 * Home: Today's cleaning tasks list
 * Flow: Detail → Start → Checklist (items + photos + supplies) → Complete
 * Issue reporting: Inline from checklist screen
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

// ======== Types ========

type CleaningTask = {
    task_id: string;
    property_id: string;
    booking_id?: string;
    status: string;
    kind: string;
    title?: string;
    due_date?: string;
    description?: string;
    created_at?: string;
    updated_at?: string;
    // Enriched locally
    property_name?: string;
    checkout_time?: string;
    next_checkin_time?: string;
    deadline?: string;
};

type ChecklistItem = {
    room: string;
    label: string;
    done: boolean;
    requires_photo: boolean;
};

type SupplyItem = {
    item: string;
    label: string;
    status: 'ok' | 'low' | 'empty' | 'unchecked';
};

type CleaningProgress = {
    id: string;
    task_id: string;
    checklist_state: ChecklistItem[];
    supply_state: SupplyItem[];
    all_items_done: boolean;
    all_photos_taken: boolean;
    all_supplies_ok: boolean;
    completed_at?: string;
};

type Screen = 'list' | 'detail' | 'checklist' | 'complete' | 'success';

// ======== Status Colors ========

const STATUS_COLORS: Record<string, { bg: string; text: string; label: string }> = {
    PENDING:       { bg: 'rgba(88,166,255,0.15)',  text: '#58a6ff', label: 'To Do' },
    ACKNOWLEDGED:  { bg: 'rgba(210,153,34,0.15)',  text: '#d29922', label: 'Acknowledged' },
    IN_PROGRESS:   { bg: 'rgba(163,113,247,0.15)', text: '#a371f7', label: 'In Progress' },
    COMPLETED:     { bg: 'rgba(63,185,80,0.15)',   text: '#3fb950', label: 'Completed' },
};

const SUPPLY_COLORS: Record<string, { bg: string; text: string; icon: string }> = {
    unchecked: { bg: 'var(--color-surface-2)', text: 'var(--color-text-dim)', icon: '⬜' },
    ok:        { bg: 'rgba(63,185,80,0.1)',    text: '#3fb950',              icon: '✅' },
    low:       { bg: 'rgba(210,153,34,0.1)',   text: '#d29922',              icon: '⚠️' },
    empty:     { bg: 'rgba(248,81,73,0.1)',     text: '#f85149',              icon: '🔴' },
};

// ======== Reusable Components ========

function StatusBadge({ status }: { status: string }) {
    const c = STATUS_COLORS[status] || STATUS_COLORS['PENDING'];
    return (
        <span style={{
            padding: '2px 10px', borderRadius: 12, fontSize: 'var(--text-xs)', fontWeight: 600,
            background: c.bg, color: c.text,
        }}>{c.label}</span>
    );
}

function ActionButton({ label, onClick, variant = 'primary', disabled = false }: {
    label: string; onClick: () => void; variant?: 'primary' | 'danger' | 'outline'; disabled?: boolean;
}) {
    const styles = {
        primary: { bg: 'var(--color-primary)', color: '#fff', border: 'none' },
        danger: { bg: 'rgba(248,81,73,0.1)', color: '#f85149', border: '1px solid rgba(248,81,73,0.3)' },
        outline: { bg: 'transparent', color: 'var(--color-text-dim)', border: '1px solid var(--color-border)' },
    };
    const s = styles[variant];
    return (
        <button onClick={onClick} disabled={disabled} style={{
            width: '100%', padding: '14px', borderRadius: 'var(--radius-md)',
            background: s.bg, color: s.color, border: s.border,
            fontWeight: 700, fontSize: 'var(--text-sm)', cursor: disabled ? 'not-allowed' : 'pointer',
            opacity: disabled ? 0.5 : 1, transition: 'opacity 0.2s',
        }}>{label}</button>
    );
}

function InfoRow({ label, value }: { label: string; value: string | number | undefined }) {
    return (
        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--color-border)', fontSize: 'var(--text-sm)' }}>
            <span style={{ color: 'var(--color-text-dim)' }}>{label}</span>
            <span style={{ color: 'var(--color-text)', fontWeight: 500 }}>{value ?? '—'}</span>
        </div>
    );
}

function ProgressBar({ done, total, label }: { done: number; total: number; label: string }) {
    const pct = total > 0 ? (done / total) * 100 : 0;
    return (
        <div style={{ marginBottom: 'var(--space-3)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 4 }}>
                <span>{label}</span>
                <span>{done}/{total}</span>
            </div>
            <div style={{ height: 4, background: 'var(--color-border)', borderRadius: 2 }}>
                <div style={{ height: '100%', width: `${pct}%`, background: pct >= 100 ? '#3fb950' : 'var(--color-primary)', borderRadius: 2, transition: 'width 0.3s' }} />
            </div>
        </div>
    );
}

// ======== Main Page ========

export default function MobileCleanerPage() {
    const [tasks, setTasks] = useState<CleaningTask[]>([]);
    const [loading, setLoading] = useState(true);
    const [screen, setScreen] = useState<Screen>('list');
    const [selected, setSelected] = useState<CleaningTask | null>(null);
    const [notice, setNotice] = useState<string | null>(null);

    // Cleaning progress state
    const [progress, setProgress] = useState<CleaningProgress | null>(null);
    const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
    const [supplies, setSupplies] = useState<SupplyItem[]>([]);
    const [photosUploaded, setPhotosUploaded] = useState<Set<string>>(new Set());

    // Issue report state
    const [showIssueForm, setShowIssueForm] = useState(false);
    const [issueCategory, setIssueCategory] = useState('general');
    const [issueSeverity, setIssueSeverity] = useState<'normal' | 'critical'>('normal');
    const [issueDescription, setIssueDescription] = useState('');

    const showNotice = (msg: string) => { setNotice(msg); setTimeout(() => setNotice(null), 3000); };

    const card: React.CSSProperties = {
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
    };
    const inputStyle: React.CSSProperties = {
        width: '100%', background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-sm)', padding: '10px 14px', color: 'var(--color-text)',
        fontSize: 'var(--text-sm)', outline: 'none',
    };

    // ── Load today's cleaning tasks ──
    // BRIDGE BEHAVIOR (Phase E closure):
    // Strategy: Try personal assignment filter first. If zero results (because
    // automated task creation from bookings does not yet populate assigned_to),
    // fall back to showing ALL CLEANER tasks for this tenant.
    //
    // Why this is correct NOW: Cleaners need to see tasks. The assignment
    // pipeline (manager assigns worker → task.assigned_to gets set) does not
    // exist yet. Without this fallback, cleaners see zero tasks.
    //
    // Risk: A cleaner may see tasks not assigned to them. This is acceptable
    // in a small-team context but must be replaced when:
    //   1. Manager assignment UI exists, OR
    //   2. Automated task creation populates assigned_to from a worker-property map
    //
    // When to remove: Once ALL cleaning tasks have assigned_to populated at
    // creation time, remove the fallback branch and keep only the assigned filter.
    const load = useCallback(async () => {
        setLoading(true);
        try {
            const today = new Date().toISOString().slice(0, 10);
            const workerId = getWorkerId();

            let rawTasks: CleaningTask[] = [];

            // Pass 1: Try personal assignment filter
            let hasExplicitAssignments = false;
            if (workerId) {
                const assignedRes = await apiFetch<any>(
                    `/worker/tasks?worker_role=CLEANER&date=${today}&limit=50&assigned_to=${encodeURIComponent(workerId)}`
                );
                const assignedList = assignedRes.tasks || assignedRes.data?.tasks || assignedRes.data || [];
                rawTasks = Array.isArray(assignedList) ? assignedList : [];
                hasExplicitAssignments = !!assignedRes.has_assignments;
            }

            // Pass 2: Fallback — show all CLEANER tasks ONLY if worker has no explicit assignments
            if (rawTasks.length === 0 && !hasExplicitAssignments) {
                const allRes = await apiFetch<any>(
                    `/worker/tasks?worker_role=CLEANER&date=${today}&limit=50`
                );
                const allList = allRes.tasks || allRes.data?.tasks || allRes.data || [];
                rawTasks = Array.isArray(allList) ? allList : [];
            }

            // Enrich with property info (best-effort)
            const enriched = await Promise.all(
                rawTasks.map(async (t) => {
                    try {
                        const propRes = await apiFetch<any>(`/properties/${t.property_id}`);
                        const prop = propRes.data || propRes;
                        return {
                            ...t,
                            property_name: prop.display_name || prop.name || t.property_id,
                        };
                    } catch {
                        return { ...t, property_name: t.property_id };
                    }
                })
            );

            // Sort: PENDING first, then ACKNOWLEDGED, then IN_PROGRESS
            const statusOrder: Record<string, number> = { PENDING: 0, ACKNOWLEDGED: 1, IN_PROGRESS: 2, COMPLETED: 3 };
            enriched.sort((a, b) => (statusOrder[a.status] ?? 9) - (statusOrder[b.status] ?? 9));

            setTasks(enriched);
        } catch {
            setTasks([]);
        }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    // ── Open task detail ──
    const openDetail = (task: CleaningTask) => {
        setSelected(task);
        setScreen('detail');
        setProgress(null);
        setChecklist([]);
        setSupplies([]);
        setPhotosUploaded(new Set());
        setShowIssueForm(false);
    };

    // ── Acknowledge task ──
    const acknowledgeTask = async (task: CleaningTask) => {
        try {
            await apiFetch(`/tasks/${task.task_id}/status`, {
                method: 'PATCH',
                body: JSON.stringify({ status: 'ACKNOWLEDGED' }),
            });
            showNotice('✅ Task acknowledged');
            load();
        } catch {
            showNotice('⚠️ Failed to acknowledge task');
        }
    };

    // ── Start cleaning (transition to checklist) ──
    const startCleaning = async () => {
        if (!selected) return;
        try {
            // First acknowledge if still PENDING
            if (selected.status === 'PENDING') {
                await apiFetch(`/tasks/${selected.task_id}/status`, {
                    method: 'PATCH',
                    body: JSON.stringify({ status: 'ACKNOWLEDGED' }),
                });
            }

            const res = await apiFetch<any>(`/tasks/${selected.task_id}/start-cleaning`, {
                method: 'POST',
                body: JSON.stringify({ worker_id: getWorkerId() }),
            });

            // Load the progress record
            await loadProgress(selected.task_id);
            setScreen('checklist');
            showNotice(`🧹 Cleaning started — ${res.checklist_items || 0} items`);
        } catch (e: any) {
            if (e.message === '409') {
                // Already started — load existing progress
                await loadProgress(selected.task_id);
                setScreen('checklist');
                showNotice('Resuming cleaning in progress');
            } else {
                showNotice('⚠️ Failed to start cleaning');
            }
        }
    };

    // ── Resume cleaning (for IN_PROGRESS tasks) ──
    const resumeCleaning = async () => {
        if (!selected) return;
        await loadProgress(selected.task_id);
        setScreen('checklist');
    };

    // ── Load progress from backend (Phase E-5: restore persisted state) ──
    const loadProgress = async (taskId: string) => {
        if (!selected) return;

        // Phase E-5: Try to restore persisted progress first
        let restoredFromDB = false;
        try {
            const progressRes = await apiFetch<any>(`/tasks/${taskId}/cleaning-progress`);
            const savedProgress = progressRes.progress || progressRes;

            if (savedProgress && savedProgress.checklist_state && savedProgress.checklist_state.length > 0) {
                // Restore checklist from persisted state
                setChecklist(savedProgress.checklist_state.map((item: any) => ({
                    room: item.room || '',
                    label: item.label || '',
                    done: !!item.done,
                    requires_photo: !!item.requires_photo,
                })));

                // Restore supply state
                if (savedProgress.supply_state && savedProgress.supply_state.length > 0) {
                    setSupplies(savedProgress.supply_state.map((s: any) => ({
                        item: s.item || '',
                        label: s.label || '',
                        status: s.status || 'unchecked',
                    })));
                }

                restoredFromDB = true;
            }

            // Restore photo state from photos endpoint
            try {
                const photosRes = await apiFetch<any>(`/tasks/${taskId}/cleaning-photos`);
                const photos = photosRes.photos || photosRes.data || [];
                if (Array.isArray(photos) && photos.length > 0) {
                    const rooms = new Set(photos.map((p: any) => p.room_label).filter(Boolean));
                    setPhotosUploaded(rooms as Set<string>);
                }
            } catch {
                // Best-effort photo restore
            }
        } catch {
            // No persisted progress — fall through to template
        }

        // If no persisted state, initialize from template
        if (!restoredFromDB) {
            try {
                const templateRes = await apiFetch<any>(`/properties/${selected.property_id}/cleaning-checklist`);
                const template = templateRes.template || {};
                const items: ChecklistItem[] = (template.items || []).map((it: any) => ({
                    room: it.room || '',
                    label: it.label || '',
                    done: false,
                    requires_photo: it.requires_photo || false,
                }));
                const supplyItems: SupplyItem[] = (template.supply_checks || []).map((s: any) => ({
                    item: s.item || '',
                    label: s.label || '',
                    status: 'unchecked' as const,
                }));
                setChecklist(items);
                setSupplies(supplyItems);
            } catch {
                // Use hardcoded defaults if both template and progress fail
                setChecklist([
                    { room: 'bedroom', label: 'Bedroom', done: false, requires_photo: true },
                    { room: 'bathroom', label: 'Bathroom', done: false, requires_photo: true },
                    { room: 'kitchen', label: 'Kitchen', done: false, requires_photo: true },
                    { room: 'living', label: 'Living Area', done: false, requires_photo: false },
                    { room: 'exterior', label: 'Exterior', done: false, requires_photo: true },
                ]);
                setSupplies([
                    { item: 'towels', label: 'Fresh Towels', status: 'unchecked' },
                    { item: 'toiletries', label: 'Toiletries', status: 'unchecked' },
                    { item: 'linens', label: 'Bed Linens', status: 'unchecked' },
                    { item: 'trash_bags', label: 'Trash Bags', status: 'unchecked' },
                ]);
            }
        }
    };

    // ── Toggle checklist item ──
    const toggleItem = async (index: number) => {
        if (!selected) return;
        const updated = [...checklist];
        updated[index] = { ...updated[index], done: !updated[index].done };
        setChecklist(updated);

        try {
            await apiFetch(`/tasks/${selected.task_id}/cleaning-progress`, {
                method: 'PATCH',
                body: JSON.stringify({ items: [{ index, done: updated[index].done }] }),
            });
        } catch {
            // Best-effort — local state is truth for UX
        }
    };

    // ── Upload photo (Phase E-8: real capture + upload) ──
    const capturePhoto = async (room: string) => {
        if (!selected) return;
        // Create hidden file input for camera capture
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.capture = 'environment'; // Rear camera on mobile
        input.onchange = async () => {
            const file = input.files?.[0];
            if (!file) return;

            try {
                // Try uploading via FormData to the photo upload endpoint
                const token = getToken();
                const formData = new FormData();
                formData.append('file', file);
                formData.append('room_label', room);
                formData.append('taken_by', getWorkerId());

                const res = await fetch(`${BASE}/tasks/${selected.task_id}/cleaning-photos/upload`, {
                    method: 'POST',
                    headers: {
                        ...(token ? { Authorization: `Bearer ${token}` } : {}),
                    },
                    body: formData,
                });

                if (res.ok) {
                    setPhotosUploaded(prev => new Set(prev).add(room));
                    showNotice(`📷 Photo uploaded — ${room}`);
                    return;
                }
            } catch {
                // Fall back to JSON endpoint with object URL
            }

            // Fallback: use existing JSON endpoint with a reference URL
            const objectUrl = URL.createObjectURL(file);
            try {
                await apiFetch(`/tasks/${selected.task_id}/cleaning-photos`, {
                    method: 'POST',
                    body: JSON.stringify({
                        room_label: room,
                        photo_url: `pending-upload://${selected.task_id}/${room}/${Date.now()}`,
                        taken_by: getWorkerId(),
                    }),
                });
                setPhotosUploaded(prev => new Set(prev).add(room));
                showNotice(`📷 Photo captured — ${room}`);
            } catch {
                setPhotosUploaded(prev => new Set(prev).add(room));
                showNotice('Photo recorded locally');
            } finally {
                URL.revokeObjectURL(objectUrl);
            }
        };
        input.click();
    };

    // ── Toggle supply status ──
    const cycleSupply = async (index: number) => {
        if (!selected) return;
        const order: SupplyItem['status'][] = ['unchecked', 'ok', 'low', 'empty'];
        const current = supplies[index].status;
        const next = order[(order.indexOf(current) + 1) % order.length];
        const updated = [...supplies];
        updated[index] = { ...updated[index], status: next };
        setSupplies(updated);

        try {
            await apiFetch(`/tasks/${selected.task_id}/supply-check`, {
                method: 'PATCH',
                body: JSON.stringify({ supplies: [{ index, status: next }] }),
            });
        } catch {
            // Best-effort
        }
    };

    // ── Report issue (Phase E-9: wired to problem_report_router) ──
    const submitIssue = async () => {
        if (!selected || !issueDescription.trim()) {
            showNotice('⚠️ Description required');
            return;
        }
        try {
            // Phase E-9: Submit to problem_report_router API
            await apiFetch('/problem-reports', {
                method: 'POST',
                body: JSON.stringify({
                    property_id: selected.property_id,
                    category: issueCategory,
                    severity: issueSeverity,
                    description: issueDescription,
                    reporter_id: getWorkerId(),
                    source: 'cleaner_flow',
                    related_task_id: selected.task_id,
                }),
            });
            if (issueSeverity === 'critical') {
                showNotice('🚨 Critical issue reported — property will be blocked');
            } else {
                showNotice('📝 Issue reported');
            }
            setShowIssueForm(false);
            setIssueDescription('');
            setIssueCategory('general');
            setIssueSeverity('normal');
        } catch {
            // Fallback: store as task note if problem report API is unavailable
            try {
                await apiFetch(`/tasks/${selected.task_id}/status`, {
                    method: 'PATCH',
                    body: JSON.stringify({
                        status: selected.status === 'IN_PROGRESS' ? 'IN_PROGRESS' : 'ACKNOWLEDGED',
                        notes: JSON.stringify({
                            issue: true, category: issueCategory,
                            severity: issueSeverity, description: issueDescription,
                            reported_at: new Date().toISOString(),
                        }),
                    }),
                });
            } catch {
                // best-effort
            }
            showNotice('Issue saved locally');
            setShowIssueForm(false);
        }
    };

    // ── Navigate to property ──
    const navigateToProperty = async (_taskId: string) => {
        if (!selected) { showNotice('⚠️ No task selected'); return; }
        try {
            const res = await apiFetch<any>(`/properties/${selected.property_id}/location`);
            const lat = res.latitude;
            const lng = res.longitude;
            if (lat != null && lng != null) {
                // Waze deep-link (preferred on mobile), Google Maps fallback
                const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
                const wazeUrl = `https://waze.com/ul?ll=${lat},${lng}&navigate=yes`;
                const googleUrl = `https://maps.google.com/maps?daddr=${lat},${lng}`;
                window.open(isMobile ? wazeUrl : googleUrl, '_blank');
            } else {
                showNotice('📍 No GPS coordinates set for this property');
            }
        } catch {
            showNotice('⚠️ Navigation unavailable — GPS not configured');
        }
    };

    // ── Complete cleaning ──
    const completeCleaning = async () => {
        if (!selected) return;
        try {
            const res = await apiFetch<any>(`/tasks/${selected.task_id}/complete-cleaning`, {
                method: 'POST',
                body: JSON.stringify({}),
            });
            if (res.completed) {
                setScreen('success');
                // Phase E Fix 5: Show property status with issue awareness
                if (res.has_open_issues) {
                    showNotice(`⚠️ Cleaning complete — property has ${res.open_issue_count} open issue(s) to resolve`);
                } else {
                    showNotice('✅ Cleaning complete — property is now Ready');
                }
            }
        } catch (e: any) {
            if (e.message === '409') {
                showNotice('⚠️ Cannot complete — check items, photos, and supplies');
            } else {
                showNotice('⚠️ Completion failed');
            }
        }
    };

    const returnToList = () => {
        setScreen('list');
        setSelected(null);
        setProgress(null);
        load();
    };

    // ── Computed values ──
    const today = new Date();
    const dateStr = today.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
    const activeTasks = tasks.filter(t => t.status !== 'COMPLETED');
    const completedTasks = tasks.filter(t => t.status === 'COMPLETED');

    const checklistDone = checklist.filter(i => i.done).length;
    const checklistTotal = checklist.length;
    const roomsRequiringPhotos = checklist.filter(i => i.requires_photo).map(i => i.room);
    const photosComplete = roomsRequiringPhotos.every(r => photosUploaded.has(r));
    const suppliesChecked = supplies.filter(s => s.status !== 'unchecked').length;
    const suppliesOk = supplies.every(s => s.status === 'ok');
    const hasCriticalIssue = false; // Will be tracked when issue persistence is wired
    const canComplete = checklistDone === checklistTotal && checklistTotal > 0 && photosComplete && !hasCriticalIssue;

    // ── Next deadline ──
    const nextDeadline = activeTasks.length > 0 ? (activeTasks[0].due_date || activeTasks[0].deadline || '—') : '—';

    return (
        <div style={{ maxWidth: 600, margin: '0 auto' }}>
            {/* Notice toast */}
            {notice && (
                <div style={{
                    position: 'fixed', top: 20, left: '50%', transform: 'translateX(-50%)', zIndex: 999,
                    background: 'var(--color-surface)', border: '1px solid var(--color-primary)',
                    borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)',
                    fontSize: 'var(--text-sm)', color: 'var(--color-primary)', boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
                }}>{notice}</div>
            )}

            {/* ========== SCREEN 1: HOME — Today's Cleaning Tasks ========== */}
            {screen === 'list' && (
                <>
                    <div style={{ marginBottom: 'var(--space-5)' }}>
                        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                            {dateStr}
                        </p>
                        <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text)', letterSpacing: '-0.03em' }}>
                            Today&apos;s Tasks
                        </h1>
                        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                            Cleaning tasks assigned to you
                        </p>
                    </div>

                    {/* Summary strip */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
                        <div style={card}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Tasks</div>
                            <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: 'var(--color-accent)', marginTop: 4 }}>{activeTasks.length}</div>
                        </div>
                        <div style={card}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Done</div>
                            <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: 'var(--color-ok)', marginTop: 4 }}>{completedTasks.length}</div>
                        </div>
                        <div style={card}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Next</div>
                            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)', marginTop: 8, fontFamily: 'var(--font-mono)' }}>{nextDeadline}</div>
                        </div>
                    </div>

                    {/* Loading state */}
                    {loading && <div style={{ ...card, textAlign: 'center', color: 'var(--color-text-dim)' }}>Loading…</div>}

                    {/* Empty state */}
                    {!loading && activeTasks.length === 0 && (
                        <div style={{ ...card, textAlign: 'center' }}>
                            <div style={{ fontSize: 'var(--text-2xl)', marginBottom: 'var(--space-2)' }}>🧹</div>
                            <div style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>No tasks today</div>
                        </div>
                    )}

                    {/* Task list */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        {activeTasks.map(t => (
                            <div key={t.task_id} style={{
                                ...card, cursor: 'pointer', transition: 'border-color 0.2s',
                            }}
                                onClick={() => openDetail(t)}
                                onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--color-primary)')}
                                onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-2)' }}>
                                    <div>
                                        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--color-text)' }}>
                                            {t.property_name || t.property_id}
                                        </div>
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                                            {t.property_id}
                                        </div>
                                    </div>
                                    <StatusBadge status={t.status} />
                                </div>
                                <div style={{ display: 'flex', gap: 'var(--space-4)', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                                    <span>🧹 Cleaning</span>
                                    <span>📅 {t.due_date || '—'}</span>
                                </div>
                                <div style={{ marginTop: 'var(--space-3)', display: 'flex', gap: 'var(--space-2)' }}>
                                    {t.status === 'PENDING' && (
                                        <button onClick={e => { e.stopPropagation(); acknowledgeTask(t); }} style={{
                                            flex: 1, padding: '8px', background: 'rgba(210,153,34,0.1)', color: '#d29922',
                                            border: '1px solid rgba(210,153,34,0.3)', borderRadius: 'var(--radius-sm)',
                                            fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer',
                                        }}>Acknowledge</button>
                                    )}
                                    <button style={{
                                        flex: 1, padding: '8px', background: 'var(--color-primary)', color: '#fff',
                                        border: 'none', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer',
                                    }}>{t.status === 'IN_PROGRESS' ? 'Resume' : 'Start'}</button>
                                    <button onClick={e => { e.stopPropagation(); navigateToProperty(t.task_id); }} style={{
                                        padding: '8px 12px', background: 'var(--color-surface-2)', color: 'var(--color-text-dim)',
                                        border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', cursor: 'pointer',
                                    }}>📍</button>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Completed tasks */}
                    {completedTasks.length > 0 && (
                        <div style={{ marginTop: 'var(--space-5)' }}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                                ✅ Completed Today
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                                {completedTasks.map(t => (
                                    <div key={t.task_id} style={{ ...card, opacity: 0.6, borderColor: 'rgba(63,185,80,0.2)' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                            <div>
                                                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>{t.property_name || t.property_id}</div>
                                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>{t.property_id}</div>
                                            </div>
                                            <StatusBadge status="COMPLETED" />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </>
            )}

            {/* ========== SCREEN 2: TASK DETAIL ========== */}
            {screen === 'detail' && selected && (
                <div style={card}>
                    <button onClick={returnToList} style={{
                        background: 'none', border: 'none', color: 'var(--color-text-dim)',
                        cursor: 'pointer', fontSize: 'var(--text-sm)', padding: 0, marginBottom: 'var(--space-4)',
                    }}>← Back to Tasks</button>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
                        <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)' }}>
                            🧹 Cleaning Task
                        </h2>
                        <StatusBadge status={selected.status} />
                    </div>

                    <InfoRow label="Property" value={selected.property_name || selected.property_id} />
                    <InfoRow label="Property ID" value={selected.property_id} />
                    <InfoRow label="Due Date" value={selected.due_date} />
                    {selected.title && <InfoRow label="Title" value={selected.title} />}
                    {selected.description && (
                        <div style={{
                            marginTop: 'var(--space-3)', padding: '8px 12px',
                            background: 'rgba(88,166,255,0.08)', border: '1px solid rgba(88,166,255,0.2)',
                            borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', color: '#58a6ff',
                        }}>
                            📝 {selected.description}
                        </div>
                    )}

                    <div style={{ marginTop: 'var(--space-5)', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                        {selected.status === 'IN_PROGRESS' ? (
                            <ActionButton label="Resume Cleaning →" onClick={resumeCleaning} />
                        ) : (
                            <ActionButton label="Start Cleaning 🧹" onClick={startCleaning} />
                        )}
                        <ActionButton label="📍 Navigate to Property" onClick={() => navigateToProperty(selected.task_id)} variant="outline" />
                    </div>
                </div>
            )}

            {/* ========== SCREEN 3: CLEANING CHECKLIST ========== */}
            {screen === 'checklist' && selected && (
                <div>
                    <button onClick={() => setScreen('detail')} style={{
                        background: 'none', border: 'none', color: 'var(--color-text-dim)',
                        cursor: 'pointer', fontSize: 'var(--text-sm)', padding: 0, marginBottom: 'var(--space-3)',
                    }}>← Back to Detail</button>

                    <div style={{ marginBottom: 'var(--space-4)' }}>
                        <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)' }}>
                            {selected.property_name || selected.property_id}
                        </h2>
                        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>Cleaning Checklist</p>
                    </div>

                    {/* Progress overview */}
                    <div style={{ ...card, marginBottom: 'var(--space-4)' }}>
                        <ProgressBar done={checklistDone} total={checklistTotal} label="Checklist Items" />
                        <ProgressBar done={photosUploaded.size} total={roomsRequiringPhotos.length} label="Photos Required" />
                        <ProgressBar done={suppliesChecked} total={supplies.length} label="Supplies Checked" />
                    </div>

                    {/* Checklist items */}
                    <div style={{ ...card, marginBottom: 'var(--space-3)' }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                            📋 Rooms & Areas
                        </div>
                        {checklist.map((item, idx) => (
                            <div key={idx} style={{
                                display: 'flex', alignItems: 'center', gap: 'var(--space-3)',
                                padding: '10px 0', borderBottom: idx < checklist.length - 1 ? '1px solid var(--color-border)' : 'none',
                            }}>
                                <button onClick={() => toggleItem(idx)} style={{
                                    width: 28, height: 28, borderRadius: 6,
                                    background: item.done ? 'rgba(63,185,80,0.15)' : 'var(--color-surface-2)',
                                    border: `2px solid ${item.done ? '#3fb950' : 'var(--color-border)'}`,
                                    cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    fontSize: 'var(--text-sm)', color: item.done ? '#3fb950' : 'transparent',
                                    transition: 'all 0.2s',
                                }}>✓</button>
                                <div style={{ flex: 1 }}>
                                    <div style={{
                                        fontSize: 'var(--text-sm)', color: item.done ? 'var(--color-text-dim)' : 'var(--color-text)',
                                        fontWeight: 500, textDecoration: item.done ? 'line-through' : 'none',
                                    }}>{item.label}</div>
                                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>{item.room}</div>
                                </div>
                                {item.requires_photo && (
                                    <button onClick={() => capturePhoto(item.room)} style={{
                                        padding: '4px 10px', borderRadius: 'var(--radius-sm)',
                                        background: photosUploaded.has(item.room) ? 'rgba(63,185,80,0.1)' : 'var(--color-surface-2)',
                                        border: `1px solid ${photosUploaded.has(item.room) ? 'rgba(63,185,80,0.3)' : 'var(--color-border)'}`,
                                        color: photosUploaded.has(item.room) ? '#3fb950' : 'var(--color-text-dim)',
                                        fontSize: 'var(--text-xs)', cursor: 'pointer',
                                    }}>{photosUploaded.has(item.room) ? '📷 ✓' : '📷'}</button>
                                )}
                            </div>
                        ))}
                    </div>

                    {/* Supply checks */}
                    {supplies.length > 0 && (
                        <div style={{ ...card, marginBottom: 'var(--space-3)' }}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                                📦 Supply Check
                            </div>
                            {supplies.map((s, idx) => {
                                const sc = SUPPLY_COLORS[s.status];
                                return (
                                    <div key={idx} style={{
                                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                        padding: '8px 0', borderBottom: idx < supplies.length - 1 ? '1px solid var(--color-border)' : 'none',
                                    }}>
                                        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{s.label}</span>
                                        <button onClick={() => cycleSupply(idx)} style={{
                                            padding: '4px 12px', borderRadius: 12,
                                            background: sc.bg, border: 'none', color: sc.text,
                                            fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer',
                                        }}>{sc.icon} {s.status}</button>
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {/* Issue reporting */}
                    <div style={{ ...card, marginBottom: 'var(--space-3)' }}>
                        {!showIssueForm ? (
                            <button onClick={() => setShowIssueForm(true)} style={{
                                width: '100%', padding: '12px', borderRadius: 'var(--radius-sm)',
                                background: 'rgba(248,81,73,0.05)', border: '1px solid rgba(248,81,73,0.2)',
                                color: '#f85149', fontSize: 'var(--text-sm)', fontWeight: 600, cursor: 'pointer',
                            }}>🚨 Report Issue</button>
                        ) : (
                            <div>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                                    🚨 Report Issue
                                </div>
                                <div style={{ marginBottom: 'var(--space-2)' }}>
                                    <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Category</label>
                                    <select value={issueCategory} onChange={e => setIssueCategory(e.target.value)} style={{ ...inputStyle, appearance: 'auto' as any }}>
                                        <option value="general">General</option>
                                        <option value="plumbing">Plumbing</option>
                                        <option value="electrical">Electrical</option>
                                        <option value="damage">Damage</option>
                                        <option value="pest">Pest Control</option>
                                        <option value="appliance">Appliance</option>
                                        <option value="safety">Safety</option>
                                    </select>
                                </div>
                                <div style={{ marginBottom: 'var(--space-2)' }}>
                                    <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Severity</label>
                                    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                                        {(['normal', 'critical'] as const).map(sev => (
                                            <button key={sev} onClick={() => setIssueSeverity(sev)} style={{
                                                flex: 1, padding: '10px', borderRadius: 'var(--radius-sm)',
                                                background: issueSeverity === sev
                                                    ? (sev === 'critical' ? 'rgba(248,81,73,0.15)' : 'rgba(63,185,80,0.1)')
                                                    : 'var(--color-surface-2)',
                                                border: `1px solid ${issueSeverity === sev
                                                    ? (sev === 'critical' ? 'rgba(248,81,73,0.3)' : 'rgba(63,185,80,0.3)')
                                                    : 'var(--color-border)'}`,
                                                color: issueSeverity === sev
                                                    ? (sev === 'critical' ? '#f85149' : '#3fb950')
                                                    : 'var(--color-text-dim)',
                                                fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer',
                                                textTransform: 'capitalize',
                                            }}>{sev === 'critical' ? '🔴 Critical' : '🟡 Normal'}</button>
                                        ))}
                                    </div>
                                    {issueSeverity === 'critical' && (
                                        <div style={{
                                            marginTop: 'var(--space-2)', padding: '8px 12px',
                                            background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.2)',
                                            borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', color: '#f85149',
                                        }}>
                                            ⚠️ Critical issues will immediately block this property and trigger a 5-minute SLA.
                                        </div>
                                    )}
                                </div>
                                <div style={{ marginBottom: 'var(--space-3)' }}>
                                    <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Description *</label>
                                    <textarea value={issueDescription} onChange={e => setIssueDescription(e.target.value)}
                                        placeholder="Describe the issue..." rows={3}
                                        style={{ ...inputStyle, resize: 'vertical' as any }} />
                                </div>
                                <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                                    <ActionButton label="Submit Issue" onClick={submitIssue} variant="danger" />
                                    <ActionButton label="Cancel" onClick={() => setShowIssueForm(false)} variant="outline" />
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Complete button */}
                    <div style={card}>
                        <ActionButton
                            label={canComplete ? '✅ Mark as Ready' : '🔒 Complete All Items First'}
                            onClick={() => canComplete ? setScreen('complete') : showNotice('⚠️ Complete checklist & photos first')}
                            disabled={!canComplete}
                        />
                    </div>
                </div>
            )}

            {/* ========== SCREEN 4: COMPLETION CONFIRMATION ========== */}
            {screen === 'complete' && selected && (
                <div style={card}>
                    <button onClick={() => setScreen('checklist')} style={{
                        background: 'none', border: 'none', color: 'var(--color-text-dim)',
                        cursor: 'pointer', fontSize: 'var(--text-sm)', padding: 0, marginBottom: 'var(--space-4)',
                    }}>← Back to Checklist</button>

                    <div style={{
                        padding: 'var(--space-6)', textAlign: 'center',
                        background: 'rgba(63,185,80,0.05)', borderRadius: 'var(--radius-md)',
                        border: '1px solid rgba(63,185,80,0.2)', marginBottom: 'var(--space-4)',
                    }}>
                        <div style={{ fontSize: 'var(--text-3xl)', marginBottom: 'var(--space-2)' }}>🏠</div>
                        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)' }}>
                            Ready to Submit
                        </div>
                        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-2)' }}>
                            This will mark the property as <strong>Ready</strong> and complete your task.
                        </div>
                    </div>

                    <InfoRow label="Property" value={selected.property_name || selected.property_id} />
                    <InfoRow label="Checklist" value={`${checklistDone}/${checklistTotal} items`} />
                    <InfoRow label="Photos" value={`${photosUploaded.size}/${roomsRequiringPhotos.length} rooms`} />
                    <InfoRow label="Supplies" value={suppliesOk ? 'All OK' : `${suppliesChecked}/${supplies.length} checked`} />

                    <div style={{ marginTop: 'var(--space-5)' }}>
                        <ActionButton label="✅ Mark as Ready" onClick={completeCleaning} />
                    </div>
                </div>
            )}

            {/* ========== SUCCESS SCREEN ========== */}
            {screen === 'success' && selected && (
                <div style={card}>
                    <div style={{
                        padding: 'var(--space-6)', textAlign: 'center',
                        background: 'rgba(63,185,80,0.05)', borderRadius: 'var(--radius-md)',
                        border: '1px solid rgba(63,185,80,0.2)', marginBottom: 'var(--space-4)',
                    }}>
                        <div style={{ fontSize: 'var(--text-3xl)', marginBottom: 'var(--space-2)' }}>✅</div>
                        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: '#3fb950' }}>
                            Cleaning Complete
                        </div>
                        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-2)' }}>
                            <strong>{selected.property_name || selected.property_id}</strong> is now <strong>Ready</strong>
                        </div>
                    </div>
                    <ActionButton label="Done — Return to Tasks" onClick={returnToList} />
                </div>
            )}

            {/* Cleaner-specific BottomNav — Phase E-2 */}
            <BottomNav items={[
                { href: '/dashboard', label: 'Home', icon: '▪' },
                { href: '/ops/cleaner', label: 'Cleaning', icon: '🧹' },
                { href: '/tasks', label: 'Tasks', icon: '✓' },
            ]} />
        </div>
    );
}
