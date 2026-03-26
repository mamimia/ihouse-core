'use client';

/**
 * Operational Core — Phase D-7: Mobile Check-out Flow
 * Architecture: 4-step checkout wired to existing backend APIs:
 *   - deposit_settlement_router.py (421 lines) — deposits, deductions, settlement
 *   - booking_checkin_router.py (317 lines) — checkout state transition + audit
 *   - problem_report_router.py (382 lines) — issue flagging
 *
 * Steps: Inspection → Issue Flagging → Deposit Resolution → Complete
 */

import { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '@/lib/staffApi';
import { useCountdown } from '@/lib/useCountdown';
import { CHECKOUT_BOTTOM_NAV } from '@/components/BottomNav';
import MobileStaffShell from '@/components/MobileStaffShell';
import WorkerTaskCard from '@/components/WorkerTaskCard';
import WorkerHeader from '@/components/WorkerHeader';

// Phase 865: apiFetch imported from lib/staffApi.ts

type Booking = {
    booking_id?: string; booking_ref?: string; id?: string;
    property_id: string; guest_name?: string; check_in?: string; check_out?: string;
    status?: string; guest_count?: number; nights?: number;
    deposit_amount?: number; deposit_currency?: string;
};

// Phase 883: Task-world checkout entry (sourced from CHECKOUT_VERIFY tasks)
type CheckoutTask = {
    task_id: string;
    property_id: string;
    booking_id?: string;
    due_date?: string;         // ISO date — the checkout date
    status: string;
    title?: string;
    // Enriched (Phase 886/889)
    guest_name?: string;
    guest_count?: number;
    check_in?: string;
    check_out?: string;
    nights?: number;
    property_name?: string;
    property_latitude?: number | null;
    property_longitude?: number | null;
    property_address?: string | null;
};

function getBookingId(b: Booking): string {
    return b.booking_id || b.booking_ref || b.id || 'unknown';
}

type CheckoutStep = 'list' | 'inspection' | 'issues' | 'deposit' | 'complete' | 'success';

// ========== Components ==========

function StepHeader({ step, total, title, onBack }: { step: number; total: number; title: string; onBack: () => void }) {
    return (
        <div style={{ marginBottom: 'var(--space-4)' }}>
            <button onClick={onBack} style={{
                background: 'none', border: 'none', color: 'var(--color-text-dim)',
                cursor: 'pointer', fontSize: 'var(--text-sm)', padding: 0, marginBottom: 'var(--space-2)',
            }}>← Back</button>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                <span style={{
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    width: 28, height: 28, borderRadius: '50%', background: 'var(--color-primary)',
                    color: '#fff', fontSize: 'var(--text-xs)', fontWeight: 700,
                }}>{step}</span>
                <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)' }}>{title}</h2>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginLeft: 'auto' }}>
                    Step {step} of {total}
                </span>
            </div>
            <div style={{ height: 3, background: 'var(--color-border)', borderRadius: 2, marginTop: 'var(--space-2)' }}>
                <div style={{ height: '100%', width: `${(step / total) * 100}%`, background: 'var(--color-primary)', borderRadius: 2, transition: 'width 0.3s' }} />
            </div>
        </div>
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

function ActionButton({ label, onClick, variant = 'primary', disabled = false }: {
    label: string; onClick: () => void; variant?: 'primary' | 'danger' | 'outline'; disabled?: boolean;
}) {
    const styles = {
        primary: { bg: 'var(--color-primary)', color: '#fff', border: 'none' },
        danger: { bg: 'rgba(248,81,73,0.1)', color: 'var(--color-alert)', border: '1px solid rgba(248,81,73,0.3)' },
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

// ========== Phase 883 Countdown Components ==========

function CheckoutSummaryStrip({ todayCount, upcomingCount, overdueCount, nextDueIso }: {
    todayCount: number; upcomingCount: number; overdueCount: number; nextDueIso: string | null;
}) {
    const { label, isOverdue, isUrgent } = useCountdown(nextDueIso, '11:00');
    const urgencyColor = isOverdue ? 'var(--color-alert)' : isUrgent ? 'var(--color-warn)' : 'var(--color-accent)';
    const card: React.CSSProperties = {
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
    };
    return (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
            <div style={{ ...card, borderColor: overdueCount > 0 ? 'rgba(196,91,74,0.4)' : 'var(--color-border)' }}>
                <div style={{ fontSize: 'var(--text-xs)', color: overdueCount > 0 ? 'var(--color-alert)' : 'var(--color-text-faint)', textTransform: 'uppercase' }}>Overdue</div>
                <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: overdueCount > 0 ? 'var(--color-alert)' : 'var(--color-text-faint)', marginTop: 4 }}>{overdueCount}</div>
            </div>
            <div style={card}>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Today</div>
                <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: todayCount > 0 ? 'var(--color-accent)' : 'var(--color-text-faint)', marginTop: 4 }}>{todayCount}</div>
            </div>
            <div style={{ ...card, borderColor: nextDueIso && isUrgent ? 'rgba(212,149,106,0.4)' : 'var(--color-border)' }}>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Next</div>
                {nextDueIso ? (
                    <>
                        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: urgencyColor, marginTop: 6, lineHeight: 1.2 }}>
                            {isOverdue ? '⚠ ' : '⏱ '}{label}
                        </div>
                        <div style={{ fontSize: '10px', color: 'var(--color-text-faint)', marginTop: 2 }}>(checkout 11:00)</div>
                    </>
                ) : (
                    <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 8 }}>—</div>
                )}
            </div>
        </div>
    );
}

function CheckoutTaskCard({ t, onStart, onAcknowledge, showNotice }: {
    t: CheckoutTask;
    onStart: (t: CheckoutTask) => void;
    onAcknowledge?: () => void;
    showNotice: (msg: string) => void;
}) {
    const handleNavigate = () => {
        if (t.property_latitude != null && t.property_longitude != null) {
            const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
            const url = isMobile
                ? `https://waze.com/ul?ll=${t.property_latitude},${t.property_longitude}&navigate=yes`
                : `https://maps.google.com/maps?daddr=${t.property_latitude},${t.property_longitude}`;
            window.open(url, '_blank');
        } else if (t.property_address) {
            window.open(`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(t.property_address)}`, '_blank');
        } else {
            showNotice('📍 No location data for this property');
        }
    };
    return (
        <WorkerTaskCard
            kind="CHECKOUT_VERIFY"
            status={t.status || 'PENDING'}
            propertyName={t.property_name || t.property_id}
            propertyCode={t.property_id}
            date={t.due_date || ''}
            checkIn={t.check_in}
            checkOut={t.check_out || t.due_date}
            guestName={t.guest_name}
            guestCount={t.guest_count}
            onStart={() => onStart(t)}
            onAcknowledge={onAcknowledge}
            onNavigate={handleNavigate}
        />
    );
}

// ========== Main Page ==========
export default function MobileCheckoutPage() {
    // Phase 883: Checkout world is built on CHECKOUT_VERIFY tasks,
    // NOT booking status. Booking status is stale/disconnected in staging.
    const [checkoutTasks, setCheckoutTasks] = useState<CheckoutTask[]>([]);
    const [bookings, setBookings] = useState<Booking[]>([]);  // kept for the checkout flow steps
    const [loading, setLoading] = useState(true);
    const [step, setStep] = useState<CheckoutStep>('list');
    const [selected, setSelected] = useState<Booking | null>(null);
    const [selectedTask, setSelectedTask] = useState<CheckoutTask | null>(null);
    const [notice, setNotice] = useState<string | null>(null);

    // Step state
    const [inspectionNotes, setInspectionNotes] = useState('');
    const [inspectionOk, setInspectionOk] = useState(true);
    const [issueDescription, setIssueDescription] = useState('');
    const [issueCategory, setIssueCategory] = useState('damage');
    const [issueSeverity, setIssueSeverity] = useState('MEDIUM');
    const [issues, setIssues] = useState<any[]>([]);
    const [depositAction, setDepositAction] = useState<'full_return' | 'deduct'>('full_return');
    const [deductionAmount, setDeductionAmount] = useState('');
    const [deductionReason, setDeductionReason] = useState('');
    const [settlement, setSettlement] = useState<any>(null);

    const showNotice = (msg: string) => { setNotice(msg); setTimeout(() => setNotice(null), 3000); };

    const load = useCallback(async () => {
        setLoading(true);
        try {
            // Phase 883/886: CHECKOUT_VERIFY tasks are the truth for the checkout world.
            const taskRes = await apiFetch<any>('/worker/tasks?worker_role=CHECKOUT&limit=100');
            const taskList = taskRes.tasks || taskRes.data?.tasks || taskRes.data || [];
            const rawTasks: CheckoutTask[] = Array.isArray(taskList) ? taskList : [];

            // Phase 886/889: Enrich each task with property + booking data.
            // Property: display name, GPS location.
            // Booking: check_in, check_out, guest_name, guest_count → enables nights.
            const enriched = await Promise.all(rawTasks.map(async (t) => {
                let result: CheckoutTask = { ...t, property_name: t.property_id };

                // Enrich with property data
                try {
                    const propRes = await apiFetch<any>(`/properties/${t.property_id}`);
                    const prop = propRes.data || propRes;
                    result.property_name = prop.display_name || prop.name || prop.short_name || t.property_id;
                    result.property_latitude  = prop.latitude  ?? null;
                    result.property_longitude = prop.longitude ?? null;
                    result.property_address   = prop.address   ?? null;
                } catch { /* keep defaults */ }

                // Phase 889: Enrich with booking data (check_in, check_out, guest_name, guest_count)
                if (t.booking_id) {
                    try {
                        const bkRes = await apiFetch<any>(`/worker/bookings/${t.booking_id}`);
                        const bk = bkRes?.data || bkRes;
                        if (bk && bk.booking_id) {
                            result.check_in    = bk.check_in ?? result.check_in;
                            result.check_out   = bk.check_out ?? result.check_out ?? t.due_date;
                            result.guest_name  = bk.guest_name ?? result.guest_name;
                            result.guest_count = bk.guest_count ?? result.guest_count;
                            // Compute nights from canonical booking dates
                            if (bk.check_in && bk.check_out && bk.check_out !== bk.check_in) {
                                const d1 = new Date(bk.check_in).getTime();
                                const d2 = new Date(bk.check_out).getTime();
                                const n = Math.round((d2 - d1) / 86400000);
                                if (n > 0) result.nights = n;
                            }
                        }
                    } catch { /* booking lookup failed — keep task-only data */ }
                }

                return result;
            }));

            // Sort: overdue first, then ascending by date.
            const today = new Date().toISOString().slice(0, 10);
            enriched.sort((a, b) => {
                const aDate = a.due_date || '';
                const bDate = b.due_date || '';
                const aOverdue = aDate < today;
                const bOverdue = bDate < today;
                if (aOverdue !== bOverdue) return aOverdue ? -1 : 1;
                return aDate.localeCompare(bDate);
            });

            setCheckoutTasks(enriched);

            // Keep booking query as secondary (needed for flow steps).
            try {
                const bookRes = await apiFetch<any>('/bookings?status=checked_in&limit=50');
                const list = bookRes.bookings || bookRes.data?.bookings || bookRes.data || [];
                setBookings(Array.isArray(list) ? list : []);
            } catch { setBookings([]); }

        } catch { setCheckoutTasks([]); }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const startCheckout = (b: Booking) => {
        setSelected(b);
        setStep('inspection');
        setInspectionNotes('');
        setInspectionOk(true);
        setIssues([]);
        setIssueDescription('');
        setDepositAction('full_return');
        setDeductionAmount('');
        setDeductionReason('');
        setSettlement(null);
    };

    const startCheckoutFromTask = (t: CheckoutTask) => {
        // Convert task to a Booking-like object enriched with real booking data
        const syntheticBooking: Booking = {
            booking_id: t.booking_id || t.task_id,
            property_id: t.property_id,
            guest_name: t.guest_name || 'Guest',
            guest_count: t.guest_count,
            check_in: t.check_in,
            check_out: t.check_out || t.due_date,
            nights: t.nights,
            status: 'checked_in',
        };
        setSelected(syntheticBooking);
        setSelectedTask(t);
        setStep('inspection');
        setInspectionNotes('');
        setInspectionOk(true);
        setIssues([]);
        setIssueDescription('');
        setDepositAction('full_return');
        setDeductionAmount('');
        setDeductionReason('');
        setSettlement(null);
    };

    const goBack = () => {
        const flow: CheckoutStep[] = ['list', 'inspection', 'issues', 'deposit', 'complete'];
        const idx = flow.indexOf(step);
        if (idx <= 1) { setStep('list'); setSelected(null); }
        else setStep(flow[idx - 1]);
    };

    // Phase 887c: Acknowledge — matches the behavior now present in Combined Tasks.
    // Allows a worker to acknowledge PENDING checkout tasks from the standalone page.
    const handleAcknowledgeTask = async (taskId: string) => {
        try {
            await apiFetch<any>(`/worker/tasks/${taskId}/acknowledge`, { method: 'PATCH' });
            showNotice('✓ Task acknowledged');
            await load();
        } catch {
            showNotice('⚠ Acknowledge failed');
        }
    };

    // Step 2: Submit an issue via existing problem_report_router
    const submitIssue = async () => {
        if (!selected || !issueDescription.trim()) return;
        try {
            const res = await apiFetch<any>('/problem-reports', {
                method: 'POST',
                body: JSON.stringify({
                    property_id: selected.property_id,
                    booking_id: getBookingId(selected),
                    description: issueDescription.trim(),
                    category: issueCategory,
                    severity: issueSeverity,
                    reported_by: 'checkout_flow',
                }),
            });
            setIssues(prev => [...prev, res.data || res]);
            setIssueDescription('');
            showNotice('🚨 Issue reported');
        } catch {
            showNotice('Issue report failed — recorded locally');
            setIssues(prev => [...prev, { description: issueDescription, category: issueCategory, severity: issueSeverity, local: true }]);
            setIssueDescription('');
        }
    };

    // Step 3: Handle deposit — deduction or full return
    // Correct flow: GET /deposits?booking_id= → get deposit_id → POST /deposits/{deposit_id}/deductions
    const handleDeposit = async () => {
        if (!selected) return;
        const bookingId = getBookingId(selected);
        try {
            // Step 1: Find the deposit record for this booking
            let depositId: string | null = null;
            try {
                const depositLookup = await apiFetch<any>(`/deposits?booking_id=${bookingId}`);
                const deposits = depositLookup.deposits || [];
                if (deposits.length > 0) {
                    depositId = deposits[0].id;
                }
            } catch { /* no deposit found — skip deductions */ }

            // Step 2: If deducting and we have a deposit_id, add the deduction
            if (depositAction === 'deduct' && deductionAmount && depositId) {
                await apiFetch(`/deposits/${depositId}/deductions`, {
                    method: 'POST',
                    body: JSON.stringify({
                        description: deductionReason || 'Damage/cleaning deduction',
                        amount: parseFloat(deductionAmount),
                        category: 'damage',
                    }),
                });
                showNotice('💰 Deduction recorded');
            } else if (depositAction === 'deduct' && deductionAmount && !depositId) {
                showNotice('⚠️ No deposit on file — deduction skipped');
            }

            // Step 3: Get settlement breakdown (if deposit exists)
            if (depositId) {
                try {
                    const s = await apiFetch<any>(`/deposits/${depositId}/settlement`);
                    setSettlement(s.data || s);
                } catch { /* settlement unavailable */ }
            }
            setStep('complete');
        } catch {
            showNotice('Deposit action failed — proceeding');
            setStep('complete');
        }
    };

    // Step 4: Complete checkout via POST /bookings/{id}/checkout
    const completeCheckout = async () => {
        if (!selected) return;
        const bookingId = getBookingId(selected);
        try {
            await apiFetch<any>(`/bookings/${bookingId}/checkout`, {
                method: 'POST',
            });
            showNotice('✅ Check-out completed');
            setStep('success');
        } catch {
            showNotice('⚠️ Checkout failed — please verify manually');
        }
    };

    const returnToList = () => {
        setStep('list');
        setSelected(null);
        load();
    };

    const navigateToProperty = async (propertyId: string) => {
        try {
            const res = await apiFetch<any>(`/properties/${propertyId}/location`);
            const lat = res.latitude;
            const lng = res.longitude;
            if (lat != null && lng != null) {
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

    const today = new Date();
    const todayStr = today.toISOString().slice(0, 10);
    const dateStr = today.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });

    // Task-world split: overdue, today, upcoming
    const overdueTasks = checkoutTasks.filter(t => t.due_date && t.due_date < todayStr);
    const todayTasks = checkoutTasks.filter(t => t.due_date === todayStr);
    const upcomingTasks = checkoutTasks.filter(t => t.due_date && t.due_date > todayStr);
    // Earliest due task for countdown
    const nextDueTask = overdueTasks[0] || todayTasks[0] || upcomingTasks[0] || null;
    const nextDueIso = nextDueTask?.due_date || null;

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
        <MobileStaffShell title="Check-out" bottomNavItems={CHECKOUT_BOTTOM_NAV}>
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

            {step === 'list' && (
                <>
                    <WorkerHeader title="Check-out" subtitle="Departures · task world" />

                    <CheckoutSummaryStrip
                        todayCount={todayTasks.length}
                        upcomingCount={upcomingTasks.length}
                        overdueCount={overdueTasks.length}
                        nextDueIso={nextDueIso}
                    />

                    {loading && <div style={{ ...card, textAlign: 'center', color: 'var(--color-text-dim)' }}>Loading…</div>}

                    {!loading && checkoutTasks.length === 0 && (
                        <div style={{ ...card, textAlign: 'center' }}>
                            <div style={{ fontSize: 'var(--text-2xl)', marginBottom: 'var(--space-2)' }}>🏠</div>
                            <div style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>No pending checkouts</div>
                        </div>
                    )}

                    {/* Overdue checkouts — shown first, with red treatment */}
                    {!loading && overdueTasks.length > 0 && (
                        <div style={{ marginBottom: 'var(--space-4)' }}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-alert)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-2)', fontWeight: 700 }}>⚠ Overdue</div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                                {overdueTasks.map(t => <CheckoutTaskCard key={t.task_id} t={t} onStart={startCheckoutFromTask} onAcknowledge={t.status === 'PENDING' ? () => handleAcknowledgeTask(t.task_id) : undefined} showNotice={showNotice} />)}
                            </div>
                        </div>
                    )}

                    {/* Today's checkouts */}
                    {!loading && todayTasks.length > 0 && (
                        <div style={{ marginBottom: 'var(--space-4)' }}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-2)' }}>Today</div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                                {todayTasks.map(t => <CheckoutTaskCard key={t.task_id} t={t} onStart={startCheckoutFromTask} onAcknowledge={t.status === 'PENDING' ? () => handleAcknowledgeTask(t.task_id) : undefined} showNotice={showNotice} />)}
                            </div>
                        </div>
                    )}

                    {/* Upcoming checkouts */}
                    {!loading && upcomingTasks.length > 0 && (
                        <div style={{ marginBottom: 'var(--space-4)' }}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-2)' }}>Upcoming</div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                                {upcomingTasks.map(t => <CheckoutTaskCard key={t.task_id} t={t} onStart={startCheckoutFromTask} onAcknowledge={t.status === 'PENDING' ? () => handleAcknowledgeTask(t.task_id) : undefined} showNotice={showNotice} />)}
                            </div>
                        </div>
                    )}
                </>
            )}

            {/* ========== STEP 1: Inspection ========== */}
            {step === 'inspection' && selected && (
                <div style={card}>
                    <StepHeader step={1} total={4} title="Property Inspection" onBack={goBack} />
                    <InfoRow label="Guest" value={selected.guest_name} />
                    <InfoRow label="Guests" value={selected.guest_count ? `${selected.guest_count} guests` : undefined} />
                    <InfoRow label="Property" value={(selectedTask?.property_name) || selected.property_id} />
                    <InfoRow label="Check-in" value={selected.check_in ? new Date(selected.check_in + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }) : undefined} />
                    <InfoRow label="Check-out" value={selected.check_out ? new Date(selected.check_out + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }) : selected.check_out} />
                    <InfoRow label="Nights" value={selected.nights} />

                    <div style={{ marginTop: 'var(--space-4)' }}>
                        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
                            Inspection Notes
                        </label>
                        <textarea value={inspectionNotes} onChange={e => setInspectionNotes(e.target.value)}
                            placeholder="Any damage, missing items, or notes..."
                            rows={3} style={{ ...inputStyle, resize: 'vertical' }} />
                    </div>

                    <div style={{ marginTop: 'var(--space-3)', display: 'flex', gap: 'var(--space-2)' }}>
                        {[{ label: '✅ All Good', ok: true }, { label: '⚠️ Issues Found', ok: false }].map(opt => (
                            <button key={String(opt.ok)} onClick={() => setInspectionOk(opt.ok)} style={{
                                flex: 1, padding: '10px', borderRadius: 'var(--radius-sm)',
                                background: inspectionOk === opt.ok ? (opt.ok ? 'rgba(63,185,80,0.1)' : 'rgba(248,81,73,0.1)') : 'var(--color-surface-2)',
                                border: `1px solid ${inspectionOk === opt.ok ? (opt.ok ? 'rgba(63,185,80,0.3)' : 'rgba(248,81,73,0.3)') : 'var(--color-border)'}`,
                                color: inspectionOk === opt.ok ? (opt.ok ? 'var(--color-ok)' : 'var(--color-alert)') : 'var(--color-text-dim)',
                                fontSize: 'var(--text-sm)', fontWeight: 600, cursor: 'pointer',
                            }}>{opt.label}</button>
                        ))}
                    </div>

                    <div style={{ marginTop: 'var(--space-5)', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                        <ActionButton label={inspectionOk ? 'Continue → Deposit' : 'Continue → Report Issues'} onClick={() => {
                            setStep(inspectionOk ? 'deposit' : 'issues');
                        }} />
                        <ActionButton label="📍 Navigate to Property" onClick={() => navigateToProperty(selected.property_id)} variant="outline" />
                    </div>
                </div>
            )}

            {/* ========== STEP 2: Issue Flagging ========== */}
            {step === 'issues' && selected && (
                <div style={card}>
                    <StepHeader step={2} total={4} title="Report Issues" onBack={goBack} />

                    {issues.length > 0 && (
                        <div style={{ marginBottom: 'var(--space-4)' }}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', marginBottom: 'var(--space-2)' }}>
                                Reported ({issues.length})
                            </div>
                            {issues.map((issue, i) => (
                                <div key={i} style={{
                                    padding: 'var(--space-2) var(--space-3)', background: 'rgba(248,81,73,0.05)',
                                    border: '1px solid rgba(248,81,73,0.15)', borderRadius: 'var(--radius-sm)',
                                    fontSize: 'var(--text-xs)', color: 'var(--color-text)', marginBottom: 4,
                                }}>
                                    🚨 {issue.description} ({issue.category} · {issue.severity})
                                </div>
                            ))}
                        </div>
                    )}

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        <div>
                            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
                                Issue Description *
                            </label>
                            <textarea value={issueDescription} onChange={e => setIssueDescription(e.target.value)}
                                placeholder="Describe the issue..." rows={2} style={{ ...inputStyle, resize: 'vertical' }} />
                        </div>
                        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                            <div style={{ flex: 1 }}>
                                <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Category</label>
                                <select value={issueCategory} onChange={e => setIssueCategory(e.target.value)} style={inputStyle}>
                                    <option value="damage">Damage</option>
                                    <option value="cleanliness">Cleanliness</option>
                                    <option value="missing_items">Missing Items</option>
                                    <option value="appliance">Appliance</option>
                                    <option value="plumbing">Plumbing</option>
                                    <option value="electrical">Electrical</option>
                                    <option value="other">Other</option>
                                </select>
                            </div>
                            <div style={{ flex: 1 }}>
                                <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Severity</label>
                                <select value={issueSeverity} onChange={e => setIssueSeverity(e.target.value)} style={inputStyle}>
                                    <option value="LOW">Low</option>
                                    <option value="MEDIUM">Medium</option>
                                    <option value="HIGH">High</option>
                                    <option value="CRITICAL">Critical</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    <div style={{ marginTop: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                        <ActionButton label="🚨 Report Issue" onClick={submitIssue} variant="danger" disabled={!issueDescription.trim()} />
                        <ActionButton label="Continue → Deposit Resolution" onClick={() => setStep('deposit')} variant="outline" />
                    </div>
                </div>
            )}

            {/* ========== STEP 3: Deposit Resolution ========== */}
            {step === 'deposit' && selected && (
                <div style={card}>
                    <StepHeader step={3} total={4} title="Deposit Resolution" onBack={goBack} />

                    {selected.deposit_amount ? (
                        <>
                            <div style={{
                                padding: 'var(--space-4)', background: 'rgba(210,153,34,0.1)',
                                border: '1px solid rgba(210,153,34,0.3)', borderRadius: 'var(--radius-md)',
                                marginBottom: 'var(--space-4)',
                            }}>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Deposit Held</div>
                                <div style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--color-warn)', marginTop: 4 }}>
                                    {selected.deposit_currency || 'THB'} {selected.deposit_amount}
                                </div>
                            </div>

                            {issues.length > 0 && (
                                <div style={{
                                    padding: 'var(--space-3)', background: 'rgba(248,81,73,0.05)',
                                    border: '1px solid rgba(248,81,73,0.15)', borderRadius: 'var(--radius-sm)',
                                    fontSize: 'var(--text-xs)', color: 'var(--color-alert)', marginBottom: 'var(--space-4)',
                                }}>
                                    ⚠ {issues.length} issue(s) reported — consider deduction
                                </div>
                            )}

                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', marginBottom: 'var(--space-3)' }}>
                                {[
                                    { action: 'full_return' as const, label: '💵 Full Return', desc: 'Return entire deposit' },
                                    { action: 'deduct' as const, label: '📉 Deduct from Deposit', desc: 'Deduct for damages/cleaning' },
                                ].map(opt => (
                                    <label key={opt.action} onClick={() => setDepositAction(opt.action)} style={{
                                        display: 'flex', alignItems: 'center', gap: 8, padding: '12px 14px',
                                        background: depositAction === opt.action ? 'rgba(63,185,80,0.08)' : 'var(--color-surface-2)',
                                        border: `1px solid ${depositAction === opt.action ? 'rgba(63,185,80,0.3)' : 'var(--color-border)'}`,
                                        borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                                    }}>
                                        <input type="radio" name="deposit_action" checked={depositAction === opt.action} readOnly />
                                        <div>
                                            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600 }}>{opt.label}</div>
                                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{opt.desc}</div>
                                        </div>
                                    </label>
                                ))}
                            </div>

                            {depositAction === 'deduct' && (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', marginBottom: 'var(--space-3)' }}>
                                    <div>
                                        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
                                            Deduction Amount ({selected.deposit_currency || 'THB'})
                                        </label>
                                        <input type="number" value={deductionAmount} onChange={e => setDeductionAmount(e.target.value)}
                                            placeholder="0" style={inputStyle} max={selected.deposit_amount} />
                                    </div>
                                    <div>
                                        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
                                            Reason
                                        </label>
                                        <input value={deductionReason} onChange={e => setDeductionReason(e.target.value)}
                                            placeholder="Damage to bathroom mirror..." style={inputStyle} />
                                    </div>
                                </div>
                            )}
                        </>
                    ) : (
                        <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--color-ok)', fontSize: 'var(--text-sm)' }}>
                            ✓ No deposit on file — skip to completion
                        </div>
                    )}

                    <div style={{ marginTop: 'var(--space-4)' }}>
                        <ActionButton label="Confirm & Continue →" onClick={handleDeposit} />
                    </div>
                </div>
            )}

            {/* ========== STEP 4: Complete ========== */}
            {step === 'complete' && selected && (
                <div style={card}>
                    <StepHeader step={4} total={4} title="Complete Check-out" onBack={goBack} />

                    <div style={{
                        padding: 'var(--space-6)', textAlign: 'center',
                        background: 'rgba(248,81,73,0.03)', borderRadius: 'var(--radius-md)',
                        border: '1px solid rgba(248,81,73,0.15)', marginBottom: 'var(--space-4)',
                    }}>
                        <div style={{ fontSize: 'var(--text-3xl)', marginBottom: 'var(--space-2)' }}>🚪</div>
                        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)' }}>
                            Ready to complete check-out
                        </div>
                        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-2)' }}>
                            This will mark the booking as <strong>Completed</strong> and create a <strong>CLEANING</strong> task.
                        </div>
                    </div>

                    <InfoRow label="Guest" value={selected.guest_name} />
                    <InfoRow label="Property" value={(selectedTask?.property_name) || selected.property_id} />
                    <InfoRow label="Nights" value={selected.nights} />
                    <InfoRow label="Issues Reported" value={issues.length > 0 ? `${issues.length} issue(s)` : 'None'} />
                    {settlement && (
                        <>
                            <InfoRow label="Deposit Held" value={`${selected.deposit_currency || 'THB'} ${settlement.total_deposit || selected.deposit_amount || 0}`} />
                            <InfoRow label="Deductions" value={`${selected.deposit_currency || 'THB'} ${settlement.total_deductions || 0}`} />
                            <InfoRow label="Return Amount" value={`${selected.deposit_currency || 'THB'} ${settlement.return_amount || settlement.total_deposit || 0}`} />
                        </>
                    )}

                    <div style={{ marginTop: 'var(--space-5)' }}>
                        <ActionButton label="✅ Complete Check-out" onClick={completeCheckout} variant="danger" />
                    </div>
                </div>
            )}

            {/* ========== SUCCESS ========== */}
            {step === 'success' && selected && (
                <div style={card}>
                    <div style={{
                        padding: 'var(--space-6)', textAlign: 'center',
                        background: 'rgba(63,185,80,0.05)', borderRadius: 'var(--radius-md)',
                        border: '1px solid rgba(63,185,80,0.2)', marginBottom: 'var(--space-4)',
                    }}>
                        <div style={{ fontSize: 'var(--text-3xl)', marginBottom: 'var(--space-2)' }}>✅</div>
                        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-ok)' }}>
                            Check-out Complete
                        </div>
                        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-2)' }}>
                            {selected.guest_name || 'Guest'} checked out from <strong>{(selectedTask?.property_name) || selected.property_id}</strong>
                            {selected.nights ? ` · ${selected.nights} night${selected.nights > 1 ? 's' : ''}` : ''}
                        </div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-3)' }}>
                            A CLEANING task has been automatically created for this property.
                        </div>
                    </div>
                    <ActionButton label="Done — Return to List" onClick={returnToList} />
                </div>
            )}

            {/* Phase 865: BottomNav now managed by MobileStaffShell via bottomNavItems prop */}
        </div>
        </MobileStaffShell>
    );
}
