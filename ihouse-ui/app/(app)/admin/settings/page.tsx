'use client';

/**
 * Admin Settings — /admin/settings
 * Property ID auto-generation configuration.
 */

import { useEffect, useState } from 'react';
import { getToken } from '@/lib/api';

const BASE = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

async function apiFetch<T = any>(path: string, init?: RequestInit): Promise<T> {
    const token = getToken();
    const res = await fetch(`${BASE}${path}`, {
        ...init,
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(init?.headers || {}),
        },
    });
    if (!res.ok) throw new Error(`${res.status}`);
    return res.json();
}

export default function AdminSettingsPage() {
    const [prefix, setPrefix] = useState('KPG');
    const [startNumber, setStartNumber] = useState(500);
    const [nextId, setNextId] = useState('');
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [notice, setNotice] = useState<string | null>(null);

    const showNotice = (msg: string) => { setNotice(msg); setTimeout(() => setNotice(null), 3500); };

    useEffect(() => {
        apiFetch('/admin/property-id-settings')
            .then(data => {
                setPrefix(data.prefix ?? 'KPG');
                setStartNumber(data.start_number ?? 500);
                setNextId(data.next_id ?? '');
            })
            .catch(() => {})
            .finally(() => setLoading(false));
    }, []);

    // Live preview: update nextId as user types
    useEffect(() => {
        if (prefix.trim()) {
            setNextId(`${prefix.trim().toUpperCase()}-${startNumber} (preview only until saved)`);
        }
    }, [prefix, startNumber]);

    const handleSave = async () => {
        if (!prefix.trim() || prefix.length > 10) {
            showNotice('Prefix must be 1–10 characters.');
            return;
        }
        if (startNumber < 1) {
            showNotice('Starting number must be at least 1.');
            return;
        }
        setSaving(true);
        try {
            const data = await apiFetch('/admin/property-id-settings', {
                method: 'PUT',
                body: JSON.stringify({ prefix: prefix.trim().toUpperCase(), start_number: startNumber }),
            });
            setPrefix(data.prefix);
            setStartNumber(data.start_number);
            setNextId(data.next_id);
            showNotice(`✓ Saved. Next property ID will be ${data.next_id}`);
        } catch {
            showNotice('Save failed. Please try again.');
        }
        setSaving(false);
    };

    const inputStyle: React.CSSProperties = {
        width: '100%', boxSizing: 'border-box',
        background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-sm)', color: 'var(--color-text)',
        fontSize: 'var(--text-sm)', padding: '10px 14px',
    };
    const labelStyle: React.CSSProperties = {
        fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)',
        fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em',
        marginBottom: 6, display: 'block',
    };
    const sectionStyle: React.CSSProperties = {
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)', padding: 'var(--space-6)',
        marginBottom: 'var(--space-5)',
    };

    return (
        <div style={{ maxWidth: 640 }}>
            {/* Notice toast */}
            {notice && (
                <div style={{
                    position: 'fixed', top: 20, right: 20, zIndex: 999,
                    background: 'var(--color-surface)', border: '1px solid var(--color-primary)',
                    borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)',
                    fontSize: 'var(--text-sm)', color: 'var(--color-primary)', boxShadow: 'var(--shadow-md)',
                }}>
                    {notice}
                </div>
            )}

            {/* Page header */}
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
                    Admin
                </p>
                <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text)', letterSpacing: '-0.03em', margin: 0 }}>
                    Settings
                </h1>
            </div>

            {loading ? (
                <div style={{ color: 'var(--color-text-dim)' }}>Loading…</div>
            ) : (
                <>
                    {/* Property ID Section */}
                    <div style={sectionStyle}>
                        <div style={{
                            fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)',
                            textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 'var(--space-5)',
                        }}>
                            Property ID Auto-generation
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)', marginBottom: 'var(--space-5)' }}>
                            <div>
                                <label style={labelStyle} htmlFor="id-prefix">Prefix</label>
                                <input
                                    id="id-prefix"
                                    style={inputStyle}
                                    value={prefix}
                                    onChange={e => setPrefix(e.target.value.toUpperCase())}
                                    maxLength={10}
                                    placeholder="e.g. KPG"
                                />
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 4 }}>
                                    Max 10 characters
                                </div>
                            </div>
                            <div>
                                <label style={labelStyle} htmlFor="id-start">Starting number</label>
                                <input
                                    id="id-start"
                                    style={inputStyle}
                                    type="number"
                                    min={1}
                                    value={startNumber}
                                    onChange={e => setStartNumber(parseInt(e.target.value) || 1)}
                                />
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 4 }}>
                                    Only applies if no properties with this prefix exist yet
                                </div>
                            </div>
                        </div>

                        {/* Next ID preview */}
                        {nextId && (
                            <div style={{
                                background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                                borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-4)',
                                marginBottom: 'var(--space-5)', fontSize: 'var(--text-sm)',
                                color: 'var(--color-text)',
                            }}>
                                <span style={{ color: 'var(--color-text-faint)' }}>Next property will be assigned: </span>
                                <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-primary)' }}>
                                    {nextId.includes('preview') ? `${prefix.trim().toUpperCase() || 'KPG'}-??? (save to confirm)` : nextId}
                                </strong>
                            </div>
                        )}

                        {/* Immutability notice */}
                        <div style={{
                            background: 'rgba(181,110,69,0.06)', border: '1px solid rgba(181,110,69,0.2)',
                            borderRadius: 'var(--radius-sm)', padding: 'var(--space-3) var(--space-4)',
                            marginBottom: 'var(--space-5)', fontSize: 'var(--text-xs)', color: 'var(--color-warn)',
                        }}>
                            <strong>Immutability rules:</strong><br />
                            • Property IDs are assigned automatically at creation and <strong>cannot be changed</strong> once set.<br />
                            • IDs are <strong>never reused</strong> — not even after archiving or deletion.<br />
                            • Archived properties retain their original IDs permanently.
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                            <button
                                onClick={handleSave}
                                disabled={saving}
                                style={{
                                    background: saving ? 'var(--color-border)' : 'var(--color-primary)',
                                    color: '#fff', border: 'none', borderRadius: 'var(--radius-md)',
                                    padding: '10px 28px', fontSize: 'var(--text-sm)', fontWeight: 700,
                                    cursor: saving ? 'not-allowed' : 'pointer',
                                    boxShadow: saving ? 'none' : 'var(--shadow-sm)',
                                }}
                            >{saving ? 'Saving…' : 'Save Settings'}</button>
                        </div>
                    </div>

                    {/* Future sections placeholder */}
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textAlign: 'center', padding: 'var(--space-4)' }}>
                        More admin settings will appear here in future phases.
                    </div>
                </>
            )}

            <div style={{ marginTop: 'var(--space-8)', paddingTop: 'var(--space-5)', borderTop: '1px solid var(--color-border)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>
                iHouse Core · Admin Settings · Phase 844
            </div>
        </div>
    );
}
