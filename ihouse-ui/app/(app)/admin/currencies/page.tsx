'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

export default function CurrenciesPage() {
    const [rates, setRates] = useState<Record<string, number>>({});
    const [base, setBase] = useState('THB');
    const [loading, setLoading] = useState(true);
    const [amount, setAmount] = useState('1000');
    const [fromCur, setFromCur] = useState('THB');
    const [toCur, setToCur] = useState('USD');
    const [convertResult, setConvertResult] = useState<{ converted_amount?: number; rate?: number } | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await (api as any).getExchangeRates?.(base) || {};
            setRates(res.rates || {});
        } catch { /* graceful */ }
        setLoading(false);
    }, [base]);

    useEffect(() => { load(); }, [load]);

    const currencies = Object.entries(rates).sort((a, b) => a[0].localeCompare(b[0]));

    return (
        <div style={{ maxWidth: 900 }}>
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Multi-currency support</p>
                <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                    Exchange <span style={{ color: 'var(--color-primary)' }}>Rates</span>
                </h1>
            </div>

            {/* Rate table */}
            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', marginBottom: 'var(--space-6)' }}>
                <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 'var(--space-4)' }}>Current Rates (Base: {base})</h2>
                {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p>}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 'var(--space-2)' }}>
                    {currencies.map(([cur, rate]) => (
                        <div key={cur} style={{ padding: 'var(--space-2) var(--space-3)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{cur}</span>
                            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-accent)', fontFamily: 'var(--font-mono)' }}>{rate}</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Converter */}
            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 'var(--space-4)' }}>Currency Converter</h2>
                <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
                    <input value={amount} onChange={e => setAmount(e.target.value)} style={{ width: 120, background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-3)', color: 'var(--color-text)', fontSize: 'var(--text-sm)' }} />
                    <select value={fromCur} onChange={e => setFromCur(e.target.value)} style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-3)', color: 'var(--color-text)', fontSize: 'var(--text-sm)' }}>
                        {currencies.map(([c]) => <option key={c} value={c}>{c}</option>)}
                    </select>
                    <span style={{ color: 'var(--color-text-dim)' }}>→</span>
                    <select value={toCur} onChange={e => setToCur(e.target.value)} style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-3)', color: 'var(--color-text)', fontSize: 'var(--text-sm)' }}>
                        {currencies.map(([c]) => <option key={c} value={c}>{c}</option>)}
                    </select>
                </div>
                {convertResult && (
                    <div style={{ marginTop: 'var(--space-3)', padding: 'var(--space-3) var(--space-4)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)' }}>
                        <span style={{ fontWeight: 700, fontSize: 'var(--text-lg)', color: 'var(--color-accent)' }}>{convertResult.converted_amount} {toCur}</span>
                        <span style={{ marginLeft: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>Rate: {convertResult.rate}</span>
                    </div>
                )}
            </div>

            <div style={{ paddingTop: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>
                Domaniqo — Exchange Rates · Phase 523
            </div>
        </div>
    );
}
