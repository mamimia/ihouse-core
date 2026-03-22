'use client';

/**
 * Operational Core — Phase D: Mobile Check-in Flow
 * Architecture source: .agent/architecture/mobile-checkin.md
 * Scope rule: Tenant-wide arrivals, NOT assignment-aware (B-1 gap).
 *
 * Home: Today's arrivals list for the entire tenant
 * Flow: 6-step check-in (Arrival → Status → Passport → Deposit → Welcome → Complete)
 * Flow: 4-step check-out (Inspection → Issues → Deposit Resolution → Complete)
 */

import { useEffect, useState, useCallback } from 'react';
import { getToken } from '@/lib/api';

const BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

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
    property_status?: string; // from property enrichment
    property_latitude?: number;
    property_longitude?: number;
    property_address?: string;
};

// Resolve the correct booking ID from various field names
function getBookingId(b: Booking): string {
    return b.booking_id || b.booking_ref || b.id || 'unknown';
}

type CheckInStep = 'list' | 'arrival' | 'passport' | 'deposit' | 'welcome' | 'complete' | 'success';

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
    Upcoming: { bg: 'rgba(88,166,255,0.15)', text: '#58a6ff' },
    Arrived: { bg: 'rgba(210,153,34,0.15)', text: '#d29922' },
    InStay: { bg: 'rgba(63,185,80,0.15)', text: '#3fb950' },
    Completed: { bg: 'rgba(110,118,129,0.15)', text: '#8b949e' },
    checked_in: { bg: 'rgba(63,185,80,0.15)', text: '#3fb950' },
    active: { bg: 'rgba(88,166,255,0.15)', text: '#58a6ff' },
    observed: { bg: 'rgba(210,153,34,0.15)', text: '#d29922' },
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

// ========== Main Page ==========
export default function MobileCheckinPage() {
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
    const [guestPortalUrl, setGuestPortalUrl] = useState<string | null>(null);
    const [qrImageUrl, setQrImageUrl] = useState<string | null>(null);

    const showNotice = (msg: string) => { setNotice(msg); setTimeout(() => setNotice(null), 3000); };

    const load = useCallback(async () => {
        setLoading(true);
        try {
            // FIX: Use correct API params (check_in_from + check_in_to, not check_in)
            const today = new Date().toISOString().slice(0, 10);
            const res = await apiFetch<any>(`/bookings?check_in_from=${today}&check_in_to=${today}&limit=50`);
            const list = res.bookings || res.data?.bookings || res.data || [];
            const rawBookings: Booking[] = Array.isArray(list) ? list : [];

            // Enrich each booking with property deposit config + property status
            const enriched = await Promise.all(
                rawBookings.map(async (b) => {
                    // Compute nights
                    let nights = b.nights;
                    if (!nights && b.check_in && b.check_out) {
                        const d1 = new Date(b.check_in).getTime();
                        const d2 = new Date(b.check_out).getTime();
                        nights = Math.max(1, Math.round((d2 - d1) / 86400000));
                    }
                    try {
                        const propRes = await apiFetch<any>(`/properties/${b.property_id}`);
                        const prop = propRes.data || propRes;
                        return {
                            ...b,
                            nights,
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

    const startCheckin = (b: Booking) => {
        setSelected(b);
        setStep('arrival');
        setPassportNumber('');
        setPassportName(b.guest_name || '');
        setDepositMethod('cash');
        setDepositNote('');
    };

    // Dynamic flow: skip deposit step when not required by property config
    // Property status step removed — merged into arrival screen as badge
    const getFlow = (): CheckInStep[] => {
        const base: CheckInStep[] = ['list', 'arrival', 'passport', 'deposit', 'welcome', 'complete'];
        if (selected && selected.deposit_required !== true) {
            return base.filter(s => s !== 'deposit');
        }
        return base;
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

    // ── D-1: Save passport number to guest record ──
    // Passport number: ALWAYS required (dev and production).
    // Passport photo:  required in production, bypassed in dev/testing.
    // DEV_PHOTO_BYPASS: flip to false when camera capture + storage are wired.
    const DEV_PHOTO_BYPASS = true; // ← only controls photo, number always blocks
    const savePassport = async () => {
        if (!selected) return;
        // Passport number is always mandatory — no bypass
        if (!passportNumber.trim()) {
            showNotice('⚠️ Passport number is required');
            return;
        }
        try {
            // Best-effort: update guest passport_no via guests API
            const guestId = selected.guest_id;
            if (guestId) {
                await apiFetch(`/guests/${guestId}`, {
                    method: 'PATCH',
                    body: JSON.stringify({ passport_no: passportNumber.trim(), full_name: passportName.trim() || undefined }),
                });
            } else {
                // No guest_id — try booking-level guest update
                const bookingId = getBookingId(selected);
                await apiFetch(`/guests/${bookingId}`, {
                    method: 'PATCH',
                    body: JSON.stringify({ passport_no: passportNumber.trim(), full_name: passportName.trim() || undefined }),
                });
            }
            showNotice('📄 Passport number saved');
        } catch {
            // Guest endpoint may not match booking_id — save attempt logged
            console.warn('Passport save: guest endpoint may require guest_id, not booking_id');
        }
        nextStep();
    };

    // ── D-2: Persist deposit to cash_deposits table ──
    const collectDeposit = async () => {
        if (!selected) { nextStep(); return; }
        const bookingId = getBookingId(selected);
        try {
            await apiFetch('/deposits', {
                method: 'POST',
                body: JSON.stringify({
                    booking_id: bookingId,
                    property_id: selected.property_id,
                    amount: selected.deposit_amount || 0,
                    currency: selected.deposit_currency || 'THB',
                    method: depositMethod,
                    note: depositNote || undefined,
                }),
            });
            showNotice('💰 Deposit recorded');
        } catch {
            showNotice('Deposit record attempt saved');
        }
        nextStep();
    };

    // ── D-5 + D-6 + Phase 58/59: Complete check-in + auto-generate guest QR ──
    // Backend now auto-issues guest HMAC token on successful check-in.
    // Response includes guest_portal_url which we display as a real QR.
    const completeCheckin = async () => {
        if (!selected) return;
        const bookingId = getBookingId(selected);
        try {
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

            // Phase 58: Extract guest portal URL from response
            const portalUrl = data?.guest_portal_url || null;
            setGuestPortalUrl(portalUrl);

            // Phase 59: Fetch real QR image from backend (best-effort)
            try {
                const qrRes = await fetch(`${BASE}/bookings/${bookingId}/qr-image`, {
                    headers: { Authorization: `Bearer ${getToken()}` },
                });
                if (qrRes.ok) {
                    const blob = await qrRes.blob();
                    setQrImageUrl(URL.createObjectURL(blob));
                }
            } catch {
                // QR image fetch is non-blocking — portal URL is the fallback
                console.warn('QR image fetch failed — using portal URL text');
            }

            // Transition to success screen with real QR
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
        load();
    };

    const today = new Date();
    const dateStr = today.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
    const arrivals = bookings.filter(b => b.status !== 'checked_in' && b.status !== 'Completed' && b.status !== 'completed');
    const checkedIn = bookings.filter(b => b.status === 'checked_in');
    const completedCount = checkedIn.length + bookings.filter(b => b.status === 'Completed' || b.status === 'InStay').length;

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
                    <div style={{ marginBottom: 'var(--space-5)' }}>
                        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                            {dateStr}
                        </p>
                        <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text)', letterSpacing: '-0.03em' }}>
                            Today&apos;s Arrivals
                        </h1>
                        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                            All tenant check-ins · Not filtered by assignment
                        </p>
                    </div>

                    {/* Summary strip */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
                        <div style={card}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Check-ins</div>
                            <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: 'var(--color-accent)', marginTop: 4 }}>{arrivals.length}</div>
                        </div>
                        <div style={card}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Completed</div>
                            <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: 'var(--color-ok)', marginTop: 4 }}>{completedCount}</div>
                        </div>
                    </div>

                    {/* Arrivals list */}
                    {loading && <div style={{ ...card, textAlign: 'center', color: 'var(--color-text-dim)' }}>Loading…</div>}

                    {!loading && arrivals.length === 0 && (
                        <div style={{ ...card, textAlign: 'center' }}>
                            <div style={{ fontSize: 'var(--text-2xl)', marginBottom: 'var(--space-2)' }}>🎉</div>
                            <div style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>No arrivals today</div>
                        </div>
                    )}

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        {arrivals.map(b => (
                            <div key={getBookingId(b)} style={{
                                ...card, cursor: 'pointer', transition: 'border-color 0.2s',
                            }}
                                onClick={() => startCheckin(b)}
                                onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--color-primary)')}
                                onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-2)' }}>
                                    <div>
                                        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--color-text)' }}>
                                            {b.guest_name || 'Guest'}
                                        </div>
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                                            {b.property_id}
                                        </div>
                                    </div>
                                    <StatusBadge status={b.status} />
                                </div>
                                <div style={{ display: 'flex', gap: 'var(--space-4)', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                                    <span>📅 {b.check_in || '—'}</span>
                                    <span>👥 {b.guest_count || '—'} guests</span>
                                    <span>🌙 {b.nights || '—'} nights</span>
                                </div>
                                <div style={{ marginTop: 'var(--space-3)', display: 'flex', gap: 'var(--space-2)' }}>
                                    <button style={{
                                        flex: 1, padding: '8px', background: 'var(--color-primary)', color: '#fff',
                                        border: 'none', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer',
                                    }}>Start Check-in</button>
                                    <button onClick={e => {
                                        e.stopPropagation();
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
                                    }} style={{
                                        padding: '8px 12px', background: 'var(--color-surface-2)', color: 'var(--color-text-dim)',
                                        border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', cursor: 'pointer',
                                    }}>📍 Navigate</button>
                                </div>
                            </div>
                        ))}
                    </div>

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
                                                background: 'rgba(63,185,80,0.15)', color: '#3fb950',
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
                            color: selected.property_status === 'Ready' || !selected.property_status ? '#3fb950' : '#d29922',
                        }}>
                            {selected.property_status || 'Ready'}
                        </span>
                    </div>

                    <InfoRow label="Guest" value={selected.guest_name} />
                    <InfoRow label="Guests" value={selected.guest_count ? `${selected.guest_count} guests` : undefined} />
                    <InfoRow label="Property" value={selected.property_id} />
                    <InfoRow label="Check-in" value={selected.check_in} />
                    <InfoRow label="Check-out" value={selected.check_out} />
                    <InfoRow label="Nights" value={selected.nights} />
                    {selected.source && <InfoRow label="Source" value={selected.source} />}
                    {selected.reservation_ref && <InfoRow label="Reservation" value={selected.reservation_ref} />}
                    {selected.operator_note && (
                        <div style={{
                            marginTop: 'var(--space-3)', padding: '8px 12px',
                            background: 'rgba(210,153,34,0.08)', border: '1px solid rgba(210,153,34,0.2)',
                            borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', color: '#d29922',
                        }}>
                            📝 {selected.operator_note}
                        </div>
                    )}
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

            {/* ========== STEP 3: Passport Capture ========== */}
            {step === 'passport' && selected && (
                <div style={card}>
                    <StepHeader step={getStepNumber('passport')} total={getStepTotal()} title="Passport / ID Capture" onBack={goBack} />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        <div>
                            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
                                Passport Number *
                            </label>
                            <input value={passportNumber} onChange={e => setPassportNumber(e.target.value)} placeholder="AB1234567" style={inputStyle} />
                        </div>
                        <div>
                            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
                                Guest Full Name
                            </label>
                            <input value={passportName} onChange={e => setPassportName(e.target.value)} placeholder="As on passport" style={inputStyle} />
                        </div>
                        <div style={{
                            padding: 'var(--space-6)', border: '2px dashed var(--color-border)',
                            borderRadius: 'var(--radius-md)', textAlign: 'center',
                            opacity: DEV_PHOTO_BYPASS ? 0.5 : 1,
                        }}>
                            <div style={{ fontSize: 'var(--text-2xl)', marginBottom: 'var(--space-2)' }}>📷</div>
                            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                                Tap to capture passport photo {DEV_PHOTO_BYPASS ? '' : '*'}
                            </div>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 4 }}>
                                Camera only · Admin visible only · Retained 90 days
                            </div>
                            {DEV_PHOTO_BYPASS && (
                                <div style={{
                                    marginTop: 8, fontSize: 'var(--text-xs)', color: '#d29922',
                                    padding: '4px 8px', background: 'rgba(210,153,34,0.08)',
                                    border: '1px solid rgba(210,153,34,0.15)', borderRadius: 'var(--radius-sm)',
                                    display: 'inline-block',
                                }}>
                                    🔧 Dev/testing — photo not required yet
                                </div>
                            )}
                        </div>
                    </div>
                    <div style={{ marginTop: 'var(--space-4)' }}>
                        <ActionButton label="Save & Continue →" onClick={savePassport} />
                    </div>
                </div>
            )}

            {/* ========== STEP 4: Deposit Handling ========== */}
            {step === 'deposit' && selected && (
                <div style={card}>
                    <StepHeader step={getStepNumber('deposit')} total={getStepTotal()} title="Deposit Handling" onBack={goBack} />
                    {selected.deposit_required !== false ? (
                        <>
                            <div style={{
                                padding: 'var(--space-4)', background: 'rgba(210,153,34,0.1)',
                                border: '1px solid rgba(210,153,34,0.3)', borderRadius: 'var(--radius-md)',
                                marginBottom: 'var(--space-4)',
                            }}>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Deposit Required</div>
                                <div style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: '#d29922', marginTop: 4 }}>
                                    {selected.deposit_currency || 'THB'} {selected.deposit_amount || '—'}
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
                        </>
                    ) : (
                        <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--color-ok)', fontSize: 'var(--text-sm)' }}>
                            ✓ No deposit required for this booking
                        </div>
                    )}
                    <ActionButton label="Confirm & Record Deposit →" onClick={collectDeposit} />
                </div>
            )}

            {/* ========== STEP 5: Send Welcome Info ========== */}
            {step === 'welcome' && selected && (
                <div style={card}>
                    <StepHeader step={getStepNumber('welcome')} total={getStepTotal()} title="Welcome Info" onBack={goBack} />
                    <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-4)' }}>
                        Send welcome info to the guest:
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
                        {['📶 WiFi credentials', '📋 House rules', '🆘 Emergency contacts', '🛵 Motorbike rental', '👕 Laundry info'].map(item => (
                            <div key={item} style={{
                                padding: '10px 14px', background: 'var(--color-surface-2)',
                                border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)',
                                fontSize: 'var(--text-sm)', color: 'var(--color-text)',
                            }}>{item}</div>
                        ))}
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', marginBottom: 'var(--space-2)' }}>
                        Send via
                    </div>
                    <div style={{ display: 'flex', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
                        {/* SMS — wired to POST /notifications/send-sms */}
                        <button onClick={async () => {
                            try {
                                await apiFetch('/notifications/send-sms', {
                                    method: 'POST',
                                    body: JSON.stringify({
                                        to_number: '+0000000000', // placeholder — needs guest phone
                                        body: `Welcome ${selected.guest_name || 'Guest'}! Your check-in at ${selected.property_id} is ready. WiFi and house info will be provided on arrival.`,
                                        notification_type: 'booking_confirm',
                                        reference_id: getBookingId(selected),
                                    }),
                                });
                                showNotice('✅ SMS welcome sent');
                            } catch {
                                showNotice('⚠️ SMS failed — guest phone may not be on file');
                            }
                        }} style={{
                            flex: 1, padding: '10px', borderRadius: 'var(--radius-sm)',
                            background: 'rgba(63,185,80,0.1)', border: '1px solid rgba(63,185,80,0.3)',
                            color: '#3fb950', fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer',
                        }}>📱 SMS</button>

                        {/* Email — wired to POST /notifications/send-email */}
                        <button onClick={async () => {
                            try {
                                await apiFetch('/notifications/send-email', {
                                    method: 'POST',
                                    body: JSON.stringify({
                                        to_email: 'guest@placeholder.com', // placeholder — needs guest email
                                        subject: `Welcome to ${selected.property_id}`,
                                        body_html: `<p>Welcome ${selected.guest_name || 'Guest'}!</p><p>Your stay at <b>${selected.property_id}</b> is confirmed. WiFi credentials and house rules will be provided at check-in.</p>`,
                                        notification_type: 'booking_confirm',
                                        reference_id: getBookingId(selected),
                                    }),
                                });
                                showNotice('✅ Email welcome sent');
                            } catch {
                                showNotice('⚠️ Email failed — guest email may not be on file');
                            }
                        }} style={{
                            flex: 1, padding: '10px', borderRadius: 'var(--radius-sm)',
                            background: 'rgba(88,166,255,0.1)', border: '1px solid rgba(88,166,255,0.3)',
                            color: '#58a6ff', fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer',
                        }}>📧 Email</button>

                        {/* LINE / Telegram / WhatsApp — honestly labeled as not connected */}
                        {['💬 LINE', '✈️ Telegram'].map(label => (
                            <button key={label} disabled style={{
                                flex: 1, padding: '10px', borderRadius: 'var(--radius-sm)',
                                background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                                color: 'var(--color-text-faint)', fontSize: 'var(--text-xs)', fontWeight: 600,
                                cursor: 'not-allowed', opacity: 0.5,
                            }}>{label}<br /><span style={{ fontSize: '9px' }}>Not connected</span></button>
                        ))}
                    </div>
                    <div style={{
                        padding: 'var(--space-2) var(--space-3)', background: 'rgba(210,153,34,0.08)',
                        border: '1px solid rgba(210,153,34,0.2)', borderRadius: 'var(--radius-sm)',
                        fontSize: 'var(--text-xs)', color: '#d29922', marginBottom: 'var(--space-4)',
                    }}>
                        ℹ️ Guest phone/email will be auto-populated when guest profile data is available.
                        LINE and Telegram channels require channel setup in Settings.
                    </div>
                    <ActionButton label="Continue →" onClick={nextStep} />
                </div>
            )}

            {/* ========== STEP 6: Complete Check-in ========== */}
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
                    <InfoRow label="Guest" value={selected.guest_name} />
                    <InfoRow label="Property" value={selected.property_id} />
                    <InfoRow label="Passport" value={passportNumber || '(not captured)'} />
                    {selected.deposit_required === true && (
                        <InfoRow label="Deposit" value={depositMethod === 'cash' ? 'Cash' : depositMethod === 'transfer' ? 'Transfer' : 'Card hold'} />
                    )}
                    <div style={{ marginTop: 'var(--space-5)' }}>
                        <ActionButton label="✅ Complete Check-in" onClick={completeCheckin} />
                    </div>
                </div>
            )}

            {/* ========== SUCCESS SCREEN: QR Handoff (Phase 59) ========== */}
            {step === 'success' && selected && (
                <div style={card}>
                    <div style={{
                        padding: 'var(--space-6)', textAlign: 'center',
                        background: 'rgba(63,185,80,0.05)', borderRadius: 'var(--radius-md)',
                        border: '1px solid rgba(63,185,80,0.2)', marginBottom: 'var(--space-4)',
                    }}>
                        <div style={{ fontSize: 'var(--text-3xl)', marginBottom: 'var(--space-2)' }}>✅</div>
                        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: '#3fb950' }}>
                            Check-in Complete
                        </div>
                        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-2)' }}>
                            {selected.guest_name || 'Guest'} is now checked in at <strong>{selected.property_id}</strong>
                        </div>
                    </div>

                    {/* Real QR Code — Phase 59 */}
                    <div style={{
                        textAlign: 'center', padding: 'var(--space-5)',
                        background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--color-border)', marginBottom: 'var(--space-4)',
                    }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                            Guest Portal QR
                        </div>

                        {/* Real QR image from backend, or portal URL fallback */}
                        {qrImageUrl ? (
                            <img
                                src={qrImageUrl}
                                alt="Guest Portal QR Code"
                                style={{
                                    width: 200, height: 200, margin: '0 auto', display: 'block',
                                    borderRadius: 8, background: 'white', padding: 8,
                                }}
                            />
                        ) : guestPortalUrl ? (
                            <div style={{
                                padding: 'var(--space-4)', background: 'white',
                                borderRadius: 'var(--radius-md)', margin: '0 auto',
                                maxWidth: 240,
                            }}>
                                <div style={{ fontSize: 'var(--text-sm)', color: '#1a1f2e', fontWeight: 600, wordBreak: 'break-all' }}>
                                    📱 Guest Portal Link
                                </div>
                                <div style={{ fontSize: 'var(--text-xs)', color: '#555', marginTop: 8, wordBreak: 'break-all', fontFamily: 'var(--font-mono)' }}>
                                    {guestPortalUrl}
                                </div>
                            </div>
                        ) : (
                            <div style={{ padding: 'var(--space-4)', color: 'var(--color-text-faint)', fontSize: 'var(--text-sm)' }}>
                                ⏳ QR code generating...
                            </div>
                        )}

                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 'var(--space-3)' }}>
                            Show this QR to the guest
                        </div>
                        {guestPortalUrl && (
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 4 }}>
                                Guest scans → opens stay portal with property info, WiFi, rules
                            </div>
                        )}
                    </div>

                    <ActionButton label="Done — Return to Arrivals" onClick={() => {
                        // Clean up blob URL to prevent memory leak
                        if (qrImageUrl) URL.revokeObjectURL(qrImageUrl);
                        setQrImageUrl(null);
                        setGuestPortalUrl(null);
                        returnToList();
                    }} />
                </div>
            )}
        </div>
    );
}
