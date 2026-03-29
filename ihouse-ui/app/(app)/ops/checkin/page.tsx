'use client';

/**
 * Phase 971 — Check-in Wizard Rebuild
 * Route: /ops/checkin
 *
 * Corrected 7-step operational check-in flow:
 *   1. Arrival Confirmation
 *   2. Property Walk-Through Photos (match reference photos)
 *   3. Electricity Meter Capture (conditional: electricity_enabled)
 *   4. Guest Contact Info
 *   5. Deposit Collection (conditional: deposit_enabled)
 *   6. Passport / Identity Capture
 *   7. Complete + Generate Guest Portal QR
 *
 * Home: Today's arrivals list for the entire tenant
 * Conditional steps auto-skip based on property_charge_rules.
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { apiFetch, getToken, API_BASE as BASE } from '@/lib/staffApi';
import { useCountdown } from '@/lib/useCountdown';
import { CHECKIN_BOTTOM_NAV } from '@/components/BottomNav';
import MobileStaffShell from '@/components/MobileStaffShell';
import WorkerTaskCard from '@/components/WorkerTaskCard';
import WorkerHeader from '@/components/WorkerHeader';
import QRCode from 'qrcode';
import OcrCaptureFlow, { type IdentityFields, type MeterFields } from '@/components/OcrCaptureFlow';

type Booking = {
    booking_ref?: string;
    booking_id?: string;
    id?: string;
    property_id: string;
    guest_name?: string;
    guest_id?: string;
    check_in?: string;
    check_out?: string;
    status?: string;
    guest_count?: number;
    deposit_required?: boolean;
    deposit_amount?: number;
    deposit_currency?: string;
    nights?: number;
    source?: string;
    reservation_ref?: string;
    operator_note?: string;
    property_status?: string;
    property_latitude?: number;
    property_longitude?: number;
    property_address?: string;
};

type ChargeConfig = {
    deposit_enabled: boolean;
    deposit_amount: number | null;
    deposit_currency: string;
    electricity_enabled: boolean;
    electricity_rate_kwh: number | null;
};

type RefPhoto = { id: string; photo_url: string; room_label: string; caption?: string };
type CapturedPhoto = { room_label: string; storage_path: string; captured_at: string; preview_url?: string };

function getBookingId(b: Booking): string {
    return b.booking_id || b.booking_ref || b.id || 'unknown';
}

/** Strip internal metadata from operator notes (e.g. "(auto, Phase 232)") */
function cleanNote(note: string): string {
    return note.replace(/\s*\(auto,.*?\)\s*/gi, '').replace(/\s*—\s*pre-arrival preparation/gi, '').trim();
}

/** Truncate long strings with ellipsis */
function truncate(s: string, max: number): string {
    return s.length > max ? s.slice(0, max) + '…' : s;
}

type CheckInStep = 'list' | 'arrival' | 'walkthrough' | 'meter' | 'contact' | 'deposit' | 'passport' | 'complete' | 'success';

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
    Upcoming: { bg: 'rgba(88,166,255,0.15)', text: 'var(--color-sage)' },
    Arrived: { bg: 'rgba(210,153,34,0.15)', text: 'var(--color-warn)' },
    InStay: { bg: 'rgba(63,185,80,0.15)', text: 'var(--color-ok)' },
    Completed: { bg: 'rgba(110,118,129,0.15)', text: 'var(--color-text-dim)' },
    checked_in: { bg: 'rgba(63,185,80,0.15)', text: 'var(--color-ok)' },
    active: { bg: 'rgba(88,166,255,0.15)', text: 'var(--color-sage)' },
    observed: { bg: 'rgba(210,153,34,0.15)', text: 'var(--color-warn)' },
};

function StatusBadge({ status }: { status?: string }) {
    const s = status || 'Upcoming';
    const c = STATUS_COLORS[s] || STATUS_COLORS['Upcoming'];
    return (
        <span style={{
            padding: '2px 10px', borderRadius: 12, fontSize: 'var(--text-xs)', fontWeight: 600,
            background: c.bg, color: c.text,
        }}>{s}</span>
    );
}

// ========== Step Components ==========

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
            {/* Progress bar */}
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

function CheckinSummaryStrip({ todayCount, upcomingCount, completedCount, nextArrivalIso }: {
    todayCount: number; upcomingCount: number; completedCount: number; nextArrivalIso: string | null;
}) {
    const { label, isOverdue, isUrgent } = useCountdown(nextArrivalIso, '14:00');
    const urgencyColor = isOverdue ? 'var(--color-danger)' : isUrgent ? 'var(--color-warn)' : 'var(--color-sage)';
    const card: React.CSSProperties = {
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
    };
    const totalPending = todayCount + upcomingCount;
    return (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
            <div style={card}>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Today</div>
                <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: todayCount > 0 ? 'var(--color-accent)' : 'var(--color-text-faint)', marginTop: 4 }}>{todayCount}</div>
            </div>
            <div style={card}>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Upcoming</div>
                <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: upcomingCount > 0 ? 'var(--color-sage)' : 'var(--color-text-faint)', marginTop: 4 }}>{upcomingCount}</div>
            </div>
            <div style={{ ...card, borderColor: nextArrivalIso && isUrgent ? 'rgba(88,166,255,0.3)' : 'var(--color-border)' }}>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Next</div>
                {nextArrivalIso && totalPending > 0 ? (
                    <>
                        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: urgencyColor, marginTop: 6, lineHeight: 1.2 }}>
                            ⏱ {label}
                        </div>
                        <div style={{ fontSize: '10px', color: 'var(--color-text-faint)', marginTop: 2 }}>(by 14:00)</div>
                    </>
                ) : (
                    <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 8 }}>
                        {completedCount > 0 ? `${completedCount} done` : '—'}
                    </div>
                )}
            </div>
        </div>
    );
}

function BookingCardList({ bookings, onStart, onAcknowledge, showNotice }: {
    bookings: Booking[]; onStart: (b: Booking) => void; onAcknowledge: (taskId: string) => void; showNotice: (msg: string) => void;
}) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            {bookings.map(b => {
                const bookingId = b.booking_id || b.booking_ref || b.id || 'unknown';
                const taskId = (b as any).task_id || bookingId;
                return (
                    <WorkerTaskCard
                        key={bookingId}
                        kind="CHECKIN_PREP"
                        status={b.status || 'Upcoming'}
                        propertyName={(b as any).property_name || b.property_id}
                        propertyCode={b.property_id}
                        date={b.check_in?.split('T')[0] || 'Unknown'}
                        checkIn={b.check_in?.split('T')[0]}
                        checkOut={b.check_out?.split('T')[0]}
                        guestName={b.guest_name}
                        guestCount={b.guest_count}
                        onStart={() => onStart(b)}
                        onAcknowledge={
                            (b.status || 'PENDING').toUpperCase() === 'PENDING'
                                ? () => onAcknowledge(taskId)
                                : undefined
                        }
                        onNavigate={() => {
                            if (b.property_latitude && b.property_longitude) {
                                const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
                                const url = isMobile
                                    ? `https://waze.com/ul?ll=${b.property_latitude},${b.property_longitude}&navigate=yes`
                                    : `https://maps.google.com/maps?daddr=${b.property_latitude},${b.property_longitude}`;
                                window.open(url, '_blank');
                            } else if (b.property_address) {
                                window.open(`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(b.property_address)}`, '_blank');
                            } else {
                                showNotice('📍 No location data for this property');
                            }
                        }}
                    />
                );
            })}
        </div>
    );
}

// ========== Main Page ==========

/**
 * CheckinWizard — Phase 1022-H: extracted as named export for embedding in ManagerExecutionDrawer.
 * Identical logic to the page; MobileStaffShell wrapper removed.
 * onCompleted: called after a booking check-in is completed (used for manager board refresh).
 */
export function CheckinWizard({ onCompleted }: { onCompleted?: () => void }) {
    const [bookings, setBookings] = useState<Booking[]>([]);
    const [loading, setLoading] = useState(true);
    const [step, setStep] = useState<CheckInStep>('list');
    const [selected, setSelected] = useState<Booking | null>(null);
    const [notice, setNotice] = useState<string | null>(null);

    // Check-in flow state
    const [depositMethod, setDepositMethod] = useState('cash');
    const [depositNote, setDepositNote] = useState('');
    const [passportNumber, setPassportNumber] = useState('');
    const [passportName, setPassportName] = useState('');
    const [passportExpiry, setPassportExpiry] = useState('');
    const [documentType, setDocumentType] = useState('PASSPORT');
    const [dateOfBirth, setDateOfBirth] = useState('');
    const [nationality, setNationality] = useState('');

    const [passportPhotoUrl, setPassportPhotoUrl] = useState<string | null>(null);
    const [documentStoragePath, setDocumentStoragePath] = useState<string | null>(null);
    const [isUploading, setIsUploading] = useState(false);
    const [isCameraActive, setIsCameraActive] = useState(false);
    const [isExtracting, setIsExtracting] = useState(false);
    const videoRef = useRef<HTMLVideoElement>(null);
    // Phase 988 — OCR audit linkage
    const [ocrIdentityResultId, setOcrIdentityResultId] = useState<string | null>(null);
    const [ocrMeterResultId, setOcrMeterResultId] = useState<string | null>(null);

    // Phase 971 — new wizard state
    const [chargeConfig, setChargeConfig] = useState<ChargeConfig>({ deposit_enabled: false, deposit_amount: null, deposit_currency: 'THB', electricity_enabled: false, electricity_rate_kwh: null });
    const [refPhotos, setRefPhotos] = useState<RefPhoto[]>([]);
    const [capturedPhotos, setCapturedPhotos] = useState<CapturedPhoto[]>([]);
    const [meterReading, setMeterReading] = useState('');
    const [meterPhotoUrl, setMeterPhotoUrl] = useState<string | null>(null);
    const [meterStoragePath, setMeterStoragePath] = useState<string | null>(null);
    const [guestPhone, setGuestPhone] = useState('');
    const [guestEmail, setGuestEmail] = useState('');

    const startCamera = async () => {
        setIsCameraActive(true);
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' }
            });
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
            }
        } catch (err) {
            console.error('Camera access denied', err);
            showNotice('Camera denied. Using fallback.');
            setIsCameraActive(false);
        }
    };

    const stopCamera = () => {
        if (videoRef.current && videoRef.current.srcObject) {
            const stream = videoRef.current.srcObject as MediaStream;
            stream.getTracks().forEach(track => track.stop());
            videoRef.current.srcObject = null;
        }
        setIsCameraActive(false);
    };

    const captureFrame = async (purpose: 'passport' | 'meter' | 'walkthrough' = 'passport', roomLabel?: string) => {
        if (!videoRef.current) return;
        const video = videoRef.current;
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        if (ctx) ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
        stopCamera();

        if (purpose === 'passport') {
            setPassportPhotoUrl(dataUrl);
        } else if (purpose === 'meter') {
            setMeterPhotoUrl(dataUrl);
        }

        // Upload to storage
        setIsUploading(true);
        try {
            const bookingId = selected ? getBookingId(selected) : undefined;
            const res = await apiFetch<any>('/worker/documents/upload', {
                method: 'POST',
                body: JSON.stringify({
                    image_base64: dataUrl,
                    side: purpose === 'passport' ? 'front' : purpose === 'meter' ? 'meter_reading' : `checkin_${roomLabel}`,
                    booking_id: bookingId,
                }),
            });
            if (res.storage_path) {
                if (purpose === 'passport') {
                    setDocumentStoragePath(res.storage_path);
                } else if (purpose === 'meter') {
                    setMeterStoragePath(res.storage_path);
                } else if (purpose === 'walkthrough' && roomLabel) {
                    setCapturedPhotos(prev => [...prev.filter(p => p.room_label !== roomLabel), {
                        room_label: roomLabel, storage_path: res.storage_path, captured_at: new Date().toISOString(), preview_url: dataUrl,
                    }]);
                }
                showNotice('✅ Photo captured & stored');
            } else {
                showNotice('⚠️ Upload completed but no path returned');
            }
        } catch (err) {
            console.warn('Upload failed', err);
            showNotice('⚠️ Upload failed — please retry');
        } finally {
            setIsUploading(false);
        }
    };
    const [guestPortalUrl, setGuestPortalUrl] = useState<string | null>(null);
    const [qrImageUrl, setQrImageUrl] = useState<string | null>(null);

    const showNotice = (msg: string) => { setNotice(msg); setTimeout(() => setNotice(null), 3000); };

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const today = new Date().toISOString().slice(0, 10);
            const nextWeek = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10);

            const [bRes, tRes] = await Promise.all([
                apiFetch<any>(`/bookings?check_in_from=${today}&check_in_to=${nextWeek}&limit=100`).catch(() => ({})),
                apiFetch<any>(`/worker/tasks?worker_role=CHECKIN&limit=100`).catch(() => ({}))
            ]);

            const bList = bRes.bookings || bRes.data?.bookings || bRes.data || [];
            const rawBookings: Booking[] = Array.isArray(bList) ? bList : [];
            
            const tList = tRes.tasks || tRes.data?.tasks || tRes.data || [];
            const checkinTasks: any[] = Array.isArray(tList) ? tList : [];

            const bookingMap = new Map<string, any>();
            rawBookings.forEach(b => {
                const id = b.booking_id || b.id;
                if (id) bookingMap.set(id, b);
            });

            checkinTasks.forEach(t => {
                if (t.status === 'COMPLETED' || t.status === 'CANCELED') return;
                const bId = t.booking_id || t.task_id;
                if (!bookingMap.has(bId)) {
                    bookingMap.set(bId, {
                        booking_id: bId,
                        booking_ref: t.task_id,
                        property_id: t.property_id,
                        guest_name: undefined,
                        check_in: t.due_date || today,
                        check_out: undefined,
                        status: t.status || 'Upcoming',
                        deposit_required: false,
                        operator_note: t.description || undefined,
                        _needs_booking_enrichment: true,
                        task_id: t.task_id,
                        _task_status: t.status,
                    });
                } else {
                    const existing = bookingMap.get(bId);
                    if (existing) {
                        existing.status = existing.status || t.status || 'Upcoming';
                        existing.task_id = t.task_id;
                        existing._task_status = t.status;
                    }
                }
            });

            // ── Phase 979e self-healing: auto-complete orphaned CHECKIN tasks ──
            // If a booking is already checked_in but the task is still active,
            // the previous (buggy) check-in flow left the task orphaned.
            // Fire forceCompleteTask in background to heal the DB state.
            const healPromises: Promise<void>[] = [];
            bookingMap.forEach((b) => {
                const bStatus = (b.status || '').toLowerCase();
                const tStatus = (b._task_status || '').toUpperCase();
                const taskId = b.task_id;
                if (
                    taskId &&
                    bStatus === 'checked_in' &&
                    tStatus !== 'COMPLETED' && tStatus !== 'CANCELED'
                ) {
                    console.log(`[checkin-heal] booking ${b.booking_id} is checked_in but task ${taskId} is ${tStatus} — auto-completing`);
                    healPromises.push(forceCompleteTask(taskId));
                }
            });
            if (healPromises.length > 0) {
                // Fire and forget — don't block the UI load
                Promise.all(healPromises).catch(() => {});
            }

            const enrichPromises: Promise<void>[] = [];
            bookingMap.forEach((b, bId) => {
                if (!b._needs_booking_enrichment) return;
                enrichPromises.push(
                    apiFetch<any>(`/worker/bookings/${bId}`)
                        .then(res => {
                            const bk = res?.data || res;
                            if (bk && bk.booking_id) {
                                b.check_out = bk.check_out ?? b.check_out;
                                b.guest_name = bk.guest_name ?? b.guest_name;
                                b.guest_count = bk.guest_count ?? b.guest_count;
                                b.check_in = bk.check_in ?? b.check_in;
                                b.source = bk.source ?? b.source;
                                b.reservation_ref = bk.reservation_ref ?? b.reservation_ref;
                                b.guest_id = bk.guest_id ?? b.guest_id;
                            }
                        })
                        .catch(() => {})
                );
            });
            await Promise.all(enrichPromises);

            const merged = Array.from(bookingMap.values());

            const enriched = await Promise.all(
                merged.map(async (b) => {
                    let nights = b.nights;
                    if (!nights && b.check_in && b.check_out && b.check_out !== b.check_in) {
                        const d1 = new Date(b.check_in).getTime();
                        const d2 = new Date(b.check_out).getTime();
                        const n = Math.round((d2 - d1) / 86400000);
                        nights = n > 0 ? n : undefined;
                    }
                    try {
                        const propRes = await apiFetch<any>(`/properties/${b.property_id}`);
                        const prop = propRes.data || propRes;
                        return {
                            ...b,
                            nights,
                            property_name: prop.display_name || null,
                            deposit_required: prop.deposit_required ?? false,
                            deposit_amount: prop.deposit_amount ?? null,
                            deposit_currency: prop.deposit_currency || 'THB',
                            property_status: prop.status || 'Ready',
                            property_latitude: prop.latitude ?? null,
                            property_longitude: prop.longitude ?? null,
                            property_address: prop.address ?? null,
                        };
                    } catch {
                        return { ...b, nights, deposit_required: false };
                    }
                })
            );

            setBookings(enriched);
        } catch {
            setBookings([]);
        }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    // Phase 971: startCheckin now fetches charge-config + reference photos
    const startCheckin = async (b: Booking) => {
        setSelected(b);
        setStep('arrival');
        // Reset wizard state
        setPassportNumber(''); setPassportName(b.guest_name || ''); setPassportExpiry('');
        setPassportPhotoUrl(null); setDocumentStoragePath(null);
        setDepositMethod('cash'); setDepositNote('');
        setCapturedPhotos([]); setMeterReading(''); setMeterPhotoUrl(null); setMeterStoragePath(null);
        setGuestPhone(''); setGuestEmail('');
        setGuestPortalUrl(null); setQrImageUrl(null);

        const bookingId = getBookingId(b);
        // Fetch charge config (deposit + electricity rules)
        try {
            const cc = await apiFetch<any>(`/worker/bookings/${bookingId}/charge-config`);
            setChargeConfig({
                deposit_enabled: cc.deposit_enabled ?? false,
                deposit_amount: cc.deposit_amount ?? null,
                deposit_currency: cc.deposit_currency ?? 'THB',
                electricity_enabled: cc.electricity_enabled ?? false,
                electricity_rate_kwh: cc.electricity_rate_kwh ?? null,
            });
        } catch { /* defaults are safe */ }
        // Fetch reference photos for walk-through matching
        try {
            const rp = await apiFetch<any>(`/properties/${b.property_id}/reference-photos`);
            const photos = rp.photos || rp.data?.photos || rp.data || rp || [];
            setRefPhotos(Array.isArray(photos) ? photos : []);
        } catch { setRefPhotos([]); }
    };

    const handleAcknowledgeTask = async (taskId: string) => {
        try {
            await apiFetch<any>(`/worker/tasks/${taskId}/acknowledge`, { method: 'PATCH' });
            setNotice('✓ Task acknowledged');
            setTimeout(() => setNotice(null), 3000);
            load();
        } catch {
            setNotice('⚠ Acknowledge failed');
            setTimeout(() => setNotice(null), 3000);
        }
    };

    // Phase 971: Dynamic flow based on charge config
    const getFlow = (): CheckInStep[] => {
        const steps: CheckInStep[] = ['list', 'arrival', 'walkthrough'];
        if (chargeConfig.electricity_enabled) steps.push('meter');
        steps.push('contact');
        if (chargeConfig.deposit_enabled) steps.push('deposit');
        steps.push('passport', 'complete');
        return steps;
    };

    // Step numbering helpers: 'list' is not a numbered step
    const getStepNumber = (s: CheckInStep): number => {
        const flow = getFlow();
        const visibleSteps = flow.filter(f => f !== 'list');
        const idx = visibleSteps.indexOf(s as typeof visibleSteps[number]);
        return idx >= 0 ? idx + 1 : 1;
    };
    const getStepTotal = (): number => getFlow().length - 1; // exclude 'list'

    const goBack = () => {
        const flow = getFlow();
        const idx = flow.indexOf(step);
        if (idx <= 1) { setStep('list'); setSelected(null); }
        else setStep(flow[idx - 1]);
    };

    const nextStep = () => {
        const flow = getFlow();
        const idx = flow.indexOf(step);
        if (idx < flow.length - 1) setStep(flow[idx + 1]);
    };

    // ── Phase 971: Persist deposit via checkin-settlement API ──
    const collectDeposit = async () => {
        if (!selected) { nextStep(); return; }
        if (!chargeConfig.deposit_enabled) { nextStep(); return; }
        const bookingId = getBookingId(selected);
        try {
            await apiFetch('/worker/bookings/' + bookingId + '/checkin-settlement', {
                method: 'POST',
                body: JSON.stringify({
                    deposit_collected: true,
                    deposit_amount: chargeConfig.deposit_amount || 0,
                    deposit_currency: chargeConfig.deposit_currency || 'THB',
                    deposit_method: depositMethod,
                    deposit_note: depositNote || undefined,
                }),
            });
            showNotice('💰 Deposit recorded');
        } catch {
            showNotice('⚠️ Deposit not saved — please retry');
        }
        nextStep();
    };


    // Called by OcrCaptureFlow.onComplete with confirmed/corrected fields.
    const savePassport = async (identityFields?: IdentityFields) => {
        if (!selected) return;
        const bookingId = getBookingId(selected);

        const name = (identityFields?.full_name ?? passportName).trim();
        if (!name) {
            showNotice('⚠️ Guest name is required');
            return;
        }

        // If called from OcrCaptureFlow, sync state for summary display
        if (identityFields) {
            setPassportName(identityFields.full_name);
            setPassportNumber(identityFields.document_number);
            setDocumentType(identityFields.document_type);
            setDateOfBirth(identityFields.date_of_birth);
            setPassportExpiry(identityFields.passport_expiry);
            setNationality(identityFields.nationality);
            if (identityFields.ocr_result_id) setOcrIdentityResultId(identityFields.ocr_result_id);
        }

        try {
            const res = await apiFetch<any>('/worker/checkin/save-guest-identity', {
                method: 'POST',
                body: JSON.stringify({
                    booking_id: bookingId,
                    full_name: name,
                    document_type: identityFields?.document_type ?? documentType,
                    document_number: (identityFields?.document_number ?? passportNumber).trim() || undefined,
                    nationality: (identityFields?.nationality ?? nationality).trim() || undefined,
                    date_of_birth: (identityFields?.date_of_birth ?? dateOfBirth) || undefined,
                    passport_expiry: (identityFields?.passport_expiry ?? passportExpiry) || undefined,
                    document_photo_url: documentStoragePath || undefined,
                    ocr_result_id: identityFields?.ocr_result_id ?? ocrIdentityResultId ?? undefined,
                }),
            });

            if (res.guest_id) {
                setSelected(prev => prev ? { ...prev, guest_id: res.guest_id, guest_name: res.full_name } : prev);
            }

            const actionLabel = res.action === 'matched' ? 'Returning guest matched' : 'Guest record created';
            showNotice(`✅ ${actionLabel} — identity saved`);
        } catch (err) {
            console.error('save-guest-identity failed', err);
            showNotice('⚠️ Could not save guest identity. Please try again.');
            return;
        }
        nextStep();
    };

    // ── Phase 971 + 988: Save meter reading (with OCR audit linkage) ──
    const saveMeterReading = async (meterFields?: MeterFields) => {
        if (!selected) { nextStep(); return; }
        const val = meterFields?.meter_value ?? meterReading;
        const reading = parseFloat(val);
        if (isNaN(reading) || reading <= 0) {
            showNotice('⚠️ Please enter a valid meter reading');
            return;
        }
        if (meterFields) {
            setMeterReading(meterFields.meter_value);
            if (meterFields.ocr_result_id) setOcrMeterResultId(meterFields.ocr_result_id);
        }
        const bookingId = getBookingId(selected);
        try {
            await apiFetch('/worker/bookings/' + bookingId + '/checkin-settlement', {
                method: 'POST',
                body: JSON.stringify({
                    meter_reading: reading,
                    meter_photo_url: meterStoragePath || undefined,
                    deposit_collected: false,
                    ocr_result_id: meterFields?.ocr_result_id ?? ocrMeterResultId ?? undefined,
                }),
            });
            showNotice('⚡ Meter reading saved');
        } catch {
            showNotice('⚠️ Meter reading not saved — please retry');
            return;
        }
        nextStep();
    };

    // ── Phase 971: Complete check-in + auto-generate guest QR ──
    const completeCheckin = async () => {
        if (!selected) return;
        const bookingId = getBookingId(selected);
        try {
            // Phase 977: Persist walkthrough photo references to DB before completing.
            // The bytes are already in Storage from /worker/documents/upload.
            // This creates the durable index in booking_checkin_photos.
            if (capturedPhotos.length > 0 || meterStoragePath) {
                const photoRefs: { room_label: string; storage_path: string; purpose: string; captured_at: string }[] = [];
                capturedPhotos.forEach(p => {
                    photoRefs.push({ room_label: p.room_label, storage_path: p.storage_path, purpose: 'walkthrough', captured_at: p.captured_at });
                });
                if (meterStoragePath) {
                    photoRefs.push({ room_label: 'meter_reading', storage_path: meterStoragePath, purpose: 'meter', captured_at: new Date().toISOString() });
                }
                if (documentStoragePath) {
                    photoRefs.push({ room_label: 'passport_front', storage_path: documentStoragePath, purpose: 'passport', captured_at: new Date().toISOString() });
                }
                try {
                    await apiFetch<any>(`/worker/bookings/${bookingId}/checkin-photos`, {
                        method: 'POST',
                        body: JSON.stringify({ photos: photoRefs }),
                    });
                } catch (photoErr) {
                    console.warn('Photo index save failed (non-blocking):', photoErr);
                }
            }

            const res = await apiFetch<any>(`/bookings/${bookingId}/checkin`, {
                method: 'POST',
            });
            const data = res?.data || res;
            const status = data?.status || 'checked_in';
            if (status === 'already_checked_in') {
                showNotice('ℹ️ Guest was already checked in');
            } else {
                showNotice('✅ Check-in completed — booking is now InStay');
            }

            // Phase 979e: Force task to COMPLETED via state-machine walk.
            // apiFetch throws ApiError on 4xx — we cannot inspect res.status.
            // Strategy: attempt each transition, treat INVALID_TRANSITION (422)
            // as "already past that state" and continue. Stop when COMPLETED.
            const taskId = (selected as any).task_id;
            if (taskId) {
                await forceCompleteTask(taskId);
            }

            // Extract guest portal URL from response
            const portalUrl = data?.guest_portal_url || null;
            setGuestPortalUrl(portalUrl);

            // Phase 971: Generate QR — try server first, fallback to client-side
            let qrGenerated = false;
            try {
                const qrRes = await fetch(`${BASE}/bookings/${bookingId}/qr-image`, {
                    headers: { Authorization: `Bearer ${getToken()}` },
                });
                if (qrRes.ok) {
                    const blob = await qrRes.blob();
                    setQrImageUrl(URL.createObjectURL(blob));
                    qrGenerated = true;
                }
            } catch { /* server QR failed, try client */ }

            // Client-side QR fallback
            if (!qrGenerated && portalUrl) {
                try {
                    const dataUrl = await QRCode.toDataURL(portalUrl, { width: 200, margin: 2, color: { dark: '#000000', light: '#ffffff' } });
                    setQrImageUrl(dataUrl);
                } catch { console.warn('Client-side QR generation failed'); }
            }

            setStep('success');
            return;
        } catch {
            showNotice('⚠️ Check-in API call failed — please verify manually');
        }
        setStep('list');
        setSelected(null);
        load();
    };


    const returnToList = () => {
        setStep('list');
        setSelected(null);
        load();  // always refresh on return — completed task must disappear
    };

    /**
     * forceCompleteTask: walks ack → start → complete unconditionally.
     * Each step catches INVALID_TRANSITION (task already past that state)
     * and continues. Uses raw fetch so we can inspect HTTP status without
     * relying on apiFetch throw shape.
     */
    async function forceCompleteTask(taskId: string): Promise<void> {
        const headers: Record<string, string> = { 'Content-Type': 'application/json' };
        const tok = getToken();
        if (tok) headers['Authorization'] = `Bearer ${tok}`;
        const previewRole = typeof window !== 'undefined' ? sessionStorage.getItem('ihouse_preview_role') : null;
        if (previewRole) headers['X-Preview-Role'] = previewRole;

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
        console.log(`[checkin] task ${taskId} ack → HTTP ${ackStatus}`);

        // Step 2: start (ACKNOWLEDGED → IN_PROGRESS). 422 = already past, fine.
        const startStatus = await patch(`/worker/tasks/${taskId}/start`);
        console.log(`[checkin] task ${taskId} start → HTTP ${startStatus}`);

        // Step 3: complete (IN_PROGRESS → COMPLETED). This must succeed.
        const doneStatus = await patch(`/worker/tasks/${taskId}/complete`, { notes: 'Check-in completed via wizard' });
        console.log(`[checkin] task ${taskId} complete → HTTP ${doneStatus}`);
        if (doneStatus < 200 || doneStatus >= 300) {
            console.warn(`[checkin] task ${taskId} complete returned ${doneStatus}`);
        }
    }

    const today = new Date();
    const todayStr = today.toISOString().slice(0, 10);
    const dateStr = today.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
    // Split arrivals into today vs upcoming
    const todayArrivals = bookings.filter(b =>
        b.status !== 'checked_in' && b.status !== 'Completed' && b.status !== 'completed'
        && b.check_in?.slice(0, 10) === todayStr
    );
    const upcomingArrivals = bookings.filter(b =>
        b.status !== 'checked_in' && b.status !== 'Completed' && b.status !== 'completed'
        && b.check_in?.slice(0, 10) !== todayStr
    );
    const checkedIn = bookings.filter(b => b.status === 'checked_in');
    const completedCount = checkedIn.length + bookings.filter(b => b.status === 'Completed' || b.status === 'InStay').length;
    // Next arrival ISO for the summary strip
    const allPending = [...todayArrivals, ...upcomingArrivals];
    const nextArrivalIso = allPending.length > 0 ? (allPending[0].check_in || null) : null;

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

            {/* ========== HOME SCREEN: Today's Arrivals ========== */}
            {step === 'list' && (
                <>
                    <WorkerHeader title="Arrivals" subtitle="Today + next 7 days" />

                    {/* Summary strip */}
                    <CheckinSummaryStrip
                        todayCount={todayArrivals.length}
                        upcomingCount={upcomingArrivals.length}
                        completedCount={completedCount}
                        nextArrivalIso={nextArrivalIso}
                    />

                    {/* Loading */}
                    {loading && <div style={{ ...card, textAlign: 'center', color: 'var(--color-text-dim)' }}>Loading…</div>}

                    {/* Empty state — shows next arrival date if any upcoming */}
                    {!loading && todayArrivals.length === 0 && upcomingArrivals.length === 0 && (
                        <div style={{ ...card, textAlign: 'center' }}>
                            <div style={{ fontSize: 'var(--text-2xl)', marginBottom: 'var(--space-2)' }}>🎉</div>
                            <div style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>No arrivals in the next 7 days</div>
                        </div>
                    )}

                    {/* Today's arrivals */}
                    {!loading && todayArrivals.length > 0 && (
                        <div style={{ marginBottom: 'var(--space-4)' }}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-2)' }}>Today</div>
                            <BookingCardList bookings={todayArrivals} onStart={startCheckin} onAcknowledge={handleAcknowledgeTask} showNotice={showNotice} />
                        </div>
                    )}

                    {/* Upcoming arrivals */}
                    {!loading && upcomingArrivals.length > 0 && (
                        <div style={{ marginBottom: 'var(--space-4)' }}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-2)' }}>Upcoming</div>
                            <BookingCardList bookings={upcomingArrivals} onStart={startCheckin} onAcknowledge={handleAcknowledgeTask} showNotice={showNotice} />
                        </div>
                    )}

                    {/* ── Checked-in bookings ── */}
                    {checkedIn.length > 0 && (
                        <div style={{ marginTop: 'var(--space-5)' }}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                                ✅ Completed Today
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                                {checkedIn.map(b => (
                                    <div key={getBookingId(b)} style={{
                                        ...card, opacity: 0.7, borderColor: 'rgba(63,185,80,0.2)',
                                    }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                            <div>
                                                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>
                                                    {b.guest_name || 'Guest'}
                                                </div>
                                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                                                    {b.property_id}
                                                </div>
                                            </div>
                                            <span style={{
                                                padding: '2px 10px', borderRadius: 12, fontSize: 'var(--text-xs)', fontWeight: 600,
                                                background: 'rgba(63,185,80,0.15)', color: 'var(--color-ok)',
                                            }}>✅ Checked In</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </>
            )}

            {/* ========== STEP 1: Arrival Confirmation (enriched) ========== */}
            {step === 'arrival' && selected && (
                <div style={card}>
                    <StepHeader step={getStepNumber('arrival')} total={getStepTotal()} title="Arrival Confirmation" onBack={goBack} />

                    {/* Property readiness badge (merged from old status step) */}
                    <div style={{
                        padding: '8px 12px', borderRadius: 'var(--radius-sm)',
                        background: selected.property_status === 'Ready' || !selected.property_status
                            ? 'rgba(63,185,80,0.08)'
                            : 'rgba(210,153,34,0.08)',
                        border: `1px solid ${selected.property_status === 'Ready' || !selected.property_status
                            ? 'rgba(63,185,80,0.2)'
                            : 'rgba(210,153,34,0.2)'}`,
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        marginBottom: 'var(--space-4)',
                    }}>
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>Property Status</span>
                        <span style={{
                            fontSize: 'var(--text-xs)', fontWeight: 700,
                            color: selected.property_status === 'Ready' || !selected.property_status ? 'var(--color-ok)' : 'var(--color-warn)',
                        }}>
                            {selected.property_status || 'Ready'}
                        </span>
                    </div>

                    <InfoRow label="Guest" value={
                        selected.guest_name && !/^ICAL-/i.test(selected.guest_name) && !/^[0-9a-f]{8}-/i.test(selected.guest_name)
                            ? selected.guest_name
                            : undefined
                    } />
                    <InfoRow label="Guests" value={selected.guest_count ? `${selected.guest_count} guests` : undefined} />
                    <InfoRow label="Property" value={(selected as any).property_name || selected.property_id} />
                    <InfoRow label="Check-in" value={selected.check_in ? new Date(selected.check_in + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }) : undefined} />
                    <InfoRow label="Check-out" value={selected.check_out ? new Date(selected.check_out + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }) : undefined} />
                    <InfoRow label="Nights" value={selected.nights} />
                    {selected.source && <InfoRow label="Source" value={selected.source} />}
                    {selected.reservation_ref && <InfoRow label="Reservation" value={truncate(selected.reservation_ref, 20)} />}
                    {selected.operator_note && (
                        <div style={{
                            marginTop: 'var(--space-3)', padding: '8px 12px',
                            background: 'rgba(210,153,34,0.08)', border: '1px solid rgba(210,153,34,0.2)',
                            borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', color: 'var(--color-warn)',
                        }}>
                            📝 {cleanNote(selected.operator_note)}
                        </div>
                    )}
                    {/* Settlement policy banner (Phase 971) */}
                    <div style={{
                        marginTop: 'var(--space-3)', padding: '10px 12px',
                        background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-sm)', display: 'flex', flexDirection: 'column', gap: 4,
                    }}>
                        <div style={{ fontSize: '10px', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Settlement Policy</div>
                        <div style={{ display: 'flex', gap: 'var(--space-3)', fontSize: 'var(--text-xs)' }}>
                            <span style={{ color: chargeConfig.deposit_enabled ? 'var(--color-warn)' : 'var(--color-text-faint)' }}>
                                {chargeConfig.deposit_enabled ? `💰 Deposit: ${chargeConfig.deposit_currency} ${chargeConfig.deposit_amount ?? '—'}` : '💰 No deposit'}
                            </span>
                            <span style={{ color: chargeConfig.electricity_enabled ? 'var(--color-sage)' : 'var(--color-text-faint)' }}>
                                {chargeConfig.electricity_enabled ? `⚡ Electricity: ${chargeConfig.electricity_rate_kwh ?? '—'} /kWh` : '⚡ Not billed'}
                            </span>
                        </div>
                    </div>
                    <div style={{ marginTop: 'var(--space-5)', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                        <ActionButton label="Guest Arrived ✓" onClick={nextStep} />
                        <ActionButton label="📍 Navigate to Property" onClick={() => {
                            if (selected.property_latitude && selected.property_longitude) {
                                const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
                                const url = isMobile
                                    ? `https://waze.com/ul?ll=${selected.property_latitude},${selected.property_longitude}&navigate=yes`
                                    : `https://maps.google.com/maps?daddr=${selected.property_latitude},${selected.property_longitude}`;
                                window.open(url, '_blank');
                            } else if (selected.property_address) {
                                window.open(`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(selected.property_address)}`, '_blank');
                            } else {
                                showNotice('📍 No location data for this property');
                            }
                        }} variant="outline" />
                    </div>
                </div>
            )}

            {/* ========== STEP 2: Property Walk-Through Photos (Phase 971) ========== */}
            {step === 'walkthrough' && selected && (
                <div style={card}>
                    <StepHeader step={getStepNumber('walkthrough')} total={getStepTotal()} title="Walk-Through Photos" onBack={goBack} />
                    <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-4)' }}>
                        Capture check-in photos matching reference photos for each area.
                    </div>
                    {refPhotos.length === 0 ? (
                        <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--color-text-faint)', fontSize: 'var(--text-sm)' }}>
                            No reference photos configured for this property.
                            <div style={{ marginTop: 'var(--space-2)', fontSize: 'var(--text-xs)' }}>You may skip this step.</div>
                        </div>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                {capturedPhotos.length} of {refPhotos.length} captured
                            </div>
                            {refPhotos.map(rp => {
                                const captured = capturedPhotos.find(c => c.room_label === rp.room_label);
                                return (
                                    <div key={rp.id || rp.room_label} style={{
                                        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-2)',
                                        padding: 'var(--space-3)', background: captured ? 'rgba(63,185,80,0.06)' : 'var(--color-surface-2)',
                                        border: `1px solid ${captured ? 'rgba(63,185,80,0.3)' : 'var(--color-border)'}`,
                                        borderRadius: 'var(--radius-md)',
                                    }}>
                                        {/* Reference photo */}
                                        <div>
                                            <div style={{ fontSize: '10px', color: 'var(--color-text-faint)', textTransform: 'uppercase', marginBottom: 4 }}>Reference</div>
                                            <img src={rp.photo_url} alt={rp.room_label} style={{ width: '100%', height: 80, objectFit: 'cover', borderRadius: 'var(--radius-sm)' }} />
                                        </div>
                                        {/* Captured photo or capture button */}
                                        <div>
                                            <div style={{ fontSize: '10px', color: 'var(--color-text-faint)', textTransform: 'uppercase', marginBottom: 4 }}>
                                                {captured ? '✅ Captured' : '📸 Tap to capture'}
                                            </div>
                                            {captured?.preview_url ? (
                                                <div style={{ position: 'relative' }}>
                                                    <img src={captured.preview_url} alt="Captured" style={{ width: '100%', height: 80, objectFit: 'cover', borderRadius: 'var(--radius-sm)' }} />
                                                    <button onClick={() => setCapturedPhotos(prev => prev.filter(p => p.room_label !== rp.room_label))} style={{
                                                        position: 'absolute', top: 2, right: 2, background: 'rgba(0,0,0,0.6)', color: '#fff',
                                                        border: 'none', borderRadius: 12, padding: '2px 8px', fontSize: '9px', cursor: 'pointer',
                                                    }}>Retake</button>
                                                </div>
                                            ) : (
                                                <label style={{
                                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                    width: '100%', height: 80, background: 'var(--color-surface)',
                                                    border: '2px dashed var(--color-border)', borderRadius: 'var(--radius-sm)',
                                                    cursor: 'pointer', fontSize: 'var(--text-2xl)',
                                                }}>
                                                    📷
                                                    <input type="file" accept="image/*" capture="environment" style={{ display: 'none' }}
                                                        onChange={async (e) => {
                                                            if (!e.target.files?.[0]) return;
                                                            const file = e.target.files[0];
                                                            const reader = new FileReader();
                                                            reader.onload = async () => {
                                                                const dataUrl = reader.result as string;
                                                                setIsUploading(true);
                                                                try {
                                                                    const bookingId = selected ? getBookingId(selected) : undefined;
                                                                    const res = await apiFetch<any>('/worker/documents/upload', {
                                                                        method: 'POST',
                                                                        body: JSON.stringify({ image_base64: dataUrl, side: `checkin_${rp.room_label}`, booking_id: bookingId }),
                                                                    });
                                                                    if (res.storage_path) {
                                                                        setCapturedPhotos(prev => [...prev.filter(p => p.room_label !== rp.room_label), {
                                                                            room_label: rp.room_label, storage_path: res.storage_path, captured_at: new Date().toISOString(), preview_url: dataUrl,
                                                                        }]);
                                                                        showNotice('✅ Photo captured');
                                                                    }
                                                                } catch { showNotice('⚠️ Upload failed'); }
                                                                finally { setIsUploading(false); }
                                                            };
                                                            reader.readAsDataURL(file);
                                                        }}
                                                    />
                                                </label>
                                            )}
                                        </div>
                                        <div style={{ gridColumn: '1 / -1', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text)' }}>
                                            {rp.room_label}{rp.caption ? ` — ${rp.caption}` : ''}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                    {isUploading && (
                        <div style={{ padding: 'var(--space-3)', textAlign: 'center', color: 'var(--color-warn)', fontSize: 'var(--text-xs)' }}>
                            <div className="spinner" style={{ margin: '0 auto var(--space-2)' }} /> Uploading…
                        </div>
                    )}
                    <div style={{ marginTop: 'var(--space-4)' }}>
                        <ActionButton
                            label={refPhotos.length === 0 || capturedPhotos.length >= refPhotos.length ? 'Continue →' : `Continue (${capturedPhotos.length}/${refPhotos.length}) →`}
                            onClick={nextStep}
                        />
                        {refPhotos.length > 0 && capturedPhotos.length < refPhotos.length && (
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-warn)', textAlign: 'center', marginTop: 'var(--space-2)' }}>
                                ⚠️ Not all reference photos matched — you may still continue
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* ========== STEP 3: Electricity Meter Capture (Phase 971 + 988 OCR) ========== */}
            {step === 'meter' && selected && (
                <div style={card}>
                    <StepHeader step={getStepNumber('meter')} total={getStepTotal()} title="Electricity Meter" onBack={goBack} />
                    <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-4)' }}>
                        Capture the opening meter reading for electricity billing.
                    </div>
                    <OcrCaptureFlow
                        captureType="checkin_opening_meter_capture"
                        bookingId={getBookingId(selected)}
                        onComplete={(fields) => {
                            void saveMeterReading(fields as MeterFields);
                        }}
                        onSkip={() => nextStep()}
                    />
                    {chargeConfig.electricity_rate_kwh && (
                        <div style={{ marginTop: 'var(--space-3)', padding: 'var(--space-2) var(--space-3)', background: 'rgba(88,166,255,0.08)', border: '1px solid rgba(88,166,255,0.2)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', color: 'var(--color-sage)' }}>
                            ⚡ Rate: {chargeConfig.electricity_rate_kwh} {chargeConfig.deposit_currency}/kWh
                        </div>
                    )}
                </div>
            )}

            {/* ========== STEP 4: Guest Contact Info (Phase 971) ========== */}
            {step === 'contact' && selected && (
                <div style={card}>
                    <StepHeader step={getStepNumber('contact')} total={getStepTotal()} title="Guest Contact" onBack={goBack} />
                    <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-4)' }}>
                        Capture guest phone and email so we can send the portal link after check-in.
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        <div>
                            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Phone Number *</label>
                            <input type="tel" value={guestPhone} onChange={e => setGuestPhone(e.target.value)} placeholder="+66 812 345 678" style={inputStyle} />
                        </div>
                        <div>
                            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Email (optional)</label>
                            <input type="email" value={guestEmail} onChange={e => setGuestEmail(e.target.value)} placeholder="guest@example.com" style={inputStyle} />
                        </div>
                    </div>
                    <div style={{ marginTop: 'var(--space-4)' }}>
                        <ActionButton label="Continue →" onClick={() => {
                            if (!guestPhone.trim()) { showNotice('⚠️ Phone number is recommended'); }
                            nextStep();
                        }} />
                    </div>
                </div>
            )}

            {/* ========== STEP 6: Identity / Document Capture (Phase 988 OCR) ========== */}
            {step === 'passport' && selected && (
                <div style={card}>
                    <StepHeader step={getStepNumber('passport')} total={getStepTotal()} title="Identify Guest" onBack={goBack} />
                    <OcrCaptureFlow
                        captureType="identity_document_capture"
                        bookingId={getBookingId(selected)}
                        initialDocType={(documentType as any) || 'PASSPORT'}
                        onComplete={(fields) => {
                            void savePassport(fields as IdentityFields);
                        }}
                        onSkip={() => nextStep()}
                    />
                </div>
            )}

            {/* ========== STEP 5: Deposit Handling (Phase 971 — from chargeConfig) ========== */}

            {step === 'deposit' && selected && (
                <div style={card}>
                    <StepHeader step={getStepNumber('deposit')} total={getStepTotal()} title="Deposit Collection" onBack={goBack} />
                    <div style={{
                        padding: 'var(--space-4)', background: 'rgba(210,153,34,0.1)',
                        border: '1px solid rgba(210,153,34,0.3)', borderRadius: 'var(--radius-md)',
                        marginBottom: 'var(--space-4)',
                    }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Deposit Required</div>
                        <div style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--color-warn)', marginTop: 4 }}>
                            {chargeConfig.deposit_currency} {chargeConfig.deposit_amount ?? '—'}
                        </div>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', marginBottom: 'var(--space-3)' }}>
                        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>Payment Method</label>
                        {['cash', 'transfer', 'card_hold'].map(m => (
                            <label key={m} style={{
                                display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px',
                                background: depositMethod === m ? 'rgba(63,185,80,0.08)' : 'var(--color-surface-2)',
                                border: `1px solid ${depositMethod === m ? 'rgba(63,185,80,0.3)' : 'var(--color-border)'}`,
                                borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 'var(--text-sm)',
                            }}>
                                <input type="radio" name="deposit" checked={depositMethod === m}
                                    onChange={() => setDepositMethod(m)} />
                                {m === 'cash' ? '💵 Cash received' : m === 'transfer' ? '🏦 Transfer received' : '💳 Card hold'}
                            </label>
                        ))}
                    </div>
                    <div style={{ marginBottom: 'var(--space-3)' }}>
                        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Note (optional)</label>
                        <input value={depositNote} onChange={e => setDepositNote(e.target.value)} placeholder="Any notes..." style={inputStyle} />
                    </div>
                    <ActionButton label="Confirm & Record Deposit →" onClick={collectDeposit} />
                </div>
            )}

            {/* ========== STEP 7: Complete Check-in (Phase 971 — full summary review) ========== */}
            {step === 'complete' && selected && (
                <div style={card}>
                    <StepHeader step={getStepNumber('complete')} total={getStepTotal()} title="Complete Check-in" onBack={goBack} />
                    <div style={{
                        padding: 'var(--space-6)', textAlign: 'center',
                        background: 'rgba(63,185,80,0.05)', borderRadius: 'var(--radius-md)',
                        border: '1px solid rgba(63,185,80,0.2)', marginBottom: 'var(--space-4)',
                    }}>
                        <div style={{ fontSize: 'var(--text-3xl)', marginBottom: 'var(--space-2)' }}>🏠</div>
                        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)' }}>
                            Ready to complete
                        </div>
                        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-2)' }}>
                            This will mark the booking as <strong>InStay</strong> and the property as <strong>Occupied</strong>.
                        </div>
                    </div>
                    {/* Summary review */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
                        <InfoRow label="Guest" value={selected.guest_name} />
                        <InfoRow label="Property" value={(selected as any).property_name || selected.property_id} />
                        <InfoRow label="Walk-through" value={refPhotos.length > 0 ? `${capturedPhotos.length}/${refPhotos.length} photos` : 'No ref photos'} />
                        {chargeConfig.electricity_enabled && (
                            <InfoRow label="Meter Reading" value={meterReading ? `${meterReading} kWh` : '(not captured)'} />
                        )}
                        <InfoRow label="Contact" value={guestPhone || '(not provided)'} />
                        {chargeConfig.deposit_enabled && (
                            <InfoRow label="Deposit" value={`${chargeConfig.deposit_currency} ${chargeConfig.deposit_amount} — ${depositMethod === 'cash' ? 'Cash' : depositMethod === 'transfer' ? 'Transfer' : 'Card hold'}`} />
                        )}
                        <InfoRow label="Passport" value={passportNumber || '(not captured)'} />
                    </div>
                    <div style={{ marginTop: 'var(--space-5)' }}>
                        <ActionButton label="✅ Complete Check-in" onClick={completeCheckin} />
                    </div>
                </div>
            )}

            {/* ========== SUCCESS SCREEN: QR Handoff (Phase 971) ========== */}
            {step === 'success' && selected && (
                <div style={card}>
                    <div style={{
                        padding: 'var(--space-6)', textAlign: 'center',
                        background: 'rgba(63,185,80,0.05)', borderRadius: 'var(--radius-md)',
                        border: '1px solid rgba(63,185,80,0.2)', marginBottom: 'var(--space-4)',
                    }}>
                        <div style={{ fontSize: 'var(--text-3xl)', marginBottom: 'var(--space-2)' }}>✅</div>
                        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-ok)' }}>
                            Check-in Complete
                        </div>
                        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-2)' }}>
                            {selected.guest_name || 'Guest'} is now checked in at <strong>{(selected as any).property_name || selected.property_id}</strong>
                        </div>
                    </div>

                    {/* QR Code */}
                    <div style={{
                        textAlign: 'center', padding: 'var(--space-5)',
                        background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--color-border)', marginBottom: 'var(--space-4)',
                    }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                            Guest Portal QR
                        </div>
                        {qrImageUrl ? (
                            <img src={qrImageUrl} alt="Guest Portal QR Code" style={{
                                width: 200, height: 200, margin: '0 auto', display: 'block',
                                borderRadius: 8, background: 'white', padding: 8,
                            }} />
                        ) : (
                            <div style={{ padding: 'var(--space-4)', color: 'var(--color-text-faint)', fontSize: 'var(--text-sm)' }}>
                                ⏳ QR code generating...
                            </div>
                        )}
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 'var(--space-3)' }}>
                            Show this QR to the guest
                        </div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 4 }}>
                            Guest scans → opens stay portal with property info, WiFi, rules
                        </div>
                    </div>

                    {/* Send link actions (Phase 971 — uses real contact from Step 4) */}
                    {(guestPhone || guestEmail) && (
                        <div style={{ display: 'flex', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
                            {guestPhone && (
                                <button onClick={async () => {
                                    try {
                                        await apiFetch('/notifications/send-sms', {
                                            method: 'POST',
                                            body: JSON.stringify({
                                                to_number: guestPhone,
                                                body: `Welcome! Your guest portal: ${guestPortalUrl || 'link available at front desk'}`,
                                                notification_type: 'guest_portal_link',
                                                reference_id: getBookingId(selected),
                                            }),
                                        });
                                        showNotice('✅ Portal link sent via SMS');
                                    } catch { showNotice('⚠️ SMS send failed'); }
                                }} style={{
                                    flex: 1, padding: '10px', borderRadius: 'var(--radius-sm)',
                                    background: 'rgba(63,185,80,0.1)', border: '1px solid rgba(63,185,80,0.3)',
                                    color: 'var(--color-ok)', fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer',
                                }}>📱 Send via SMS</button>
                            )}
                            {guestEmail && (
                                <button onClick={async () => {
                                    try {
                                        await apiFetch('/notifications/send-email', {
                                            method: 'POST',
                                            body: JSON.stringify({
                                                to_email: guestEmail,
                                                subject: `Your stay at ${(selected as any).property_name || selected.property_id}`,
                                                body_html: `<p>Welcome! Access your guest portal here: <a href="${guestPortalUrl}">${guestPortalUrl}</a></p>`,
                                                notification_type: 'guest_portal_link',
                                                reference_id: getBookingId(selected),
                                            }),
                                        });
                                        showNotice('✅ Portal link sent via email');
                                    } catch { showNotice('⚠️ Email send failed'); }
                                }} style={{
                                    flex: 1, padding: '10px', borderRadius: 'var(--radius-sm)',
                                    background: 'rgba(88,166,255,0.1)', border: '1px solid rgba(88,166,255,0.3)',
                                    color: 'var(--color-sage)', fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer',
                                }}>📧 Send via Email</button>
                            )}
                        </div>
                    )}

                    <ActionButton label="Done — Return to Arrivals" onClick={() => {
                        if (qrImageUrl && qrImageUrl.startsWith('blob:')) URL.revokeObjectURL(qrImageUrl);
                        setQrImageUrl(null);
                        setGuestPortalUrl(null);
                        returnToList();
                    }} />
                </div>
            )}
        </div>
    );
}

/** Page-level default — workers access the check-in wizard at /ops/checkin */
export default function MobileCheckinPage() {
    return (
        <MobileStaffShell title="Check-in" bottomNavItems={CHECKIN_BOTTOM_NAV}>
            <CheckinWizard />
        </MobileStaffShell>
    );
}
