'use client';

/**
 * Phase 164 — Owner Statement UI
 * Route: /financial/statements
 *
 * Monthly statement per property for managers and owners.
 *
 * Sections:
 *  1. Property + month selector (+ management fee %)
 *  2. Per-booking line items – check-in/out, OTA, gross, commission, net,
 *     epistemic tier badge (✅ A / 🔵 B / ⚠️ C), payout status chip
 *  3. Totals summary – gross / commission / net / mgmt fee / owner net
 *  4. Export – plain-text (PDF) download + CSV trigger
 */

import { useEffect, useState, useCallback } from 'react';
import { api } from '../../../../lib/api';
import type { OwnerStatementResponse } from '../../../../lib/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(n: string | number | undefined | null): string {
    if (n === null || n === undefined) return '—';
    const num = typeof n === 'string' ? parseFloat(n) : n;
    if (isNaN(num)) return '—';
    return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function today() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function prevMonth(ym: string): string {
    const [y, m] = ym.split('-').map(Number);
    return m === 1 ? `${y - 1}-12` : `${y}-${String(m - 1).padStart(2, '0')}`;
}

function nextMonth(ym: string): string {
    const [y, m] = ym.split('-').map(Number);
    return m === 12 ? `${y + 1}-01` : `${y}-${String(m + 1).padStart(2, '0')}`;
}

function periodLabel(ym: string): string {
    const [y, m] = ym.split('-');
    return new Date(Number(y), Number(m) - 1, 1)
        .toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

function formatDate(d: string | null | undefined): string {
    if (!d) return '—';
    const parsed = new Date(d);
    if (isNaN(parsed.getTime())) return d;
    return parsed.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// ---------------------------------------------------------------------------
// Epistemic tier badge
// ---------------------------------------------------------------------------

const TIER_CFG: Record<string, { icon: string; color: string; bg: string; label: string }> = {
    A: { icon: '✅', color: '#10b981', bg: 'rgba(16,185,129,0.1)', label: 'Measured' },
    B: { icon: '🔵', color: '#3b82f6', bg: 'rgba(59,130,246,0.1)', label: 'Calculated' },
    C: { icon: '⚠️', color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', label: 'Incomplete' },
};

function TierBadge({ tier }: { tier: string }) {
    const cfg = TIER_CFG[tier] ?? { icon: '?', color: '#6b7280', bg: 'rgba(100,100,100,0.1)', label: 'Unknown' };
    return (
        <span
            title={cfg.label}
            style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 3,
                padding: '2px 7px',
                borderRadius: 'var(--radius-full)',
                background: cfg.bg,
                color: cfg.color,
                fontSize: 'var(--text-xs)',
                fontWeight: 700,
                whiteSpace: 'nowrap',
            }}
        >
            {cfg.icon} {tier}
        </span>
    );
}

// ---------------------------------------------------------------------------
// Lifecycle chip
// ---------------------------------------------------------------------------

const LIFECYCLE_CFG: Record<string, { color: string; bg: string; label: string }> = {
    GUEST_PAID: { color: '#10b981', bg: 'rgba(16,185,129,0.1)', label: 'Guest Paid' },
    OTA_COLLECTING: { color: '#3b82f6', bg: 'rgba(59,130,246,0.1)', label: 'OTA Collecting' },
    PAYOUT_PENDING: { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', label: 'Pending' },
    PAYOUT_RELEASED: { color: '#06b6d4', bg: 'rgba(6,182,212,0.1)', label: 'Released' },
    RECONCILIATION_PENDING: { color: '#ef4444', bg: 'rgba(239,68,68,0.1)', label: 'Recon.' },
    OWNER_NET_PENDING: { color: '#8b5cf6', bg: 'rgba(139,92,246,0.1)', label: 'Owner Pending' },
    UNKNOWN: { color: '#6b7280', bg: 'rgba(107,114,128,0.1)', 'label': 'Unknown' },
};

function LifecycleChip({ status }: { status: string | null }) {
    const s = status ?? 'UNKNOWN';
    const cfg = LIFECYCLE_CFG[s] ?? LIFECYCLE_CFG.UNKNOWN;
    return (
        <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 'var(--radius-full)',
            background: cfg.bg,
            color: cfg.color,
            fontSize: 'var(--text-xs)',
            fontWeight: 600,
            whiteSpace: 'nowrap',
        }}>
            {cfg.label}
        </span>
    );
}

// ---------------------------------------------------------------------------
// OTA colour dot
// ---------------------------------------------------------------------------

const OTA_COLOURS: Record<string, string> = {
    airbnb: '#FF5A5F', bookingcom: '#003580', expedia: '#00355F',
    vrbo: '#3D67FF', hotelbeds: '#0099CC', tripadvisor: '#34E0A1',
    operator: '#8b5cf6', unknown: '#6b7280',
};

function OtaDot({ provider }: { provider: string }) {
    const c = OTA_COLOURS[provider?.toLowerCase()] ?? '#6b7280';
    return (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: c, flexShrink: 0, display: 'inline-block' }} />
            <span style={{ textTransform: 'capitalize', fontWeight: 500 }}>{provider ?? '—'}</span>
        </span>
    );
}

// ---------------------------------------------------------------------------
// Skeleton / empty states
// ---------------------------------------------------------------------------

function Skeleton({ width = '60%', height = 16 }: { width?: string; height?: number }) {
    return (
        <div style={{
            width, height,
            borderRadius: 'var(--radius-sm)',
            background: 'linear-gradient(90deg, var(--color-surface-2) 25%, var(--color-surface-3) 50%, var(--color-surface-2) 75%)',
            backgroundSize: '200% 100%',
            animation: 'shimmer 1.4s infinite',
        }} />
    );
}

function EmptyState({ label }: { label: string }) {
    return (
        <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--color-muted)', fontSize: 'var(--text-sm)' }}>
            {label}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Summary row helper
// ---------------------------------------------------------------------------

function SummaryRow({
    label, value, accent, large, dimLabel, note,
}: {
    label: string; value: string; accent?: string; large?: boolean; dimLabel?: boolean; note?: string;
}) {
    return (
        <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
            padding: 'var(--space-3) 0',
            borderBottom: '1px solid var(--color-border)',
        }}>
            <span style={{
                fontSize: large ? 'var(--text-base)' : 'var(--text-sm)',
                color: dimLabel ? 'var(--color-text-dim)' : 'var(--color-text)',
                fontWeight: large ? 700 : 400,
            }}>
                {label}
                {note && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)', marginLeft: 6 }}>{note}</span>}
            </span>
            <span style={{
                fontSize: large ? 'var(--text-lg)' : 'var(--text-sm)',
                fontWeight: large ? 800 : 600,
                color: accent ?? 'var(--color-text)',
                fontVariantNumeric: 'tabular-nums',
            }}>
                {value}
            </span>
        </div>
    );
}

// ---------------------------------------------------------------------------
// CSV export helper (client-side from line_items)
// ---------------------------------------------------------------------------

function exportCsv(propertyId: string, month: string, data: OwnerStatementResponse) {
    const headers = ['booking_id', 'provider', 'currency', 'check_in', 'check_out', 'gross', 'ota_commission', 'net_to_property', 'epistemic_tier', 'lifecycle_status'];
    const rows = data.line_items.map(item =>
        headers.map(h => String(((item as unknown) as Record<string, unknown>)[h] ?? '')).join(',')
    );
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `owner-statement-${propertyId}-${month}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function OwnerStatementPage() {
    const [propertyId, setPropertyId] = useState<string>('');
    const [month, setMonth] = useState<string>(today());
    const [mgmtFee, setMgmtFee] = useState<string>('0');
    const [data, setData] = useState<OwnerStatementResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [hasLoaded, setHasLoaded] = useState(false);

    const load = useCallback(async () => {
        if (!propertyId.trim()) return;
        setLoading(true);
        setError(null);
        setData(null);
        try {
            const result = await api.getOwnerStatement(propertyId.trim(), month, mgmtFee !== '0' ? mgmtFee : undefined);
            setData(result);
            setHasLoaded(true);
        } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : 'Unexpected error';
            setError(msg);
        } finally {
            setLoading(false);
        }
    }, [propertyId, month, mgmtFee]);

    // Auto-load when month or fee changes if we already have a property
    useEffect(() => {
        if (hasLoaded && propertyId.trim()) load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [month, mgmtFee]);

    const sum = data?.summary;
    const items = data?.line_items ?? [];

    const handlePdfExport = () => {
        if (!propertyId.trim()) return;
        const lang = typeof window !== 'undefined' ? localStorage.getItem('domaniqo_lang') || 'en' : 'en';
        const q = new URLSearchParams({ month, format: 'pdf', lang });
        if (mgmtFee !== '0') q.set('management_fee_pct', mgmtFee);
        const token = typeof window !== 'undefined' ? localStorage.getItem('ihouse_token') : null;
        const base = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';
        // Open in new tab — browser will prompt download
        window.open(`${base}/owner-statement/${encodeURIComponent(propertyId.trim())}?${q}${token ? `&token=${token}` : ''}`, '_blank');
    };

    return (
        <div style={{ minHeight: '100vh', background: 'var(--color-bg)', padding: 'var(--space-8) var(--space-6)', maxWidth: 1200, margin: '0 auto' }}>
            <style>{`
                @keyframes shimmer {
                    0%   { background-position: 200% 0; }
                    100% { background-position: -200% 0; }
                }
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(6px); }
                    to   { opacity: 1; transform: translateY(0); }
                }
                .stmt-fade { animation: fadeIn .3s ease both; }
            `}</style>

            {/* ── Header ── */}
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: 'var(--color-text)', margin: 0 }}>
                    Owner Statement
                </h1>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 4 }}>
                    Monthly financial statement per property · epistemic confidence tiers
                </p>
            </div>

            {/* ── Controls ── */}
            <div style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)',
                padding: 'var(--space-5) var(--space-6)',
                display: 'flex',
                flexWrap: 'wrap',
                gap: 'var(--space-4)',
                alignItems: 'flex-end',
                marginBottom: 'var(--space-6)',
            }}>
                {/* Property ID */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1, minWidth: 180 }}>
                    <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        Property ID
                    </label>
                    <input
                        value={propertyId}
                        onChange={e => setPropertyId(e.target.value)}
                        placeholder="e.g. prop-villa-oceanview"
                        onKeyDown={e => e.key === 'Enter' && load()}
                        style={{
                            background: 'var(--color-surface-2)',
                            border: '1px solid var(--color-border)',
                            borderRadius: 'var(--radius-md)',
                            color: 'var(--color-text)',
                            fontSize: 'var(--text-sm)',
                            padding: '7px 12px',
                            outline: 'none',
                        }}
                    />
                </div>

                {/* Period nav */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        Month
                    </label>
                    <div style={{
                        display: 'flex', alignItems: 'center', gap: 4,
                        background: 'var(--color-surface-2)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-md)',
                        padding: '0 4px',
                    }}>
                        <button
                            onClick={() => setMonth(prevMonth(month))}
                            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-dim)', fontSize: 18, lineHeight: 1, padding: '4px 6px' }}
                        >‹</button>
                        <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)', minWidth: 100, textAlign: 'center' }}>
                            {periodLabel(month)}
                        </span>
                        <button
                            onClick={() => setMonth(nextMonth(month))}
                            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-dim)', fontSize: 18, lineHeight: 1, padding: '4px 6px' }}
                        >›</button>
                    </div>
                </div>

                {/* Management fee */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, width: 120 }}>
                    <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        Mgmt Fee %
                    </label>
                    <input
                        type="number"
                        min="0"
                        max="100"
                        step="0.1"
                        value={mgmtFee}
                        onChange={e => setMgmtFee(e.target.value)}
                        style={{
                            background: 'var(--color-surface-2)',
                            border: '1px solid var(--color-border)',
                            borderRadius: 'var(--radius-md)',
                            color: 'var(--color-text)',
                            fontSize: 'var(--text-sm)',
                            padding: '7px 12px',
                            outline: 'none',
                            width: '100%',
                        }}
                    />
                </div>

                {/* Load button */}
                <button
                    onClick={load}
                    disabled={!propertyId.trim() || loading}
                    style={{
                        background: propertyId.trim() ? 'var(--color-primary)' : 'var(--color-surface-3)',
                        color: propertyId.trim() ? '#fff' : 'var(--color-muted)',
                        border: 'none',
                        borderRadius: 'var(--radius-md)',
                        padding: '8px 20px',
                        fontSize: 'var(--text-sm)',
                        fontWeight: 700,
                        cursor: propertyId.trim() ? 'pointer' : 'not-allowed',
                        transition: 'opacity .15s',
                    }}
                >
                    {loading ? 'Loading…' : 'Load Statement'}
                </button>
            </div>

            {/* ── Error ── */}
            {error && (
                <div style={{
                    background: 'rgba(239,68,68,0.08)',
                    border: '1px solid rgba(239,68,68,0.3)',
                    borderRadius: 'var(--radius-md)',
                    padding: 'var(--space-4) var(--space-5)',
                    color: 'var(--color-danger)',
                    marginBottom: 'var(--space-6)',
                    fontSize: 'var(--text-sm)',
                }}>
                    ⚠ {error.includes('404') ? `No financial records found for "${propertyId}" in ${periodLabel(month)}.` : error}
                </div>
            )}

            {/* ── Skeleton ── */}
            {loading && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                    {[1, 2, 3, 4].map(i => (
                        <div key={i} style={{
                            background: 'var(--color-surface)',
                            border: '1px solid var(--color-border)',
                            borderRadius: 'var(--radius-lg)',
                            padding: 'var(--space-5)',
                            display: 'flex',
                            gap: 'var(--space-4)',
                        }}>
                            <Skeleton width="12%" />
                            <Skeleton width="10%" />
                            <Skeleton width="15%" />
                            <Skeleton width="10%" />
                            <Skeleton width="10%" />
                        </div>
                    ))}
                </div>
            )}

            {/* ── Statement ── */}
            {!loading && data && (
                <>
                    {/* Header row: property + export controls */}
                    <div className="stmt-fade" style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        flexWrap: 'wrap',
                        gap: 'var(--space-3)',
                        marginBottom: 'var(--space-5)',
                    }}>
                        <div>
                            <div style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--color-text)' }}>
                                {data.property_id}
                            </div>
                            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                                {periodLabel(data.month)} · {data.total_bookings_checked} booking{data.total_bookings_checked !== 1 ? 's' : ''} · tier{' '}
                                <TierBadge tier={sum?.overall_epistemic_tier ?? 'C'} />
                            </div>
                        </div>

                        {/* Export buttons */}
                        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                            <button
                                onClick={() => exportCsv(data.property_id, data.month, data)}
                                style={{
                                    background: 'var(--color-surface-2)',
                                    border: '1px solid var(--color-border)',
                                    borderRadius: 'var(--radius-md)',
                                    color: 'var(--color-text-dim)',
                                    fontSize: 'var(--text-xs)',
                                    fontWeight: 600,
                                    padding: '6px 14px',
                                    cursor: 'pointer',
                                }}
                            >
                                ↓ CSV
                            </button>
                            <button
                                onClick={handlePdfExport}
                                style={{
                                    background: 'var(--color-surface-2)',
                                    border: '1px solid var(--color-border)',
                                    borderRadius: 'var(--radius-md)',
                                    color: 'var(--color-text-dim)',
                                    fontSize: 'var(--text-xs)',
                                    fontWeight: 600,
                                    padding: '6px 14px',
                                    cursor: 'pointer',
                                }}
                            >
                                ↓ PDF (text)
                            </button>
                            {/* Phase 559 — Email statement to owner */}
                            <button
                                onClick={async () => {
                                    try {
                                        const base = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';
                                        const token = typeof window !== 'undefined' ? localStorage.getItem('ihouse_token') : null;
                                        const headers: Record<string, string> = { 'Content-Type': 'application/json' };
                                        if (token) headers['Authorization'] = `Bearer ${token}`;
                                        const resp = await fetch(`${base}/owner-statement/${encodeURIComponent(data.property_id)}/email`, {
                                            method: 'POST',
                                            headers,
                                            body: JSON.stringify({ month: data.month, management_fee_pct: mgmtFee !== '0' ? mgmtFee : undefined }),
                                        });
                                        if (resp.ok) alert('Statement emailed successfully!');
                                        else alert('Failed to email statement');
                                    } catch { alert('Email service unavailable'); }
                                }}
                                style={{
                                    background: 'var(--color-primary)',
                                    border: '1px solid var(--color-primary)',
                                    borderRadius: 'var(--radius-md)',
                                    color: '#fff',
                                    fontSize: 'var(--text-xs)',
                                    fontWeight: 600,
                                    padding: '6px 14px',
                                    cursor: 'pointer',
                                }}
                            >
                                ✉ Email Statement
                            </button>
                        </div>
                    </div>

                    {/* ── Line items table ── */}
                    <div className="stmt-fade" style={{ animationDelay: '.04s', marginBottom: 'var(--space-8)' }}>
                        <h2 style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--color-text)', marginBottom: 'var(--space-3)' }}>
                            Booking Line Items
                        </h2>
                        <div style={{
                            background: 'var(--color-surface)',
                            border: '1px solid var(--color-border)',
                            borderRadius: 'var(--radius-lg)',
                            overflow: 'hidden',
                        }}>
                            {items.length === 0 ? (
                                <EmptyState label="No bookings for this period." />
                            ) : (
                                <div style={{ overflowX: 'auto' }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--text-sm)', minWidth: 780 }}>
                                        <thead>
                                            <tr style={{ background: 'var(--color-surface-2)' }}>
                                                {['Booking', 'Provider', 'Check-in', 'Check-out', 'Gross', 'Commission', 'Net', 'Tier', 'Status'].map((h, idx) => (
                                                    <th key={h} style={{
                                                        padding: 'var(--space-3) var(--space-4)',
                                                        textAlign: idx >= 4 && idx <= 6 ? 'right' : 'left',
                                                        color: 'var(--color-text-dim)',
                                                        fontWeight: 600,
                                                        fontSize: 'var(--text-xs)',
                                                        textTransform: 'uppercase',
                                                        letterSpacing: '0.06em',
                                                        borderBottom: '1px solid var(--color-border)',
                                                        whiteSpace: 'nowrap',
                                                    }}>
                                                        {h}
                                                    </th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {items.map((item, idx) => {
                                                const isOtaCollecting = item.lifecycle_status === 'OTA_COLLECTING';
                                                return (
                                                    <LineItemRow key={item.booking_id + idx} item={item} isOtaCollecting={isOtaCollecting} />
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>

                        {/* OTA-collecting note */}
                        {(sum?.ota_collecting_excluded_from_net ?? 0) > 0 && (
                            <div style={{
                                marginTop: 'var(--space-3)',
                                fontSize: 'var(--text-xs)',
                                color: 'var(--color-text-dim)',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 5,
                            }}>
                                <span style={{ color: '#3b82f6' }}>ℹ</span>
                                {sum?.ota_collecting_excluded_from_net} OTA-Collecting booking{(sum?.ota_collecting_excluded_from_net ?? 0) > 1 ? 's' : ''} shown but excluded from net totals (payout not yet received).
                            </div>
                        )}
                    </div>

                    {/* ── Summary / totals ── */}
                    {sum && (
                        <div className="stmt-fade" style={{ animationDelay: '.08s' }}>
                            <h2 style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--color-text)', marginBottom: 'var(--space-3)' }}>
                                Statement Totals
                            </h2>
                            <div style={{
                                background: 'var(--color-surface)',
                                border: '1px solid var(--color-border)',
                                borderRadius: 'var(--radius-lg)',
                                padding: 'var(--space-5) var(--space-6)',
                                maxWidth: 480,
                            }}>
                                <SummaryRow label="Gross Revenue" value={fmt(sum.gross_total)} dimLabel />
                                <SummaryRow label="OTA Commission" value={fmt(sum.ota_commission_total)} dimLabel accent="var(--color-danger)" />
                                <SummaryRow label="Net to Property" value={fmt(sum.net_to_property_total)} dimLabel accent="var(--color-text)" />
                                {sum.management_fee_amount && (
                                    <SummaryRow
                                        label="Management Fee"
                                        note={`(${fmt(sum.management_fee_pct)}%)`}
                                        value={`− ${fmt(sum.management_fee_amount)}`}
                                        dimLabel
                                        accent="var(--color-warn)"
                                    />
                                )}
                                <SummaryRow
                                    label="Owner Net Total"
                                    value={fmt(sum.owner_net_total)}
                                    accent="var(--color-ok)"
                                    large
                                />

                                {/* Tier footer */}
                                <div style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    marginTop: 'var(--space-4)',
                                    paddingTop: 'var(--space-3)',
                                }}>
                                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                                        Confidence tier (worst-wins)
                                    </span>
                                    <TierBadge tier={sum.overall_epistemic_tier} />
                                </div>

                                {/* Currency */}
                                <div style={{
                                    marginTop: 'var(--space-2)',
                                    fontSize: 'var(--text-xs)',
                                    color: 'var(--color-muted)',
                                }}>
                                    Currency: <strong style={{ color: 'var(--color-text-dim)' }}>{sum.currency}</strong>
                                    {sum.currency === 'MIXED' && (
                                        <span style={{ color: 'var(--color-warn)', marginLeft: 6 }}>
                                            ⚠ Multiple currencies — monetary totals not shown
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}
                </>
            )}

            {/* ── Idle prompt ── */}
            {!loading && !data && !error && (
                <div style={{
                    textAlign: 'center',
                    padding: 'var(--space-16) 0',
                    color: 'var(--color-muted)',
                }}>
                    <div style={{ fontSize: 48, marginBottom: 'var(--space-4)' }}>📋</div>
                    <div style={{ fontSize: 'var(--text-base)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 4 }}>
                        Enter a property ID to generate a statement
                    </div>
                    <div style={{ fontSize: 'var(--text-sm)' }}>
                        Set an optional management fee percentage to compute owner net.
                    </div>
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Line item row — extracted to avoid inline hook-in-map issues
// ---------------------------------------------------------------------------

function LineItemRow({ item, isOtaCollecting }: {
    item: {
        booking_id: string;
        provider: string;
        check_in: string | null;
        check_out: string | null;
        gross: string | null;
        ota_commission: string | null;
        net_to_property: string | null;
        epistemic_tier: string;
        lifecycle_status: string | null;
    };
    isOtaCollecting: boolean;
}) {
    const [hov, setHov] = useState(false);
    return (
        <tr
            onMouseEnter={() => setHov(true)}
            onMouseLeave={() => setHov(false)}
            style={{
                background: hov ? 'rgba(59,130,246,0.04)' : 'transparent',
                transition: 'background .12s',
                opacity: isOtaCollecting ? 0.7 : 1,
            }}
        >
            <td style={{ padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)', whiteSpace: 'nowrap' }}>
                <span style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: 'var(--color-text-dim)' }}>
                    {item.booking_id}
                </span>
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)', whiteSpace: 'nowrap' }}>
                <OtaDot provider={item.provider} />
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)', whiteSpace: 'nowrap', color: 'var(--color-text-dim)', fontSize: 'var(--text-xs)' }}>
                {formatDate(item.check_in)}
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)', whiteSpace: 'nowrap', color: 'var(--color-text-dim)', fontSize: 'var(--text-xs)' }}>
                {formatDate(item.check_out)}
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)', textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontWeight: 500 }}>
                {fmt(item.gross)}
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: 'var(--color-danger)' }}>
                {fmt(item.ota_commission)}
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)', textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontWeight: 700, color: isOtaCollecting ? 'var(--color-muted)' : 'var(--color-ok)' }}>
                {isOtaCollecting ? '—' : fmt(item.net_to_property)}
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)', whiteSpace: 'nowrap' }}>
                <TierBadge tier={item.epistemic_tier} />
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)', whiteSpace: 'nowrap' }}>
                <LifecycleChip status={item.lifecycle_status} />
            </td>
        </tr>
    );
}
