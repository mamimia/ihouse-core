'use client';

/**
 * Phase 193 — Guest Profile UI
 * Route: /guests
 *
 * Guest list with:
 *  - Live search bar (debounced)
 *  - Guest table (name, email, phone, nationality, created_at)
 *  - "New Guest" slide-in create panel
 *  - Empty / loading states
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { api, Guest } from '../../lib/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtDate(s: string | undefined | null) {
    if (!s) return '—';
    return new Date(s).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' });
}

function useDebounce<T>(value: T, ms = 350): T {
    const [dval, setDval] = useState(value);
    useEffect(() => {
        const t = setTimeout(() => setDval(value), ms);
        return () => clearTimeout(t);
    }, [value, ms]);
    return dval;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Skeleton() {
    return (
        <div style={{
            background: 'linear-gradient(90deg, var(--color-surface-2) 25%, var(--color-surface-3) 50%, var(--color-surface-2) 75%)',
            backgroundSize: '200% 100%',
            animation: 'shimmer 1.4s infinite',
            borderRadius: 'var(--radius-md)',
            height: 16, width: '60%',
        }} />
    );
}

function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
    return (
        <th style={{
            padding: 'var(--space-3) var(--space-4)',
            textAlign: right ? 'right' : 'left',
            color: 'var(--color-text-dim)', fontWeight: 600,
            fontSize: 'var(--text-xs)', textTransform: 'uppercase', letterSpacing: '0.06em',
            borderBottom: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
            whiteSpace: 'nowrap',
        }}>{children}</th>
    );
}

function Td({ children, right, muted }: { children: React.ReactNode; right?: boolean; muted?: boolean }) {
    return (
        <td style={{
            padding: 'var(--space-3) var(--space-4)', textAlign: right ? 'right' : 'left',
            color: muted ? 'var(--color-text-dim)' : 'var(--color-text)',
            borderBottom: '1px solid var(--color-border)', fontSize: 'var(--text-sm)',
            whiteSpace: 'nowrap',
        }}>{children}</td>
    );
}

// ---------------------------------------------------------------------------
// Create Panel (slide-in)
// ---------------------------------------------------------------------------

function CreatePanel({ onCreated, onClose }: { onCreated: (g: Guest) => void; onClose: () => void }) {
    const [form, setForm] = useState({ full_name: '', email: '', phone: '', nationality: '' });
    const [saving, setSaving] = useState(false);
    const [err, setErr] = useState<string | null>(null);

    const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
        setForm(f => ({ ...f, [k]: e.target.value }));

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!form.full_name.trim()) { setErr('Full name is required'); return; }
        setSaving(true); setErr(null);
        try {
            const g = await api.createGuest({
                full_name: form.full_name.trim(),
                email: form.email || undefined,
                phone: form.phone || undefined,
                nationality: form.nationality || undefined,
            });
            onCreated(g);
        } catch {
            setErr('Failed to create guest — please try again.');
        } finally {
            setSaving(false);
        }
    };

    const inputStyle: React.CSSProperties = {
        width: '100%', padding: '8px 10px',
        background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)', color: 'var(--color-text)',
        fontSize: 'var(--text-sm)', boxSizing: 'border-box',
    };
    const labelStyle: React.CSSProperties = {
        display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600,
        color: 'var(--color-text-dim)', textTransform: 'uppercase',
        letterSpacing: '0.05em', marginBottom: 4,
    };

    return (
        <div style={{
            position: 'fixed', top: 0, right: 0, bottom: 0, width: 360,
            background: 'var(--color-surface)', borderLeft: '1px solid var(--color-border)',
            zIndex: 100, display: 'flex', flexDirection: 'column',
            boxShadow: '-4px 0 24px rgba(0,0,0,0.25)',
            animation: 'slideIn .2s ease',
        }}>
            <style>{`
                @keyframes slideIn { from { transform: translateX(40px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
            `}</style>
            <div style={{ padding: 'var(--space-6)', borderBottom: '1px solid var(--color-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <h2 style={{ margin: 0, fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--color-text)' }}>New Guest</h2>
                <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-dim)', fontSize: 20, lineHeight: 1 }}>✕</button>
            </div>

            <form onSubmit={submit} style={{ flex: 1, padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-5)', overflowY: 'auto' }}>
                <div>
                    <label style={labelStyle}>Full Name *</label>
                    <input id="new-guest-name" value={form.full_name} onChange={set('full_name')} style={inputStyle} placeholder="Alice Smith" autoFocus />
                </div>
                <div>
                    <label style={labelStyle}>Email</label>
                    <input type="email" value={form.email} onChange={set('email')} style={inputStyle} placeholder="alice@example.com" />
                </div>
                <div>
                    <label style={labelStyle}>Phone</label>
                    <input value={form.phone} onChange={set('phone')} style={inputStyle} placeholder="+66 81 000 0000" />
                </div>
                <div>
                    <label style={labelStyle}>Nationality</label>
                    <input value={form.nationality} onChange={set('nationality')} style={inputStyle} placeholder="TH" maxLength={3} />
                </div>

                {err && (
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-danger)', background: 'rgba(239,68,68,0.08)', borderRadius: 'var(--radius-md)', padding: '8px 10px' }}>
                        {err}
                    </div>
                )}

                <div style={{ marginTop: 'auto', display: 'flex', gap: 'var(--space-3)' }}>
                    <button
                        type="submit" disabled={saving}
                        style={{
                            flex: 1, padding: '10px', background: 'var(--color-primary)',
                            color: '#fff', border: 'none', borderRadius: 'var(--radius-md)',
                            fontWeight: 600, fontSize: 'var(--text-sm)', cursor: saving ? 'default' : 'pointer',
                            opacity: saving ? 0.7 : 1,
                        }}
                    >{saving ? 'Creating…' : 'Create Guest'}</button>
                    <button type="button" onClick={onClose} style={{ padding: '10px 16px', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text)', cursor: 'pointer', fontSize: 'var(--text-sm)' }}>
                        Cancel
                    </button>
                </div>
            </form>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function GuestsPage() {
    const [search, setSearch] = useState('');
    const debouncedSearch = useDebounce(search);
    const [guests, setGuests] = useState<Guest[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [creating, setCreating] = useState(false);
    const searchInputRef = useRef<HTMLInputElement>(null);

    const load = useCallback(async (q: string) => {
        setLoading(true); setError(null);
        try {
            const res = await api.listGuests(q || undefined);
            setGuests(res.guests);
        } catch {
            setError('Failed to load guests.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(debouncedSearch); }, [debouncedSearch, load]);

    const handleCreated = (g: Guest) => {
        setGuests(prev => [g, ...prev]);
        setCreating(false);
    };

    return (
        <div style={{ minHeight: '100vh', background: 'var(--color-bg)', padding: 'var(--space-8) var(--space-6)' }}>
            <style>{`
                @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
                @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
            `}</style>

            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--space-4)', marginBottom: 'var(--space-8)' }}>
                <div>
                    <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: 'var(--color-text)', margin: 0 }}>Guests</h1>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 4 }}>
                        Guest identity records · {loading ? '…' : guests.length + ' shown'}
                    </p>
                </div>
                <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center' }}>
                    {/* Search */}
                    <div style={{ position: 'relative' }}>
                        <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-text-dim)', fontSize: 14, pointerEvents: 'none' }}>🔍</span>
                        <input
                            ref={searchInputRef}
                            id="guest-search"
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                            placeholder="Search name or email…"
                            style={{
                                paddingLeft: 32, paddingRight: 12, paddingTop: 8, paddingBottom: 8,
                                background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                                borderRadius: 'var(--radius-md)', color: 'var(--color-text)',
                                fontSize: 'var(--text-sm)', width: 220,
                            }}
                        />
                    </div>
                    <button
                        id="new-guest-btn"
                        onClick={() => setCreating(true)}
                        style={{
                            padding: '8px 16px', background: 'var(--color-primary)', color: '#fff',
                            border: 'none', borderRadius: 'var(--radius-md)', fontWeight: 600,
                            fontSize: 'var(--text-sm)', cursor: 'pointer', whiteSpace: 'nowrap',
                        }}
                    >+ New Guest</button>
                </div>
            </div>

            {/* Error */}
            {error && (
                <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 'var(--radius-md)', padding: 'var(--space-4)', color: 'var(--color-danger)', marginBottom: 'var(--space-6)', fontSize: 'var(--text-sm)' }}>
                    ⚠ {error}
                </div>
            )}

            {/* PII notice */}
            <div style={{ background: 'rgba(99,102,241,0.07)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)', marginBottom: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>🔒</span> This page contains personally identifiable information (PII). Handle with care.
            </div>

            {/* Table */}
            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden', animation: 'fadeIn .3s ease' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--text-sm)' }}>
                    <thead>
                        <tr>
                            <Th>Name</Th>
                            <Th>Email</Th>
                            <Th>Phone</Th>
                            <Th>Nationality</Th>
                            <Th>Created</Th>
                            <Th right>Detail</Th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            [1, 2, 3, 4, 5].map(i => (
                                <tr key={i}>
                                    {[1, 2, 3, 4, 5, 6].map(j => (
                                        <td key={j} style={{ padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)' }}>
                                            <Skeleton />
                                        </td>
                                    ))}
                                </tr>
                            ))
                        ) : guests.length === 0 ? (
                            <tr>
                                <td colSpan={6} style={{ textAlign: 'center', padding: 'var(--space-12)', color: 'var(--color-muted)', fontSize: 'var(--text-sm)' }}>
                                    {search ? `No guests match "${search}"` : 'No guests yet — create one above.'}
                                </td>
                            </tr>
                        ) : (
                            guests.map(g => (
                                <tr
                                    key={g.id}
                                    style={{ transition: 'background .12s' }}
                                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(59,130,246,0.04)')}
                                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                                >
                                    <Td>
                                        <span style={{ fontWeight: 600, color: 'var(--color-text)' }}>{g.full_name}</span>
                                    </Td>
                                    <Td muted={!g.email}>{g.email ?? '—'}</Td>
                                    <Td muted={!g.phone}>{g.phone ?? '—'}</Td>
                                    <Td>
                                        {g.nationality
                                            ? <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, padding: '2px 8px', borderRadius: 'var(--radius-full)', background: 'var(--color-surface-2)', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)' }}>{g.nationality}</span>
                                            : <span style={{ color: 'var(--color-muted)' }}>—</span>}
                                    </Td>
                                    <Td muted>{fmtDate(g.created_at)}</Td>
                                    <td style={{ padding: 'var(--space-3) var(--space-4)', textAlign: 'right', borderBottom: '1px solid var(--color-border)' }}>
                                        <a
                                            href={`/guests/${g.id}`}
                                            style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-primary)', textDecoration: 'none' }}
                                        >
                                            View →
                                        </a>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>

            {/* Create slide-in */}
            {creating && <CreatePanel onCreated={handleCreated} onClose={() => setCreating(false)} />}
        </div>
    );
}
