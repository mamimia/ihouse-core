'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

export default function BulkOperationsPage() {
    const [results, setResults] = useState<{ action: string; status: string; affected: number }[]>([]);
    const [loading, setLoading] = useState(false);
    const [notice, setNotice] = useState<string | null>(null);

    const showNotice = (msg: string) => { setNotice(msg); setTimeout(() => setNotice(null), 3000); };

    const actions = [
        { id: 'bulk_sync', label: '🔄 Trigger Full Sync', desc: 'Force outbound sync for all active properties' },
        { id: 'bulk_financial', label: '💰 Extract Financials', desc: 'Re-run financial extraction for all bookings' },
        { id: 'bulk_guest', label: '👤 Backfill Guests', desc: 'Extract guest profiles from all bookings' },
    ];

    return (
        <div style={{ maxWidth: 900 }}>
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Power tools</p>
                <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                    Bulk <span style={{ color: 'var(--color-primary)' }}>Operations</span>
                </h1>
            </div>

            {notice && <div style={{ position: 'fixed', bottom: 'var(--space-6)', right: 'var(--space-6)', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)', fontSize: 'var(--text-sm)', color: 'var(--color-text)', boxShadow: '0 8px 32px rgba(0,0,0,0.4)', zIndex: 100 }}>{notice}</div>}

            <div style={{ display: 'grid', gap: 'var(--space-4)' }}>
                {actions.map(a => (
                    <div key={a.id} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                            <div style={{ fontWeight: 600, fontSize: 'var(--text-base)', color: 'var(--color-text)' }}>{a.label}</div>
                            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-1)' }}>{a.desc}</div>
                        </div>
                        <button onClick={() => showNotice(`✓ ${a.label} triggered (dry-run)`)} style={{ background: 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-5)', fontSize: 'var(--text-sm)', fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                            Execute
                        </button>
                    </div>
                ))}
            </div>

            <div style={{ paddingTop: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>
                Domaniqo — Bulk Operations · Phase 521
            </div>
        </div>
    );
}
