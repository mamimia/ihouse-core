'use client';

/**
 * Phase 862 P19 — Profile Page
 *
 * Shared profile page accessible to ALL authenticated users regardless of role.
 * Calls GET /auth/profile and PATCH /auth/profile.
 * Client-side auth check redirects to /login if no Supabase session.
 */

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import DMonogram from '@/components/DMonogram';
import PasswordInput from '@/components/auth/PasswordInput';
import { supabase } from '@/lib/supabaseClient';
import { usePasswordRules } from '@/hooks/usePasswordRules';
import SignedInShell, { SHELL_TOP_PADDING } from '@/components/SignedInShell';

interface Profile {
    user_id: string;
    email: string;
    full_name: string;
    phone: string;
    avatar_url: string;
    language: string;
    providers: string[];       // Phase 862 P29: linked login methods
    role: string;
    tenant_id: string;
    has_membership: boolean;
}

const card: React.CSSProperties = {
    background: 'var(--color-elevated, #1E2127)',
    border: '1px solid rgba(234,229,222,0.06)',
    borderRadius: 'var(--radius-lg, 16px)',
    padding: 'var(--space-6, 24px)',
};

const inputStyle: React.CSSProperties = {
    background: 'rgba(234,229,222,0.04)',
    border: '1px solid rgba(234,229,222,0.1)',
    borderRadius: '10px',
    padding: '12px 16px',
    color: 'var(--color-text-primary, #EAE5DE)',
    fontSize: '15px',
    width: '100%',
    outline: 'none',
};

const labelStyle: React.CSSProperties = {
    color: 'rgba(234,229,222,0.5)',
    fontSize: '13px',
    fontWeight: 500,
    marginBottom: '6px',
    display: 'block',
};

const btnPrimary: React.CSSProperties = {
    background: 'linear-gradient(135deg, #B56E45, #C4854F)',
    color: '#fff',
    border: 'none',
    borderRadius: '10px',
    padding: '12px 28px',
    fontSize: '15px',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'opacity 0.2s',
};

export default function ProfilePage() {
    const router = useRouter();
    const [profile, setProfile] = useState<Profile | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState('');
    const [editMode, setEditMode] = useState(false);
    const [form, setForm] = useState({ full_name: '', phone: '', language: '' });
    // Phase 873: inline add-password state
    const [addPasswordMode, setAddPasswordMode] = useState(false);
    const [newPassword, setNewPassword] = useState('');
    const [confirmNewPassword, setConfirmNewPassword] = useState('');
    const [passwordFocused, setPasswordFocused] = useState(false);
    const pwRules = usePasswordRules(newPassword);
    const allPwRulesPass = pwRules.every(r => r.pass);

    const fetchProfile = useCallback(async () => {
        try {
            if (!supabase) { router.push('/login'); return; }
            const { data: { session } } = await supabase.auth.getSession();
            if (!session) { router.push('/login'); return; }

            const token = document.cookie
                .split('; ')
                .find(c => c.startsWith('ihouse_token='))
                ?.split('=')[1];

            if (!token) { router.push('/login'); return; }

            const apiBase = process.env.NEXT_PUBLIC_API_URL || '';
            const res = await fetch(`${apiBase}/auth/profile`, {
                headers: { 'Authorization': `Bearer ${token}` },
            });

            if (!res.ok) { setMessage('Failed to load profile'); setLoading(false); return; }

            const data = await res.json();
            const p = data.data || data;
            setProfile(p);
            setForm({ full_name: p.full_name || '', phone: p.phone || '', language: p.language || '' });
        } catch (e) {
            setMessage('Error loading profile');
        }
        setLoading(false);
    }, [router]);

    useEffect(() => { fetchProfile(); }, [fetchProfile]);

    const handleSave = async () => {
        setSaving(true);
        setMessage('');
        try {
            const token = document.cookie
                .split('; ')
                .find(c => c.startsWith('ihouse_token='))
                ?.split('=')[1];

            const apiBase = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
            const res = await fetch(`${apiBase}/auth/profile`, {
                method: 'PATCH',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    full_name: form.full_name.trim() || undefined,
                    phone: form.phone.trim() || undefined,
                    language: form.language.trim() || undefined,
                }),
            });

            if (res.ok) {
                setMessage('Profile updated ✓');
                setEditMode(false);
                fetchProfile();
            } else {
                setMessage('Failed to save');
            }
        } catch {
            setMessage('Error saving profile');
        }
        setSaving(false);
    };

    if (loading) {
        return (
            <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--color-background, #161719)' }}>
                <div style={{ color: 'rgba(234,229,222,0.4)', fontSize: '15px' }}>Loading…</div>
            </div>
        );
    }

    return (
        <>
        <SignedInShell back="/welcome" backLabel="← Home" />
        <div style={{ minHeight: '100vh', background: 'var(--color-background, #161719)', paddingTop: SHELL_TOP_PADDING, padding: `${SHELL_TOP_PADDING} var(--space-6, 24px) var(--space-10, 40px)` }}>
            <div style={{ maxWidth: 600, margin: '0 auto' }}>

                {message && (
                    <div style={{
                        padding: '10px 16px',
                        borderRadius: '10px',
                        background: message.includes('✓') ? 'rgba(74,124,89,0.1)' : 'rgba(181,110,69,0.1)',
                        color: message.includes('✓') ? '#4A7C59' : '#B56E45',
                        fontSize: '14px',
                        marginBottom: 'var(--space-4, 16px)',
                    }}>
                        {message}
                    </div>
                )}

                <div style={card}>
                    {/* Email (read-only) */}
                    <div style={{ marginBottom: 'var(--space-4, 16px)' }}>
                        <label style={labelStyle}>Email</label>
                        <div style={{
                            ...inputStyle,
                            opacity: 0.6,
                            cursor: 'not-allowed',
                        }}>
                            {profile?.email || '—'}
                        </div>
                    </div>

                    {/* Full Name */}
                    <div style={{ marginBottom: 'var(--space-4, 16px)' }}>
                        <label style={labelStyle}>Full Name</label>
                        {editMode ? (
                            <input
                                style={inputStyle}
                                value={form.full_name}
                                onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))}
                                placeholder="Your name"
                            />
                        ) : (
                            <div style={inputStyle}>{profile?.full_name || '—'}</div>
                        )}
                    </div>

                    {/* Phone */}
                    <div style={{ marginBottom: 'var(--space-4, 16px)' }}>
                        <label style={labelStyle}>Phone</label>
                        {editMode ? (
                            <input
                                style={inputStyle}
                                value={form.phone}
                                onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                                placeholder="+66 XXX XXX XXXX"
                            />
                        ) : (
                            <div style={inputStyle}>{profile?.phone || '—'}</div>
                        )}
                    </div>

                    {/* Language */}
                    <div style={{ marginBottom: 'var(--space-6, 24px)' }}>
                        <label style={labelStyle}>Language</label>
                        {editMode ? (
                            <select
                                style={{ ...inputStyle, appearance: 'auto' as any }}
                                value={form.language}
                                onChange={e => setForm(f => ({ ...f, language: e.target.value }))}
                            >
                                <option value="">Not set</option>
                                <option value="en">English</option>
                                <option value="th">ไทย</option>
                                <option value="he">עברית</option>
                            </select>
                        ) : (
                            <div style={inputStyle}>
                                {profile?.language === 'th' ? 'ไทย' :
                                 profile?.language === 'he' ? 'עברית' :
                                 profile?.language === 'en' ? 'English' : '—'}
                            </div>
                        )}
                    </div>

                    {/* Actions */}
                    <div style={{ display: 'flex', gap: '12px' }}>
                        {editMode ? (
                            <>
                                <button
                                    style={btnPrimary}
                                    onClick={handleSave}
                                    disabled={saving}
                                >
                                    {saving ? 'Saving…' : 'Save'}
                                </button>
                                <button
                                    style={{
                                        ...btnPrimary,
                                        background: 'rgba(234,229,222,0.06)',
                                        color: 'var(--color-text-primary, #EAE5DE)',
                                    }}
                                    onClick={() => {
                                        setEditMode(false);
                                        setForm({
                                            full_name: profile?.full_name || '',
                                            phone: profile?.phone || '',
                                            language: profile?.language || '',
                                        });
                                    }}
                                >
                                    Cancel
                                </button>
                            </>
                        ) : (
                            <button
                                style={btnPrimary}
                                onClick={() => setEditMode(true)}
                            >
                                Edit Profile
                            </button>
                        )}
                    </div>
                </div>

                {/* Linked Login Methods — Phase 862 P40: Interactive Linking */}
                <div style={{ ...card, marginTop: 'var(--space-4, 16px)' }}>
                    <label style={labelStyle}>Linked Login Methods</label>

                    {/* Current providers */}
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
                        {(profile?.providers || []).map(provider => (
                            <span
                                key={provider}
                                style={{
                                    background: 'rgba(234,229,222,0.06)',
                                    border: '1px solid rgba(234,229,222,0.1)',
                                    borderRadius: '6px',
                                    padding: '6px 12px',
                                    fontSize: '13px',
                                    color: 'var(--color-text-primary, #EAE5DE)',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '6px',
                                }}
                            >
                                {provider === 'email' ? '📧 Email' : provider === 'google' ? '🔵 Google' : provider}
                                {/* Show unlink button only if > 1 providers */}
                                {(profile?.providers?.length || 0) > 1 && (
                                    <button
                                        onClick={async () => {
                                            if (!supabase) return;
                                            if (!confirm(`Unlink ${provider} login? You'll still have other login methods.`)) return;
                                            try {
                                                const { data: { user } } = await supabase.auth.getUser();
                                                const identity = user?.identities?.find(i => i.provider === provider);
                                                if (identity) {
                                                    await supabase.auth.unlinkIdentity(identity);
                                                    setMessage(`${provider} unlinked ✓`);
                                                    fetchProfile();
                                                }
                                            } catch {
                                                setMessage('Failed to unlink provider');
                                            }
                                        }}
                                        style={{
                                            background: 'none',
                                            border: 'none',
                                            color: 'rgba(234,229,222,0.3)',
                                            fontSize: '11px',
                                            cursor: 'pointer',
                                            padding: '0 2px',
                                        }}
                                        title={`Unlink ${provider}`}
                                    >
                                        ✕
                                    </button>
                                )}
                            </span>
                        ))}
                    </div>

                    {/* Link Google — if not already linked */}
                    {!(profile?.providers || []).includes('google') && (
                        <button
                            id="link-google-btn"
                            onClick={async () => {
                                if (!supabase) return;
                                try {
                                    // Phase 865: flag for /auth/callback to redirect back to profile
                                    sessionStorage.setItem('ihouse_linking_provider', 'google');
                                    await supabase.auth.linkIdentity({ provider: 'google' });
                                    // Supabase will redirect to Google OAuth
                                } catch {
                                    sessionStorage.removeItem('ihouse_linking_provider');
                                    setMessage('Failed to link Google account');
                                }
                            }}
                            style={{
                                ...btnPrimary,
                                background: 'rgba(234,229,222,0.06)',
                                color: 'var(--color-text-primary, #EAE5DE)',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                marginBottom: '8px',
                                width: '100%',
                                justifyContent: 'center',
                            }}
                        >
                            🟢 Link Google Account
                        </button>
                    )}

                    {/* Add Password — Phase 873: inline form replaces prompt() */}
                    {!(profile?.providers || []).includes('email') && (
                        addPasswordMode ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px' }}>
                                <PasswordInput
                                    id="profile-add-password"
                                    value={newPassword}
                                    onChange={e => setNewPassword(e.target.value)}
                                    onFocus={() => setPasswordFocused(true)}
                                    onBlur={() => setPasswordFocused(false)}
                                    placeholder="Create a password"
                                    autoComplete="new-password"
                                />
                                <PasswordInput
                                    id="profile-confirm-password"
                                    value={confirmNewPassword}
                                    onChange={e => setConfirmNewPassword(e.target.value)}
                                    placeholder="Confirm password"
                                    autoComplete="new-password"
                                />
                                {(passwordFocused || newPassword.length > 0) && (
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 16px', fontSize: 11, lineHeight: 1.8 }}>
                                        {pwRules.map(r => (
                                            <span key={r.key} style={{
                                                color: newPassword.length === 0
                                                    ? 'rgba(234,229,222,0.25)'
                                                    : r.pass ? '#4A7C59' : 'rgba(234,229,222,0.3)',
                                                transition: 'color 0.2s',
                                            }}>
                                                {newPassword.length > 0 && r.pass ? '✓' : '○'} {r.label}
                                            </span>
                                        ))}
                                    </div>
                                )}
                                {confirmNewPassword.length > 0 && newPassword !== confirmNewPassword && (
                                    <div style={{ fontSize: 12, color: '#D64545' }}>✗ Passwords do not match</div>
                                )}
                                {confirmNewPassword.length > 0 && newPassword === confirmNewPassword && newPassword.length > 0 && (
                                    <div style={{ fontSize: 12, color: '#4A7C59' }}>✓ Passwords match</div>
                                )}
                                <div style={{ display: 'flex', gap: '8px' }}>
                                    <button
                                        onClick={async () => {
                                            if (!supabase || !allPwRulesPass || newPassword !== confirmNewPassword) return;
                                            try {
                                                const { error } = await supabase.auth.updateUser({ password: newPassword });
                                                if (error) throw error;
                                                setMessage('Password added ✓ — you can now login with email + password');
                                                setAddPasswordMode(false);
                                                setNewPassword('');
                                                setConfirmNewPassword('');
                                                fetchProfile();
                                            } catch {
                                                setMessage('Failed to add password');
                                            }
                                        }}
                                        disabled={!allPwRulesPass || newPassword !== confirmNewPassword}
                                        style={{
                                            ...btnPrimary,
                                            background: allPwRulesPass && newPassword === confirmNewPassword ? 'linear-gradient(135deg, #B56E45, #C4854F)' : 'rgba(234,229,222,0.06)',
                                            opacity: allPwRulesPass && newPassword === confirmNewPassword ? 1 : 0.4,
                                            flex: 1,
                                        }}
                                    >
                                        Save Password
                                    </button>
                                    <button
                                        onClick={() => { setAddPasswordMode(false); setNewPassword(''); setConfirmNewPassword(''); }}
                                        style={{
                                            ...btnPrimary,
                                            background: 'rgba(234,229,222,0.06)',
                                            color: 'var(--color-text-primary, #EAE5DE)',
                                        }}
                                    >
                                        Cancel
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <button
                                id="add-password-btn"
                                onClick={() => setAddPasswordMode(true)}
                                style={{
                                    ...btnPrimary,
                                    background: 'rgba(234,229,222,0.06)',
                                    color: 'var(--color-text-primary, #EAE5DE)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px',
                                    width: '100%',
                                    justifyContent: 'center',
                                }}
                            >
                                📧 Add Email + Password Login
                            </button>
                        )
                    )}
                </div>

                {/* Membership Status — Phase 862 P29 */}
                <div style={{ ...card, marginTop: 'var(--space-4, 16px)' }}>
                    <label style={labelStyle}>Account Status</label>
                    <div style={{
                        ...inputStyle,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                    }}>
                        <span style={{
                            width: 8, height: 8,
                            borderRadius: '50%',
                            background: profile?.has_membership ? '#4A7C59' : '#B56E45',
                            display: 'inline-block',
                        }} />
                        {profile?.has_membership
                            ? `${(profile.role || 'member').charAt(0).toUpperCase() + (profile.role || 'member').slice(1)}`
                            : 'Identity only — no organization assigned'
                        }
                    </div>
                </div>

                {/* User ID (small, for debugging) */}
                <div style={{
                    marginTop: 'var(--space-4, 16px)',
                    color: 'rgba(234,229,222,0.2)',
                    fontSize: '11px',
                    fontFamily: 'monospace',
                }}>
                    ID: {profile?.user_id || '—'}
                </div>
            </div>
        </div>
        </>
    );
}
