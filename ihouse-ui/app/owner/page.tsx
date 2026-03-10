'use client';

import { useEffect, useState, useCallback } from 'react';
import { api, OwnerStatementResponse, FinancialByPropertyResponse } from '@/lib/api';

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

interface CashflowWeek {
    week_start: string;
    expected_inflow: string;
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
                gridTemplateColumns: '1fr 1fr 1fr',
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

    useEffect(() => {
        setLoading(true);
        api.getOwnerStatement(propertyId, month)
            .then(setStmt)
            .catch(() => setStmt(null))
            .finally(() => setLoading(false));
    }, [propertyId, month]);

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
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-6)' }}>
                    <div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 2 }}>Owner Statement</div>
                        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)' }}>
                            {propertyId} · {month}
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: 'var(--color-text-dim)' }}
                    >✕</button>
                </div>

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
    const [loading, setLoading] = useState(true);
    const [selectedProperty, setSelectedProperty] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.getFinancialByProperty(month);
            // Flatten into PropertyCard[]
            const byProp = res.properties || {};
            const built: PropertyCard[] = Object.entries(byProp).map(([propId, currencies]) => {
                // Pick first currency bucket (primary)
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
        } catch {
            setCards([]);
        } finally {
            setLoading(false);
        }
    }, [month]);

    useEffect(() => { load(); }, [load]);

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
                gridTemplateColumns: 'repeat(4, 1fr)',
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

            {/* Payout timeline placeholder */}
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
                    📅 Payout Timeline — upcoming expected inflows
                </div>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                    Cashflow projection available via{' '}
                    <a href="/financial" style={{ color: 'var(--color-primary)', textDecoration: 'none' }}>
                        Financial Dashboard →
                    </a>
                </p>
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
                <span>iHouse Core — Owner Portal · Phase 170</span>
                <span>Role-scoped via Phase 165–166 · Statement: Phase 121</span>
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
