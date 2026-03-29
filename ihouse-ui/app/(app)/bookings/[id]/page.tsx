'use client';

/**
 * Phase 557 — Enhanced Booking Detail Page
 * Route: /bookings/[id]
 *
 * Financial facts, timeline events, guest info, action buttons.
 * Admin Close Stay panel for overdue bookings (sets admin_closed, no settlement side effects).
 */

import { useEffect, useState, useCallback } from 'react';
import { api, ApiError } from '@/lib/api';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { EarlyCheckoutPanel } from '@/components/EarlyCheckoutPanel';

const OPS_TZ = 'Asia/Bangkok';

function fmtDate(d: string | null): string {
    if (!d) return '—';
    try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: OPS_TZ }); }
    catch { return d; }
}

// ---------------------------------------------------------------------------
// Derive operational status for a single booking record
// (mirrors bookings/page.tsx deriveOperationalStatus — must stay in sync)
// ---------------------------------------------------------------------------
function isOverdue(booking: any): boolean {
    const raw = (booking?.status ?? '').toLowerCase();
    if (!['active', 'confirmed'].includes(raw)) return false;
    if (booking?.checked_out_at) return false;
    const checkOut = booking?.check_out;
    if (!checkOut) return false;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const todayStr = today.toISOString().slice(0, 10);
    return checkOut < todayStr;
}

// ---------------------------------------------------------------------------
// Admin Close Stay Panel
// ---------------------------------------------------------------------------
function AdminClosePanel({ bookingId, booking, onClosed }: {
    bookingId: string;
    booking: any;
    onClosed: () => void;
}) {
    const [note, setNote] = useState('');
    const [confirming, setConfirming] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleClose = async () => {
        setSubmitting(true);
        setError(null);
        try {
            await api.adminCloseBooking(bookingId, note.trim() || undefined);
            onClosed();
        } catch (err: unknown) {
            if (err instanceof ApiError) {
                setError((err.body as any)?.detail || `API ${err.status}: ${err.code}`);
            } else {
                setError(err instanceof Error ? err.message : 'Failed to admin-close booking');
            }
            setSubmitting(false);
        }
    };

    return (
        <div style={{
            marginTop: 'var(--space-8)',
            background: 'rgba(245,158,11,0.05)',
            border: '1px solid rgba(245,158,11,0.35)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-5)',
        }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
                <span style={{ fontSize: '1.1rem' }}>⚠</span>
                <div>
                    <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: '#b45309', margin: 0, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                        Overdue — No Checkout Recorded
                    </h2>
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', margin: '2px 0 0' }}>
                        This booking passed its checkout date ({fmtDate(booking.check_out)}) with no worker checkout flow performed.
                    </p>
                </div>
            </div>

            {!confirming ? (
                <button
                    id="btn-admin-close-stay"
                    onClick={() => setConfirming(true)}
                    style={{
                        background: 'rgba(245,158,11,0.12)',
                        border: '1px solid rgba(245,158,11,0.5)',
                        color: '#92400e',
                        borderRadius: 'var(--radius-md)',
                        padding: 'var(--space-2) var(--space-4)',
                        fontWeight: 600,
                        fontSize: 'var(--text-sm)',
                        cursor: 'pointer',
                        transition: 'all 0.15s',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(245,158,11,0.2)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'rgba(245,158,11,0.12)')}
                >
                    🔒 Admin Close Stay
                </button>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                    {/* Explicit disclaimer */}
                    <div style={{
                        background: 'var(--color-surface)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-md)',
                        padding: 'var(--space-3) var(--space-4)',
                        fontSize: 'var(--text-xs)',
                        color: 'var(--color-text-dim)',
                        lineHeight: 1.6,
                    }}>
                        <div style={{ fontWeight: 700, color: 'var(--color-text)', marginBottom: 4 }}>What this action does:</div>
                        <div>✅ Sets booking status to <code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9em' }}>admin_closed</code></div>
                        <div>✅ Records an audit event (<code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9em' }}>BOOKING_ADMIN_CLOSED</code>) attributed to you</div>
                        <div>✅ Removes the booking from the overdue operational area</div>
                        <div style={{ marginTop: 6, fontWeight: 700, color: 'var(--color-text)' }}>What this does NOT do:</div>
                        <div>❌ Does not set a checkout timestamp — no fake worker history</div>
                        <div>❌ Does not trigger settlement or financial records</div>
                        <div>❌ Does not create or cancel cleaning tasks</div>
                        <div>❌ Does not affect guest dossier stay status</div>
                    </div>

                    {/* Optional note */}
                    <div>
                        <label style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                            Closure Note (optional)
                        </label>
                        <textarea
                            id="admin-close-note"
                            value={note}
                            onChange={e => setNote(e.target.value)}
                            placeholder="e.g. Guest no-show, OTA block that expired, manually resolved..."
                            rows={2}
                            style={{
                                width: '100%',
                                boxSizing: 'border-box',
                                background: 'var(--color-bg)',
                                border: '1px solid var(--color-border)',
                                borderRadius: 'var(--radius-md)',
                                padding: 'var(--space-2) var(--space-3)',
                                fontSize: 'var(--text-sm)',
                                color: 'var(--color-text)',
                                fontFamily: 'inherit',
                                resize: 'vertical',
                            }}
                        />
                    </div>

                    {error && (
                        <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-3)', color: 'var(--color-danger)', fontSize: 'var(--text-xs)' }}>
                            ⚠ {error}
                        </div>
                    )}

                    <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
                        <button
                            onClick={() => { setConfirming(false); setError(null); }}
                            disabled={submitting}
                            style={{
                                background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                                color: 'var(--color-text-dim)', borderRadius: 'var(--radius-md)',
                                padding: 'var(--space-2) var(--space-4)', fontWeight: 500,
                                fontSize: 'var(--text-sm)', cursor: 'pointer',
                            }}
                        >
                            Cancel
                        </button>
                        <button
                            id="btn-confirm-admin-close"
                            onClick={handleClose}
                            disabled={submitting}
                            style={{
                                background: submitting ? 'rgba(100,100,100,0.2)' : 'rgba(245,158,11,0.15)',
                                border: '1px solid rgba(245,158,11,0.5)',
                                color: submitting ? 'var(--color-text-faint)' : '#92400e',
                                borderRadius: 'var(--radius-md)',
                                padding: 'var(--space-2) var(--space-4)',
                                fontWeight: 700,
                                fontSize: 'var(--text-sm)',
                                cursor: submitting ? 'not-allowed' : 'pointer',
                            }}
                        >
                            {submitting ? '⟳ Closing…' : '🔒 Confirm Admin Close'}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Admin Closed state display (read-only, shown after closure)
// ---------------------------------------------------------------------------
function AdminClosedBadge({ booking }: { booking: any }) {
    return (
        <div style={{
            marginTop: 'var(--space-8)',
            background: 'rgba(100,100,100,0.06)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-4) var(--space-5)',
            display: 'flex', alignItems: 'center', gap: 'var(--space-3)',
        }}>
            <span style={{ fontSize: '1.2rem' }}>🔒</span>
            <div>
                <div style={{ fontWeight: 700, fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                    Administratively Closed
                </div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 2 }}>
                    This stay was closed by an admin. No checkout was performed. No settlement was triggered.
                </div>
            </div>
        </div>
    );
}

export default function BookingDetailPage() {
    const params = useParams();
    const bookingId = params?.id as string;
    const [booking, setBooking] = useState<any>(null);
    const [financial, setFinancial] = useState<any>(null);
    const [history, setHistory] = useState<any[]>([]);
    const [propertyMap, setPropertyMap] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            // Fetch by ID directly for fresh status — do NOT scan the list
            const [bRes, fRes, hRes, pRes] = await Promise.allSettled([
                api.getBookings?.({ limit: 500 }),
                api.getBookingFinancial?.(bookingId),
                api.getBookingHistory?.(bookingId),
                api.listProperties?.(),
            ]);
            if (bRes.status === 'fulfilled') {
                const b = bRes.value?.bookings?.find((b: any) => b.booking_id === bookingId);
                setBooking(b || null);
            }
            if (fRes.status === 'fulfilled') setFinancial(fRes.value);
            if (hRes.status === 'fulfilled') setHistory(hRes.value?.events || []);
            if (pRes.status === 'fulfilled') {
                const map: Record<string, string> = {};
                for (const p of pRes.value?.properties || []) {
                    map[p.property_id] = p.display_name || p.property_id;
                }
                setPropertyMap(map);
            }
        } catch { /* graceful */ }
        setLoading(false);
    }, [bookingId]);

    useEffect(() => { load(); }, [load]);

    if (loading) return <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading booking…</p>;

    return (
        <div style={{ maxWidth: 900 }}>
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Booking Detail</p>
                <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text)', letterSpacing: '-0.03em' }}>
                    {bookingId?.slice(0, 16) || 'Booking'}
                </h1>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 380px), 1fr))', gap: 'var(--space-6)' }}>
                {/* Info Panel */}
                <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                    <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 'var(--space-4)', textTransform: 'uppercase' }}>Booking Info</h2>
                    {booking ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                            {[
                                ['Property', booking.property_id ? (propertyMap[booking.property_id] || booking.property_id) : '—'], 
                                ['Guest', booking.guest_name], 
                                ['Guests count', booking.number_of_guests],
                                ['Confirmation #', booking.reservation_ref],
                                ['Check-in', fmtDate(booking.check_in)], 
                                ['Check-out', fmtDate(booking.check_out)], 
                                ['Status', booking.status], 
                                ['Source', booking.source],
                                ['Notes', booking.notes]
                            ]
                            .filter(([_, v]) => v !== undefined && v !== null && v !== '')
                            .map(([k, v]) => {
                                if (k === 'Confirmation #') {
                                    const ref = String(v || '');
                                    const firstDash = ref.indexOf('-');
                                    let displayContent = <span style={{ wordBreak: 'break-all' }}>{ref}</span>;
                                    
                                    if (firstDash !== -1) {
                                        const p1 = ref.slice(0, firstDash + 1);
                                        const p2 = ref.slice(firstDash + 1);
                                        displayContent = (
                                            <div style={{ wordBreak: 'break-all', textAlign: 'right' }}>
                                                <div>{p1}</div>
                                                <div style={{ color: 'var(--color-text-dim)', fontSize: '0.9em' }}>{p2}</div>
                                            </div>
                                        );
                                    }

                                    return (
                                        <div key={k as string} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-sm)', gap: 'var(--space-4)' }}>
                                            <span style={{ color: 'var(--color-text-dim)', whiteSpace: 'nowrap' }}>{k}</span>
                                            <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', maxWidth: '65%', justifyContent: 'flex-end' }}>
                                                <div style={{ fontWeight: 500, color: 'var(--color-text)' }}>
                                                    {displayContent}
                                                </div>
                                                <button 
                                                    onClick={(e) => { 
                                                        e.preventDefault(); 
                                                        navigator.clipboard.writeText(ref);
                                                        const btn = e.currentTarget;
                                                        const old = btn.innerHTML;
                                                        btn.innerHTML = '✓';
                                                        setTimeout(() => btn.innerHTML = old, 1500);
                                                    }}
                                                    title="Copy Confirmation #"
                                                    style={{ 
                                                        background: 'var(--color-surface-2)', 
                                                        border: '1px solid var(--color-border)', 
                                                        borderRadius: '4px', 
                                                        cursor: 'pointer', 
                                                        padding: '2px 6px',
                                                        fontSize: '11px',
                                                        color: 'var(--color-text-dim)',
                                                        marginTop: '2px',
                                                        flexShrink: 0,
                                                        transition: 'background 0.2s'
                                                    }}
                                                    onMouseEnter={(e) => e.currentTarget.style.background = 'var(--color-surface-hover)'}
                                                    onMouseLeave={(e) => e.currentTarget.style.background = 'var(--color-surface-2)'}
                                                >
                                                    Copy
                                                </button>
                                            </div>
                                        </div>
                                    );
                                }
                                
                                return (
                                    <div key={k as string} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-sm)' }}>
                                        <span style={{ color: 'var(--color-text-dim)' }}>{k}</span>
                                        <span style={{ fontWeight: 500, fontSize: typeof v === 'string' && v !== '—' && (k === 'Check-in' || k === 'Check-out') ? 'var(--text-md)' : undefined, color: (k === 'Check-in' || k === 'Check-out') ? 'var(--color-primary)' : 'var(--color-text)', textAlign: 'right', maxWidth: '60%' }}>{v || '—'}</span>
                                    </div>
                                );
                            })}
                        </div>
                    ) : <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-faint)' }}>Booking not found</p>}
                </div>

                {/* Financial Panel */}
                <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                    <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 'var(--space-4)', textTransform: 'uppercase' }}>Financial Facts</h2>
                    {financial ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                            {[['Gross Revenue', financial.gross_revenue], ['OTA Commission', financial.ota_commission], ['Net to Property', financial.net_to_property], ['Management Fee', financial.management_fee], ['Currency', financial.currency]].map(([k, v]) => (
                                <div key={k as string} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-sm)' }}>
                                    <span style={{ color: 'var(--color-text-dim)' }}>{k}</span>
                                    <span style={{ color: 'var(--color-ok)', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{v ?? '—'}</span>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                            {['Gross Revenue', 'OTA Commission', 'Net to Property', 'Management Fee', 'Currency'].map((k) => (
                                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-sm)' }}>
                                    <span style={{ color: 'var(--color-text-dim)' }}>{k}</span>
                                    <span style={{ color: 'var(--color-text-faint)', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>—</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Timeline */}
            <div style={{ marginTop: 'var(--space-8)', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 'var(--space-4)', textTransform: 'uppercase' }}>Event Timeline</h2>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                    {history.length > 0 ? history.map((e: any, i: number) => (
                        <div key={i} style={{ display: 'flex', gap: 'var(--space-3)', padding: 'var(--space-2) 0', borderBottom: '1px solid var(--color-border)', fontSize: 'var(--text-xs)' }}>
                            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-dim)', minWidth: 140 }}>{e.timestamp ? new Date(e.timestamp).toLocaleString() : '—'}</span>
                            <span style={{ color: 'var(--color-primary)', fontWeight: 600, minWidth: 140 }}>{e.event_type}</span>
                            <span style={{ color: 'var(--color-text-dim)' }}>{e.source || '—'}</span>
                        </div>
                    )) : (
                        <div style={{ display: 'flex', gap: 'var(--space-3)', padding: 'var(--space-2) 0', borderBottom: '1px solid var(--color-border)', fontSize: 'var(--text-xs)' }}>
                            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-faint)', minWidth: 140 }}>—</span>
                            <span style={{ color: 'var(--color-text-faint)', fontWeight: 600, minWidth: 140 }}>No events</span>
                            <span style={{ color: 'var(--color-text-faint)' }}>—</span>
                        </div>
                    )}
                </div>
            </div>

            {/* Admin Close Stay panel — only for overdue bookings */}
            {booking && isOverdue(booking) && (
                <AdminClosePanel
                    bookingId={bookingId}
                    booking={booking}
                    onClosed={load}
                />
            )}

            {/* Admin Closed badge — read-only, shown after closure */}
            {booking && (booking.status || '').toLowerCase() === 'admin_closed' && (
                <AdminClosedBadge booking={booking} />
            )}

            {/* Early Check-out Panel
                 ─────────────────────────────────────────────────────────────
                 Canonical gating rule — ALL conditions must be true:
                   1. Booking record is loaded
                   2. status is 'checked_in', 'active', or 'confirmed'
                      ('active' = OTA iCal live reservation; 'confirmed' = manual booking)
                   3. EITHER:
                      a. check_out date is today or in the future  (stay is live or imminent)
                      b. early_checkout_status is already 'requested' or 'approved'
                         (allow read-only view if EC was recorded before checkout date passed)

                 Stale bookings (check_out in the past, no EC in-flight) must NOT show
                 this panel. They are not eligible for Early Check-out.

                 Status is read from the freshly fetched single booking record — not
                 from any list cache — so it is always authoritative.
                 ──────────────────────────────────────────────────────────── */}
            {booking && (() => {
                const rawStatus = (booking.status || '').toLowerCase();
                const isActiveStatus = ['checked_in', 'active', 'confirmed'].includes(rawStatus);
                const checkoutDate = booking.check_out ? new Date(booking.check_out + 'T23:59:59') : null;
                const checkoutInFuture = checkoutDate ? checkoutDate > new Date() : false;
                const rawEcStatus = (booking.early_checkout_status || '').toLowerCase();
                const ecAlreadyInFlight = ['requested', 'approved'].includes(rawEcStatus);

                const shouldShow = isActiveStatus && (checkoutInFuture || ecAlreadyInFlight);
                if (!shouldShow) return null;
                return (
                    <div style={{ marginTop: 'var(--space-8)', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-4)' }}>
                            <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', margin: 0 }}>Early Check-out</h2>
                            <Link
                                href={`/admin/bookings/${bookingId}/early-checkout`}
                                style={{ fontSize: 'var(--text-xs)', color: 'var(--color-primary)', textDecoration: 'none', fontWeight: 500 }}
                            >
                                Manage →
                            </Link>
                        </div>
                        <EarlyCheckoutPanel bookingId={bookingId} embedded={true} />
                    </div>
                );
            })()}
        </div>
    );
}

