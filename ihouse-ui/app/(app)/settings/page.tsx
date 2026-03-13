'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

export default function SettingsPage() {
    const [profile, setProfile] = useState<{ tenant_id: string; role: string; email?: string } | null>(null);
    const [loading, setLoading] = useState(true);
    const [currentPw, setCurrentPw] = useState('');
    const [newPw, setNewPw] = useState('');
    const [notice, setNotice] = useState<string | null>(null);
    const [tz, setTz] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone);

    const showNotice = (msg: string) => { setNotice(msg); setTimeout(() => setNotice(null), 3000); };

    useEffect(() => {
        (async () => {
            try {
                const res = await api.getSessionInfo();
                setProfile(res as any);
            } catch { setProfile({ tenant_id: '—', role: '—' }); }
            setLoading(false);
        })();
    }, []);

    const handlePasswordChange = async () => {
        if (!newPw || newPw.length < 6) { showNotice('⚠ Password must be at least 6 characters'); return; }
        showNotice('✓ Password updated (demo)');
        setCurrentPw(''); setNewPw('');
    };

    return (
        <div style={{ maxWidth: 700 }}>
            {notice && <div style={{ position: 'fixed', bottom: 'var(--space-6)', right: 'var(--space-6)', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)', fontSize: 'var(--text-sm)', color: 'var(--color-text)', boxShadow: '0 8px 32px rgba(0,0,0,0.4)', zIndex: 100 }}>{notice}</div>}

            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Account</p>
                <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                    <span style={{ color: 'var(--color-primary)' }}>Settings</span>
                </h1>
            </div>

            {/* Profile info */}
            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', marginBottom: 'var(--space-6)' }}>
                <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 'var(--space-4)' }}>Profile</h2>
                {loading ? <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p> : (
                    <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 'var(--space-3)' }}>
                        {[
                            ['Tenant', profile?.tenant_id || '—'],
                            ['Role', profile?.role || '—'],
                            ['Email', profile?.email || '(not set)'],
                        ].map(([label, value]) => (
                            <>
                                <div key={`${label}-l`} style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', paddingTop: 2 }}>{label}</div>
                                <div key={`${label}-v`} style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)', fontFamily: label === 'Tenant' ? 'var(--font-mono)' : 'inherit' }}>{value}</div>
                            </>
                        ))}
                    </div>
                )}
            </div>

            {/* Timezone */}
            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', marginBottom: 'var(--space-6)' }}>
                <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 'var(--space-4)' }}>Timezone</h2>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                    <select value={tz} onChange={e => { setTz(e.target.value); showNotice('✓ Timezone updated'); }}
                        style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', padding: 'var(--space-2) var(--space-3)', flex: 1 }}>
                        {['Asia/Bangkok', 'Asia/Jerusalem', 'Europe/London', 'America/New_York', 'America/Los_Angeles', 'Asia/Tokyo', 'Australia/Sydney'].map(z => (
                            <option key={z} value={z}>{z}</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Password change */}
            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 'var(--space-4)' }}>Change Password</h2>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                    <input type="password" placeholder="Current password" value={currentPw} onChange={e => setCurrentPw(e.target.value)}
                        style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', padding: 'var(--space-2) var(--space-3)' }} />
                    <input type="password" placeholder="New password (min. 6 characters)" value={newPw} onChange={e => setNewPw(e.target.value)}
                        style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', padding: 'var(--space-2) var(--space-3)' }} />
                    <button onClick={handlePasswordChange} disabled={!currentPw || !newPw}
                        style={{ background: (!currentPw || !newPw) ? 'var(--color-surface-3)' : 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-5)', fontSize: 'var(--text-sm)', fontWeight: 600, cursor: (!currentPw || !newPw) ? 'not-allowed' : 'pointer', alignSelf: 'flex-start' }}>
                        Update Password
                    </button>
                </div>
            </div>

            <div style={{ paddingTop: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>
                iHouse Core — Settings · Phase 528
            </div>
        </div>
    );
}
