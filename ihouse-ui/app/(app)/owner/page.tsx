'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { api, OwnerStatementResponse, CashflowWeek as ApiCashflowWeek } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PropertyCard {
    property_id: string;
    gross_total: string | null;
    ota_commission_total: string | null;
    owner_net_total: string | null;
    booking_count: number;
    currency: string;
}



// ---------------------------------------------------------------------------
// Reusable components
// ---------------------------------------------------------------------------

function MetricTile({ label, value, sub, accent }: {
    label: string;
    value: string | number;
    sub?: string;
    accent?: string;
}) {
    return (
        <div style={{
            background: 'var(--color-surface-2)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-5)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-1)',
        }}>
            <span style={{
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-faint)',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
            }}>{label}</span>
            <span style={{
                fontSize: 'var(--text-2xl)',
                fontWeight: 700,
                color: accent || 'var(--color-text)',
                lineHeight: 1.1,
                fontVariantNumeric: 'tabular-nums',
            }}>{value}</span>
            {sub && (
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{sub}</span>
            )}
        </div>
    );
}

function EpistemicBadge({ tier }: { tier: string }) {
    const map: Record<string, { icon: string; color: string }> = {
        CONFIRMED: { icon: '✅', color: 'var(--color-ok)' },
        PROVISIONAL: { icon: '🔵', color: 'var(--color-primary)' },
        ESTIMATED: { icon: '⚠️', color: 'var(--color-warn)' },
        UNVERIFIED: { icon: '⚠️', color: 'var(--color-warn)' },
    };
    const t = map[tier?.toUpperCase()] ?? { icon: '—', color: 'var(--color-text-dim)' };
    return (
        <span title={tier} style={{ fontSize: '1em', cursor: 'help' }}>{t.icon}</span>
    );
}

function PropertyCard({ card, month, onSelect }: {
    card: PropertyCard;
    month: string;
    onSelect: (id: string) => void;
}) {
    const fmt = (v: string | null) => v ? `${card.currency} ${parseFloat(v).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : '—';

    return (
        <div
            onClick={() => onSelect(card.property_id)}
            style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)',
                padding: 'var(--space-5)',
                cursor: 'pointer',
                transition: 'all var(--transition-fast)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--space-3)',
            }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--color-primary)')}
            onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}
        >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                    <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)', marginBottom: 2 }}>
                        {card.property_id}
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                        {card.booking_count} booking{card.booking_count !== 1 ? 's' : ''} · {month}
                    </div>
                </div>
                <a
                    href={`/financial/statements?property=${encodeURIComponent(card.property_id)}&month=${month}`}
                    onClick={e => e.stopPropagation()}
                    style={{
                        fontSize: 'var(--text-xs)',
                        color: 'var(--color-primary)',
                        textDecoration: 'none',
                        padding: '2px 8px',
                        border: '1px solid var(--color-primary)',
                        borderRadius: 'var(--radius-full)',
                        opacity: 0.8,
                    }}
                >
                    Statement →
                </a>
            </div>

            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 240px), 1fr))',
                gap: 'var(--space-3)',
                paddingTop: 'var(--space-3)',
                borderTop: '1px solid var(--color-border)',
            }}>
                {[
                    { label: 'Gross', value: fmt(card.gross_total), accent: 'var(--color-text)' },
                    { label: 'Commission', value: fmt(card.ota_commission_total), accent: 'var(--color-warn)' },
                    { label: 'Owner net', value: fmt(card.owner_net_total), accent: 'var(--color-ok)' },
                ].map(({ label, value, accent }) => (
                    <div key={label}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginBottom: 2 }}>{label}</div>
                        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: accent, fontVariantNumeric: 'tabular-nums' }}>
                            {value}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Statement drawer
// ---------------------------------------------------------------------------

function StatementDrawer({ propertyId, month, onClose }: {
    propertyId: string;
    month: string;
    onClose: () => void;
}) {
    const [stmt, setStmt] = useState<OwnerStatementResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [emailMode, setEmailMode] = useState<null | 'choose' | 'self' | 'other'>(null);
    const [emailInput, setEmailInput] = useState('');
    const [emailSent, setEmailSent] = useState(false);
    const [emailSending, setEmailSending] = useState(false);

    const lang = typeof window !== 'undefined' ? localStorage.getItem('domaniqo_lang') || 'en' : 'en';
    const pdfUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/owner-statement/${encodeURIComponent(propertyId)}?month=${month}&format=pdf&lang=${lang}`;

    useEffect(() => {
        setLoading(true);
        api.getOwnerStatement(propertyId, month)
            .then(setStmt)
            .catch(() => setStmt(null))
            .finally(() => setLoading(false));
    }, [propertyId, month]);

    // Simulated email send (placeholder — real send would call a /send-statement endpoint)
    const handleSendEmail = async (to: string) => {
        if (!to.trim()) return;
        setEmailSending(true);
        await new Promise(r => setTimeout(r, 900)); // simulate API call
        setEmailSending(false);
        setEmailSent(true);
        setTimeout(() => { setEmailMode(null); setEmailSent(false); setEmailInput(''); }, 2400);
    };

    return (
        <div style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.55)',
            backdropFilter: 'blur(4px)',
            zIndex: 200,
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'flex-end',
        }}
            onClick={onClose}
        >
            <div
                onClick={e => e.stopPropagation()}
                style={{
                    width: 520,
                    maxWidth: '95vw',
                    height: '100vh',
                    background: 'var(--color-surface)',
                    borderLeft: '1px solid var(--color-border)',
                    overflowY: 'auto',
                    padding: 'var(--space-8)',
                }}
            >
                {/* Header row */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-6)' }}>
                    <div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 2 }}>Owner Statement</div>
                        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)' }}>
                            {propertyId} · {month}
                        </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                        {/* ↓ PDF */}
                        <a
                            href={pdfUrl}
                            download={`owner-statement-${propertyId}-${month}.pdf`}
                            title="Download as PDF"
                            style={{
                                fontSize: 'var(--text-xs)',
                                fontWeight: 600,
                                color: 'var(--color-primary)',
                                textDecoration: 'none',
                                padding: '4px 10px',
                                border: '1px solid var(--color-primary)',
                                borderRadius: 'var(--radius-md)',
                                opacity: 0.9,
                                transition: 'all var(--transition-fast)',
                                whiteSpace: 'nowrap',
                            }}
                            onMouseEnter={e => {
                                (e.currentTarget as HTMLElement).style.background = 'var(--color-primary)';
                                (e.currentTarget as HTMLElement).style.color = '#fff';
                            }}
                            onMouseLeave={e => {
                                (e.currentTarget as HTMLElement).style.background = 'transparent';
                                (e.currentTarget as HTMLElement).style.color = 'var(--color-primary)';
                            }}
                        >
                            ↓ PDF
                        </a>

                        {/* Send by email */}
                        <button
                            onClick={() => setEmailMode(emailMode ? null : 'choose')}
                            title="Send by email"
                            style={{
                                fontSize: 'var(--text-xs)',
                                fontWeight: 600,
                                color: 'var(--color-text-dim)',
                                background: 'none',
                                border: '1px solid var(--color-border)',
                                borderRadius: 'var(--radius-md)',
                                padding: '4px 10px',
                                cursor: 'pointer',
                                whiteSpace: 'nowrap',
                                transition: 'all var(--transition-fast)',
                            }}
                            onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--color-text-dim)')}
                            onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}
                        >
                            ✉ Email
                        </button>

                        {/* Close */}
                        <button
                            onClick={onClose}
                            style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: 'var(--color-text-dim)', padding: '0 4px' }}
                        >✕</button>
                    </div>
                </div>

                {/* Email panel */}
                {emailMode && (
                    <div style={{
                        background: 'var(--color-surface-2)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-md)',
                        padding: 'var(--space-4)',
                        marginBottom: 'var(--space-5)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 'var(--space-3)',
                    }}>
                        {emailSent ? (
                            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-ok)', fontWeight: 600 }}>
                                ✓ Statement sent successfully
                            </div>
                        ) : emailMode === 'other' ? (
                            <>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>Send to another email</div>
                                <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                                    <input
                                        type="email"
                                        placeholder="address@example.com"
                                        value={emailInput}
                                        onChange={e => setEmailInput(e.target.value)}
                                        onKeyDown={e => e.key === 'Enter' && handleSendEmail(emailInput)}
                                        style={{
                                            flex: 1,
                                            background: 'var(--color-surface)',
                                            border: '1px solid var(--color-border)',
                                            borderRadius: 'var(--radius-md)',
                                            color: 'var(--color-text)',
                                            fontSize: 'var(--text-sm)',
                                            padding: 'var(--space-2) var(--space-3)',
                                        }}
                                        autoFocus
                                    />
                                    <button
                                        onClick={() => handleSendEmail(emailInput)}
                                        disabled={emailSending || !emailInput.trim()}
                                        style={{
                                            background: 'var(--color-primary)',
                                            color: '#fff',
                                            border: 'none',
                                            borderRadius: 'var(--radius-md)',
                                            padding: 'var(--space-2) var(--space-4)',
                                            fontSize: 'var(--text-sm)',
                                            fontWeight: 600,
                                            cursor: emailSending ? 'wait' : 'pointer',
                                            opacity: emailSending ? 0.7 : 1,
                                        }}
                                    >{emailSending ? '⟳' : 'Send'}</button>
                                </div>
                                <button onClick={() => setEmailMode('choose')} style={{ background: 'none', border: 'none', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', cursor: 'pointer', textAlign: 'left', padding: 0 }}>← back</button>
                            </>
                        ) : (
                            <>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>Send PDF statement by email</div>
                                <button
                                    onClick={() => handleSendEmail('me')}
                                    disabled={emailSending}
                                    style={{
                                        background: 'var(--color-surface)',
                                        border: '1px solid var(--color-border)',
                                        borderRadius: 'var(--radius-md)',
                                        color: 'var(--color-text)',
                                        fontSize: 'var(--text-sm)',
                                        padding: 'var(--space-2) var(--space-4)',
                                        cursor: 'pointer',
                                        textAlign: 'left',
                                        width: '100%',
                                        fontWeight: 500,
                                    }}
                                >📨  Send to my email</button>
                                <button
                                    onClick={() => setEmailMode('other')}
                                    style={{
                                        background: 'var(--color-surface)',
                                        border: '1px solid var(--color-border)',
                                        borderRadius: 'var(--radius-md)',
                                        color: 'var(--color-text)',
                                        fontSize: 'var(--text-sm)',
                                        padding: 'var(--space-2) var(--space-4)',
                                        cursor: 'pointer',
                                        textAlign: 'left',
                                        width: '100%',
                                        fontWeight: 500,
                                    }}
                                >✉  Send to another email…</button>
                            </>
                        )}
                    </div>
                )}


                {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p>}

                {!loading && !stmt && (
                    <p style={{ color: 'var(--color-warn)', fontSize: 'var(--text-sm)' }}>No statement data available.</p>
                )}

                {!loading && stmt && (
                    <>
                        {/* Summary */}
                        <div style={{
                            background: 'var(--color-surface-2)',
                            borderRadius: 'var(--radius-md)',
                            padding: 'var(--space-5)',
                            marginBottom: 'var(--space-6)',
                        }}>
                            {[
                                ['Gross revenue', stmt.summary.gross_total],
                                ['OTA commission', stmt.summary.ota_commission_total],
                                ['Net to property', stmt.summary.net_to_property_total],
                                [`Mgmt fee (${stmt.summary.management_fee_pct}%)`, stmt.summary.management_fee_amount],
                            ].map(([label, val]) => (
                                <div key={label as string} style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    padding: 'var(--space-2) 0',
                                    borderBottom: '1px solid var(--color-border)',
                                    fontSize: 'var(--text-sm)',
                                }}>
                                    <span style={{ color: 'var(--color-text-dim)' }}>{label}</span>
                                    <span style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--color-text)' }}>
                                        {stmt.summary.currency} {val || '—'}
                                    </span>
                                </div>
                            ))}
                            <div style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                padding: 'var(--space-3) 0 0',
                                fontSize: 'var(--text-base)',
                                fontWeight: 700,
                            }}>
                                <span style={{ color: 'var(--color-text)' }}>Owner net</span>
                                <span style={{ color: 'var(--color-ok)', fontVariantNumeric: 'tabular-nums' }}>
                                    {stmt.summary.currency} {stmt.summary.owner_net_total || '—'}
                                </span>
                            </div>
                        </div>

                        {/* Line items */}
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 'var(--space-3)' }}>
                            Bookings ({stmt.line_items.length})
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                            {stmt.line_items.map(item => (
                                <div key={item.booking_id} style={{
                                    background: 'var(--color-surface-2)',
                                    borderRadius: 'var(--radius-md)',
                                    padding: 'var(--space-3) var(--space-4)',
                                    display: 'grid',
                                    gridTemplateColumns: '1fr auto',
                                    gap: 'var(--space-2)',
                                    alignItems: 'start',
                                }}>
                                    <div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 2 }}>
                                            <EpistemicBadge tier={item.epistemic_tier} />
                                            <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text)', fontFamily: 'var(--font-mono)' }}>
                                                {item.booking_id.slice(-8)}
                                            </span>
                                            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{item.provider}</span>
                                        </div>
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                                            {item.check_in || '—'} → {item.check_out || '—'}
                                        </div>
                                    </div>
                                    <div style={{ textAlign: 'right' }}>
                                        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--color-ok)', fontVariantNumeric: 'tabular-nums' }}>
                                            {item.currency} {item.net_to_property || '—'}
                                        </div>
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>
                                            gross {item.gross || '—'}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Owner Portal page
// ---------------------------------------------------------------------------

function currentMonth() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

export default function OwnerPage() {
    const [month, setMonth] = useState(currentMonth());
    const [cards, setCards] = useState<PropertyCard[]>([]);
    const [cashflow, setCashflow] = useState<ApiCashflowWeek[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedProperty, setSelectedProperty] = useState<string | null>(null);
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [propRes, cfRes] = await Promise.allSettled([
                api.getFinancialByProperty(month),
                api.getCashflowProjection(month),
            ]);

            // Properties
            if (propRes.status === 'fulfilled') {
                const byProp = propRes.value.properties || {};
                const built: PropertyCard[] = Object.entries(byProp).map(([propId, currencies]) => {
                    const firstCur = Object.keys(currencies)[0] || 'USD';
                    const bucket = (currencies as Record<string, {
                        gross: string;
                        commission: string;
                        net: string;
                        booking_count: number;
                    }>)[firstCur];
                    return {
                        property_id: propId,
                        currency: firstCur,
                        gross_total: bucket?.gross ?? null,
                        ota_commission_total: bucket?.commission ?? null,
                        owner_net_total: bucket?.net ?? null,
                        booking_count: bucket?.booking_count ?? 0,
                    };
                });
                setCards(built.sort((a, b) => a.property_id.localeCompare(b.property_id)));
            } else {
                setCards([]);
            }

            // Cashflow
            if (cfRes.status === 'fulfilled') {
                setCashflow(cfRes.value.weeks ?? []);
            } else {
                setCashflow([]);
            }
        } catch {
            setCards([]);
            setCashflow([]);
        } finally {
            setLoading(false);
        }
    }, [month]);

    useEffect(() => { load(); }, [load]);

    // 60s auto-refresh
    useEffect(() => {
        timerRef.current = setInterval(load, 60_000);
        return () => { if (timerRef.current) clearInterval(timerRef.current); };
    }, [load]);

    // SSE for real-time financial events (Phase 309)
    useEffect(() => {
        const token = typeof window !== 'undefined' ? localStorage.getItem('ihouse_token') ?? '' : '';
        const baseUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';
        const es = new EventSource(`${baseUrl}/events/stream?channels=financial&token=${token}`);
        es.onmessage = (e) => {
            try {
                const evt = JSON.parse(e.data);
                if (evt.channel === 'financial') {
                    setTimeout(load, 1000);
                }
            } catch { /* ignore */ }
        };
        return () => es.close();
    }, [load]);

    // Aggregate totals
    const totalGross = cards.reduce((s, c) => s + parseFloat(c.gross_total || '0'), 0);
    const totalNet = cards.reduce((s, c) => s + parseFloat(c.owner_net_total || '0'), 0);
    const totalBookings = cards.reduce((s, c) => s + c.booking_count, 0);
    const primaryCurrency = cards[0]?.currency || '—';

    return (
        <div style={{ maxWidth: 1000 }}>

            {/* Header */}
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-1)' }}>
                    Revenue & payouts
                </p>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
                    <h1 style={{
                        fontSize: 'var(--text-3xl)',
                        fontWeight: 700,
                        letterSpacing: '-0.03em',
                        color: 'var(--color-text)',
                    }}>
                        Owner <span style={{ color: 'var(--color-primary)' }}>Portal</span>
                    </h1>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                        <input
                            id="owner-month"
                            type="month"
                            value={month}
                            onChange={e => setMonth(e.target.value)}
                            style={{
                                background: 'var(--color-surface-2)',
                                border: '1px solid var(--color-border)',
                                borderRadius: 'var(--radius-md)',
                                color: 'var(--color-text)',
                                fontSize: 'var(--text-sm)',
                                padding: 'var(--space-2) var(--space-3)',
                                fontFamily: 'var(--font-mono)',
                            }}
                        />
                        <button
                            onClick={load}
                            disabled={loading}
                            style={{
                                background: loading ? 'var(--color-surface-3)' : 'var(--color-primary)',
                                color: '#fff',
                                border: 'none',
                                borderRadius: 'var(--radius-md)',
                                padding: 'var(--space-2) var(--space-5)',
                                fontSize: 'var(--text-sm)',
                                fontWeight: 600,
                                opacity: loading ? 0.7 : 1,
                                cursor: loading ? 'not-allowed' : 'pointer',
                                transition: 'all var(--transition-fast)',
                            }}
                        >
                            {loading ? '⟳' : '↺'}
                        </button>
                    </div>
                </div>
            </div>

            {/* Portfolio summary */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 200px), 1fr))',
                gap: 'var(--space-4)',
                marginBottom: 'var(--space-8)',
            }}>
                <MetricTile
                    label="Properties"
                    value={cards.length}
                    sub="in portfolio"
                    accent="var(--color-primary)"
                />
                <MetricTile
                    label="Total bookings"
                    value={totalBookings}
                    sub={month}
                />
                <MetricTile
                    label="Gross revenue"
                    value={`${primaryCurrency} ${totalGross.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                    sub="before commission"
                    accent="var(--color-text)"
                />
                <MetricTile
                    label="Owner net"
                    value={`${primaryCurrency} ${totalNet.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                    sub="after mgmt fee"
                    accent="var(--color-ok)"
                />
            </div>

            {/* Property cards */}
            <div style={{
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-faint)',
                textTransform: 'uppercase',
                letterSpacing: '0.07em',
                marginBottom: 'var(--space-4)',
            }}>
                Properties · click to view statement
            </div>

            {loading ? (
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', padding: 'var(--space-8) 0' }}>
                    Loading…
                </div>
            ) : cards.length === 0 ? (
                <div style={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-lg)',
                    padding: 'var(--space-10)',
                    textAlign: 'center',
                    color: 'var(--color-text-dim)',
                    fontSize: 'var(--text-sm)',
                }}>
                    No property data for {month}
                </div>
            ) : (
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                    gap: 'var(--space-4)',
                    marginBottom: 'var(--space-8)',
                }}>
                    {cards.map(card => (
                        <PropertyCard
                            key={card.property_id}
                            card={card}
                            month={month}
                            onSelect={setSelectedProperty}
                        />
                    ))}
                </div>
            )}

            {/* Cashflow timeline */}
            <div style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)',
                padding: 'var(--space-6)',
                marginBottom: 'var(--space-8)',
            }}>
                <div style={{
                    fontSize: 'var(--text-xs)',
                    color: 'var(--color-text-dim)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                    marginBottom: 'var(--space-4)',
                }}>
                    📅 Cashflow Timeline — expected weekly inflows
                </div>
                {cashflow.length === 0 ? (
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                        No cashflow data for {month}.{' '}
                        <a href="/financial" style={{ color: 'var(--color-primary)', textDecoration: 'none' }}>
                            View Financial Dashboard →
                        </a>
                    </p>
                ) : (() => {
                    const maxNet = Math.max(...cashflow.map(w => parseFloat(w.expected_net) || 0)) || 1;
                    return (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                            {cashflow.map(w => {
                                const net = parseFloat(w.expected_net) || 0;
                                const pct = (net / maxNet) * 100;
                                const weekLabel = w.week_start
                                    ? new Date(w.week_start).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
                                    : w.week;
                                return (
                                    <div key={w.week} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                                        <span style={{
                                            fontSize: 'var(--text-xs)',
                                            color: 'var(--color-text-dim)',
                                            fontFamily: 'var(--font-mono)',
                                            minWidth: 65,
                                            textAlign: 'right',
                                        }}>{weekLabel}</span>
                                        <div style={{ flex: 1, height: 16, background: 'var(--color-surface-3)', borderRadius: 4, overflow: 'hidden', position: 'relative' }}>
                                            <div style={{
                                                height: '100%',
                                                width: `${pct}%`,
                                                background: 'linear-gradient(90deg, var(--color-ok), #34d399)',
                                                borderRadius: 4,
                                                transition: 'width .5s ease',
                                            }} />
                                        </div>
                                        <span style={{
                                            fontSize: 'var(--text-xs)',
                                            fontWeight: 600,
                                            color: 'var(--color-ok)',
                                            fontVariantNumeric: 'tabular-nums',
                                            minWidth: 80,
                                            textAlign: 'right',
                                        }}>
                                            {w.currency} {net.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                                        </span>
                                        <span style={{
                                            fontSize: 'var(--text-xs)',
                                            color: 'var(--color-text-faint)',
                                            minWidth: 25,
                                            textAlign: 'right',
                                        }}>
                                            {w.booking_count}b
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    );
                })()}
            </div>

            {/* Footer */}
            <div style={{
                paddingTop: 'var(--space-6)',
                borderTop: '1px solid var(--color-border)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-faint)',
                display: 'flex',
                justifyContent: 'space-between',
            }}>
                <span>Domaniqo — Owner Portal · Phase 309</span>
                <span>Auto-refresh: 60s · SSE live</span>
            </div>

            {/* Statement drawer */}
            {selectedProperty && (
                <StatementDrawer
                    propertyId={selectedProperty}
                    month={month}
                    onClose={() => setSelectedProperty(null)}
                />
            )}
        </div>
    );
}
