'use client';

/**
 * Phase 973 — Guest Dossier
 * Route: /guests/[id]
 *
 * Replaces the Phase 193 flat guest form with a full dossier:
 *   Overview (always visible) → Tabs: Identity | Contact | Current Stay | History | Activity
 */

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { api, Guest, GuestDossier, DossierStay, DossierActivity } from '../../../../lib/api';

// ---------------------------------------------------------------------------
// Types & Helpers
// ---------------------------------------------------------------------------

type TabId = 'identity' | 'contact' | 'stay' | 'history' | 'activity';

function fmtDate(s: string | null | undefined, withTime = false) {
    if (!s) return '—';
    const opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short', year: 'numeric' };
    if (withTime) { opts.hour = '2-digit'; opts.minute = '2-digit'; }
    return new Date(s).toLocaleString('en-US', opts);
}

function fmtDateShort(s: string | null | undefined) {
    if (!s) return '—';
    return new Date(s + 'T00:00:00').toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' });
}

function nightCount(checkIn?: string | null, checkOut?: string | null): number | null {
    if (!checkIn || !checkOut) return null;
    const d1 = new Date(checkIn + 'T00:00:00');
    const d2 = new Date(checkOut + 'T00:00:00');
    return Math.max(0, Math.round((d2.getTime() - d1.getTime()) / 86400000));
}

function initials(name: string) {
    return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

function actionLabel(action: string): string {
    const map: Record<string, string> = {
        guest_created: 'Guest record created',
        guest_patched: 'Guest record updated',
        passport_captured: 'Passport captured',
        guest_identity_saved: 'Identity saved at check-in',
        deposit_collected_at_checkin: 'Deposit collected',
        meter_opening_recorded: 'Meter reading recorded',
        checkin_completed: 'Check-in completed',
        checkin_override_deposit_skipped: 'Deposit override (skipped)',
        checkin_override_meter_skipped: 'Meter override (skipped)',
        meter_reading_corrected: 'Meter reading corrected',
    };
    return map[action] || action.replace(/_/g, ' ');
}

function actionIcon(action: string): string {
    const map: Record<string, string> = {
        guest_created: '👤',
        guest_patched: '✏️',
        passport_captured: '🛂',
        guest_identity_saved: '🛂',
        deposit_collected_at_checkin: '💰',
        meter_opening_recorded: '⚡',
        checkin_completed: '✅',
        meter_reading_corrected: '🔧',
    };
    return map[action] || '📋';
}

function statusBadge(status: string | null | undefined) {
    const s = status || 'Unknown';
    const colors: Record<string, { bg: string; fg: string }> = {
        InStay:     { bg: 'rgba(63,185,80,0.12)', fg: 'var(--color-ok)' },
        Confirmed:  { bg: 'rgba(88,166,255,0.12)', fg: 'var(--color-sage)' },
        CheckedIn:  { bg: 'rgba(63,185,80,0.12)', fg: 'var(--color-ok)' },
        CheckedOut: { bg: 'rgba(139,148,158,0.12)', fg: 'var(--color-text-dim)' },
        Cancelled:  { bg: 'rgba(239,68,68,0.12)', fg: 'var(--color-danger)' },
    };
    const c = colors[s] || { bg: 'var(--color-surface-2)', fg: 'var(--color-text-dim)' };
    return (
        <span style={{
            display: 'inline-block', padding: '2px 10px', borderRadius: 'var(--radius-full)',
            background: c.bg, color: c.fg, fontSize: 'var(--text-xs)', fontWeight: 700,
        }}>{s}</span>
    );
}

// ---------------------------------------------------------------------------
// Shared style tokens
// ---------------------------------------------------------------------------

const card: React.CSSProperties = {
    background: 'var(--color-surface)', border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-lg)', padding: 'var(--space-5) var(--space-6)',
    marginBottom: 'var(--space-4)',
};

const sectionTitle: React.CSSProperties = {
    fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-dim)',
    textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-4)',
};

const rowStyle: React.CSSProperties = {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: 'var(--space-2) 0', borderBottom: '1px solid var(--color-border)',
    fontSize: 'var(--text-sm)',
};

const labelStyle: React.CSSProperties = {
    color: 'var(--color-text-dim)', fontWeight: 600, fontSize: 'var(--text-xs)',
    textTransform: 'uppercase', letterSpacing: '0.04em', minWidth: 140,
};

const valueStyle: React.CSSProperties = { color: 'var(--color-text)', textAlign: 'right' as const };
const mutedValue: React.CSSProperties = { color: 'var(--color-muted)', textAlign: 'right' as const };

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function InfoRow({ label, value }: { label: string; value?: string | number | null }) {
    return (
        <div style={rowStyle}>
            <span style={labelStyle}>{label}</span>
            <span style={value ? valueStyle : mutedValue}>{value ?? '—'}</span>
        </div>
    );
}

function TabBar({ active, tabs, onChange }: { active: TabId; tabs: { id: TabId; label: string; icon: string }[]; onChange: (t: TabId) => void }) {
    return (
        <div style={{
            display: 'flex', gap: 'var(--space-1)', borderBottom: '1px solid var(--color-border)',
            marginBottom: 'var(--space-5)', overflowX: 'auto', WebkitOverflowScrolling: 'touch',
        }}>
            {tabs.map(t => (
                <button key={t.id} onClick={() => onChange(t.id)} style={{
                    padding: 'var(--space-3) var(--space-4)', background: 'none', border: 'none',
                    borderBottom: active === t.id ? '2px solid var(--color-primary)' : '2px solid transparent',
                    color: active === t.id ? 'var(--color-primary)' : 'var(--color-text-dim)',
                    fontWeight: active === t.id ? 700 : 500,
                    fontSize: 'var(--text-sm)', cursor: 'pointer', whiteSpace: 'nowrap',
                    transition: 'all .15s',
                }}>
                    {t.icon} {t.label}
                </button>
            ))}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Stay Card (for both Current Stay and History)
// ---------------------------------------------------------------------------

function StayCard({ stay, expanded, onToggle }: { stay: DossierStay; expanded?: boolean; onToggle?: () => void }) {
    const nights = nightCount(stay.check_in, stay.check_out);
    const deposit = stay.settlement?.deposit;
    const meters = stay.settlement?.meter_readings || [];
    const openingMeter = meters.find(m => m.reading_type === 'opening');

    return (
        <div style={{
            ...card, cursor: onToggle ? 'pointer' : 'default',
            ...(expanded ? { borderColor: 'var(--color-primary)', borderWidth: 1 } : {}),
        }}>
            <div onClick={onToggle} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <div style={{ fontWeight: 700, fontSize: 'var(--text-base)', color: 'var(--color-text)' }}>
                        {stay.property_name}
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                        {fmtDateShort(stay.check_in)} → {fmtDateShort(stay.check_out)}{nights ? ` · ${nights} nights` : ''}
                    </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    {statusBadge(stay.status)}
                    {onToggle && <span style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{expanded ? '▲' : '▼'}</span>}
                </div>
            </div>
            {(expanded || !onToggle) && (
                <div style={{ marginTop: 'var(--space-4)', paddingTop: 'var(--space-3)', borderTop: '1px solid var(--color-border)' }}>
                    <InfoRow label="Booking ID" value={stay.booking_id.slice(0, 16) + '…'} />
                    {stay.source && <InfoRow label="Source" value={stay.source} />}
                    {stay.reservation_ref && <InfoRow label="Reservation" value={stay.reservation_ref.length > 20 ? stay.reservation_ref.slice(0, 20) + '…' : stay.reservation_ref} />}

                    {/* Settlement: Deposit */}
                    {deposit && (
                        <div style={{ marginTop: 'var(--space-3)' }}>
                            <div style={{ ...sectionTitle, marginBottom: 'var(--space-2)' }}>💰 Deposit</div>
                            <InfoRow label="Amount" value={`${deposit.currency} ${deposit.amount}`} />
                            <InfoRow label="Status" value={deposit.status} />
                            <InfoRow label="Collected" value={fmtDate(deposit.collected_at, true)} />
                            {deposit.notes && <InfoRow label="Notes" value={deposit.notes} />}
                        </div>
                    )}

                    {/* Settlement: Meter */}
                    {openingMeter && (
                        <div style={{ marginTop: 'var(--space-3)' }}>
                            <div style={{ ...sectionTitle, marginBottom: 'var(--space-2)' }}>⚡ Electricity Meter</div>
                            <InfoRow label="Opening" value={`${openingMeter.meter_value} ${openingMeter.meter_unit}`} />
                            <InfoRow label="Recorded" value={fmtDate(openingMeter.recorded_at, true)} />
                            {openingMeter.meter_photo_url && (
                                <div style={{ marginTop: 'var(--space-2)', fontSize: 'var(--text-xs)', color: 'var(--color-sage)' }}>
                                    📷 Meter photo on file
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function GuestDossierPage() {
    const params = useParams();
    const id = params?.id as string;

    const [dossier, setDossier] = useState<GuestDossier | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [tab, setTab] = useState<TabId>('identity');
    const [expandedStay, setExpandedStay] = useState<string | null>(null);

    // Edit state for contact tab
    const [editingContact, setEditingContact] = useState(false);
    const [contactForm, setContactForm] = useState({ phone: '', email: '', whatsapp: '', line_id: '', telegram: '', preferred_channel: '' });
    const [savingContact, setSavingContact] = useState(false);

    const load = useCallback(async () => {
        setLoading(true); setError(null);
        try {
            const d = await api.getGuestDossier(id);
            setDossier(d);
            setContactForm({
                phone: d.guest.phone || '',
                email: d.guest.email || '',
                whatsapp: d.guest.whatsapp || '',
                line_id: d.guest.line_id || '',
                telegram: d.guest.telegram || '',
                preferred_channel: d.guest.preferred_channel || '',
            });
            // Auto-select current stay tab if there's an active stay
            if (d.current_stay) setTab('stay');
        } catch {
            setError('Guest not found or access denied.');
        } finally {
            setLoading(false);
        }
    }, [id]);

    useEffect(() => { if (id) load(); }, [id, load]);

    const guest = dossier?.guest;

    const saveContact = async () => {
        if (!dossier) return;
        setSavingContact(true);
        try {
            await api.patchGuest(id, {
                phone: contactForm.phone || null,
                email: contactForm.email || null,
                whatsapp: contactForm.whatsapp || null,
                line_id: contactForm.line_id || null,
                telegram: contactForm.telegram || null,
                preferred_channel: contactForm.preferred_channel || null,
            });
            setEditingContact(false);
            load(); // refresh
        } catch {
            // keep editing
        } finally {
            setSavingContact(false);
        }
    };

    // ---------------------------------------------------------------------------
    // Render
    // ---------------------------------------------------------------------------

    if (loading) {
        return (
            <div style={{ padding: 'var(--space-8)', color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>
                Loading guest dossier…
            </div>
        );
    }

    if (error || !guest || !dossier) {
        return (
            <div style={{ padding: 'var(--space-8)' }}>
                <a href="/guests" style={{ color: 'var(--color-primary)', fontSize: 'var(--text-sm)', textDecoration: 'none' }}>← Back to Guests</a>
                <div style={{ marginTop: 'var(--space-6)', color: 'var(--color-danger)', fontSize: 'var(--text-sm)' }}>{error ?? 'Guest not found.'}</div>
            </div>
        );
    }

    const hasActiveStay = !!dossier.current_stay;

    const tabs: { id: TabId; label: string; icon: string }[] = [
        { id: 'identity', label: 'Identity', icon: '🛂' },
        { id: 'contact', label: 'Contact', icon: '📱' },
        { id: 'stay', label: hasActiveStay ? 'Current Stay' : 'Stay', icon: '🏠' },
        { id: 'history', label: 'History', icon: '📋' },
        { id: 'activity', label: 'Activity', icon: '🕐' },
    ];

    const inputStyle: React.CSSProperties = {
        padding: '6px 10px', background: 'var(--color-surface-2)',
        border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)',
        color: 'var(--color-text)', fontSize: 'var(--text-sm)', width: '100%',
        boxSizing: 'border-box',
    };

    return (
        <div style={{ minHeight: '100vh', background: 'var(--color-bg)', padding: 'var(--space-6) var(--space-5)' }}>
            <style>{`
                @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
            `}</style>

            {/* Back link */}
            <a href="/guests" style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4, marginBottom: 'var(--space-5)' }}>
                ← Guest Directory
            </a>

            {/* ================================================================ */}
            {/* OVERVIEW BANNER (always visible above tabs)                      */}
            {/* ================================================================ */}
            <div style={{ ...card, display: 'flex', gap: 'var(--space-5)', alignItems: 'center', animation: 'fadeIn .3s ease' }}>
                {/* Avatar */}
                <div style={{
                    width: 56, height: 56, borderRadius: 'var(--radius-full)',
                    background: 'linear-gradient(135deg, rgba(99,102,241,0.2), rgba(88,166,255,0.2))',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 'var(--text-lg)', fontWeight: 800, color: 'var(--color-primary)',
                    flexShrink: 0,
                }}>
                    {initials(guest.full_name)}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
                        <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 800, color: 'var(--color-text)', margin: 0 }}>
                            {guest.full_name}
                        </h1>
                        {hasActiveStay ? (
                            <span style={{
                                display: 'inline-flex', alignItems: 'center', gap: 4,
                                padding: '3px 12px', borderRadius: 'var(--radius-full)',
                                background: 'rgba(63,185,80,0.1)', color: 'var(--color-ok)',
                                fontSize: 'var(--text-xs)', fontWeight: 700,
                            }}>
                                🟢 In Stay — {dossier.current_stay!.property_name}
                            </span>
                        ) : (
                            <span style={{
                                padding: '3px 12px', borderRadius: 'var(--radius-full)',
                                background: 'var(--color-surface-2)', color: 'var(--color-text-dim)',
                                fontSize: 'var(--text-xs)', fontWeight: 600,
                            }}>
                                No Active Stay
                            </span>
                        )}
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
                        {guest.id}
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)', marginTop: 2 }}>
                        Created {fmtDate(guest.created_at, true)} · Updated {fmtDate(guest.updated_at, true)}
                    </div>
                </div>
                {/* Quick contact summary */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'flex-end', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', flexShrink: 0 }}>
                    {guest.phone && <span>📱 {guest.phone}</span>}
                    {guest.email && <span>📧 {guest.email}</span>}
                    {guest.nationality && <span>🌍 {guest.nationality}</span>}
                </div>
            </div>

            {/* PII notice */}
            <div style={{ background: 'rgba(99,102,241,0.07)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-4)', marginBottom: 'var(--space-4)', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>🔒</span> This dossier contains personally identifiable information (PII). Handle with care.
            </div>

            {/* ================================================================ */}
            {/* TAB BAR                                                          */}
            {/* ================================================================ */}
            <TabBar active={tab} tabs={tabs} onChange={setTab} />

            {/* ================================================================ */}
            {/* TAB: Identity                                                    */}
            {/* ================================================================ */}
            {tab === 'identity' && (
                <div style={{ display: 'flex', gap: 'var(--space-5)', flexWrap: 'wrap', animation: 'fadeIn .2s ease' }}>
                    {/* Left: Fields */}
                    <div style={{ ...card, flex: '1 1 340px', minWidth: 300 }}>
                        <div style={sectionTitle}>Document Identity</div>
                        <InfoRow label="Full Name" value={guest.full_name} />
                        <InfoRow label="Document Type" value={guest.document_type} />
                        <InfoRow label="Document Number" value={guest.passport_no} />
                        <InfoRow label="Nationality" value={guest.nationality} />
                        <InfoRow label="Date of Birth" value={guest.date_of_birth ? fmtDateShort(guest.date_of_birth) : null} />
                        <InfoRow label="Expiry Date" value={guest.passport_expiry ? fmtDateShort(guest.passport_expiry) : null} />
                        {guest.notes && <InfoRow label="Notes" value={guest.notes} />}
                    </div>
                    {/* Right: Passport image */}
                    <div style={{ ...card, flex: '0 0 240px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                        <div style={sectionTitle}>Document Photo</div>
                        {dossier.document_photo_signed_url ? (
                            <a href={dossier.document_photo_signed_url} target="_blank" rel="noopener noreferrer" style={{ display: 'block' }}>
                                <img
                                    src={dossier.document_photo_signed_url}
                                    alt="Passport / Document"
                                    style={{
                                        width: 180, maxHeight: 260, objectFit: 'contain',
                                        borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)',
                                        cursor: 'pointer',
                                    }}
                                />
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-primary)', textAlign: 'center', marginTop: 'var(--space-2)' }}>
                                    Click to view full size ↗
                                </div>
                            </a>
                        ) : (
                            <div style={{
                                width: 180, height: 220, borderRadius: 'var(--radius-md)',
                                background: 'var(--color-surface-2)', border: '1px dashed var(--color-border)',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                fontSize: 'var(--text-sm)', color: 'var(--color-muted)', textAlign: 'center',
                                padding: 'var(--space-4)',
                            }}>
                                No document photo captured yet
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* ================================================================ */}
            {/* TAB: Contact                                                     */}
            {/* ================================================================ */}
            {tab === 'contact' && (
                <div style={{ ...card, animation: 'fadeIn .2s ease' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
                        <div style={sectionTitle}>Communication Channels</div>
                        {editingContact ? (
                            <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                                <button onClick={saveContact} disabled={savingContact} style={{ padding: '4px 14px', background: 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer' }}>
                                    {savingContact ? 'Saving…' : 'Save'}
                                </button>
                                <button onClick={() => setEditingContact(false)} style={{ padding: '4px 14px', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', fontSize: 'var(--text-xs)', cursor: 'pointer', color: 'var(--color-text)' }}>Cancel</button>
                            </div>
                        ) : (
                            <button onClick={() => setEditingContact(true)} style={{ padding: '4px 14px', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', fontSize: 'var(--text-xs)', cursor: 'pointer', fontWeight: 600, color: 'var(--color-text)' }}>✎ Edit</button>
                        )}
                    </div>
                    {editingContact ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                            {[
                                { key: 'phone', label: '📱 Phone', placeholder: '+66 81 000 0000' },
                                { key: 'email', label: '📧 Email', placeholder: 'guest@example.com' },
                                { key: 'whatsapp', label: '💬 WhatsApp', placeholder: '+66 81 000 0000' },
                                { key: 'line_id', label: '🟢 LINE', placeholder: 'LINE ID' },
                                { key: 'telegram', label: '✈️ Telegram', placeholder: '@username' },
                            ].map(f => (
                                <div key={f.key} style={{ display: 'grid', gridTemplateColumns: '140px 1fr', alignItems: 'center', gap: 'var(--space-3)' }}>
                                    <span style={labelStyle}>{f.label}</span>
                                    <input value={(contactForm as any)[f.key]} onChange={e => setContactForm(p => ({ ...p, [f.key]: e.target.value }))} placeholder={f.placeholder} style={inputStyle} />
                                </div>
                            ))}
                            <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', alignItems: 'center', gap: 'var(--space-3)' }}>
                                <span style={labelStyle}>Preferred</span>
                                <select value={contactForm.preferred_channel} onChange={e => setContactForm(p => ({ ...p, preferred_channel: e.target.value }))} style={{ ...inputStyle, cursor: 'pointer' }}>
                                    <option value="">Not set</option>
                                    <option value="phone">Phone</option>
                                    <option value="email">Email</option>
                                    <option value="whatsapp">WhatsApp</option>
                                    <option value="line">LINE</option>
                                    <option value="telegram">Telegram</option>
                                </select>
                            </div>
                        </div>
                    ) : (
                        <>
                            <InfoRow label="📱 Phone" value={guest.phone} />
                            <InfoRow label="📧 Email" value={guest.email} />
                            <InfoRow label="💬 WhatsApp" value={guest.whatsapp} />
                            <InfoRow label="🟢 LINE" value={guest.line_id} />
                            <InfoRow label="✈️ Telegram" value={guest.telegram} />
                            <InfoRow label="Preferred Channel" value={guest.preferred_channel} />
                        </>
                    )}
                </div>
            )}

            {/* ================================================================ */}
            {/* TAB: Current Stay                                                */}
            {/* ================================================================ */}
            {tab === 'stay' && (
                <div style={{ animation: 'fadeIn .2s ease' }}>
                    {dossier.current_stay ? (
                        <StayCard stay={dossier.current_stay} />
                    ) : (
                        <div style={{ ...card, textAlign: 'center', padding: 'var(--space-8)' }}>
                            <div style={{ fontSize: 'var(--text-2xl)', marginBottom: 'var(--space-2)' }}>🏡</div>
                            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', fontWeight: 600 }}>
                                No Active Stay
                            </div>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)', marginTop: 4 }}>
                                This guest does not currently have a checked-in or confirmed booking.
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* ================================================================ */}
            {/* TAB: Stay History                                                 */}
            {/* ================================================================ */}
            {tab === 'history' && (
                <div style={{ animation: 'fadeIn .2s ease' }}>
                    <div style={sectionTitle}>
                        {dossier.stay_history.length} past {dossier.stay_history.length === 1 ? 'stay' : 'stays'}
                        {dossier.current_stay ? ' + 1 active' : ''}
                    </div>
                    {dossier.stay_history.length === 0 && !dossier.current_stay ? (
                        <div style={{ ...card, textAlign: 'center', padding: 'var(--space-8)' }}>
                            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)' }}>
                                No stay records linked to this guest yet.
                            </div>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 'var(--space-2)' }}>
                                Stays appear here when a booking is linked to this guest identity during check-in.
                            </div>
                        </div>
                    ) : (
                        <>
                            {dossier.current_stay && (
                                <StayCard stay={dossier.current_stay} expanded={expandedStay === dossier.current_stay.booking_id} onToggle={() => setExpandedStay(s => s === dossier.current_stay!.booking_id ? null : dossier.current_stay!.booking_id)} />
                            )}
                            {dossier.stay_history.map(s => (
                                <StayCard key={s.booking_id} stay={s} expanded={expandedStay === s.booking_id} onToggle={() => setExpandedStay(prev => prev === s.booking_id ? null : s.booking_id)} />
                            ))}
                        </>
                    )}
                </div>
            )}

            {/* ================================================================ */}
            {/* TAB: Activity Timeline                                           */}
            {/* ================================================================ */}
            {tab === 'activity' && (
                <div style={{ animation: 'fadeIn .2s ease' }}>
                    <div style={sectionTitle}>Activity Trail · {dossier.activity.length} events</div>
                    {dossier.activity.length === 0 ? (
                        <div style={{ ...card, textAlign: 'center', color: 'var(--color-muted)', fontSize: 'var(--text-sm)', padding: 'var(--space-8)' }}>
                            No activity recorded yet.
                        </div>
                    ) : (
                        <div style={{ position: 'relative', paddingLeft: 28 }}>
                            {/* Timeline line */}
                            <div style={{ position: 'absolute', left: 9, top: 8, bottom: 8, width: 2, background: 'var(--color-border)' }} />

                            {dossier.activity.map((ev, i) => (
                                <div key={i} style={{ position: 'relative', marginBottom: 'var(--space-4)' }}>
                                    {/* Dot */}
                                    <div style={{
                                        position: 'absolute', left: -22, top: 4,
                                        width: 20, height: 20, borderRadius: '50%',
                                        background: 'var(--color-surface)', border: '2px solid var(--color-border)',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        fontSize: 10,
                                    }}>
                                        {actionIcon(ev.action)}
                                    </div>
                                    {/* Content */}
                                    <div style={{
                                        ...card, marginBottom: 0,
                                        padding: 'var(--space-3) var(--space-4)',
                                    }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                            <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>
                                                {actionLabel(ev.action)}
                                            </span>
                                            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)' }}>
                                                {fmtDate(ev.performed_at, true)}
                                            </span>
                                        </div>
                                        {ev.actor_id && (
                                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                                                by {ev.actor_id.slice(0, 12)}…
                                            </div>
                                        )}
                                        {ev.details && Object.keys(ev.details).length > 0 && (
                                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 4, fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>
                                                {JSON.stringify(ev.details).slice(0, 120)}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
