'use client';

/**
 * Phase 979 — Guest Dossier (Hardened Implementation)
 * Route: /guests/[id]
 *
 * Fixes applied:
 *   1. Check-in status contradiction resolved — reads status + checked_in_at aligned
 *   2. Portal/QR block made actionable with Generate/Send/Resend actions
 *   3. Current Stay shows full operational data
 *   4. Activity wired to real audit_events + admin_audit_log
 *   5. History stays have full expandable lifecycle structure
 *   6. Contact has proper empty state with CTA
 *   7. Extras & Orders section added (future-ready)
 *   8. Checkout Record section structured for future
 *   9. All sections connected to real system state
 */

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import {
    api, apiFetch, Guest, GuestDossier, DossierStay, DossierActivity,
    DossierPhoto, DossierCheckinRecord, DossierPortal, DossierMeter
} from '../../../../lib/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
// Operational timezone — iHouse operates in Thailand (ICT = UTC+7).
// All datetime values stored in the DB are UTC (TIMESTAMPTZ).
// Effective checkout times and event timestamps are always displayed in ICT
// so operational staff see the correct local time without manual conversion.
// ---------------------------------------------------------------------------
const OPS_TZ = 'Asia/Bangkok';

type TabId = 'identity' | 'contact' | 'stay' | 'history' | 'activity';

function fmtDate(s: string | null | undefined, withTime = false) {
    if (!s) return '—';
    const opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short', year: 'numeric', timeZone: OPS_TZ };
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

/** Determine if a booking is effectively checked in, using status as primary truth */
function isCheckedIn(stay: DossierStay): boolean {
    const s = stay.status?.toLowerCase() || '';
    return ['checked_in', 'instay', 'checkedin', 'active'].includes(s);
}

/** Human-readable booking source label from raw source string or booking ID prefix */
function fmtSource(source: string | null | undefined, bookingId?: string): string {
    if (!source && !bookingId) return 'Unknown';
    // Derive hint from iCal booking ID prefix
    const idHint = (bookingId || '').startsWith('ICAL-') ? 'ical' : '';
    const s = (source || idHint || '').toLowerCase();
    if (s.includes('airbnb') || s === 'airbnb') return 'Airbnb iCal';
    if (s.includes('booking') || s === 'booking_com') return 'Booking.com iCal';
    if (s.includes('ical') || s === 'ota') {
        // Guess from reservation ref if available
        return 'OTA iCal';
    }
    if (s === 'direct') return 'Direct';
    if (s === 'manual') return 'Manual';
    if (s === 'api') return 'API';
    if (s === 'import' || s === 'imported') return 'Imported';
    // Capitalise anything else cleanly
    return source ? source.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) : 'Unknown';
}

/** Borderless copy utility — inline text, no box */
function CopyBtn({ value }: { value: string }) {
    const [copied, setCopied] = useState(false);
    const [hover, setHover] = useState(false);
    return (
        <span
            role="button"
            tabIndex={0}
            onClick={(e) => {
                e.stopPropagation();
                navigator.clipboard.writeText(value).then(() => {
                    setCopied(true);
                    setTimeout(() => setCopied(false), 1500);
                });
            }}
            onMouseEnter={() => setHover(true)}
            onMouseLeave={() => setHover(false)}
            onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.click()}
            style={{
                display: 'inline-flex', alignItems: 'center',
                marginLeft: 5, padding: '0 2px',
                fontSize: 9, fontWeight: 700, lineHeight: '14px',
                color: copied ? '#3fb850' : hover ? 'var(--color-primary)' : 'var(--color-muted)',
                cursor: 'pointer', userSelect: 'none',
                transition: 'color .12s',
                letterSpacing: '0.03em',
            }}
            title={`Copy: ${value}`}
        >
            {copied ? '✓ copied' : 'copy'}
        </span>
    );
}

/** Compact view of a long string: truncated + copy, full value on title tooltip */
function CompactRef({ value, maxChars = 28, mono = true }: { value: string; maxChars?: number; mono?: boolean }) {
    const truncated = value.length > maxChars ? value.slice(0, maxChars) + '…' : value;
    return (
        <span style={{ display: 'inline-flex', alignItems: 'center' }}>
            <span
                title={value}
                style={{
                    fontFamily: mono ? 'var(--font-mono)' : undefined,
                    fontSize: 12, color: 'var(--color-text)',
                    cursor: value.length > maxChars ? 'help' : 'default',
                }}
            >
                {truncated}
            </span>
            <CopyBtn value={value} />
        </span>
    );
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
        'booking.checkout': 'Checkout completed',
        checkin_override_deposit_skipped: 'Deposit override — skipped',
        checkin_override_meter_skipped: 'Meter override — skipped',
        meter_reading_corrected: 'Meter reading corrected',
        TASK_COMPLETED: 'Task completed',
        ACT_AS_STARTED: 'Admin acting session started',
        qr_token_generated: 'Guest portal QR generated',
        portal_link_sent: 'Portal link sent to guest',
        // Early checkout lifecycle
        'early_checkout.request_received': 'Early Check-out Requested',
        'early_checkout.approved':         'Early Check-out Approved',
        'early_checkout.revoked':          'Early Check-out Revoked',
        'early_checkout.completed':        'Early Check-out Completed',
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
        'booking.checkout': '🚪',
        checkin_override_deposit_skipped: '⚠️',
        checkin_override_meter_skipped: '⚠️',
        meter_reading_corrected: '🔧',
        TASK_COMPLETED: '☑️',
        ACT_AS_STARTED: '🔑',
        qr_token_generated: '🔗',
        portal_link_sent: '📤',
        // Early checkout lifecycle
        'early_checkout.request_received': '🔴',
        'early_checkout.approved':         '⚡',
        'early_checkout.revoked':          '↩️',
        'early_checkout.completed':        '🏁',
    };
    return map[action] || '📋';
}

function statusColor(status: string | null | undefined): { bg: string; fg: string } {
    const s = (status || '').toLowerCase();
    if (['instay', 'checkedin', 'checked_in', 'active'].includes(s))
        return { bg: 'rgba(63,185,80,0.12)', fg: '#3fb850' };
    if (['confirmed'].includes(s))
        return { bg: 'rgba(88,166,255,0.12)', fg: '#58a6ff' };
    if (['checkedout', 'checked_out', 'completed'].includes(s))
        return { bg: 'rgba(139,148,158,0.12)', fg: 'var(--color-text-dim)' };
    if (['cancelled', 'canceled'].includes(s))
        return { bg: 'rgba(239,68,68,0.12)', fg: '#ef4444' };
    return { bg: 'var(--color-surface-2)', fg: 'var(--color-text-dim)' };
}

function StatusBadge({ status }: { status?: string | null }) {
    const s = status || 'Unknown';
    const c = statusColor(s);
    // Human-readable display label
    const displayMap: Record<string, string> = {
        checked_in: 'In Stay',
        CheckedIn:  'In Stay',
        instay:     'In Stay',
        active:     'In Stay',
        completed:  'Completed',
        CheckedOut: 'Checked Out',
        checked_out:'Checked Out',
        Cancelled:  'Cancelled',
        cancelled:  'Cancelled',
        Confirmed:  'Upcoming',
        confirmed:  'Upcoming',
    };
    const label = displayMap[s] ?? s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    return (
        <span style={{
            display: 'inline-block', padding: '2px 10px', borderRadius: 999,
            background: c.bg, color: c.fg, fontSize: 12, fontWeight: 700,
        }}>{label}</span>
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
            <span style={value != null && value !== '' ? { ...valueStyle, fontFamily: mono ? 'var(--font-mono)' : undefined } : mutedStyle}>
                {value != null && value !== '' ? value : '—'}
            </span>
        </div>
    );
}

function SectionHeader({ title }: { title: string }) {
    return <div style={sectionTitleStyle}>{title}</div>;
}

const btnPrimary: React.CSSProperties = {
    padding: '6px 16px', background: 'var(--color-primary)', color: '#fff',
    border: 'none', borderRadius: 8, fontSize: 12, fontWeight: 600,
    cursor: 'pointer', transition: 'opacity .15s',
};
const btnSecondary: React.CSSProperties = {
    padding: '6px 16px', background: 'var(--color-surface-2)', color: 'var(--color-text)',
    border: '1px solid var(--color-border)', borderRadius: 8, fontSize: 12, fontWeight: 600,
    cursor: 'pointer', transition: 'opacity .15s',
};
const btnDisabled: React.CSSProperties = { ...btnSecondary, opacity: 0.4, cursor: 'not-allowed' };

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
// Portal Block — tight action card
// ---------------------------------------------------------------------------

function PortalBlock({
    portal, guest, stay, onGeneratePortalFull,
}: {
    portal: DossierPortal;
    guest: Guest;
    stay: DossierStay;
    /** Called on Generate — resolves with the fresh portal URL to open */
    onGeneratePortalFull?: () => Promise<string>;
}) {
    const [generating, setGenerating] = useState(false);
    const [genError, setGenError] = useState<string | null>(null);
    // freshUrl: set after generation, shown as copyable link + mailto
    const [freshUrl, setFreshUrl] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);

    const checkedIn = isCheckedIn(stay);
    const generated = portal.qr_generated;

    // Effective URL — either just-generated or existing portal_url
    const activeUrl = freshUrl || portal.portal_url || null;

    const handleGenerate = async () => {
        if (!onGeneratePortalFull || generating) return;
        setGenerating(true);
        setGenError(null);
        try {
            const url = await onGeneratePortalFull();
            setFreshUrl(url);
            // Open the portal in a new tab immediately
            window.open(url, '_blank', 'noopener,noreferrer');
        } catch (err: unknown) {
            const e = err as { message?: string };
            setGenError(e?.message || 'Failed to generate portal link. Check API connectivity.');
        } finally {
            setGenerating(false);
        }
    };

    const copyUrl = () => {
        if (!activeUrl) return;
        navigator.clipboard.writeText(activeUrl).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        });
    };

    const mailtoHref = activeUrl
        ? `mailto:${guest.email || ''}?subject=${encodeURIComponent('Your Stay Portal — ' + (stay.property_name || 'iHouse'))}&body=${encodeURIComponent('Here is your personal guest portal link:\n\n' + activeUrl + '\n\nThis link gives you access to your stay information, home guide, and departure instructions.')}`
        : '#';

    // Status display
    const isReady = generated || !!freshUrl;
    const statusLabel = freshUrl
        ? '🔗 Portal Generated'
        : generated ? '🔗 Portal Ready' : '⬜ Portal Not Yet Generated';
    const statusColor = isReady ? '#3fb850' : 'var(--color-text-dim)';

    return (
        <div style={{
            ...cardStyle,
            background: isReady ? 'rgba(63,185,80,0.04)' : 'var(--color-surface)',
            borderColor: isReady ? 'rgba(63,185,80,0.2)' : 'var(--color-border)',
            padding: '16px 20px',
        }}>
            {/* Header row: status + primary action inline */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: statusColor }}>
                    {statusLabel}
                </span>

                {/* Not yet generated + checked in → Generate button */}
                {!isReady && checkedIn && (
                    <button
                        style={{ ...btnPrimary, padding: '5px 14px', opacity: generating ? 0.6 : 1 }}
                        disabled={generating || !onGeneratePortalFull}
                        onClick={handleGenerate}
                        title="Generate guest portal link and open in new tab"
                    >
                        {generating ? '⏳ Generating…' : '🔗 Generate QR'}
                    </button>
                )}

                {/* Not generated + not checked in */}
                {!isReady && !checkedIn && (
                    <span style={{ fontSize: 11, color: 'var(--color-muted)' }}>Awaiting check-in</span>
                )}

                {/* Already existed before this session — open portal */}
                {isReady && !freshUrl && activeUrl && (
                    <a
                        href={activeUrl} target="_blank" rel="noopener noreferrer"
                        style={{ ...btnSecondary, textDecoration: 'none', padding: '5px 14px', fontSize: 12 }}
                    >
                        ↗ Open Portal
                    </a>
                )}

                {/* Regenerate if already ready */}
                {isReady && checkedIn && (
                    <button
                        style={{ ...btnSecondary, padding: '5px 14px', opacity: generating ? 0.6 : 1 }}
                        disabled={generating || !onGeneratePortalFull}
                        onClick={handleGenerate}
                        title="Regenerate and open a new portal link"
                    >
                        {generating ? '⏳…' : '🔄 Regenerate'}
                    </button>
                )}
            </div>

            {/* Meta: issued/expires */}
            {(portal.issued_at || portal.expires_at) && !freshUrl && (
                <div style={{ fontSize: 11, color: 'var(--color-muted)', marginBottom: 8 }}>
                    {portal.issued_at && <>issued {fmtDate(portal.issued_at, true)}</>}
                    {portal.expires_at && <> · expires {fmtDate(portal.expires_at, true)}</>}
                </div>
            )}

            {/* Error */}
            {genError && (
                <div style={{
                    margin: '6px 0', padding: '6px 10px', borderRadius: 6,
                    background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
                    fontSize: 12, color: '#ef4444',
                }}>
                    ⚠ {genError}
                </div>
            )}

            {/* Post-generation panel: URL + Copy + Mailto */}
            {activeUrl && (
                <div style={{
                    marginTop: 8, padding: '10px 14px',
                    background: 'var(--color-surface-2)', borderRadius: 8,
                    border: '1px solid var(--color-border)',
                }}>
                    {/* Portal URL — copyable */}
                    <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginBottom: 6, wordBreak: 'break-all' }}>
                        <span style={{ fontWeight: 600, marginRight: 6 }}>Link:</span>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                            {activeUrl.length > 60 ? activeUrl.slice(0, 58) + '…' : activeUrl}
                        </span>
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        {/* Open in new tab */}
                        <a
                            href={activeUrl} target="_blank" rel="noopener noreferrer"
                            style={{ ...btnPrimary, textDecoration: 'none', padding: '4px 12px', fontSize: 11 }}
                        >
                            ↗ Open Portal
                        </a>
                        {/* Copy link */}
                        <button
                            onClick={copyUrl}
                            style={{ ...btnSecondary, padding: '4px 12px', fontSize: 11 }}
                        >
                            {copied ? '✓ Copied!' : '📋 Copy Link'}
                        </button>
                        {/* Mailto */}
                        <a
                            href={mailtoHref}
                            style={{ ...btnSecondary, textDecoration: 'none', padding: '4px 12px', fontSize: 11 }}
                            title={guest.email ? `Send to ${guest.email}` : 'No email on file — opens default mail client'}
                        >
                            📧 Send Email
                        </a>
                    </div>
                </div>
            )}
        </div>
    );
}


// ---------------------------------------------------------------------------
// Check-in Record Block — compact with expandable operational detail
// ---------------------------------------------------------------------------

/** Small pill chips to summarise operational coverage at a glance */
function CheckinChip({ ok, label }: { ok: boolean; label: string }) {
    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            padding: '2px 9px', borderRadius: 999, fontSize: 11, fontWeight: 600,
            background: ok ? 'rgba(63,185,80,0.1)' : 'var(--color-surface-2)',
            color: ok ? '#3fb850' : 'var(--color-text-dim)',
            border: `1px solid ${ok ? 'rgba(63,185,80,0.2)' : 'var(--color-border)'}`,
        }}>
            {ok ? '✓' : '–'} {label}
        </span>
    );
}

function CheckinRecordBlock({ record, stayStatus }: { record: DossierCheckinRecord; stayStatus: string | null }) {
    const statusIsCheckedIn = ['checked_in', 'instay', 'checkedin', 'active'].includes((stayStatus || '').toLowerCase());
    const effectivelyCompleted = !!record.checked_in_at || statusIsCheckedIn;
    const [showDetail, setShowDetail] = useState(false);

    const hasWalkthrough = record.walkthrough_photos.length > 0;
    const hasMeter = !!record.opening_meter;
    const checkedInBy = (record as any).checked_in_by;

    return (
        <div style={{ ...cardStyle, padding: '14px 20px' }}>
            {/* Header row */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: effectivelyCompleted ? 10 : 0 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    ✅ Check-in Record
                </span>
                {effectivelyCompleted && (
                    <button
                        onClick={() => setShowDetail(d => !d)}
                        style={{ ...btnSecondary, padding: '2px 10px', fontSize: 11 }}
                    >
                        {showDetail ? 'Less ▲' : 'Details ▼'}
                    </button>
                )}
            </div>

            {!effectivelyCompleted ? (
                <div style={{
                    padding: '10px 14px', borderRadius: 8,
                    background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.2)',
                    fontSize: 12, color: 'var(--color-text-dim)', display: 'flex', alignItems: 'center', gap: 8,
                }}>
                    ⏳ Check-in not yet completed
                </div>
            ) : (
                <>
                    {/* Summary line */}
                    <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginBottom: 8 }}>
                        {record.checked_in_at
                            ? fmtDate(record.checked_in_at, true)
                            : 'Timestamp not recorded (legacy check-in)'}
                        {checkedInBy && (
                            <span style={{ marginLeft: 8, color: 'var(--color-muted)' }}>
                                · by {checkedInBy.length > 20 ? checkedInBy.slice(0, 16) + '…' : checkedInBy}
                            </span>
                        )}
                    </div>

                    {/* Coverage chips */}
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        <CheckinChip ok label="Check-in" />
                        <CheckinChip ok={hasWalkthrough} label="Walk-through" />
                        <CheckinChip ok={hasMeter} label="Meter" />
                    </div>

                    {/* Expanded operational detail */}
                    {showDetail && (
                        <div style={{ marginTop: 14, borderTop: '1px solid var(--color-border)', paddingTop: 14, animation: 'fadeIn .15s ease' }}>
                            {hasMeter && (
                                <>
                                    <div style={{ ...sectionTitleStyle, marginBottom: 8 }}>⚡ Opening Meter</div>
                                    <InfoRow label="Reading" value={`${record.opening_meter!.meter_value} ${record.opening_meter!.meter_unit}`} />
                                    <InfoRow label="Recorded" value={fmtDate(record.opening_meter!.recorded_at, true)} />
                                    {record.meter_photos.length > 0 && (
                                        <PhotoGrid photos={record.meter_photos} title="Meter Photos" />
                                    )}
                                </>
                            )}
                            {hasWalkthrough
                                ? <PhotoGrid photos={record.walkthrough_photos} title="Walk-Through Photos" />
                                : <div style={{ fontSize: 12, color: 'var(--color-muted)', marginTop: 8 }}>No walk-through photos indexed.</div>
                            }
                        </div>
                    )}
                </>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Settlement Block (Issue #3 — richer data)
// ---------------------------------------------------------------------------

function SettlementBlock({ stay }: { stay: DossierStay }) {
    const { deposit, meter_readings } = stay.settlement;
    const openingMeter = meter_readings.find(m => m.reading_type === 'opening');
    const closingMeter = meter_readings.find(m => m.reading_type === 'closing');
    const hasAny = deposit || openingMeter || closingMeter;

    return (
        <div style={cardStyle}>
            <SectionHeader title="💳 Settlement" />

            {!hasAny ? (
                <div style={{
                    padding: '12px 16px', borderRadius: 8,
                    background: 'var(--color-surface-2)', border: '1px dashed var(--color-border)',
                    display: 'flex', alignItems: 'center', gap: 10,
                }}>
                    <span style={{ fontSize: 18 }}>💳</span>
                    <div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-dim)' }}>No settlement data recorded</div>
                        <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 2 }}>
                            Deposit · opening meter · checkout settlement will appear here.
                        </div>
                    </div>
                </div>
            ) : (
                <>
                    {deposit && (
                        <>
                            <SectionHeader title="💰 Security Deposit" />
                            <InfoRow label="Amount" value={`${deposit.currency} ${deposit.amount}`} />
                            <InfoRow label="Status" value={deposit.status} />
                            <InfoRow label="Collected At" value={fmtDate(deposit.collected_at, true)} />
                            {deposit.collected_by && <InfoRow label="Collected By" value={deposit.collected_by} />}
                            {deposit.notes && <InfoRow label="Notes" value={deposit.notes} />}
                            {deposit.refund_amount != null && (
                                <InfoRow label="Refund Amount" value={`${deposit.currency} ${deposit.refund_amount}`} />
                            )}
                        </>
                    )}
                    {openingMeter && (
                        <div style={{ marginTop: deposit ? 16 : 0 }}>
                            <SectionHeader title="⚡ Electricity — Opening" />
                            <InfoRow label="Reading" value={`${openingMeter.meter_value} ${openingMeter.meter_unit}`} />
                            <InfoRow label="Recorded At" value={fmtDate(openingMeter.recorded_at, true)} />
                            {openingMeter.recorded_by && <InfoRow label="Recorded By" value={openingMeter.recorded_by} />}
                        </div>
                    )}
                    {closingMeter && (
                        <div style={{ marginTop: 16 }}>
                            <SectionHeader title="⚡ Electricity — Closing" />
                            <InfoRow label="Reading" value={`${closingMeter.meter_value} ${closingMeter.meter_unit}`} />
                            <InfoRow label="Recorded At" value={fmtDate(closingMeter.recorded_at, true)} />
                            {openingMeter && (
                                <InfoRow
                                    label="Units Consumed"
                                    value={`${(closingMeter.meter_value - openingMeter.meter_value).toFixed(1)} ${closingMeter.meter_unit}`}
                                />
                            )}
                        </div>
                    )}
                </>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Extras & Orders Block — compact spacer, future-ready
// ---------------------------------------------------------------------------

function ExtrasOrdersBlock() {
    return (
        <div style={{ ...cardStyle, padding: '12px 20px', display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 16 }}>🛎️</span>
            <div style={{ flex: 1 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-dim)' }}>Extras & Orders</span>
                <span style={{ fontSize: 11, color: 'var(--color-muted)', marginLeft: 8 }}>
                    No concierge orders yet — portal ordering coming soon
                </span>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Checkout Record Block — compact, future-ready
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Early Check-out Block — surfaces exception state inside a stay record
// ---------------------------------------------------------------------------

function EarlyCheckoutBlock({ stay }: { stay: DossierStay }) {
    const ec = stay.early_checkout;
    if (!ec || ec.status === 'none' || !ec.status) return null;

    const statusConfig = {
        requested: { label: '⏳ Request Received', bg: '#fef3c7', border: '#fde68a', fg: '#92400e' },
        approved:  { label: '⚡ Exception Approved', bg: 'rgba(217,119,6,0.08)', border: '#fde68a', fg: '#b45309' },
        completed: { label: '🏁 Early Checkout Completed', bg: 'rgba(63,185,80,0.08)', border: 'rgba(63,185,80,0.3)', fg: '#15803d' },
    }[ec.status] ?? { label: ec.status, bg: 'var(--color-surface-2)', border: 'var(--color-border)', fg: 'var(--color-text-dim)' };

    function fmtDt(d: string | null | undefined): string {
        if (!d) return '—';
        // Display in operational timezone (ICT = UTC+7) so staff see correct local time.
        // DB stores TIMESTAMPTZ in UTC; e.g. '2026-04-05 11:00:00+00' → '6:00 PM ICT'.
        try { return new Date(d).toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: OPS_TZ }); }
        catch { return d; }
    }
    function fmtD(d: string | null | undefined): string {
        if (!d) return '—';
        try { return new Date(d + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }); }
        catch { return d; }
    }

    const sourceLabels: Record<string, string> = {
        phone: '📞 Phone call', message: '💬 Message',
        guest_portal: '🌐 Guest portal', ops_escalation: '⚡ Ops escalation', other: 'Other',
    };

    return (
        <div style={{
            ...cardStyle, padding: '14px 20px',
            background: statusConfig.bg,
            borderColor: statusConfig.border,
            borderWidth: 1,
        }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: statusConfig.fg, textTransform: 'uppercase' as const, letterSpacing: '0.05em' }}>
                    🔴 Early Check-out
                </span>
                <span style={{ fontSize: 12, fontWeight: 700, color: statusConfig.fg }}>
                    {statusConfig.label}
                </span>
            </div>

            {/* Dates */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px', fontSize: 12, marginBottom: 8 }}>
                <div style={{ color: 'var(--color-text-dim)', fontWeight: 600, fontSize: 10, textTransform: 'uppercase' as const, letterSpacing: '0.05em' }}>Original Checkout</div>
                <div style={{ color: 'var(--color-text-dim)', fontWeight: 600, fontSize: 10, textTransform: 'uppercase' as const, letterSpacing: '0.05em' }}>
                    {ec.status === 'approved' || ec.status === 'completed' ? 'Effective Early Checkout' : 'Proposed Date'}
                </div>
                <div style={{ fontWeight: 600, color: 'var(--color-text)' }}>{fmtD(ec.original_checkout_date || stay.check_out)}</div>
                <div style={{ fontWeight: 700, color: '#b45309' }}>
                    {ec.effective_at ? fmtDt(ec.effective_at) : ec.effective_date ? fmtD(ec.effective_date) : '—'}
                </div>
            </div>

            {/* Reason / note */}
            {ec.reason && (
                <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginBottom: 4 }}>
                    <span style={{ fontWeight: 600, marginRight: 6 }}>Reason:</span>{ec.reason}
                </div>
            )}
            {ec.request_source && (
                <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginBottom: 4 }}>
                    <span style={{ fontWeight: 600, marginRight: 6 }}>Source:</span>{sourceLabels[ec.request_source] || ec.request_source}
                </div>
            )}

            {/* Deep link to canonical control surface */}
            <div style={{ marginTop: 10, borderTop: '1px solid ' + statusConfig.border, paddingTop: 10, display: 'flex', justifyContent: 'flex-end' }}>
                <a
                    href={`/admin/bookings/${stay.booking_id}/early-checkout`}
                    style={{ fontSize: 11, fontWeight: 600, color: '#b45309', textDecoration: 'none' }}
                >
                    Manage in Booking →
                </a>
            </div>
        </div>
    );
}

function CheckoutRecordBlock({ stay }: { stay: DossierStay }) {
    const record = stay.checkout_record;
    const checkedOut = record?.checked_out_at || (stay.status?.toLowerCase() === 'checked_out');
    const [showDetail, setShowDetail] = useState(false);

    if (checkedOut && record) {
        const sr = record.settlement;
        const hasSettlement = !!sr;
        const hasPhotos = record.checkout_photos && record.checkout_photos.length > 0;
        const hasMeter = !!record.closing_meter;

        return (
            <div style={{ ...cardStyle, padding: '14px 20px' }}>
                {/* Header row */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        🚪 Checkout Record
                    </span>
                    <button
                        onClick={() => setShowDetail(d => !d)}
                        style={{ ...btnSecondary, padding: '2px 10px', fontSize: 11 }}
                    >
                        {showDetail ? 'Less ▲' : 'Details ▼'}
                    </button>
                </div>

                {/* Summary line */}
                <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginBottom: 8 }}>
                    {record.checked_out_at
                        ? fmtDate(record.checked_out_at, true)
                        : 'Timestamp not recorded'}
                    {record.checked_out_by && (
                        <span style={{ marginLeft: 8, color: 'var(--color-muted)' }}>
                            · by {record.checked_out_by.length > 20 ? record.checked_out_by.slice(0, 16) + '…' : record.checked_out_by}
                        </span>
                    )}
                </div>

                {/* Coverage chips */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    <CheckinChip ok label="Check-out" />
                    <CheckinChip ok={hasMeter} label="Closing Meter" />
                    <CheckinChip ok={hasSettlement} label="Settlement" />
                    <CheckinChip ok={hasPhotos} label="Evidence" />
                </div>

                {/* Expanded detail */}
                {showDetail && (
                    <div style={{ marginTop: 14, borderTop: '1px solid var(--color-border)', paddingTop: 14, animation: 'fadeIn .15s ease' }}>
                        {/* Inspection notes */}
                        {record.inspection_notes && (
                            <>
                                <div style={{ ...sectionTitleStyle, marginBottom: 8 }}>📋 Inspection Notes</div>
                                <div style={{
                                    padding: '8px 12px', background: 'var(--color-surface-2)',
                                    borderRadius: 8, fontSize: 12, color: 'var(--color-text)',
                                    marginBottom: 12, whiteSpace: 'pre-wrap',
                                }}>
                                    {record.inspection_notes}
                                </div>
                            </>
                        )}

                        {/* Closing Meter */}
                        {hasMeter && (
                            <>
                                <div style={{ ...sectionTitleStyle, marginBottom: 8 }}>⚡ Closing Meter</div>
                                <InfoRow label="Reading" value={`${record.closing_meter!.meter_value} ${record.closing_meter!.meter_unit}`} />
                                <InfoRow label="Recorded" value={fmtDate(record.closing_meter!.recorded_at, true)} />
                            </>
                        )}

                        {/* Settlement */}
                        {hasSettlement && sr && (
                            <>
                                <div style={{ ...sectionTitleStyle, marginBottom: 8, marginTop: hasMeter ? 16 : 0 }}>💳 Settlement</div>
                                <InfoRow label="Status" value={sr.status} />
                                <InfoRow label="Deposit Held" value={sr.deposit_held != null ? `${sr.deposit_currency || 'THB'} ${sr.deposit_held}` : undefined} />
                                {sr.electricity_kwh_used != null && sr.electricity_kwh_used > 0 && (
                                    <>
                                        <InfoRow label="⚡ kWh Used" value={`${sr.electricity_kwh_used}`} />
                                        <InfoRow label="Rate" value={sr.electricity_rate_kwh != null ? `${sr.electricity_rate_kwh} /kWh` : undefined} />
                                        <InfoRow label="Electricity Charge" value={sr.electricity_charged != null ? `${sr.electricity_currency || 'THB'} ${sr.electricity_charged}` : undefined} />
                                    </>
                                )}
                                {sr.damage_deductions_total != null && sr.damage_deductions_total > 0 && (
                                    <InfoRow label="🔨 Damage" value={`${sr.deposit_currency || 'THB'} ${sr.damage_deductions_total}`} />
                                )}
                                {sr.miscellaneous_deductions_total != null && sr.miscellaneous_deductions_total > 0 && (
                                    <InfoRow label="📋 Miscellaneous" value={`${sr.deposit_currency || 'THB'} ${sr.miscellaneous_deductions_total}`} />
                                )}
                                <InfoRow label="Total Deductions" value={sr.total_deductions != null ? `${sr.deposit_currency || 'THB'} ${sr.total_deductions}` : undefined} />
                                <div style={{
                                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                    padding: '8px 0', borderTop: '2px solid var(--color-border)', marginTop: 8,
                                    fontWeight: 700, fontSize: 13, color: 'var(--color-text)',
                                }}>
                                    <span style={{ color: '#3fb850' }}>💵 Refund</span>
                                    <span style={{ color: '#3fb850' }}>
                                        {sr.deposit_currency || 'THB'} {sr.refund_amount ?? 0}
                                    </span>
                                </div>
                                {(sr.retained_amount ?? 0) > 0 && (
                                    <InfoRow label="Retained" value={`${sr.deposit_currency || 'THB'} ${sr.retained_amount}`} />
                                )}
                                {sr.finalized_at && (
                                    <InfoRow label="Finalized" value={fmtDate(sr.finalized_at, true)} />
                                )}
                            </>
                        )}

                        {/* Checkout Photos */}
                        {hasPhotos && (
                            <PhotoGrid photos={record.checkout_photos} title="Checkout Photos" />
                        )}
                    </div>
                )}
            </div>
        );
    }

    // Not yet checked out — show pending state with any early checkout context
    const ec = stay.early_checkout;
    const hasEarlyCheckout = ec && ec.status !== 'none' && !!ec.status;

    return (
        <div style={{ ...cardStyle, padding: '12px 20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 16 }}>🚪</span>
                <div style={{ flex: 1 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-dim)' }}>Checkout Record</span>
                    <span style={{ fontSize: 11, color: 'var(--color-muted)', marginLeft: 8 }}>
                        {isCheckedIn(stay) ? 'Guest in-stay · not yet performed' : 'No checkout data'}
                    </span>
                </div>
                {hasEarlyCheckout && (
                    <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: 4,
                        padding: '2px 9px', borderRadius: 999, fontSize: 11, fontWeight: 700,
                        background: ec!.status === 'approved' ? 'rgba(217,119,6,0.12)' : 'rgba(251,191,36,0.12)',
                        color: ec!.status === 'approved' ? '#b45309' : '#92400e',
                        border: '1px solid #fde68a',
                    }}>
                        🔴 Early Check-out
                    </span>
                )}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Stay Card (Issue #5 — deeper expandable structure)
// ---------------------------------------------------------------------------

function StayCard({ stay, guest, expanded, onToggle, onGeneratePortal }: {
    stay: DossierStay;
    guest: Guest;
    expanded: boolean;
    onToggle: () => void;
    onGeneratePortal?: (bookingId: string) => Promise<string>;
}) {
    const nights = nightCount(stay.check_in, stay.check_out);
    const deposit = stay.settlement?.deposit;
    const hasEarlyCheckout = stay.early_checkout && stay.early_checkout.status !== 'none' && !!stay.early_checkout.status;

    return (
        <div style={{ ...cardStyle, ...(expanded ? { borderColor: 'rgba(99,102,241,0.4)' } : {}) }}>
            {/* Header row — always visible */}
            <div onClick={onToggle} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}>
                <div>
                    <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--color-text)', display: 'flex', alignItems: 'center', gap: 8 }}>
                        {stay.property_name}
                        {hasEarlyCheckout && (
                            <span style={{
                                display: 'inline-flex', alignItems: 'center',
                                padding: '1px 7px', borderRadius: 999, fontSize: 10, fontWeight: 700,
                                background: 'rgba(217,119,6,0.12)', color: '#b45309', border: '1px solid #fde68a',
                            }}>🔴 Early C/O</span>
                        )}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginTop: 2 }}>
                        {fmtDateShort(stay.check_in)} → {fmtDateShort(stay.check_out)}{nights != null ? ` · ${nights} nights` : ''}
                    </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <StatusBadge status={stay.status} />
                    {stay.portal.qr_generated && <span title="Portal generated" style={{ fontSize: 16 }}>🔗</span>}
                    {deposit && <span title={`Deposit: ${deposit.currency} ${deposit.amount}`} style={{ fontSize: 16 }}>💰</span>}
                    <span style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{expanded ? '▲' : '▼'}</span>
                </div>
            </div>

            {/* Expanded detail — full lifecycle */}
            {expanded && (
                <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--color-border)', animation: 'fadeIn .2s ease' }}>
                    {/* Booking Header — compact */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px', fontSize: 12, marginBottom: 4 }}>
                        <div style={{ color: 'var(--color-text-dim)', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Source</div>
                        <div style={{ color: 'var(--color-text-dim)', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Ref</div>
                        <div style={{ fontWeight: 500, color: 'var(--color-text)' }}>{fmtSource(stay.source, stay.booking_id)}</div>
                        <div>{stay.reservation_ref ? <CompactRef value={stay.reservation_ref} maxChars={20} /> : <span style={{ color: 'var(--color-muted)' }}>—</span>}</div>
                    </div>

                    {/* Early Check-out Exception Block — surfaces before checkout record */}
                    <EarlyCheckoutBlock stay={stay} />

                    {/* Check-in Record */}
                    <div style={{ marginTop: 16 }}>
                        <CheckinRecordBlock record={stay.checkin_record} stayStatus={stay.status} />
                    </div>

                    {/* Portal / QR */}
                    <PortalBlock
                        portal={stay.portal}
                        guest={guest}
                        stay={stay}
                        onGeneratePortalFull={onGeneratePortal
                            ? () => onGeneratePortal(stay.booking_id)
                            : undefined
                        }
                    />

                    {/* Settlement */}
                    <SettlementBlock stay={stay} />

                    {/* Extras & Orders */}
                    <ExtrasOrdersBlock />

                    {/* Checkout Record */}
                    <CheckoutRecordBlock stay={stay} />
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
        } catch (err: unknown) {
            const apiErr = err as { status?: number; code?: string; message?: string };
            const status = apiErr?.status;
            if (status === 404) {
                setError('Guest not found (ID may be invalid).');
            } else if (status === 403) {
                setError('Access denied — insufficient permissions to view this dossier.');
            } else if (status === 500) {
                setError('Server error loading dossier (HTTP 500). The backend may be deploying — please retry in a moment.');
            } else if (status === 0 || !status) {
                setError('Cannot reach backend — check your connection or try again shortly.');
            } else {
                setError(`Failed to load dossier (HTTP ${status}). Please try again.`);
            }
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

    const totalStays = dossier.stay_history.length + (hasActiveStay ? 1 : 0);
    const tabs: { id: TabId; label: string; icon: string }[] = [
        { id: 'identity', label: 'Identity', icon: '🛂' },
        { id: 'contact', label: 'Contact', icon: '📱' },
        { id: 'stay', label: hasActiveStay ? 'Current Stay' : 'Stay', icon: '🏠' },
        { id: 'history', label: `History (${totalStays})`, icon: '📋' },
        { id: 'activity', label: `Activity (${dossier.activity.length})`, icon: '🕐' },
    ];

    const inputStyle: React.CSSProperties = {
        padding: '6px 10px', background: 'var(--color-surface-2)',
        border: '1px solid var(--color-border)', borderRadius: 8,
        color: 'var(--color-text)', fontSize: 13, width: '100%', boxSizing: 'border-box',
    };

    // Contact completeness
    const contactChannels = [
        { key: 'phone', label: '📱 Phone', value: guest.phone },
        { key: 'email', label: '📧 Email', value: guest.email },
        { key: 'whatsapp', label: '💬 WhatsApp', value: guest.whatsapp },
        { key: 'line_id', label: '🟢 LINE', value: guest.line_id },
        { key: 'telegram', label: '✈️ Telegram', value: guest.telegram },
    ];
    const hasAnyContact = contactChannels.some(c => !!c.value);

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
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                        <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--color-text)', margin: 0 }}>
                            {guest.full_name}
                        </h1>
                        {/* Header badge — only show when a genuinely current/upcoming stay exists */}
                        {dossier.current_stay && (() => {
                            const s = (dossier.current_stay.status || '').toLowerCase();
                            const isActive   = ['checked_in', 'instay', 'checkedin', 'active'].includes(s);
                            const isUpcoming = ['confirmed', 'booked', 'approved'].includes(s);
                            if (isActive) return (
                                <span style={{
                                    display: 'inline-flex', alignItems: 'center', gap: 4,
                                    padding: '3px 12px', borderRadius: 999,
                                    background: 'rgba(63,185,80,0.1)', color: '#3fb850',
                                    fontSize: 12, fontWeight: 700,
                                }}>
                                    🟢 In Stay — {dossier.current_stay.property_name}
                                </span>
                            );
                            if (isUpcoming) return (
                                <span style={{
                                    display: 'inline-flex', alignItems: 'center', gap: 4,
                                    padding: '3px 12px', borderRadius: 999,
                                    background: 'rgba(88,166,255,0.1)', color: '#58a6ff',
                                    fontSize: 12, fontWeight: 700,
                                }}>
                                    📅 Upcoming — {dossier.current_stay.property_name}
                                </span>
                            );
                            return null;
                        })()}
                    </div>

                    {/* Sub-line: guest record metadata only, no stay-level signals */}
                    <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
                        {guest.id}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 2, display: 'flex', flexWrap: 'wrap', gap: 10 }}>
                        <span>Guest record created {fmtDate(guest.created_at, true)}</span>
                        {guest.identity_verified_at && (
                            <span style={{ color: '#3fb850' }}>✔ Identity verified {fmtDate(guest.identity_verified_at)}</span>
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
            {/* CONTACT TAB (Issue #6 — better empty state)                   */}
            {/* ============================================================ */}
            {tab === 'contact' && (
                <div style={{ ...cardStyle, animation: 'fadeIn .2s ease' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                        <SectionHeader title="Communication Channels" />
                        {editingContact ? (
                            <div style={{ display: 'flex', gap: 8 }}>
                                <button onClick={saveContact} disabled={savingContact} style={btnPrimary}>
                                    {savingContact ? 'Saving…' : 'Save'}
                                </button>
                                <button onClick={() => setEditingContact(false)} style={btnSecondary}>Cancel</button>
                            </div>
                        ) : (
                            <button onClick={() => setEditingContact(true)} style={btnSecondary}>
                                {hasAnyContact ? '✎ Edit' : '+ Add Contact'}
                            </button>
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
                    ) : hasAnyContact ? (
                        <>
                            {contactChannels.map(ch => (
                                <InfoRow key={ch.key} label={ch.label} value={ch.value} />
                            ))}
                            <InfoRow label="📌 Preferred Channel" value={guest.preferred_channel} />
                        </>
                    ) : (
                        /* Empty state (Issue #6) */
                        <div style={{
                            padding: '32px 16px', borderRadius: 8,
                            background: 'var(--color-surface-2)', border: '1px dashed var(--color-border)',
                            textAlign: 'center',
                        }}>
                            <div style={{ fontSize: 32, marginBottom: 8 }}>📱</div>
                            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-text)' }}>
                                No contact channels collected yet
                            </div>
                            <div style={{ fontSize: 12, color: 'var(--color-muted)', marginTop: 6, maxWidth: 360, margin: '6px auto 0' }}>
                                Contact details are typically captured during check-in or manually by staff.
                                Add at least one channel to enable portal link delivery.
                            </div>
                            <button
                                onClick={() => setEditingContact(true)}
                                style={{ ...btnPrimary, marginTop: 16 }}
                            >
                                + Add Guest Contact Details
                            </button>
                        </div>
                    )}
                </div>
            )}

            {/* ============================================================ */}
            {/* CURRENT STAY TAB (Issues #1, #3 — aligned + richer)          */}
            {/* ============================================================ */}
            {tab === 'stay' && (
                <div style={{ animation: 'fadeIn .2s ease' }}>
                    {dossier.current_stay ? (() => {
                        const stay = dossier.current_stay!;
                        const nights = nightCount(stay.check_in, stay.check_out);
                        return (
                            <>
                                {/* Booking header — compact metadata */}
                                <div style={{ ...cardStyle, padding: '16px 20px' }}>
                                    {/* Title row */}
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                                        <div>
                                            <div style={{ fontSize: 17, fontWeight: 800, color: 'var(--color-text)' }}>{stay.property_name}</div>
                                            <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginTop: 3 }}>
                                                {fmtDateShort(stay.check_in)} → {fmtDateShort(stay.check_out)}{nights != null ? ` · ${nights}n` : ''}
                                            </div>
                                        </div>
                                        <StatusBadge status={stay.status} />
                                    </div>

                                    {/* Compact metadata grid — 2 columns */}
                                    <div style={{
                                        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px',
                                        fontSize: 12, paddingTop: 10, borderTop: '1px solid var(--color-border)',
                                    }}>
                                        <div style={{ color: 'var(--color-text-dim)', fontWeight: 600, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Source</div>
                                        <div style={{ color: 'var(--color-text-dim)', fontWeight: 600, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Booking Name</div>
                                        <div style={{ color: 'var(--color-text)', fontWeight: 500 }}>{fmtSource(stay.source, stay.booking_id)}</div>
                                        <div style={{ color: 'var(--color-text)', fontWeight: 500 }}>{stay.guest_name || '—'}</div>

                                        <div style={{ color: 'var(--color-text-dim)', fontWeight: 600, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 6 }}>Booking ID</div>
                                        <div style={{ color: 'var(--color-text-dim)', fontWeight: 600, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 6 }}>Reservation Ref</div>
                                        <div><CompactRef value={stay.booking_id} maxChars={20} /></div>
                                        <div>{stay.reservation_ref ? <CompactRef value={stay.reservation_ref} maxChars={22} /> : <span style={{ color: 'var(--color-muted)' }}>—</span>}</div>
                                    </div>
                                </div>

                                {/* Check-in record (Issue #1 — reads status for truth) */}
                                <CheckinRecordBlock record={stay.checkin_record} stayStatus={stay.status} />

                                {/* Portal / QR (Issue #2 — actionable) */}
                                <PortalBlock portal={stay.portal} guest={guest} stay={stay} />

                                {/* Settlement (Issue #3 — richer) */}
                                <SettlementBlock stay={stay} />

                                {/* Extras & Orders (Issue #7) */}
                                <ExtrasOrdersBlock />

                                {/* Checkout Record (Issue #8 — future-ready) */}
                                <CheckoutRecordBlock stay={stay} />
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
            {/* HISTORY TAB (Issue #5 — deeper expandable)                   */}
            {/* ============================================================ */}
            {tab === 'history' && (
                <div style={{ animation: 'fadeIn .2s ease' }}>
                    <div style={sectionTitleStyle}>
                        {totalStays} stay{totalStays !== 1 ? 's' : ''} on record
                    </div>
                    {totalStays === 0 ? (
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
                                    guest={guest}
                                    expanded={expandedStay === dossier.current_stay.booking_id}
                                    onToggle={() => setExpandedStay(s => s === dossier.current_stay!.booking_id ? null : dossier.current_stay!.booking_id)}
                                    onGeneratePortal={async (bookingId) => {
                                        // POST with required body; returns { token, expires_at, ... }
                                        const PORTAL_BASE = window.location.origin + '/guest';
                                        const res = await apiFetch<{ token: string }>(
                                            `/admin/guest-token/${encodeURIComponent(bookingId)}`,
                                            {
                                                method: 'POST',
                                                headers: { 'Content-Type': 'application/json' },
                                                body: JSON.stringify({ guest_email: '', ttl_days: 30 }),
                                            }
                                        );
                                        return `${PORTAL_BASE}/${res.token}`;
                                    }}
                                />
                            )}
                            {dossier.stay_history.map(s => (
                                <StayCard
                                    key={s.booking_id}
                                    stay={s}
                                    guest={guest}
                                    expanded={expandedStay === s.booking_id}
                                    onToggle={() => setExpandedStay(p => p === s.booking_id ? null : s.booking_id)}
                                    onGeneratePortal={async (bookingId) => {
                                        const PORTAL_BASE = window.location.origin + '/guest';
                                        const res = await apiFetch<{ token: string }>(
                                            `/admin/guest-token/${encodeURIComponent(bookingId)}`,
                                            {
                                                method: 'POST',
                                                headers: { 'Content-Type': 'application/json' },
                                                body: JSON.stringify({ guest_email: '', ttl_days: 30 }),
                                            }
                                        );
                                        return `${PORTAL_BASE}/${res.token}`;
                                    }}
                                />
                            ))}
                        </>
                    )}
                </div>
            )}

            {/* ============================================================ */}
            {/* ACTIVITY TAB (Issue #4 — wired to real events)               */}
            {/* ============================================================ */}
            {tab === 'activity' && (
                <div style={{ animation: 'fadeIn .2s ease' }}>
                    <div style={sectionTitleStyle}>{dossier.activity.length} events recorded</div>
                    {dossier.activity.length === 0 ? (
                        <div style={{ ...cardStyle, textAlign: 'center', padding: 48 }}>
                            <div style={{ fontSize: 32, marginBottom: 8 }}>📋</div>
                            <div style={{ fontSize: 13, color: 'var(--color-muted)' }}>
                                No activity recorded yet.
                            </div>
                            <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginTop: 4 }}>
                                Events like guest creation, identity capture, check-in, and portal generation will appear here automatically.
                            </div>
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
                                        <div style={{ display: 'flex', gap: 12, marginTop: 4, fontSize: 11, color: 'var(--color-text-dim)' }}>
                                            {ev.actor_id && (
                                                <span>by {ev.actor_id.length > 16 ? ev.actor_id.slice(0, 12) + '…' : ev.actor_id}</span>
                                            )}
                                            {ev.entity_type && ev.entity_type !== 'guest' && (
                                                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                                                    {ev.entity_type}: {ev.entity_id ? ev.entity_id.slice(0, 20) : ''}
                                                </span>
                                            )}
                                        </div>
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
