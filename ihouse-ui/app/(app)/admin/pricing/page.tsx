'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface RateCard {
    id: string;
    room_type: string;
    season: string;
    base_rate: number;
    currency: string;
    created_at: string;
}

interface PriceSuggestion {
    date: string;
    suggested_rate: number;
    reason: string;
    confidence: number;
}

export default function RateCardsPricingPage() {
    const [rateCards, setRateCards] = useState<RateCard[]>([]);
    const [suggestions, setSuggestions] = useState<PriceSuggestion[]>([]);
    const [propertyId, setPropertyId] = useState('');
    const [loading, setLoading] = useState(false);
    const [notice, setNotice] = useState<string | null>(null);

    const showNotice = (msg: string) => { setNotice(msg); setTimeout(() => setNotice(null), 3000); };

    const loadData = useCallback(async () => {
        if (!propertyId) return;
        setLoading(true);
        try {
            const [rcRes, psRes] = await Promise.allSettled([
                api.getRateCards(propertyId),
                api.getPricingSuggestion(propertyId),
            ]);
            if (rcRes.status === 'fulfilled') setRateCards((rcRes.value.rate_cards || []) as RateCard[]);
            if (psRes.status === 'fulfilled') setSuggestions((psRes.value.suggestions || []) as PriceSuggestion[]);
        } catch { showNotice('Failed to load data'); }
        setLoading(false);
    }, [propertyId]);

    return (
        <div style={{ maxWidth: 1000 }}>
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Revenue management</p>
                <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                    Rate Cards & <span style={{ color: 'var(--color-primary)' }}>Pricing</span>
                </h1>
            </div>

            {/* Property selector */}
            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', marginBottom: 'var(--space-6)', display: 'flex', gap: 'var(--space-4)', alignItems: 'center' }}>
                <input
                    value={propertyId}
                    onChange={e => setPropertyId(e.target.value)}
                    placeholder="Enter property ID"
                    style={{ flex: 1, background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-3)', color: 'var(--color-text)', fontSize: 'var(--text-sm)' }}
                />
                <button onClick={loadData} disabled={!propertyId || loading} style={{ background: 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-5)', fontSize: 'var(--text-sm)', fontWeight: 600, cursor: propertyId ? 'pointer' : 'not-allowed', opacity: propertyId ? 1 : 0.5 }}>
                    {loading ? 'Loading…' : 'Load Pricing'}
                </button>
            </div>

            {notice && <div style={{ position: 'fixed', bottom: 'var(--space-6)', right: 'var(--space-6)', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)', fontSize: 'var(--text-sm)', color: 'var(--color-text)', boxShadow: '0 8px 32px rgba(0,0,0,0.4)', zIndex: 100 }}>{notice}</div>}

            {/* Rate Cards */}
            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', marginBottom: 'var(--space-6)' }}>
                <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 'var(--space-4)' }}>📋 Rate Cards</h2>
                {rateCards.length === 0 && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>{propertyId ? 'No rate cards found.' : 'Enter a property ID above.'}</p>}
                {rateCards.map(rc => (
                    <div key={rc.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-3) var(--space-4)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--space-2)' }}>
                        <div>
                            <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{rc.room_type}</span>
                            <span style={{ margin: '0 var(--space-2)', color: 'var(--color-text-dim)' }}>·</span>
                            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{rc.season}</span>
                        </div>
                        <span style={{ fontWeight: 700, fontSize: 'var(--text-sm)', color: 'var(--color-primary)', fontFamily: 'var(--font-mono)' }}>{rc.currency} {rc.base_rate}</span>
                    </div>
                ))}
            </div>

            {/* Dynamic Pricing Suggestions */}
            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 'var(--space-4)' }}>💡 Pricing Suggestions</h2>
                {suggestions.length === 0 && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>{propertyId ? 'No suggestions available.' : 'Load a property first.'}</p>}
                {suggestions.slice(0, 14).map((s, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-3) var(--space-4)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--space-2)' }}>
                        <div>
                            <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{s.date}</span>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{s.reason}</div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                            <div style={{ fontWeight: 700, fontSize: 'var(--text-sm)', color: 'var(--color-accent)', fontFamily: 'var(--font-mono)' }}>฿{s.suggested_rate}</div>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>{(s.confidence * 100).toFixed(0)}% conf</div>
                        </div>
                    </div>
                ))}
            </div>

            <div style={{ paddingTop: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>
                Domaniqo — Rate Cards & Pricing · Phase 514
            </div>
        </div>
    );
}
