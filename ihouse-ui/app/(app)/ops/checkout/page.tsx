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
import { apiFetch, getToken, API_BASE as BASE } from '@/lib/staffApi';
import { useCountdown } from '@/lib/useCountdown';
import { CHECKOUT_BOTTOM_NAV } from '@/components/BottomNav';
import MobileStaffShell from '@/components/MobileStaffShell';
import WorkerTaskCard from '@/components/WorkerTaskCard';
import WorkerHeader from '@/components/WorkerHeader';
import OcrCaptureFlow, { type MeterFields } from '@/components/OcrCaptureFlow';

// Phase 865: apiFetch imported from lib/staffApi.ts

// Operational timezone — iHouse properties operate in Thailand (ICT = UTC+7).
// All TIMESTAMPTZ values in the DB are UTC. Early checkout effective times and
// event timestamps must be displayed in ICT so workers see correct local times.
const OPS_TZ = 'Asia/Bangkok';

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
    due_date?: string;         // ISO date — the checkout date (rescheduled to early_date if approved)
    status: string;
    title?: string;
    // Phase 1000: Early checkout flags from tasks table
    is_early_checkout?: boolean;         // set by early_checkout_router on approval
    original_due_date?: string;          // original checkout date before reschedule
    // Enriched (Phase 886/889)
    guest_name?: string;
    guest_count?: number;
    check_in?: string;
    check_out?: string;                  // original booking check_out — preserved always
    early_checkout_date?: string;        // effective early checkout date (DATE)
    early_checkout_effective_at?: string; // effective early checkout moment (TIMESTAMPTZ)
    early_checkout_status?: string;      // none|requested|approved|completed
    early_checkout_reason?: string;
    nights?: number;
    property_name?: string;
    property_latitude?: number | null;
    property_longitude?: number | null;
    property_address?: string | null;
    // Phase 1033: server-computed timing fields
    ack_is_open?: boolean;
    ack_allowed_at?: string;
    start_is_open?: boolean;
    start_allowed_at?: string;
};

function getBookingId(b: Booking): string {
    return b.booking_id || b.booking_ref || b.id || 'unknown';
}

type CheckoutStep = 'list' | 'inspection' | 'closing_meter' | 'issues' | 'deposit' | 'complete' | 'success';

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

    // Phase 993-fix / Phase 1000-early: Checkout eligibility gate.
    //
    // Normal checkout: actionable when check_out (original booking date) is today or past.
    // Early checkout : the task was rescheduled — due_date = early_checkout_date.
    //                  Use due_date as the actionable date for early tasks.
    //
    // Rule: if is_early_checkout=true, the task is already approved and rescheduled.
    //       Use due_date (= early_checkout_date) for the eligibility comparison.
    //       The original check_out is preserved but NOT used for the eligibility gate.
    const todayStr = new Date().toISOString().slice(0, 10);
    const actionableDate = t.is_early_checkout
        ? (t.due_date || t.early_checkout_date || '')   // rescheduled to early date
        : (t.check_out || t.due_date || '');              // normal: use original booking date
    const isActionable = !actionableDate || actionableDate <= todayStr;
    const lockedLabel = !isActionable && actionableDate
        ? (t.is_early_checkout
            ? `Early Checkout: ${new Date(actionableDate + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
            : `Checkout: ${new Date(actionableDate + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`)
        : undefined;

    return (
        <WorkerTaskCard
            kind="CHECKOUT_VERIFY"
            status={t.status || 'PENDING'}
            propertyName={t.property_name || t.property_id}
            propertyCode={t.property_id}
            date={actionableDate}             // countdown uses the correct actionable date
            checkIn={t.check_in}
            checkOut={t.check_out || t.due_date}
            guestName={t.guest_name}
            guestCount={t.guest_count}
            onStart={() => onStart(t)}
            onAcknowledge={onAcknowledge}
            onNavigate={handleNavigate}
            isActionable={isActionable}
            lockedLabel={lockedLabel}
            isEarlyCheckout={t.is_early_checkout}
            earlyCheckoutEffectiveAt={t.early_checkout_effective_at}
            originalCheckoutDate={t.is_early_checkout ? (t.original_due_date || t.check_out) : undefined}
            ackIsOpen={t.ack_is_open}
            ackAllowedAt={t.ack_allowed_at}
            startIsOpen={isActionable ? t.start_is_open : false}
            startAllowedAt={t.start_allowed_at}
        />
    );
}

// ========== Main Page ==========
/**
 * CheckoutWizard — Phase 1022-H: extracted as named export for embedding in ManagerExecutionDrawer.
 * Identical logic to the page; MobileStaffShell wrapper removed.
 * onCompleted: called after checkout is completed (used for manager board refresh).
 */
export function CheckoutWizard({ onCompleted }: { onCompleted?: () => void }) {
    // ─── Architectural rule (Phase 883 / Issue 16) ───────────────────────────
    // The checkout LIST uses CHECKOUT_VERIFY tasks as its source of truth,
    // NOT booking status. This is the correct and deliberate architecture.
    //
    // Historical context: a Phase 690 shadow route (now removed — Issue 15)
    // wrote booking status directly to the `bookings` table, bypassing
    // `booking_state` and `event_log`. This caused `booking_state.status` to
    // remain stale after checkout, making status-based lists unreliable.
    // Phase 883 replaced the status-based list with a task-based list.
    //
    // Current state (post Issue 15 fix): booking_checkin_router.py (Phase 398)
    // is now the sole checkout endpoint and correctly updates `booking_state`
    // and emits `BOOKING_CHECKED_OUT` to `event_log`. However, the task-based
    // list architecture is preserved as the authoritative design:
    //   - CHECKOUT_VERIFY tasks are generated daily by the pre-arrival scan
    //   - They are independent of booking status and more operationally reliable
    //   - Do NOT build future checkout-readiness surfaces on booking.status
    // ─────────────────────────────────────────────────────────────────────────
    const [checkoutTasks, setCheckoutTasks] = useState<CheckoutTask[]>([]);
    const [bookings, setBookings] = useState<Booking[]>([]);  // enrichment only — NOT the list source
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
    // Phase 692: Checkout condition photos
    const [checkoutPhotos, setCheckoutPhotos] = useState<Array<{ room_label: string; photo_url: string; local?: boolean }>>([]);
    const [photoUploading, setPhotoUploading] = useState(false);
    // Phase 988 — OCR audit linkage for closing meter
    const [ocrClosingMeterResultId, setOcrClosingMeterResultId] = useState<string | null>(null);
    const [closingMeterValue, setClosingMeterValue] = useState('');

    // Phase 993-994: Checkout baseline (before/after comparison data)
    type CheckoutBaseline = {
        property_reference_photos: Array<{ photo_url: string; room_label?: string; caption?: string }>;
        checkin_walkthrough_photos: Array<{ storage_path: string; room_label?: string; purpose?: string; captured_at?: string }>;
        checkin_meter_photos: Array<{ storage_path: string; room_label?: string }>;
        opening_meter: { id: string; meter_value: number | null; meter_unit: string; meter_photo_url: string | null; recorded_at: string | null } | null;
        deposit: { amount: number; currency: string } | null;
        charge_rules: { electricity_rate_kwh: number | null; electricity_currency: string | null; electricity_enabled: boolean } | null;
    };
    const [baseline, setBaseline] = useState<CheckoutBaseline | null>(null);
    const [baselineLoading, setBaselineLoading] = useState(false);
    const [baselineTab, setBaselineTab] = useState<'reference' | 'checkin' | 'checkout'>('checkout');

    const showNotice = (msg: string) => { setNotice(msg); setTimeout(() => setNotice(null), 3000); };

    const load = useCallback(async () => {
        setLoading(true);
        try {
            // Phase 883/886: CHECKOUT_VERIFY tasks are the truth for the checkout world.
            const taskRes = await apiFetch<any>('/worker/tasks?worker_role=CHECKOUT&limit=100');
            const taskList = taskRes.tasks || taskRes.data?.tasks || taskRes.data || [];
            const rawTasks: CheckoutTask[] = Array.isArray(taskList) ? taskList : [];
            // Phase 989: Exclude COMPLETED/CANCELED tasks — they must not appear in the active list
            const activeTasks = rawTasks.filter(t => {
                const s = (t.status || '').toUpperCase();
                return s !== 'COMPLETED' && s !== 'CANCELED';
            });

            // Phase 886/889: Enrich each task with property + booking data.
            // Property: display name, GPS location.
            // Booking: check_in, check_out, guest_name, guest_count → enables nights.
            const enriched = await Promise.all(activeTasks.map(async (t) => {
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
                // Phase 1000: Also enrich with early checkout context from booking_state
                if (t.booking_id) {
                    try {
                        const bkRes = await apiFetch<any>(`/worker/bookings/${t.booking_id}`);
                        const bk = bkRes?.data || bkRes;
                        if (bk && bk.booking_id) {
                            result.check_in    = bk.check_in ?? result.check_in;
                            result.check_out   = bk.check_out ?? result.check_out ?? t.due_date;
                            result.guest_name  = bk.guest_name ?? result.guest_name;
                            result.guest_count = bk.guest_count ?? result.guest_count;
                            // Phase 1000: Pull early checkout context from booking
                            if (bk.early_checkout_approved) {
                                result.early_checkout_date        = bk.early_checkout_date ?? result.early_checkout_date;
                                result.early_checkout_effective_at = bk.early_checkout_effective_at ?? result.early_checkout_effective_at;
                                result.early_checkout_status      = bk.early_checkout_status ?? result.early_checkout_status;
                                result.early_checkout_reason      = bk.early_checkout_reason ?? result.early_checkout_reason;
                                // Ensure is_early_checkout flag is set (may already be set on the task)
                                if (!result.is_early_checkout) result.is_early_checkout = true;
                            }
                            // Compute nights from canonical booking dates (original check_out)
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

            // Secondary: fetch checked_in bookings for FLOW STEP detail hydration only.
            // This is NOT used for the checkout list — checkoutTasks is the list source.
            // The status=checked_in filter is best-effort; stale values are tolerated
            // because booking data is used only for guest name, dates, and deposit lookup
            // during the 4-step checkout flow after a task has already been selected.
            try {
                const bookRes = await apiFetch<any>('/bookings?status=checked_in&limit=50');
                const list = bookRes.bookings || bookRes.data?.bookings || bookRes.data || [];
                setBookings(Array.isArray(list) ? list : []);
            } catch { setBookings([]); }

        } catch { setCheckoutTasks([]); }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    // Phase 993: Load baseline data when checkout starts
    const loadBaseline = async (bookingId: string) => {
        setBaselineLoading(true);
        try {
            const res = await apiFetch<any>(`/worker/bookings/${bookingId}/checkout-baseline`);
            const data = res?.data || res;
            setBaseline({
                property_reference_photos: data.property_reference_photos || [],
                checkin_walkthrough_photos: data.checkin_walkthrough_photos || [],
                checkin_meter_photos: data.checkin_meter_photos || [],
                opening_meter: data.opening_meter || null,
                deposit: data.deposit || null,
                charge_rules: data.charge_rules || null,
            });
        } catch { setBaseline(null); }
        setBaselineLoading(false);
    };

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
        setCheckoutPhotos([]);
        setBaselineTab('checkout');
        void loadBaseline(getBookingId(b));
    };

    const startCheckoutFromTask = (t: CheckoutTask) => {
        const syntheticBooking: Booking = {
            booking_id: t.booking_id || t.task_id,
            property_id: t.property_id,
            guest_name: t.guest_name || 'Guest',
            guest_count: t.guest_count,
            check_in: t.check_in,
            // Always pass the original booking check_out so settlement and dossier have it.
            // For early checkout display in the wizard, is_early_checkout + early_checkout_* is used.
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
        setCheckoutPhotos([]);
        setBaselineTab('checkout');
        void loadBaseline(t.booking_id || t.task_id);
    };

    const goBack = () => {
        const flow: CheckoutStep[] = ['list', 'inspection', 'closing_meter', 'issues', 'deposit', 'complete'];
        const idx = flow.indexOf(step);
        if (idx <= 1) { setStep('list'); setSelected(null); }
        else setStep(flow[idx - 1]);
    };

    // Phase 988: Save closing meter reading with OCR audit linkage
    const saveClosingMeter = async (meterFields?: MeterFields) => {
        if (!selected) { setStep('issues'); return; }
        const val = meterFields?.meter_value ?? closingMeterValue;
        const reading = parseFloat(val);
        if (isNaN(reading) || reading <= 0) {
            // Skip silently if no valid reading
            setStep(inspectionOk ? 'deposit' : 'issues');
            return;
        }
        if (meterFields) {
            setClosingMeterValue(meterFields.meter_value);
            if (meterFields.ocr_result_id) setOcrClosingMeterResultId(meterFields.ocr_result_id);
        }
        const bookingId = getBookingId(selected);
        try {
            await apiFetch<any>(`/worker/bookings/${bookingId}/closing-meter`, {
                method: 'POST',
                body: JSON.stringify({
                    meter_reading: reading,
                    ocr_result_id: meterFields?.ocr_result_id ?? ocrClosingMeterResultId ?? undefined,
                }),
            });
            showNotice('⚡ Closing meter saved');
        } catch {
            // Non-blocking — meter failure must not block checkout
            showNotice('⚠️ Meter reading not saved — continue anyway');
        }
        setStep(inspectionOk ? 'deposit' : 'issues');
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


    // Phase 692: Upload a checkout condition photo for a room
    // Uses <input type="file" capture="environment"> to open device camera.
    const uploadCheckoutPhoto = async (file: File, roomLabel: string) => {
        if (!selected) return;
        const bookingId = getBookingId(selected);
        setPhotoUploading(true);
        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('room_label', roomLabel);
            formData.append('taken_by', 'checkout_flow');

            // Use raw fetch for FormData (apiFetch uses JSON)
            const { getTabToken } = await import('@/lib/tokenStore');
            const token = getTabToken();
            const apiBase = process.env.NEXT_PUBLIC_API_URL || '';
            const response = await fetch(`${apiBase}/bookings/${bookingId}/checkout-photos/upload`, {
                method: 'POST',
                headers: token ? { Authorization: `Bearer ${token}` } : {},
                body: formData,
            });
            if (response.ok) {
                const data = await response.json();
                setCheckoutPhotos(prev => [...prev, {
                    room_label: roomLabel,
                    photo_url: data.photo_url || URL.createObjectURL(file),
                }]);
                showNotice(`📷 ${roomLabel} photo saved`);
            } else {
                // Fallback: record locally using object URL so the session preserves it
                setCheckoutPhotos(prev => [...prev, {
                    room_label: roomLabel,
                    photo_url: URL.createObjectURL(file),
                    local: true,
                }]);
                showNotice('📷 Photo saved locally (upload queued)');
            }
        } catch {
            showNotice('⚠️ Photo capture failed — try again');
        }
        setPhotoUploading(false);
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


    // Phase 989d: Persist inspection data (notes + photos) to backend
    const saveCheckoutInspection = async () => {
        if (!selected) return;
        const bookingId = getBookingId(selected);
        // Save inspection notes as a photo record with purpose=checkout_inspection
        // This reuses the existing checkin-photos endpoint with expanded purpose
        if (inspectionNotes.trim()) {
            try {
                await apiFetch<any>(`/worker/bookings/${bookingId}/checkin-photos`, {
                    method: 'POST',
                    body: JSON.stringify({
                        photos: [{
                            room_label: 'inspection_summary',
                            storage_path: `checkout/${bookingId}/inspection_notes.txt`,
                            purpose: 'checkout_inspection',
                            notes: inspectionNotes.trim(),
                        }],
                    }),
                });
            } catch { /* non-blocking */ }
        }
        // Save checkout photos with checkout_condition purpose
        if (checkoutPhotos.length > 0) {
            try {
                await apiFetch<any>(`/worker/bookings/${bookingId}/checkin-photos`, {
                    method: 'POST',
                    body: JSON.stringify({
                        photos: checkoutPhotos.map((p: any) => ({
                            room_label: p.room_label || 'checkout_photo',
                            storage_path: p.photo_url || p.storage_path || `checkout/${bookingId}/photo_${Date.now()}.jpg`,
                            purpose: 'checkout_condition',
                        })),
                    }),
                });
            } catch { /* non-blocking */ }
        }
    };

    // Phase 989d: Handle deposit — uses real settlement engine
    // Flow: settlement/start → settlement/calculate → show results → add deductions if needed
    const handleDeposit = async () => {
        if (!selected) return;
        const bookingId = getBookingId(selected);
        try {
            // Step 1: Start the settlement (creates draft record)
            try {
                await apiFetch<any>(`/worker/bookings/${bookingId}/settlement/start`, {
                    method: 'POST',
                    body: JSON.stringify({}),
                });
            } catch {
                // 409 = settlement already exists, which is fine
            }

            // Step 2: If worker chose to add a manual damage deduction, add it first
            if (depositAction === 'deduct' && deductionAmount && parseFloat(deductionAmount) > 0) {
                try {
                    await apiFetch<any>(`/worker/bookings/${bookingId}/settlement/deductions`, {
                        method: 'POST',
                        body: JSON.stringify({
                            description: deductionReason || 'Damage/cleaning deduction',
                            amount: parseFloat(deductionAmount),
                            category: 'damage',
                        }),
                    });
                    showNotice('💰 Damage deduction recorded');
                } catch {
                    showNotice('⚠️ Deduction may not have saved');
                }
            }

            // Step 3: Calculate settlement — triggers auto-electricity deduction
            try {
                const calcResult = await apiFetch<any>(`/worker/bookings/${bookingId}/settlement/calculate`, {
                    method: 'POST',
                    body: JSON.stringify({}),
                });
                setSettlement(calcResult);
            } catch {
                // Calculation failed — we can still proceed with what we have
                showNotice('⚠️ Settlement calculation unavailable');
            }

            setStep('complete');
        } catch {
            showNotice('Settlement setup failed — proceeding');
            setStep('complete');
        }
    };

    /**
     * Phase 989: forceCompleteTask — walks task through ack → start → complete.
     * Each step catches INVALID_TRANSITION (task already past that state)
     * and continues. Mirrors the checkin wizard pattern.
     */
    async function forceCompleteTask(taskId: string): Promise<void> {
        const headers: Record<string, string> = { 'Content-Type': 'application/json' };
        const tok = getToken();
        if (tok) headers['Authorization'] = `Bearer ${tok}`;

        const patch = async (endpoint: string, body?: object) => {
            try {
                const r = await fetch(`${BASE}${endpoint}`, {
                    method: 'PATCH',
                    headers,
                    body: body ? JSON.stringify(body) : undefined,
                });
                return r.status;
            } catch {
                return 0;
            }
        };

        // Step 1: acknowledge (PENDING → ACKNOWLEDGED). 422 = already past, fine.
        const ackStatus = await patch(`/worker/tasks/${taskId}/acknowledge`);
        console.log(`[checkout] task ${taskId} ack → HTTP ${ackStatus}`);

        // Step 2: start (ACKNOWLEDGED → IN_PROGRESS). 422 = already past, fine.
        const startStatus = await patch(`/worker/tasks/${taskId}/start`);
        console.log(`[checkout] task ${taskId} start → HTTP ${startStatus}`);

        // Step 3: complete (IN_PROGRESS → COMPLETED). This must succeed.
        const doneStatus = await patch(`/worker/tasks/${taskId}/complete`, { notes: 'Check-out completed via wizard' });
        console.log(`[checkout] task ${taskId} complete → HTTP ${doneStatus}`);
        if (doneStatus < 200 || doneStatus >= 300) {
            console.warn(`[checkout] task ${taskId} complete returned ${doneStatus}`);
        }
    }

    // Step 4: Complete checkout via POST /bookings/{id}/checkout + finalize settlement
    const completeCheckout = async () => {
        if (!selected) return;
        const bookingId = getBookingId(selected);
        try {
            // Finalize settlement before completing checkout (best-effort)
            try {
                await apiFetch<any>(`/worker/bookings/${bookingId}/settlement/finalize`, {
                    method: 'POST',
                    body: JSON.stringify({}),
                });
            } catch { /* non-blocking — settlement may not exist or may already be finalized */ }

            await apiFetch<any>(`/bookings/${bookingId}/checkout`, {
                method: 'POST',
            });

            // Phase 989: Force CHECKOUT_VERIFY task to COMPLETED
            // This is the same pattern used by the checkin wizard.
            const taskId = selectedTask?.task_id;
            if (taskId) {
                await forceCompleteTask(taskId);
            }

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

    // Phase 993-fix: Task-world split uses check_out (real checkout date), NOT due_date.
    // due_date was corrupted by backfill (set to check_in). Even after the DB fix,
    // check_out from the enriched booking is the canonical source for eligibility.
    // Tasks without check_out fall back to due_date.
    const getCheckoutDate = (t: CheckoutTask) => t.check_out || t.due_date || '';

    const overdueTasks  = checkoutTasks.filter(t => { const d = getCheckoutDate(t); return d && d < todayStr; });
    const todayTasks    = checkoutTasks.filter(t => getCheckoutDate(t) === todayStr);
    const upcomingTasks = checkoutTasks.filter(t => { const d = getCheckoutDate(t); return d && d > todayStr; });
    // Earliest actionable task for summary strip countdown
    const nextDueTask = overdueTasks[0] || todayTasks[0] || upcomingTasks[0] || null;
    const nextDueIso = nextDueTask ? getCheckoutDate(nextDueTask) : null;

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
                    <StepHeader step={1} total={5} title="Property Inspection" onBack={goBack} />

                    {/* Phase 1000: Early Checkout wizard context banner */}
                    {selectedTask?.is_early_checkout && (
                        <div style={{
                            margin: '0 0 var(--space-4)',
                            background: '#fef3c7',
                            border: '2px solid #f59e0b',
                            borderRadius: 'var(--radius-md)',
                            padding: 'var(--space-3)',
                        }}>
                            <div style={{ fontSize: 13, fontWeight: 800, color: '#92400e', marginBottom: 4 }}>
                                ⚡ EARLY DEPARTURE — Exception Flow
                            </div>
                            <div style={{ fontSize: 12, color: '#78350f', lineHeight: 1.5 }}>
                                {selectedTask.early_checkout_effective_at ? (
                                    <>Effective checkout:{' '}
                                    <strong>{new Date(selectedTask.early_checkout_effective_at).toLocaleString('en-US', {
                                            weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
                                            timeZone: OPS_TZ,
                                        })}</strong>
                                    </>
                                ) : selectedTask.early_checkout_date ? (
                                    <>Effective checkout: <strong>{selectedTask.early_checkout_date}</strong></>
                                ) : null}
                            </div>
                            {(selectedTask.original_due_date || selected.check_out) && (
                                <div style={{ fontSize: 11, color: '#92400e', opacity: 0.75, marginTop: 2 }}>
                                    Original booking checkout:{' '}
                                    {(() => {
                                        const orig = selectedTask.original_due_date || selected.check_out || '';
                                        try { return new Date(orig.slice(0, 10) + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }); }
                                        catch { return orig; }
                                    })()}
                                </div>
                            )}
                            {selectedTask.early_checkout_reason && (
                                <div style={{ fontSize: 11, color: '#78350f', marginTop: 4, fontStyle: 'italic' }}>
                                    Reason: "{selectedTask.early_checkout_reason}"
                                </div>
                            )}
                            <div style={{ fontSize: 10, color: '#92400e', marginTop: 6, opacity: 0.7 }}>
                                The checkout workflow is the same as normal. Settlement, meter, deposit, and inspection all apply.
                            </div>
                        </div>
                    )}

                    <InfoRow label="Guest" value={selected.guest_name} />
                    <InfoRow label="Guests" value={selected.guest_count ? `${selected.guest_count} guests` : undefined} />
                    <InfoRow label="Property" value={(selectedTask?.property_name) || selected.property_id} />
                    <InfoRow label="Check-in" value={selected.check_in ? new Date(selected.check_in + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }) : undefined} />
                    <InfoRow
                        label={selectedTask?.is_early_checkout ? 'Early Checkout' : 'Check-out'}
                        value={
                            selectedTask?.is_early_checkout && selectedTask.early_checkout_date
                                ? new Date(selectedTask.early_checkout_date + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }) + ' ⚡'
                                : selected.check_out ? new Date(selected.check_out + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }) : selected.check_out
                        }
                    />
                    <InfoRow label="Nights" value={selected.nights} />


                    {/* Phase 993-994: Before/After Photo Comparison */}
                    <div style={{ marginTop: 'var(--space-4)' }}>
                        {/* Tab bar: Reference / Check-in / Checkout */}
                        <div style={{ display: 'flex', gap: 0, marginBottom: 'var(--space-3)', borderRadius: 'var(--radius-sm)', overflow: 'hidden', border: '1px solid var(--color-border)' }}>
                            {[
                                { key: 'reference' as const, label: '🏠 Reference', count: baseline?.property_reference_photos?.length || 0 },
                                { key: 'checkin' as const, label: '📋 Check-in', count: baseline?.checkin_walkthrough_photos?.length || 0 },
                                { key: 'checkout' as const, label: '📷 Checkout', count: checkoutPhotos.length },
                            ].map(tab => (
                                <button key={tab.key} onClick={() => setBaselineTab(tab.key)} style={{
                                    flex: 1, padding: '8px 4px', border: 'none', cursor: 'pointer',
                                    background: baselineTab === tab.key ? 'var(--color-primary)' : 'var(--color-surface-2)',
                                    color: baselineTab === tab.key ? '#fff' : 'var(--color-text-dim)',
                                    fontSize: 11, fontWeight: 600, transition: 'background 0.2s',
                                }}>
                                    {tab.label} {tab.count > 0 && `(${tab.count})`}
                                </button>
                            ))}
                        </div>

                        {/* Reference photos tab */}
                        {baselineTab === 'reference' && (
                            <div>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginBottom: 'var(--space-2)' }}>
                                    Property standard — how each room should look.
                                </div>
                                {baselineLoading ? <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>Loading…</div> :
                                    (baseline?.property_reference_photos?.length ?? 0) === 0 ?
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', fontStyle: 'italic', padding: 'var(--space-3) 0' }}>No reference photos configured for this property.</div> :
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--space-2)' }}>
                                            {baseline!.property_reference_photos.map((ph, i) => (
                                                <div key={i} style={{ position: 'relative' }}>
                                                    {/* eslint-disable-next-line @next/next/no-img-element */}
                                                    <img src={ph.photo_url} alt={ph.room_label || 'ref'} style={{ width: '100%', aspectRatio: '4/3', objectFit: 'cover', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }} />
                                                    <div style={{ fontSize: 9, color: 'var(--color-text-faint)', marginTop: 2, textAlign: 'center' }}>{ph.room_label || ph.caption || ''}</div>
                                                </div>
                                            ))}
                                        </div>
                                }
                            </div>
                        )}

                        {/* Check-in walkthrough photos tab */}
                        {baselineTab === 'checkin' && (
                            <div>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginBottom: 'var(--space-2)' }}>
                                    Condition at arrival — captured during check-in walkthrough.
                                </div>
                                {baselineLoading ? <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>Loading…</div> :
                                    (baseline?.checkin_walkthrough_photos?.length ?? 0) === 0 ?
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', fontStyle: 'italic', padding: 'var(--space-3) 0' }}>No check-in walkthrough photos found for this stay.</div> :
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--space-2)' }}>
                                            {baseline!.checkin_walkthrough_photos.map((ph, i) => (
                                                <div key={i} style={{ position: 'relative' }}>
                                                    {/* eslint-disable-next-line @next/next/no-img-element */}
                                                    <img src={ph.storage_path} alt={ph.room_label || 'checkin'} style={{ width: '100%', aspectRatio: '4/3', objectFit: 'cover', borderRadius: 'var(--radius-sm)', border: '1px solid rgba(88,166,255,0.3)' }} />
                                                    <div style={{ fontSize: 9, color: 'var(--color-text-faint)', marginTop: 2, textAlign: 'center' }}>{ph.room_label || ''}</div>
                                                </div>
                                            ))}
                                        </div>
                                }
                            </div>
                        )}

                        {/* Checkout capture tab (existing functionality) */}
                        {baselineTab === 'checkout' && (
                            <div>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginBottom: 'var(--space-2)' }}>
                                    Current condition — photograph each room now for before/after comparison.
                                </div>

                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-2)', marginBottom: 'var(--space-3)' }}>
                                    {['Living Room', 'Bedroom', 'Bathroom', 'Kitchen', 'Balcony', 'Other'].map(room => {
                                        const roomKey = room.toLowerCase().replace(' ', '_');
                                        const taken = checkoutPhotos.some(p => p.room_label === roomKey);
                                        return (
                                            <label key={room} style={{
                                                display: 'flex', alignItems: 'center', gap: 8,
                                                padding: '10px 12px',
                                                background: taken ? 'rgba(63,185,80,0.08)' : 'var(--color-surface-2)',
                                                border: `1px solid ${taken ? 'rgba(63,185,80,0.3)' : 'var(--color-border)'}`,
                                                borderRadius: 'var(--radius-sm)',
                                                cursor: photoUploading ? 'not-allowed' : 'pointer',
                                                opacity: photoUploading ? 0.6 : 1,
                                                fontSize: 'var(--text-xs)', fontWeight: 600,
                                                color: taken ? 'var(--color-ok)' : 'var(--color-text-dim)',
                                            }}>
                                                <input type="file" accept="image/*" capture="environment" style={{ display: 'none' }} disabled={photoUploading}
                                                    onChange={e => { const f = e.target.files?.[0]; if (f) uploadCheckoutPhoto(f, roomKey); e.target.value = ''; }} />
                                                <span>{taken ? '✅' : '📷'}</span>
                                                <span>{room}</span>
                                            </label>
                                        );
                                    })}
                                </div>

                                {checkoutPhotos.length > 0 && (
                                    <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap', marginBottom: 'var(--space-3)' }}>
                                        {checkoutPhotos.map((p, i) => (
                                            <div key={i} style={{ position: 'relative' }}>
                                                {/* eslint-disable-next-line @next/next/no-img-element */}
                                                <img src={p.photo_url} alt={p.room_label} style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }} />
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {photoUploading && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginBottom: 'var(--space-2)' }}>⏳ Uploading photo…</div>}
                            </div>
                        )}
                    </div>

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
                        <ActionButton label={'Continue → Meter'} onClick={() => {
                            // Persist inspection data in background (non-blocking)
                            void saveCheckoutInspection();
                            setStep('closing_meter');
                        }} />
                        <ActionButton label="📍 Navigate to Property" onClick={() => navigateToProperty(selected.property_id)} variant="outline" />
                    </div>
                </div>
            )}

            {/* ========== STEP 2: Closing Meter Capture (Phase 988 OCR + Phase 994 baseline) ========== */}
            {step === 'closing_meter' && selected && (
                <div style={card}>
                    <StepHeader step={2} total={5} title="Closing Meter" onBack={goBack} />

                    {/* Phase 994: Show opening meter from check-in as baseline context */}
                    {baseline?.opening_meter && baseline.opening_meter.meter_value !== null && (
                        <div style={{
                            padding: 'var(--space-3) var(--space-4)', marginBottom: 'var(--space-4)',
                            background: 'rgba(88,166,255,0.06)', border: '1px solid rgba(88,166,255,0.2)',
                            borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: 'var(--space-3)',
                        }}>
                            {baseline.opening_meter.meter_photo_url && (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img src={baseline.opening_meter.meter_photo_url} alt="Opening meter" style={{
                                    width: 56, height: 56, objectFit: 'cover', borderRadius: 'var(--radius-sm)',
                                    border: '1px solid rgba(88,166,255,0.3)', flexShrink: 0,
                                }} />
                            )}
                            <div>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', fontWeight: 600 }}>
                                    ⚡ Opening Meter (from check-in)
                                </div>
                                <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-sage)', fontFamily: 'var(--font-mono)' }}>
                                    {Number(baseline.opening_meter.meter_value).toLocaleString()} {baseline.opening_meter.meter_unit || 'kWh'}
                                </div>
                                {baseline.opening_meter.recorded_at && (
                                    <div style={{ fontSize: 10, color: 'var(--color-text-faint)' }}>
                                        Recorded {new Date(baseline.opening_meter.recorded_at).toLocaleDateString()}
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Live delta preview if closing meter has been entered */}
                    {closingMeterValue && baseline?.opening_meter?.meter_value != null && parseFloat(closingMeterValue) > 0 && (
                        <div style={{
                            padding: 'var(--space-2) var(--space-3)', marginBottom: 'var(--space-3)',
                            background: 'rgba(210,153,34,0.06)', border: '1px solid rgba(210,153,34,0.2)',
                            borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-sm)',
                        }}>
                            <span style={{ color: 'var(--color-text-dim)' }}>Usage: </span>
                            <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-warn)' }}>
                                {Math.max(0, parseFloat(closingMeterValue) - Number(baseline.opening_meter.meter_value)).toLocaleString()} kWh
                            </strong>
                            {baseline.charge_rules?.electricity_rate_kwh != null && baseline.charge_rules.electricity_rate_kwh > 0 && (
                                <span style={{ color: 'var(--color-text-faint)', marginLeft: 8 }}>
                                    ≈ {(Math.max(0, parseFloat(closingMeterValue) - Number(baseline.opening_meter.meter_value)) * baseline.charge_rules.electricity_rate_kwh).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })} {baseline.charge_rules.electricity_currency || 'THB'}
                                </span>
                            )}
                        </div>
                    )}

                    <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-4)' }}>
                        Capture the closing electricity meter reading for accurate billing.
                    </div>
                    <OcrCaptureFlow
                        captureType="checkout_closing_meter_capture"
                        bookingId={getBookingId(selected)}
                        onComplete={(fields) => {
                            void saveClosingMeter(fields as MeterFields);
                        }}
                        onSkip={() => setStep(inspectionOk ? 'deposit' : 'issues')}
                    />
                </div>
            )}

            {/* ========== STEP 3: Issue Flagging ========== */}
            {step === 'issues' && selected && (
                <div style={card}>
                    <StepHeader step={3} total={5} title="Report Issues" onBack={goBack} />

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

            {/* ========== STEP 4: Deposit Resolution (Phase 989d — real settlement) ========== */}
            {step === 'deposit' && selected && (
                <div style={card}>
                    <StepHeader step={4} total={5} title="Deposit Resolution" onBack={goBack} />

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

                            {/* Electricity info from closing meter */}
                            {closingMeterValue && (
                                <div style={{
                                    padding: 'var(--space-3)', background: 'rgba(88,166,255,0.06)',
                                    border: '1px solid rgba(88,166,255,0.2)', borderRadius: 'var(--radius-sm)',
                                    fontSize: 'var(--text-xs)', marginBottom: 'var(--space-3)',
                                }}>
                                    <div style={{ fontWeight: 600, color: 'var(--color-text)', marginBottom: 4 }}>⚡ Electricity</div>
                                    <div style={{ color: 'var(--color-text-dim)' }}>Closing meter: {closingMeterValue} kWh</div>
                                    <div style={{ color: 'var(--color-text-faint)', marginTop: 2 }}>
                                        Electricity deduction will be auto-calculated from the property rate.
                                    </div>
                                </div>
                            )}

                            {issues.length > 0 && (
                                <div style={{
                                    padding: 'var(--space-3)', background: 'rgba(248,81,73,0.05)',
                                    border: '1px solid rgba(248,81,73,0.15)', borderRadius: 'var(--radius-sm)',
                                    fontSize: 'var(--text-xs)', color: 'var(--color-alert)', marginBottom: 'var(--space-4)',
                                }}>
                                    ⚠ {issues.length} issue(s) reported — consider adding a damage deduction
                                </div>
                            )}

                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', marginBottom: 'var(--space-3)' }}>
                                {[
                                    { action: 'full_return' as const, label: '💵 Full Return', desc: 'Return deposit (electricity deducted automatically)' },
                                    { action: 'deduct' as const, label: '📉 Add Damage Deduction', desc: 'Add extra deduction for damages/cleaning' },
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
                                            Damage Amount ({selected.deposit_currency || 'THB'})
                                        </label>
                                        <input type="number" value={deductionAmount} onChange={e => setDeductionAmount(e.target.value)}
                                            placeholder="0" style={inputStyle} max={selected.deposit_amount} />
                                    </div>
                                    <div>
                                        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
                                            Reason
                                        </label>
                                        <input value={deductionReason} onChange={e => setDeductionReason(e.target.value)}
                                            placeholder="Describe the damage..." style={inputStyle} />
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
                        <ActionButton label="Calculate & Continue →" onClick={handleDeposit} />
                    </div>
                </div>
            )}

            {/* ========== STEP 5: Settlement Summary + Complete (Phase 989d) ========== */}
            {step === 'complete' && selected && (
                <div style={card}>
                    <StepHeader step={5} total={5} title="Checkout Summary" onBack={goBack} />

                    <div style={{
                        padding: 'var(--space-4)', textAlign: 'center',
                        background: 'rgba(248,81,73,0.03)', borderRadius: 'var(--radius-md)',
                        border: '1px solid rgba(248,81,73,0.15)', marginBottom: 'var(--space-4)',
                    }}>
                        <div style={{ fontSize: 'var(--text-3xl)', marginBottom: 'var(--space-2)' }}>🚪</div>
                        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)' }}>
                            Review & Complete
                        </div>
                        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-2)' }}>
                            This will finalize the settlement and mark the booking as <strong>Checked Out</strong>.
                        </div>
                    </div>

                    {/* Guest & Property */}
                    <InfoRow label="Guest" value={selected.guest_name} />
                    <InfoRow label="Property" value={(selectedTask?.property_name) || selected.property_id} />
                    <InfoRow label="Nights" value={selected.nights} />

                    {/* Phase 1000: Early checkout summary rows */}
                    {selectedTask?.is_early_checkout && (
                        <>
                            <InfoRow
                                label="⚡ Early Checkout"
                                value={selectedTask.early_checkout_date
                                    ? new Date(selectedTask.early_checkout_date + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
                                    : 'Approved'}
                            />
                            <InfoRow
                                label="Original Checkout"
                                value={(selectedTask.original_due_date || selected.check_out)
                                    ? new Date(((selectedTask.original_due_date || selected.check_out || '').slice(0, 10)) + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                                    : '—'}
                            />
                            {selectedTask.early_checkout_reason && (
                                <InfoRow label="Reason" value={`"${selectedTask.early_checkout_reason}"`} />
                            )}
                        </>
                    )}

                    <InfoRow label="Inspection" value={inspectionOk ? '✓ All OK' : `⚠ Issues: ${inspectionNotes || 'See reports'}`} />
                    {closingMeterValue && <InfoRow label="Closing Meter" value={`${closingMeterValue} kWh`} />}
                    <InfoRow label="Issues Reported" value={issues.length > 0 ? `${issues.length} issue(s)` : 'None'} />


                    {/* Settlement Breakdown */}
                    {settlement && (
                        <div style={{
                            marginTop: 'var(--space-4)', padding: 'var(--space-4)',
                            background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)',
                            border: '1px solid var(--color-border)',
                        }}>
                            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-dim)', textTransform: 'uppercase', marginBottom: 'var(--space-3)' }}>
                                💳 Settlement Breakdown
                            </div>
                            <InfoRow label="Deposit Held" value={`${settlement.deposit_currency || selected.deposit_currency || 'THB'} ${settlement.deposit_held ?? selected.deposit_amount ?? 0}`} />

                            {/* Electricity */}
                            {settlement.electricity && (
                                <>
                                    {settlement.electricity.kwh_used != null && (
                                        <InfoRow label="⚡ Electricity Used" value={`${settlement.electricity.kwh_used} kWh`} />
                                    )}
                                    {settlement.electricity.rate_kwh != null && (
                                        <InfoRow label="Rate" value={`${settlement.electricity.rate_kwh} /kWh`} />
                                    )}
                                    {settlement.electricity.charged != null && settlement.electricity.charged > 0 && (
                                        <InfoRow label="⚡ Electricity Charge" value={`${settlement.electricity.currency || 'THB'} ${settlement.electricity.charged}`} />
                                    )}
                                </>
                            )}

                            {/* Deductions by category */}
                            {settlement.deductions_by_category && (
                                <>
                                    {settlement.deductions_by_category.damage?.total > 0 && (
                                        <InfoRow label="🔨 Damage Deductions" value={`${selected.deposit_currency || 'THB'} ${settlement.deductions_by_category.damage.total}`} />
                                    )}
                                    {settlement.deductions_by_category.miscellaneous?.total > 0 && (
                                        <InfoRow label="📋 Other Deductions" value={`${selected.deposit_currency || 'THB'} ${settlement.deductions_by_category.miscellaneous.total}`} />
                                    )}
                                </>
                            )}

                            <div style={{ borderTop: '2px solid var(--color-border)', marginTop: 'var(--space-3)', paddingTop: 'var(--space-3)' }}>
                                <InfoRow label="Total Deductions" value={`${selected.deposit_currency || 'THB'} ${settlement.total_deductions ?? 0}`} />
                                <div style={{
                                    display: 'flex', justifyContent: 'space-between', padding: '10px 0',
                                    fontSize: 'var(--text-md)', fontWeight: 700,
                                }}>
                                    <span style={{ color: 'var(--color-ok)' }}>💵 Refund to Guest</span>
                                    <span style={{ color: 'var(--color-ok)' }}>
                                        {selected.deposit_currency || 'THB'} {settlement.refund_amount ?? 0}
                                    </span>
                                </div>
                                {(settlement.retained_amount ?? 0) > 0 && (
                                    <InfoRow label="Retained by Property" value={`${selected.deposit_currency || 'THB'} ${settlement.retained_amount}`} />
                                )}
                            </div>

                            {/* Warnings */}
                            {settlement.warnings && settlement.warnings.length > 0 && (
                                <div style={{ marginTop: 'var(--space-2)' }}>
                                    {settlement.warnings.map((w: string, i: number) => (
                                        <div key={i} style={{
                                            fontSize: 'var(--text-xs)', color: 'var(--color-warn)',
                                            padding: '4px 0',
                                        }}>⚠ {w}</div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {!settlement && (
                        <div style={{
                            marginTop: 'var(--space-4)', padding: 'var(--space-3)',
                            background: 'var(--color-surface-2)', borderRadius: 'var(--radius-sm)',
                            fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', textAlign: 'center',
                        }}>
                            💳 No deposit on file — no settlement required
                        </div>
                    )}

                    <div style={{ marginTop: 'var(--space-5)' }}>
                        <ActionButton label="✅ Finalize & Complete Check-out" onClick={completeCheckout} variant="danger" />
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
                    </div>

                    {/* Settlement result summary */}
                    {settlement && (
                        <div style={{
                            padding: 'var(--space-4)', background: 'var(--color-surface-2)',
                            borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)',
                            marginBottom: 'var(--space-4)',
                        }}>
                            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-dim)', textTransform: 'uppercase', marginBottom: 'var(--space-2)' }}>
                                Settlement Result
                            </div>
                            <InfoRow label="Deposit Held" value={`${selected.deposit_currency || 'THB'} ${settlement.deposit_held ?? 0}`} />
                            <InfoRow label="Total Deductions" value={`${selected.deposit_currency || 'THB'} ${settlement.total_deductions ?? 0}`} />
                            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', fontWeight: 700, fontSize: 'var(--text-sm)', color: 'var(--color-ok)' }}>
                                <span>💵 Refund Amount</span>
                                <span>{selected.deposit_currency || 'THB'} {settlement.refund_amount ?? 0}</span>
                            </div>
                        </div>
                    )}

                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textAlign: 'center', marginBottom: 'var(--space-3)' }}>
                        A CLEANING task has been automatically created for this property.
                    </div>
                    <ActionButton label="Done — Return to List" onClick={returnToList} />
                </div>
            )}

            {/* Phase 865: BottomNav now managed by MobileStaffShell via bottomNavItems prop */}
        </div>
    );
}

/** Page-level default — workers access the checkout wizard at /ops/checkout */
export default function MobileCheckoutPage() {
    return (
        <MobileStaffShell title="Check-out" bottomNavItems={CHECKOUT_BOTTOM_NAV}>
            <CheckoutWizard />
        </MobileStaffShell>
    );
}
