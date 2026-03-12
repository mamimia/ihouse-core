'use client';

/**
 * Phase 291 — Financial Dashboard UI (Phase 163 + Phase 191 + Phase 291 audit)
 * Route: /financial
 *
 * Portfolio-level financial view for managers and admins.
 *
 * Sections:
 *  1. Summary bar   — gross / commission / net / period selector
 *  2. Provider breakdown — per-OTA table: bookings, gross, commission, net, ratio
 *  3. Property breakdown — per-property: gross, net, booking count
 *  4. Lifecycle distribution — 7 payment states as a segmented bar
 *  5. Reconciliation inbox  — exception count chip + link
 */

import { useEffect, useState, useCallback } from 'react';
import { api, CurrencyOverviewRow } from '../../lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CurrencyBucket {
    gross: string;
    commission: string;
    net: string;
    booking_count: number;
}

interface SummaryData {
    tenant_id: string;
    period: string;
    total_bookings: number;
    currencies: Record<string, CurrencyBucket>;
    base_currency?: string;
}

interface ProviderData {
    tenant_id: string;
    period: string;
    providers: Record<string, Record<string, CurrencyBucket>>;
}

interface PropertyData {
    tenant_id: string;
    period: string;
    properties: Record<string, Record<string, CurrencyBucket>>;
}

interface LifecycleData {
    tenant_id: string;
    period: string;
    total_bookings: number;
    distribution: Record<string, number>;
}

interface ReconciliationEntry {
    booking_id: string;
    issue?: string;
}

interface ReconciliationData {
    exceptions?: ReconciliationEntry[];
    count?: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(n: string | number | undefined | null): string {
    if (n === null || n === undefined) return '—';
    const num = typeof n === 'string' ? parseFloat(n) : n;
    if (isNaN(num)) return '—';
    return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function ratio(commission: string, gross: string): string {
    const c = parseFloat(commission);
    const g = parseFloat(gross);
    if (!g || isNaN(c) || isNaN(g)) return '—';
    return ((c / g) * 100).toFixed(1) + '%';
}

function prevMonth(ym: string): string {
    const [y, m] = ym.split('-').map(Number);
    if (m === 1) return `${y - 1}-12`;
    return `${y}-${String(m - 1).padStart(2, '0')}`;
}

function nextMonth(ym: string): string {
    const [y, m] = ym.split('-').map(Number);
    if (m === 12) return `${y + 1}-01`;
    return `${y}-${String(m + 1).padStart(2, '0')}`;
}

function today() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

// Lifecycle pill colours
const LIFECYCLE_COLOURS: Record<string, { bg: string; label: string }> = {
    GUEST_PAID: { bg: '#10b981', label: 'Guest Paid' },
    OTA_COLLECTING: { bg: '#3b82f6', label: 'OTA Collecting' },
    PAYOUT_PENDING: { bg: '#f59e0b', label: 'Payout Pending' },
    PAYOUT_RELEASED: { bg: '#06b6d4', label: 'Payout Released' },
    RECONCILIATION_PENDING: { bg: '#ef4444', label: 'Recon. Pending' },
    OWNER_NET_PENDING: { bg: '#8b5cf6', label: 'Owner Net Pending' },
    UNKNOWN: { bg: '#4b5563', label: 'Unknown' },
};

// OTA source colours
const OTA_COLOURS: Record<string, string> = {
    airbnb: '#FF5A5F', bookingcom: '#003580', expedia: '#00355F',
    vrbo: '#3D67FF', hotelbeds: '#0099CC', tripadvisor: '#34E0A1',
    unknown: '#6b7280',
};

function otaColour(src: string) {
    return OTA_COLOURS[src.toLowerCase()] ?? '#6b7280';
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SummaryCard({
    label, value, currency, accent,
}: { label: string; value: string; currency: string; accent?: string }) {
    return (
        <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-5) var(--space-6)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-2)',
            minWidth: 160,
            flex: 1,
            transition: 'border-color .2s',
        }}>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
                {label}
            </span>
            <span style={{
                fontSize: 'var(--text-2xl)',
                fontWeight: 700,
                color: accent ?? 'var(--color-text)',
                fontVariantNumeric: 'tabular-nums',
            }}>
                {value}
            </span>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)' }}>{currency}</span>
        </div>
    );
}

function SectionHeader({ title, sub }: { title: string; sub?: string }) {
    return (
        <div style={{ marginBottom: 'var(--space-4)' }}>
            <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)', margin: 0 }}>{title}</h2>
            {sub && <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 2 }}>{sub}</p>}
        </div>
    );
}

function TableShell({ children }: { children: React.ReactNode }) {
    return (
        <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
        }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--text-sm)' }}>
                {children}
            </table>
        </div>
    );
}

function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
    return (
        <th style={{
            padding: 'var(--space-3) var(--space-4)',
            textAlign: right ? 'right' : 'left',
            color: 'var(--color-text-dim)',
            fontWeight: 600,
            fontSize: 'var(--text-xs)',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            borderBottom: '1px solid var(--color-border)',
            background: 'var(--color-surface-2)',
            whiteSpace: 'nowrap',
        }}>
            {children}
        </th>
    );
}

function Td({ children, right, bold, accent }: { children: React.ReactNode; right?: boolean; bold?: boolean; accent?: string }) {
    return (
        <td style={{
            padding: 'var(--space-3) var(--space-4)',
            textAlign: right ? 'right' : 'left',
            color: accent ?? 'var(--color-text)',
            fontWeight: bold ? 700 : 400,
            borderBottom: '1px solid var(--color-border)',
            fontVariantNumeric: 'tabular-nums',
            whiteSpace: 'nowrap',
        }}>
            {children}
        </td>
    );
}

function Tr({ children, hover }: { children: React.ReactNode; hover?: boolean }) {
    const [hov, setHov] = useState(false);
    return (
        <tr
            onMouseEnter={() => setHov(true)}
            onMouseLeave={() => setHov(false)}
            style={{ background: hov ? 'rgba(59,130,246,0.04)' : 'transparent', transition: 'background .12s' }}
        >
            {children}
        </tr>
    );
}

function Badge({ children, color }: { children: React.ReactNode; color: string }) {
    return (
        <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 'var(--radius-full)',
            fontSize: 'var(--text-xs)',
            fontWeight: 600,
            background: color + '22',
            color: color,
            whiteSpace: 'nowrap',
        }}>
            {children}
        </span>
    );
}

function EmptyState({ label }: { label: string }) {
    return (
        <div style={{
            textAlign: 'center',
            padding: 'var(--space-12) 0',
            color: 'var(--color-muted)',
            fontSize: 'var(--text-sm)',
        }}>
            {label}
        </div>
    );
}

function Skeleton() {
    return (
        <div style={{
            background: 'linear-gradient(90deg, var(--color-surface-2) 25%, var(--color-surface-3) 50%, var(--color-surface-2) 75%)',
            backgroundSize: '200% 100%',
            animation: 'shimmer 1.4s infinite',
            borderRadius: 'var(--radius-md)',
            height: 18,
            width: '60%',
        }} />
    );
}

// ---------------------------------------------------------------------------
// Lifecycle distribution bar
// ---------------------------------------------------------------------------

function LifecycleBar({ distribution, total }: { distribution: Record<string, number>; total: number }) {
    if (!total) return <EmptyState label="No lifecycle data for this period." />;

    const entries = Object.entries(distribution).filter(([, v]) => v > 0);

    return (
        <div>
            {/* Segmented bar */}
            <div style={{
                display: 'flex',
                height: 24,
                borderRadius: 'var(--radius-md)',
                overflow: 'hidden',
                border: '1px solid var(--color-border)',
                marginBottom: 'var(--space-5)',
            }}>
                {entries.map(([key, count]) => {
                    const pct = (count / total) * 100;
                    const cfg = LIFECYCLE_COLOURS[key] ?? { bg: '#6b7280', label: key };
                    return (
                        <div
                            key={key}
                            title={`${cfg.label}: ${count} (${pct.toFixed(1)}%)`}
                            style={{
                                width: `${pct}%`,
                                background: cfg.bg,
                                transition: 'width .4s',
                            }}
                        />
                    );
                })}
            </div>

            {/* Legend */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
                {entries.map(([key, count]) => {
                    const pct = ((count / total) * 100).toFixed(1);
                    const cfg = LIFECYCLE_COLOURS[key] ?? { bg: '#6b7280', label: key };
                    return (
                        <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <div style={{ width: 10, height: 10, borderRadius: 2, background: cfg.bg, flexShrink: 0 }} />
                            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                                {cfg.label}
                            </span>
                            <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text)' }}>
                                {count} <span style={{ color: 'var(--color-muted)' }}>({pct}%)</span>
                            </span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Portfolio Overview component (Phase 191)
// ---------------------------------------------------------------------------

function PortfolioOverview({ rows, loading }: { rows: CurrencyOverviewRow[]; loading: boolean }) {
    if (loading) {
        return (
            <div style={{
                display: 'flex', flexDirection: 'column', gap: 'var(--space-3)',
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)',
                padding: 'var(--space-5) var(--space-6)',
            }}>
                {[1, 2, 3].map(i => (
                    <div key={i} style={{ height: 36, background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', animation: 'shimmer 1.4s infinite' }} />
                ))}
            </div>
        );
    }
    if (!rows.length) {
        return (
            <div style={{
                background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)', padding: 'var(--space-8)',
            }}>
                <EmptyState label="No multi-currency data for this period." />
            </div>
        );
    }

    // For bar width: normalise against largest gross
    const maxGross = Math.max(...rows.map(r => parseFloat(r.gross_total) || 0)) || 1;

    const CCY_COLOURS: Record<string, string> = {
        THB: '#f59e0b', USD: '#3b82f6', EUR: '#6366f1', GBP: '#8b5cf6',
        JPY: '#ec4899', SGD: '#14b8a6', AUD: '#22c55e', CNY: '#ef4444',
    };

    return (
        <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
        }}>
            {/* Table header */}
            <div style={{
                display: 'grid', gridTemplateColumns: '70px 1fr 130px 130px 110px 80px',
                gap: 'var(--space-4)',
                padding: 'var(--space-3) var(--space-5)',
                background: 'var(--color-surface-2)',
                borderBottom: '1px solid var(--color-border)',
            }}>
                {['Currency', 'Revenue bar', 'Gross', 'Net', 'Avg Commission', 'Bookings'].map(h => (
                    <span key={h} style={{
                        fontSize: 'var(--text-xs)', fontWeight: 600,
                        color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em',
                    }}>{h}</span>
                ))}
            </div>

            {/* Rows */}
            {rows.map(r => {
                const pct = ((parseFloat(r.gross_total) || 0) / maxGross) * 100;
                const col = CCY_COLOURS[r.currency] ?? '#6b7280';
                return (
                    <div key={r.currency} style={{
                        display: 'grid', gridTemplateColumns: '70px 1fr 130px 130px 110px 80px',
                        gap: 'var(--space-4)',
                        padding: 'var(--space-3) var(--space-5)',
                        borderBottom: '1px solid var(--color-border)',
                        alignItems: 'center',
                        transition: 'background var(--transition-fast)',
                    }}
                        onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-surface-2)')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                    >
                        {/* Currency badge */}
                        <span style={{
                            fontSize: 'var(--text-xs)', fontWeight: 700,
                            padding: '2px 8px', borderRadius: 'var(--radius-full)',
                            background: col + '22', color: col,
                            fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap',
                        }}>{r.currency}</span>

                        {/* Mini bar */}
                        <div style={{ position: 'relative', height: 8, background: 'var(--color-surface-3)', borderRadius: 4, overflow: 'hidden' }}>
                            <div style={{
                                position: 'absolute', top: 0, left: 0, bottom: 0,
                                width: `${pct}%`, background: col,
                                borderRadius: 4, transition: 'width .5s ease',
                            }} />
                        </div>

                        {/* Gross */}
                        <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, fontVariantNumeric: 'tabular-nums', textAlign: 'right' }}>
                            {parseFloat(r.gross_total).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </span>

                        {/* Net */}
                        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-ok)', fontWeight: 600, fontVariantNumeric: 'tabular-nums', textAlign: 'right' }}>
                            {parseFloat(r.net_total).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </span>

                        {/* Avg commission rate */}
                        <span style={{ textAlign: 'right' }}>
                            {r.avg_commission_rate !== null
                                ? <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, background: '#f59e0b22', color: '#f59e0b', padding: '2px 8px', borderRadius: 'var(--radius-full)' }}>{r.avg_commission_rate}%</span>
                                : <span style={{ color: 'var(--color-text-faint)', fontSize: 'var(--text-xs)' }}>—</span>
                            }
                        </span>

                        {/* Booking count */}
                        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                            {r.booking_count}
                        </span>
                    </div>
                );
            })}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function FinancialDashboardPage() {
    const [period, setPeriod] = useState<string>(today());
    const [currency, setCurrency] = useState<string>('USD');

    const [summary, setSummary] = useState<SummaryData | null>(null);
    const [byProvider, setByProvider] = useState<ProviderData | null>(null);
    const [byProperty, setByProperty] = useState<PropertyData | null>(null);
    const [lifecycle, setLifecycle] = useState<LifecycleData | null>(null);
    const [recon, setRecon] = useState<ReconciliationData | null>(null);
    const [overview, setOverview] = useState<CurrencyOverviewRow[]>([]);

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async (p: string, cur: string) => {
        setLoading(true);
        setError(null);
        try {
            const [sumRes, provRes, propRes, lcRes, recRes, ovRes] = await Promise.allSettled([
                api.getFinancialSummary(p, cur),
                api.getFinancialByProvider(p, cur),
                api.getFinancialByProperty(p, cur),
                api.getLifecycleDistribution(p),
                api.getReconciliation(p),
                api.getMultiCurrencyOverview(p),
            ]);

            if (sumRes.status === 'fulfilled') setSummary(sumRes.value as SummaryData);
            if (provRes.status === 'fulfilled') setByProvider(provRes.value as ProviderData);
            if (propRes.status === 'fulfilled') setByProperty(propRes.value as PropertyData);
            if (lcRes.status === 'fulfilled') setLifecycle(lcRes.value as LifecycleData);
            if (recRes.status === 'fulfilled') setRecon(recRes.value as ReconciliationData);
            if (ovRes.status === 'fulfilled') setOverview(ovRes.value.currencies);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Unexpected error');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(period, currency); }, [period, currency, load]);

    // Derive summary values (use first key in currencies — should be base_currency)
    const sumBucket: CurrencyBucket | null = summary
        ? Object.values(summary.currencies ?? {})[0] ?? null
        : null;

    const reconCount = recon?.exceptions?.length ?? recon?.count ?? 0;

    // label
    const periodLabel = (() => {
        const [y, m] = period.split('-');
        return new Date(Number(y), Number(m) - 1, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
    })();

    return (
        <div style={{ minHeight: '100vh', background: 'var(--color-bg)', padding: 'var(--space-8) var(--space-6)' }}>
            <style>{`
                @keyframes shimmer {
                    0%   { background-position: 200% 0; }
                    100% { background-position: -200% 0; }
                }
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(6px); }
                    to   { opacity: 1; transform: translateY(0); }
                }
                .fin-section { animation: fadeIn .3s ease both; }
            `}</style>

            {/* ── Header ── */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--space-4)', marginBottom: 'var(--space-8)' }}>
                <div>
                    <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: 'var(--color-text)', margin: 0 }}>
                        Financial Dashboard
                    </h1>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 4 }}>
                        Portfolio-level financials · {periodLabel}
                    </p>
                </div>

                {/* Controls */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                    {/* Period nav */}
                    <div style={{
                        display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
                        background: 'var(--color-surface)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-md)',
                        padding: '4px 8px',
                    }}>
                        <button
                            onClick={() => setPeriod(prevMonth(period))}
                            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-dim)', fontSize: 18, lineHeight: 1, padding: 4 }}
                        >‹</button>
                        <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)', minWidth: 90, textAlign: 'center' }}>
                            {periodLabel}
                        </span>
                        <button
                            onClick={() => setPeriod(nextMonth(period))}
                            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-dim)', fontSize: 18, lineHeight: 1, padding: 4 }}
                        >›</button>
                    </div>

                    {/* Currency selector */}
                    <select
                        value={currency}
                        onChange={e => setCurrency(e.target.value)}
                        style={{
                            background: 'var(--color-surface)',
                            border: '1px solid var(--color-border)',
                            borderRadius: 'var(--radius-md)',
                            color: 'var(--color-text)',
                            fontSize: 'var(--text-sm)',
                            padding: '6px 10px',
                            cursor: 'pointer',
                        }}
                    >
                        {['USD', 'THB', 'EUR', 'GBP', 'SGD', 'AUD', 'JPY'].map(c =>
                            <option key={c} value={c}>{c}</option>
                        )}
                    </select>
                </div>
            </div>

            {/* ── Error ── */}
            {error && (
                <div style={{
                    background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)',
                    borderRadius: 'var(--radius-md)', padding: 'var(--space-4) var(--space-5)',
                    color: 'var(--color-danger)', marginBottom: 'var(--space-6)', fontSize: 'var(--text-sm)',
                }}>
                    ⚠ {error}
                </div>
            )}

            {/* ── Reconciliation banner ── */}
            {!loading && reconCount > 0 && (
                <div style={{
                    background: 'rgba(245,158,11,0.08)',
                    border: '1px solid rgba(245,158,11,0.3)',
                    borderRadius: 'var(--radius-md)',
                    padding: 'var(--space-3) var(--space-5)',
                    marginBottom: 'var(--space-6)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-3)',
                    fontSize: 'var(--text-sm)',
                    color: 'var(--color-warn)',
                }}>
                    <span style={{
                        background: '#f59e0b',
                        color: '#0b0f1a',
                        borderRadius: 'var(--radius-full)',
                        width: 22, height: 22,
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 800,
                        fontSize: 11,
                        flexShrink: 0,
                    }}>
                        {reconCount}
                    </span>
                    <span>
                        <strong>{reconCount} reconciliation exception{reconCount !== 1 ? 's' : ''}</strong> need attention for {periodLabel}.{' '}
                        <a href="/admin/reconciliation" style={{ color: 'var(--color-primary)', textDecoration: 'underline' }}>
                            Review →
                        </a>
                    </span>
                </div>
            )}

            {/* ── Section 0: Portfolio Overview (Phase 191) ── */}
            <div className="fin-section" style={{ marginBottom: 'var(--space-8)' }}>
                <SectionHeader
                    title="Portfolio Overview"
                    sub="All currencies · sorted by gross revenue · each currency independent"
                />
                <PortfolioOverview rows={overview} loading={loading} />
            </div>

            {/* ── Section 1: Summary Bar ── */}
            <div className="fin-section" style={{ marginBottom: 'var(--space-8)' }}>
                <SectionHeader
                    title="Portfolio Summary"
                    sub={`All figures in ${currency} · ${loading ? '…' : (summary?.total_bookings ?? 0) + ' bookings'}`}
                />
                <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap' }}>
                    {loading ? (
                        ['Gross Revenue', 'OTA Commission', 'Net to Portfolio', 'Bookings'].map(l => (
                            <div key={l} style={{
                                flex: 1, minWidth: 160,
                                background: 'var(--color-surface)',
                                border: '1px solid var(--color-border)',
                                borderRadius: 'var(--radius-lg)',
                                padding: 'var(--space-5) var(--space-6)',
                            }}>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 8 }}>{l}</div>
                                <Skeleton />
                            </div>
                        ))
                    ) : sumBucket ? (
                        <>
                            <SummaryCard label="Gross Revenue" value={fmt(sumBucket.gross)} currency={currency} accent="var(--color-text)" />
                            <SummaryCard label="OTA Commission" value={fmt(sumBucket.commission)} currency={currency} accent="var(--color-danger)" />
                            <SummaryCard label="Net to Portfolio" value={fmt(sumBucket.net)} currency={currency} accent="var(--color-ok)" />
                            <SummaryCard label="Bookings" value={String(sumBucket.booking_count)} currency="bookings" accent="var(--color-primary)" />
                        </>
                    ) : (
                        <div style={{ color: 'var(--color-muted)', fontSize: 'var(--text-sm)', padding: 'var(--space-6) 0' }}>
                            No financial data for {periodLabel}.
                        </div>
                    )}
                </div>
            </div>

            {/* ── Section 1.5: OTA Mix Donut (Phase 291) ── */}
            {!loading && byProvider && Object.keys(byProvider.providers ?? {}).length > 1 && (() => {
                const entries = Object.entries(byProvider.providers)
                    .map(([prov, curMap]) => ({
                        prov,
                        count: Object.values(curMap)[0]?.booking_count ?? 0,
                        gross: parseFloat(Object.values(curMap)[0]?.gross ?? '0') || 0,
                    }))
                    .filter(e => e.count > 0)
                    .sort((a, b) => b.gross - a.gross);
                const total = entries.reduce((s, e) => s + e.gross, 0) || 1;

                // Build SVG donut
                const R = 54; const cx = 70; const cy = 70;
                let angle = -Math.PI / 2;
                const slices = entries.map(e => {
                    const pct = e.gross / total;
                    const a1 = angle; const a2 = angle + pct * 2 * Math.PI;
                    angle = a2;
                    const x1 = cx + R * Math.cos(a1); const y1 = cy + R * Math.sin(a1);
                    const x2 = cx + R * Math.cos(a2); const y2 = cy + R * Math.sin(a2);
                    const large = pct > 0.5 ? 1 : 0;
                    return { prov: e.prov, pct, d: `M${cx},${cy} L${x1.toFixed(1)},${y1.toFixed(1)} A${R},${R} 0 ${large},1 ${x2.toFixed(1)},${y2.toFixed(1)} Z`, col: otaColour(e.prov) };
                });

                return (
                    <div className="fin-section" style={{ marginBottom: 'var(--space-8)', animationDelay: '.04s' }}>
                        <SectionHeader title="OTA Mix" sub="Revenue share by channel · hover slice for detail" />
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-6)', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5) var(--space-6)' }}>
                            <svg width={140} height={140} viewBox="0 0 140 140">
                                {slices.map(s => (
                                    <path key={s.prov} d={s.d} fill={s.col} stroke="var(--color-surface)" strokeWidth={2}>
                                        <title>{s.prov}: {(s.pct * 100).toFixed(1)}%</title>
                                    </path>
                                ))}
                                <circle cx={cx} cy={cy} r={30} fill="var(--color-surface)" />
                                <text x={cx} y={cy - 4} textAnchor="middle" fontSize={9} fill="var(--color-text-dim)" fontFamily="var(--font-body)">MIX</text>
                                <text x={cx} y={cy + 10} textAnchor="middle" fontSize={11} fontWeight={700} fill="var(--color-text)" fontFamily="var(--font-body)">{entries.length} OTAs</text>
                            </svg>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                                {slices.map(s => (
                                    <div key={s.prov} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                        <div style={{ width: 10, height: 10, borderRadius: 2, background: s.col, flexShrink: 0 }} />
                                        <span style={{ fontSize: 'var(--text-xs)', textTransform: 'capitalize', color: 'var(--color-text)', minWidth: 90 }}>{s.prov}</span>
                                        <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-dim)', fontVariantNumeric: 'tabular-nums' }}>{(s.pct * 100).toFixed(1)}%</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                );
            })()}

            {/* ── Section 2: Provider Breakdown ── */}
            <div className="fin-section" style={{ marginBottom: 'var(--space-8)', animationDelay: '.05s' }}>
                <SectionHeader title="By OTA Provider" sub="Gross, commission, net and commission ratio per channel" />

                {loading ? (
                    <div style={{ ...skeletonTableStyle }}>
                        {[1, 2, 3].map(i => <Skeleton key={i} />)}
                    </div>
                ) : !byProvider || !Object.keys(byProvider.providers ?? {}).length ? (
                    <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-8)' }}>
                        <EmptyState label="No provider data for this period." />
                    </div>
                ) : (
                    <TableShell>
                        <thead>
                            <tr>
                                <Th>Provider</Th>
                                <Th right>Bookings</Th>
                                <Th right>Gross</Th>
                                <Th right>Commission</Th>
                                <Th right>Net</Th>
                                <Th right>Commission Rate</Th>
                            </tr>
                        </thead>
                        <tbody>
                            {Object.entries(byProvider.providers).map(([prov, curMap]) => {
                                const bucket = Object.values(curMap)[0];
                                if (!bucket) return null;
                                return (
                                    <Tr key={prov}>
                                        <Td>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                <div style={{
                                                    width: 8, height: 8, borderRadius: '50%',
                                                    background: otaColour(prov), flexShrink: 0,
                                                }} />
                                                <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>{prov}</span>
                                            </div>
                                        </Td>
                                        <Td right>{bucket.booking_count}</Td>
                                        <Td right>{fmt(bucket.gross)}</Td>
                                        <Td right accent="var(--color-danger)">{fmt(bucket.commission)}</Td>
                                        <Td right accent="var(--color-ok)" bold>{fmt(bucket.net)}</Td>
                                        <Td right>
                                            <Badge color="#f59e0b">{ratio(bucket.commission, bucket.gross)}</Badge>
                                        </Td>
                                    </Tr>
                                );
                            })}
                        </tbody>
                    </TableShell>
                )}
            </div>

            {/* ── Section 3: Property Breakdown ── */}
            <div className="fin-section" style={{ marginBottom: 'var(--space-8)', animationDelay: '.10s' }}>
                <SectionHeader title="By Property" sub="Revenue attribution per property unit" />

                {loading ? (
                    <div style={skeletonTableStyle}>{[1, 2, 3].map(i => <Skeleton key={i} />)}</div>
                ) : !byProperty || !Object.keys(byProperty.properties ?? {}).length ? (
                    <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-8)' }}>
                        <EmptyState label="No property data for this period." />
                    </div>
                ) : (
                    <TableShell>
                        <thead>
                            <tr>
                                <Th>Property</Th>
                                <Th right>Bookings</Th>
                                <Th right>Gross</Th>
                                <Th right>Net</Th>
                            </tr>
                        </thead>
                        <tbody>
                            {Object.entries(byProperty.properties).map(([prop, curMap]) => {
                                const bucket = Object.values(curMap)[0];
                                if (!bucket) return null;
                                return (
                                    <Tr key={prop}>
                                        <Td bold>{prop}</Td>
                                        <Td right>{bucket.booking_count}</Td>
                                        <Td right>{fmt(bucket.gross)}</Td>
                                        <Td right accent="var(--color-ok)" bold>{fmt(bucket.net)}</Td>
                                    </Tr>
                                );
                            })}
                        </tbody>
                    </TableShell>
                )}
            </div>

            {/* ── Section 4: Lifecycle Distribution ── */}
            <div className="fin-section" style={{ marginBottom: 'var(--space-8)', animationDelay: '.15s' }}>
                <SectionHeader
                    title="Payment Lifecycle Distribution"
                    sub={lifecycle ? `${lifecycle.total_bookings} bookings across 7 states` : 'Payment states for this period'}
                />
                <div style={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-lg)',
                    padding: 'var(--space-6)',
                }}>
                    {loading ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                            <div style={{ height: 24, background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', animation: 'shimmer 1.4s infinite' }} />
                            <Skeleton />
                        </div>
                    ) : lifecycle ? (
                        <LifecycleBar distribution={lifecycle.distribution} total={lifecycle.total_bookings} />
                    ) : (
                        <EmptyState label="No lifecycle data." />
                    )}
                </div>
            </div>

            {/* ── Section 5: Reconciliation Inbox ── */}
            <div className="fin-section" style={{ animationDelay: '.20s' }}>
                <SectionHeader title="Reconciliation Inbox" sub="Bookings with missing or inconsistent financial data" />
                <div style={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-lg)',
                    padding: 'var(--space-5) var(--space-6)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 'var(--space-4)',
                }}>
                    {loading ? <Skeleton /> : (
                        <>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                                <span style={{
                                    width: 36, height: 36,
                                    background: reconCount > 0 ? 'rgba(245,158,11,0.15)' : 'rgba(16,185,129,0.12)',
                                    color: reconCount > 0 ? '#f59e0b' : '#10b981',
                                    borderRadius: 'var(--radius-md)',
                                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                                    fontSize: 'var(--text-lg)', fontWeight: 800,
                                }}>
                                    {reconCount > 0 ? '⚠' : '✓'}
                                </span>
                                <div>
                                    <div style={{ fontWeight: 600, color: 'var(--color-text)', fontSize: 'var(--text-sm)' }}>
                                        {reconCount > 0
                                            ? `${reconCount} exception${reconCount !== 1 ? 's' : ''} need review`
                                            : 'All clear — no exceptions'}
                                    </div>
                                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                                        {periodLabel}
                                    </div>
                                </div>
                            </div>

                            {reconCount > 0 && (
                                <a href="/admin/reconciliation" style={{
                                    display: 'inline-flex', alignItems: 'center', gap: 4,
                                    background: 'var(--color-primary)',
                                    color: '#fff',
                                    borderRadius: 'var(--radius-md)',
                                    padding: '6px 14px',
                                    fontSize: 'var(--text-sm)',
                                    fontWeight: 600,
                                    textDecoration: 'none',
                                    transition: 'opacity .15s',
                                }}>
                                    Review exceptions →
                                </a>
                            )}
                        </>
                    )}
                </div>
            </div>

            {/* ── Quick nav: Owner Statements (Phase 291) ── */}
            <div className="fin-section" style={{ marginTop: 'var(--space-8)', animationDelay: '.25s' }}>
                <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-lg)', padding: 'var(--space-4) var(--space-6)',
                }}>
                    <div>
                        <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>Owner Statements</div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>Per-property net payout reports with management fee breakdown</div>
                    </div>
                    <a href="/financial/statements" style={{
                        background: 'var(--color-primary)', color: '#fff',
                        borderRadius: 'var(--radius-md)', padding: '6px 16px',
                        fontSize: 'var(--text-sm)', fontWeight: 600, textDecoration: 'none',
                    }}>View statements →</a>
                </div>
            </div>
        </div>
    );
}

// Skeleton table placeholder styles
const skeletonTableStyle: React.CSSProperties = {
    background: 'var(--color-surface)',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-lg)',
    padding: 'var(--space-6)',
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-4)',
};
