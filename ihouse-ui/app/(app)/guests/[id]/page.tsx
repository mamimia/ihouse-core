'use client';

/**
 * Phase 975–978 — Guest Dossier (Full Implementation)
 * Route: /guests/[id]
 *
 * Structured dossier with all 9 sections:
 *   Overview (banner, always visible)
 *   Tabs: Identity | Contact | Current Stay | History | Activity
 *
 * Inside Current Stay:
 *   Booking details → Check-in Record → Portal/QR → Settlement
 *
 * Inside each History stay card (expandable):
 *   Booking → Check-in → Settlement → Checkout (when available)
 */

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import {
    api, Guest, GuestDossier, DossierStay, DossierActivity,
    DossierPhoto, DossierCheckinRecord, DossierPortal, DossierMeter
} from '../../../../lib/api';

// ---------------------------------------------------------------------------
// Helpers
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
        'GUEST_IDENTITY_SAVED': 'Identity captured at check-in',
        guest_identity_saved: 'Identity captured at check-in',
        deposit_collected_at_checkin: 'Deposit collected',
        meter_opening_recorded: 'Opening meter recorded',
        checkin_completed: 'Check-in completed',
        'booking.checkin': 'Check-in completed',
        checkin_override_deposit_skipped: 'Deposit override (skipped)',
        checkin_override_meter_skipped: 'Meter override (skipped)',
        meter_reading_corrected: 'Meter reading corrected',
    };
    return map[action] || action.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function actionIcon(action: string): string {
    const map: Record<string, string> = {
        guest_created: '👤',
        guest_patched: '✏️',
        'GUEST_IDENTITY_SAVED': '🛂',
        guest_identity_saved: '🛂',
        deposit_collected_at_checkin: '💰',
        meter_opening_recorded: '⚡',
        checkin_completed: '✅',
        'booking.checkin': '✅',
        checkin_override_deposit_skipped: '⚠️',
        checkin_override_meter_skipped: '⚠️',
        meter_reading_corrected: '🔧',
    };
    return map[action] || '📋';
}

function statusColor(status: string | null | undefined): { bg: string; fg: string } {
    const s = status || '';
    const map: Record<string, { bg: string; fg: string }> = {
        InStay:     { bg: 'rgba(63,185,80,0.12)', fg: '#3fb850' },
        CheckedIn:  { bg: 'rgba(63,185,80,0.12)', fg: '#3fb850' },
        checked_in: { bg: 'rgba(63,185,80,0.12)', fg: '#3fb850' },
        active:     { bg: 'rgba(63,185,80,0.12)', fg: '#3fb850' },
        Confirmed:  { bg: 'rgba(88,166,255,0.12)', fg: '#58a6ff' },
        CheckedOut: { bg: 'rgba(139,148,158,0.12)', fg: 'var(--color-text-dim)' },
        Cancelled:  { bg: 'rgba(239,68,68,0.12)', fg: '#ef4444' },
    };
    return map[s] || { bg: 'var(--color-surface-2)', fg: 'var(--color-text-dim)' };
}

function StatusBadge({ status }: { status?: string | null }) {
    const s = status || 'Unknown';
    const c = statusColor(s);
    return (
        <span style={{
            display: 'inline-block', padding: '2px 10px', borderRadius: 999,
            background: c.bg, color: c.fg, fontSize: 12, fontWeight: 700,
        }}>{s}</span>
    );
}

// ---------------------------------------------------------------------------
// Shared styles
// ---------------------------------------------------------------------------

const cardStyle: React.CSSProperties = {
    background: 'var(--color-surface)', border: '1px solid var(--color-border)',
    borderRadius: 12, padding: '20px 24px', marginBottom: 16,
};

const sectionTitleStyle: React.CSSProperties = {
    fontSize: 11, fontWeight: 700, color: 'var(--color-text-dim)',
    textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 16,
};

const rowStyle: React.CSSProperties = {
    display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
    padding: '8px 0', borderBottom: '1px solid var(--color-border)', fontSize: 13,
};

const labelStyle: React.CSSProperties = {
    color: 'var(--color-text-dim)', fontWeight: 600, fontSize: 11,
    textTransform: 'uppercase', letterSpacing: '0.04em', minWidth: 140, paddingTop: 1,
};

const valueStyle: React.CSSProperties = { color: 'var(--color-text)', textAlign: 'right' as const, maxWidth: 260, wordBreak: 'break-word' };
const mutedStyle: React.CSSProperties = { color: 'var(--color-muted)', textAlign: 'right' as const };

function InfoRow({ label, value, mono }: { label: string; value?: string | number | null; mono?: boolean }) {
    return (
        <div style={rowStyle}>
            <span style={labelStyle}>{label}</span>
            <span style={value ? { ...valueStyle, fontFamily: mono ? 'var(--font-mono)' : undefined } : mutedStyle}>
                {value ?? '—'}
            </span>
        </div>
    );
}

function SectionHeader({ title }: { title: string }) {
    return <div style={sectionTitleStyle}>{title}</div>;
}

// ---------------------------------------------------------------------------
// Photo Grid
// ---------------------------------------------------------------------------

function PhotoGrid({ photos, title }: { photos: DossierPhoto[]; title: string }) {
    if (!photos.length) return null;
    return (
        <div style={{ marginTop: 16 }}>
            <SectionHeader title={`📷 ${title} (${photos.length})`} />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(80px, 1fr))', gap: 8 }}>
                {photos.map((p, i) => (
                    <div key={i} style={{
                        background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                        borderRadius: 8, height: 80, display: 'flex', flexDirection: 'column',
                        alignItems: 'center', justifyContent: 'center', padding: 4,
                        fontSize: 10, color: 'var(--color-text-dim)', textAlign: 'center',
                    }}>
                        <span style={{ fontSize: 24 }}>📸</span>
                        <span style={{ marginTop: 2, wordBreak: 'break-all' }}>
                            {p.room_label.replace(/_/g, ' ')}
                        </span>
                    </div>
                ))}
            </div>
            <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginTop: 6 }}>
                Photos stored in secure storage. Download/view full-size from Storage.
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Portal Block
// ---------------------------------------------------------------------------

function PortalBlock({ portal }: { portal: DossierPortal }) {
    return (
        <div style={{ ...cardStyle, background: portal.qr_generated ? 'rgba(63,185,80,0.05)' : 'var(--color-surface)' }}>
            <SectionHeader title="🔗 Guest Portal / QR" />
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                <span style={{
                    width: 40, height: 40, borderRadius: '50%',
                    background: portal.qr_generated ? 'rgba(63,185,80,0.15)' : 'var(--color-surface-2)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20,
                }}>
                    {portal.qr_generated ? '✅' : '⬜'}
                </span>
                <div>
                    <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--color-text)' }}>
                        {portal.qr_generated ? 'Portal Generated' : 'Portal Not Yet Generated'}
                    </div>
                    {portal.issued_at && (
                        <div style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>
                            Issued {fmtDate(portal.issued_at, true)}
                        </div>
                    )}
                </div>
            </div>
            {portal.portal_url && (
                <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginBottom: 4 }}>Portal URL</div>
                    <a
                        href={portal.portal_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                            display: 'block', padding: '6px 10px',
                            background: 'var(--color-surface-2)', borderRadius: 8,
                            fontSize: 12, color: 'var(--color-primary)', fontFamily: 'var(--font-mono)',
                            wordBreak: 'break-all', textDecoration: 'none', border: '1px solid var(--color-border)',
                        }}
                    >
                        {portal.portal_url}
                    </a>
                </div>
            )}
            {portal.expires_at && (
                <div style={{ marginTop: 8, fontSize: 11, color: 'var(--color-text-dim)' }}>
                    Expires {fmtDate(portal.expires_at, true)}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Check-in Record Block
// ---------------------------------------------------------------------------

function CheckinRecordBlock({ record }: { record: DossierCheckinRecord }) {
    return (
        <div style={cardStyle}>
            <SectionHeader title="✅ Check-in Record" />
            <InfoRow label="Completed" value={record.checked_in_at ? fmtDate(record.checked_in_at, true) : null} />

            {/* Opening meter */}
            {record.opening_meter && (
                <div style={{ marginTop: 16 }}>
                    <SectionHeader title="⚡ Opening Electricity Meter" />
                    <InfoRow label="Reading" value={`${record.opening_meter.meter_value} ${record.opening_meter.meter_unit}`} />
                    <InfoRow label="Recorded" value={fmtDate(record.opening_meter.recorded_at, true)} />
                    {record.opening_meter.meter_photo_url && (
                        <div style={{ marginTop: 8, fontSize: 12, color: 'var(--color-text-dim)' }}>
                            📷 Meter photo stored in secure storage
                        </div>
                    )}
                    {record.meter_photos.length > 0 && (
                        <PhotoGrid photos={record.meter_photos} title="Meter Photos" />
                    )}
                </div>
            )}

            {/* Walkthrough photos */}
            {record.walkthrough_photos.length > 0 ? (
                <PhotoGrid photos={record.walkthrough_photos} title="Property Walk-Through Photos" />
            ) : (
                record.checked_in_at && (
                    <div style={{ marginTop: 16, fontSize: 12, color: 'var(--color-muted)' }}>
                        No walk-through photos indexed (check-in completed before Phase 977 fix).
                    </div>
                )
            )}

            {!record.checked_in_at && (
                <div style={{ color: 'var(--color-muted)', fontSize: 13 }}>Check-in not yet completed.</div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Settlement Block
// ---------------------------------------------------------------------------

function SettlementBlock({ stay }: { stay: DossierStay }) {
    const { deposit, meter_readings } = stay.settlement;
    const openingMeter = meter_readings.find(m => m.reading_type === 'opening');
    const closingMeter = meter_readings.find(m => m.reading_type === 'closing');
    const hasAny = deposit || openingMeter || closingMeter;

    if (!hasAny) return (
        <div style={cardStyle}>
            <SectionHeader title="💳 Settlement" />
            <div style={{ fontSize: 13, color: 'var(--color-muted)' }}>No settlement data recorded yet.</div>
        </div>
    );

    return (
        <div style={cardStyle}>
            <SectionHeader title="💳 Settlement" />
            {deposit && (
                <>
                    <SectionHeader title="Deposit" />
                    <InfoRow label="Amount" value={`${deposit.currency} ${deposit.amount}`} />
                    <InfoRow label="Status" value={deposit.status} />
                    <InfoRow label="Collected" value={fmtDate(deposit.collected_at, true)} />
                    {deposit.notes && <InfoRow label="Notes" value={deposit.notes} />}
                    {deposit.refund_amount != null && <InfoRow label="Refund Amount" value={`${deposit.currency} ${deposit.refund_amount}`} />}
                </>
            )}
            {openingMeter && (
                <div style={{ marginTop: deposit ? 16 : 0 }}>
                    <SectionHeader title="Electricity — Opening" />
                    <InfoRow label="Reading" value={`${openingMeter.meter_value} ${openingMeter.meter_unit}`} />
                    <InfoRow label="Recorded" value={fmtDate(openingMeter.recorded_at, true)} />
                </div>
            )}
            {closingMeter && (
                <div style={{ marginTop: 16 }}>
                    <SectionHeader title="Electricity — Closing" />
                    <InfoRow label="Reading" value={`${closingMeter.meter_value} ${closingMeter.meter_unit}`} />
                    <InfoRow label="Recorded" value={fmtDate(closingMeter.recorded_at, true)} />
                    {openingMeter && (
                        <InfoRow
                            label="Units Consumed"
                            value={`${(closingMeter.meter_value - openingMeter.meter_value).toFixed(1)} ${closingMeter.meter_unit}`}
                        />
                    )}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Stay Card (History)
// ---------------------------------------------------------------------------

function StayCard({ stay, expanded, onToggle }: { stay: DossierStay; expanded: boolean; onToggle: () => void }) {
    const nights = nightCount(stay.check_in, stay.check_out);
    const deposit = stay.settlement?.deposit;

    return (
        <div style={{ ...cardStyle, ...(expanded ? { borderColor: 'rgba(99,102,241,0.4)' } : {}) }}>
            {/* Header row — always visible */}
            <div onClick={onToggle} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}>
                <div>
                    <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--color-text)' }}>
                        {stay.property_name}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginTop: 2 }}>
                        {fmtDateShort(stay.check_in)} → {fmtDateShort(stay.check_out)}{nights != null ? ` · ${nights} nights` : ''}
                    </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <StatusBadge status={stay.status} />
                    {stay.portal.qr_generated && (
                        <span title="Portal generated" style={{ fontSize: 16 }}>🔗</span>
                    )}
                    {deposit && (
                        <span title={`Deposit: ${deposit.currency} ${deposit.amount}`} style={{ fontSize: 16 }}>💰</span>
                    )}
                    <span style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{expanded ? '▲' : '▼'}</span>
                </div>
            </div>

            {/* Expanded detail */}
            {expanded && (
                <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--color-border)', animation: 'fadeIn .2s ease' }}>
                    <InfoRow label="Booking ID" value={stay.booking_id.slice(0, 20) + '…'} mono />
                    {stay.source && <InfoRow label="Source" value={stay.source} />}
                    {stay.reservation_ref && <InfoRow label="Reservation" value={stay.reservation_ref.slice(0, 30)} mono />}

                    <div style={{ marginTop: 16 }}>
                        <CheckinRecordBlock record={stay.checkin_record} />
                    </div>

                    <PortalBlock portal={stay.portal} />

                    <SettlementBlock stay={stay} />

                    {stay.checkout_record?.checked_out_at && (
                        <div style={cardStyle}>
                            <SectionHeader title="🚪 Checkout Record" />
                            <InfoRow label="Checked Out" value={fmtDate(stay.checkout_record.checked_out_at, true)} />
                            {stay.checkout_record.closing_meter && (
                                <InfoRow label="Closing Meter" value={`${stay.checkout_record.closing_meter.meter_value} ${stay.checkout_record.closing_meter.meter_unit}`} />
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Tab bar
// ---------------------------------------------------------------------------

function TabBar({ active, tabs, onChange }: { active: TabId; tabs: { id: TabId; label: string; icon: string }[]; onChange: (t: TabId) => void }) {
    return (
        <div style={{
            display: 'flex', gap: 2, borderBottom: '1px solid var(--color-border)',
            marginBottom: 20, overflowX: 'auto',
        }}>
            {tabs.map(t => (
                <button key={t.id} onClick={() => onChange(t.id)} style={{
                    padding: '10px 16px', background: 'none', border: 'none',
                    borderBottom: active === t.id ? '2px solid var(--color-primary)' : '2px solid transparent',
                    color: active === t.id ? 'var(--color-primary)' : 'var(--color-text-dim)',
                    fontWeight: active === t.id ? 700 : 500, fontSize: 13,
                    cursor: 'pointer', whiteSpace: 'nowrap', transition: 'all .15s',
                }}>
                    {t.icon} {t.label}
                </button>
            ))}
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

    // Contact editing
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
            if (d.current_stay) setTab('stay');
        } catch {
            setError('Guest not found or access denied.');
        } finally {
            setLoading(false);
        }
    }, [id]);

    useEffect(() => { if (id) load(); }, [id, load]);

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
            load();
        } finally {
            setSavingContact(false);
        }
    };

    if (loading) return (
        <div style={{ padding: 32, color: 'var(--color-text-dim)', fontSize: 14 }}>Loading guest dossier…</div>
    );

    if (error || !dossier) return (
        <div style={{ padding: 32 }}>
            <a href="/guests" style={{ color: 'var(--color-primary)', fontSize: 13, textDecoration: 'none' }}>← Back</a>
            <div style={{ marginTop: 24, color: 'var(--color-danger)', fontSize: 13 }}>{error ?? 'Not found.'}</div>
        </div>
    );

    const { guest } = dossier;
    const hasActiveStay = !!dossier.current_stay;

    const tabs: { id: TabId; label: string; icon: string }[] = [
        { id: 'identity', label: 'Identity', icon: '🛂' },
        { id: 'contact', label: 'Contact', icon: '📱' },
        { id: 'stay', label: hasActiveStay ? 'Current Stay' : 'Stay', icon: '🏠' },
        { id: 'history', label: `History (${dossier.stay_history.length + (hasActiveStay ? 1 : 0)})`, icon: '📋' },
        { id: 'activity', label: 'Activity', icon: '🕐' },
    ];

    const inputStyle: React.CSSProperties = {
        padding: '6px 10px', background: 'var(--color-surface-2)',
        border: '1px solid var(--color-border)', borderRadius: 8,
        color: 'var(--color-text)', fontSize: 13, width: '100%', boxSizing: 'border-box',
    };

    return (
        <div style={{ minHeight: '100vh', background: 'var(--color-bg)', padding: '24px 20px' }}>
            <style>{`
              @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
            `}</style>

            {/* Nav */}
            <a href="/guests" style={{ fontSize: 13, color: 'var(--color-text-dim)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4, marginBottom: 20 }}>
                ← Guest Directory
            </a>

            {/* ============================================================ */}
            {/* OVERVIEW BANNER                                               */}
            {/* ============================================================ */}
            <div style={{ ...cardStyle, display: 'flex', gap: 20, alignItems: 'center', animation: 'fadeIn .3s ease', flexWrap: 'wrap' }}>
                {/* Avatar */}
                <div style={{
                    width: 56, height: 56, borderRadius: '50%', flexShrink: 0,
                    background: 'linear-gradient(135deg, rgba(99,102,241,0.18), rgba(88,166,255,0.18))',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 20, fontWeight: 800, color: 'var(--color-primary)',
                }}>
                    {initials(guest.full_name)}
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                        <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--color-text)', margin: 0 }}>
                            {guest.full_name}
                        </h1>
                        {hasActiveStay ? (
                            <span style={{
                                display: 'inline-flex', alignItems: 'center', gap: 4,
                                padding: '3px 12px', borderRadius: 999,
                                background: 'rgba(63,185,80,0.1)', color: '#3fb850',
                                fontSize: 12, fontWeight: 700,
                            }}>
                                🟢 In Stay — {dossier.current_stay!.property_name}
                            </span>
                        ) : (
                            <span style={{
                                padding: '3px 12px', borderRadius: 999,
                                background: 'var(--color-surface-2)', color: 'var(--color-text-dim)',
                                fontSize: 12, fontWeight: 600,
                            }}>No Active Stay</span>
                        )}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
                        {guest.id}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 2 }}>
                        Created {fmtDate(guest.created_at, true)}
                        {guest.identity_verified_at && (
                            <span style={{ marginLeft: 12, color: '#3fb850' }}>✔ Identity verified {fmtDate(guest.identity_verified_at)}</span>
                        )}
                    </div>
                </div>

                {/* Quick contact summary */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'flex-end', fontSize: 12, color: 'var(--color-text-dim)', flexShrink: 0 }}>
                    {guest.phone && <span>📱 {guest.phone}</span>}
                    {guest.email && <span>📧 {guest.email}</span>}
                    {guest.nationality && <span>🌍 {guest.nationality}</span>}
                    {guest.preferred_channel && <span>💬 via {guest.preferred_channel}</span>}
                </div>
            </div>

            {/* PII notice */}
            <div style={{
                background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.18)',
                borderRadius: 8, padding: '8px 16px', marginBottom: 16,
                fontSize: 12, color: 'var(--color-text-dim)', display: 'flex', alignItems: 'center', gap: 8,
            }}>
                🔒 This dossier contains PII. Access is restricted to authorised staff only.
            </div>

            {/* ============================================================ */}
            {/* TAB BAR                                                       */}
            {/* ============================================================ */}
            <TabBar active={tab} tabs={tabs} onChange={setTab} />

            {/* ============================================================ */}
            {/* IDENTITY TAB                                                  */}
            {/* ============================================================ */}
            {tab === 'identity' && (
                <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', animation: 'fadeIn .2s ease' }}>
                    {/* Fields */}
                    <div style={{ ...cardStyle, flex: '1 1 340px', minWidth: 280 }}>
                        <SectionHeader title="Document Identity" />
                        <InfoRow label="Full Name" value={guest.full_name} />
                        <InfoRow label="Document Type" value={guest.document_type} />
                        <InfoRow label="Document No." value={guest.passport_no} mono />
                        <InfoRow label="Nationality" value={guest.nationality} />
                        <InfoRow label="Date of Birth" value={guest.date_of_birth ? fmtDateShort(guest.date_of_birth) : null} />
                        <InfoRow label="Expiry Date" value={guest.passport_expiry ? fmtDateShort(guest.passport_expiry) : null} />
                        <InfoRow label="Issuing Country" value={guest.issuing_country} />
                        <InfoRow label="Identity Source" value={guest.identity_source} />
                        <InfoRow label="Verified At" value={guest.identity_verified_at ? fmtDate(guest.identity_verified_at, true) : null} />
                        {guest.notes && <InfoRow label="Notes" value={guest.notes} />}
                    </div>

                    {/* Passport image */}
                    <div style={{ ...cardStyle, flex: '0 0 220px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minWidth: 180 }}>
                        <SectionHeader title="Document Photo" />
                        {dossier.document_photo_signed_url ? (
                            <a href={dossier.document_photo_signed_url} target="_blank" rel="noopener noreferrer">
                                <img
                                    src={dossier.document_photo_signed_url}
                                    alt="Passport"
                                    style={{
                                        width: 180, maxHeight: 240, objectFit: 'contain',
                                        borderRadius: 8, border: '1px solid var(--color-border)', cursor: 'pointer',
                                    }}
                                />
                                <div style={{ fontSize: 11, color: 'var(--color-primary)', textAlign: 'center', marginTop: 8 }}>
                                    Click to view full size ↗
                                </div>
                                <div style={{ fontSize: 10, color: 'var(--color-muted)', textAlign: 'center', marginTop: 2 }}>
                                    Link valid for 15 minutes
                                </div>
                            </a>
                        ) : (
                            <div style={{
                                width: 180, height: 220, borderRadius: 8,
                                background: 'var(--color-surface-2)', border: '1px dashed var(--color-border)',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                fontSize: 13, color: 'var(--color-muted)', textAlign: 'center', padding: 16,
                            }}>
                                No document photo on file
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* ============================================================ */}
            {/* CONTACT TAB                                                   */}
            {/* ============================================================ */}
            {tab === 'contact' && (
                <div style={{ ...cardStyle, animation: 'fadeIn .2s ease' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                        <SectionHeader title="Communication Channels" />
                        {editingContact ? (
                            <div style={{ display: 'flex', gap: 8 }}>
                                <button onClick={saveContact} disabled={savingContact} style={{ padding: '4px 14px', background: 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
                                    {savingContact ? 'Saving…' : 'Save'}
                                </button>
                                <button onClick={() => setEditingContact(false)} style={{ padding: '4px 14px', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 8, fontSize: 12, cursor: 'pointer', color: 'var(--color-text)' }}>Cancel</button>
                            </div>
                        ) : (
                            <button onClick={() => setEditingContact(true)} style={{ padding: '4px 14px', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 8, fontSize: 12, cursor: 'pointer', fontWeight: 600, color: 'var(--color-text)' }}>✎ Edit</button>
                        )}
                    </div>
                    {editingContact ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                            {[
                                { key: 'phone', label: '📱 Phone', placeholder: '+66 81 000 0000' },
                                { key: 'email', label: '📧 Email', placeholder: 'guest@example.com' },
                                { key: 'whatsapp', label: '💬 WhatsApp', placeholder: '+66 81 000 0000' },
                                { key: 'line_id', label: '🟢 LINE', placeholder: 'LINE ID' },
                                { key: 'telegram', label: '✈️ Telegram', placeholder: '@username' },
                            ].map(f => (
                                <div key={f.key} style={{ display: 'grid', gridTemplateColumns: '140px 1fr', alignItems: 'center', gap: 12 }}>
                                    <span style={labelStyle}>{f.label}</span>
                                    <input value={(contactForm as any)[f.key]} onChange={e => setContactForm(p => ({ ...p, [f.key]: e.target.value }))} placeholder={f.placeholder} style={inputStyle} />
                                </div>
                            ))}
                            <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', alignItems: 'center', gap: 12 }}>
                                <span style={labelStyle}>Preferred Channel</span>
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

            {/* ============================================================ */}
            {/* CURRENT STAY TAB                                              */}
            {/* ============================================================ */}
            {tab === 'stay' && (
                <div style={{ animation: 'fadeIn .2s ease' }}>
                    {dossier.current_stay ? (() => {
                        const stay = dossier.current_stay!;
                        const nights = nightCount(stay.check_in, stay.check_out);
                        return (
                            <>
                                {/* Booking header */}
                                <div style={cardStyle}>
                                    <SectionHeader title="🏠 Active Stay" />
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                                        <div>
                                            <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--color-text)' }}>{stay.property_name}</div>
                                            <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginTop: 4 }}>
                                                {fmtDateShort(stay.check_in)} → {fmtDateShort(stay.check_out)}{nights != null ? ` · ${nights} nights` : ''}
                                            </div>
                                        </div>
                                        <StatusBadge status={stay.status} />
                                    </div>
                                    <InfoRow label="Booking ID" value={stay.booking_id.slice(0, 24) + '…'} mono />
                                    {stay.source && <InfoRow label="Source" value={stay.source} />}
                                    {stay.reservation_ref && <InfoRow label="Reservation Ref" value={stay.reservation_ref} mono />}
                                </div>

                                {/* Check-in record */}
                                <CheckinRecordBlock record={stay.checkin_record} />

                                {/* Portal / QR */}
                                <PortalBlock portal={stay.portal} />

                                {/* Settlement */}
                                <SettlementBlock stay={stay} />
                            </>
                        );
                    })() : (
                        <div style={{ ...cardStyle, textAlign: 'center', padding: 48 }}>
                            <div style={{ fontSize: 32, marginBottom: 8 }}>🏡</div>
                            <div style={{ fontSize: 14, color: 'var(--color-text-dim)', fontWeight: 600 }}>No Active Stay</div>
                            <div style={{ fontSize: 12, color: 'var(--color-muted)', marginTop: 4 }}>
                                This guest is not currently checked in.
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* ============================================================ */}
            {/* HISTORY TAB                                                   */}
            {/* ============================================================ */}
            {tab === 'history' && (
                <div style={{ animation: 'fadeIn .2s ease' }}>
                    <div style={sectionTitleStyle}>
                        {(dossier.stay_history.length + (hasActiveStay ? 1 : 0))} stay{dossier.stay_history.length + (hasActiveStay ? 1 : 0) !== 1 ? 's' : ''} on record
                    </div>
                    {!hasActiveStay && dossier.stay_history.length === 0 ? (
                        <div style={{ ...cardStyle, textAlign: 'center', padding: 48 }}>
                            <div style={{ fontSize: 13, color: 'var(--color-muted)' }}>
                                No stay records linked to this guest yet.
                            </div>
                            <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginTop: 8 }}>
                                Stays appear here when a booking is linked to this guest during check-in.
                            </div>
                        </div>
                    ) : (
                        <>
                            {dossier.current_stay && (
                                <StayCard
                                    stay={dossier.current_stay}
                                    expanded={expandedStay === dossier.current_stay.booking_id}
                                    onToggle={() => setExpandedStay(s => s === dossier.current_stay!.booking_id ? null : dossier.current_stay!.booking_id)}
                                />
                            )}
                            {dossier.stay_history.map(s => (
                                <StayCard
                                    key={s.booking_id}
                                    stay={s}
                                    expanded={expandedStay === s.booking_id}
                                    onToggle={() => setExpandedStay(p => p === s.booking_id ? null : s.booking_id)}
                                />
                            ))}
                        </>
                    )}
                </div>
            )}

            {/* ============================================================ */}
            {/* ACTIVITY TAB                                                  */}
            {/* ============================================================ */}
            {tab === 'activity' && (
                <div style={{ animation: 'fadeIn .2s ease' }}>
                    <div style={sectionTitleStyle}>{dossier.activity.length} events recorded</div>
                    {dossier.activity.length === 0 ? (
                        <div style={{ ...cardStyle, textAlign: 'center', color: 'var(--color-muted)', fontSize: 13, padding: 48 }}>
                            No activity recorded yet.
                        </div>
                    ) : (
                        <div style={{ position: 'relative', paddingLeft: 28 }}>
                            <div style={{ position: 'absolute', left: 9, top: 8, bottom: 8, width: 2, background: 'var(--color-border)' }} />
                            {dossier.activity.map((ev, i) => (
                                <div key={i} style={{ position: 'relative', marginBottom: 12 }}>
                                    <div style={{
                                        position: 'absolute', left: -22, top: 4,
                                        width: 20, height: 20, borderRadius: '50%',
                                        background: 'var(--color-surface)', border: '2px solid var(--color-border)',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10,
                                    }}>
                                        {actionIcon(ev.action)}
                                    </div>
                                    <div style={{ ...cardStyle, marginBottom: 0, padding: '10px 16px' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)' }}>
                                                {actionLabel(ev.action)}
                                            </span>
                                            <span style={{ fontSize: 11, color: 'var(--color-muted)' }}>
                                                {fmtDate(ev.performed_at, true)}
                                            </span>
                                        </div>
                                        {ev.actor_id && (
                                            <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginTop: 2 }}>
                                                by {ev.actor_id.slice(0, 12)}…
                                            </div>
                                        )}
                                        {ev.details && Object.keys(ev.details).length > 0 && (
                                            <div style={{ fontSize: 10, color: 'var(--color-text-faint)', marginTop: 4, fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>
                                                {JSON.stringify(ev.details).slice(0, 100)}
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
