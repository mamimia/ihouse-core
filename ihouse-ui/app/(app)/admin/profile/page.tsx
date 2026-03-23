'use client';

/**
 * Admin Profile & Account Settings — /admin/profile
 *
 * Dedicated admin-facing profile page accessible from the admin sidebar.
 * Same identity/profile data as /profile but rendered in the admin layout (light theme, sidebar).
 *
 * Features:
 * - View account details (email, name, role, tenant)
 * - Edit profile (name, phone, language)
 * - Identity linking: link/unlink Google, add email+password
 * - Account status display
 */

import { useState, useEffect, useCallback } from 'react';
import { supabase } from '@/lib/supabaseClient';
import { usePasswordRules } from '@/hooks/usePasswordRules';
import PasswordInput from '@/components/auth/PasswordInput';
import { useLanguage } from '@/lib/LanguageContext';
import { linkGoogleAccount, unlinkProvider, addPassword as addPasswordShared, GoogleIcon } from '@/lib/identityLinking';

const COUNTRY_CODES = [
    { code: '+66', country: 'TH' }, { code: '+1', country: 'US' },
    { code: '+44', country: 'UK' }, { code: '+61', country: 'AU' },
    { code: '+81', country: 'JP' }, { code: '+82', country: 'KR' },
    { code: '+49', country: 'DE' }, { code: '+33', country: 'FR' },
    { code: '+39', country: 'IT' }, { code: '+34', country: 'ES' },
    { code: '+7', country: 'RU' }, { code: '+86', country: 'CN' },
    { code: '+91', country: 'IN' }, { code: '+65', country: 'SG' },
    { code: '+60', country: 'MY' }, { code: '+62', country: 'ID' },
    { code: '+63', country: 'PH' }, { code: '+84', country: 'VN' },
    { code: '+852', country: 'HK' }, { code: '+971', country: 'AE' },
    { code: '+55', country: 'BR' }, { code: '+52', country: 'MX' },
    { code: '+27', country: 'ZA' }, { code: '+64', country: 'NZ' },
    { code: '+46', country: 'SE' }, { code: '+47', country: 'NO' },
    { code: '+45', country: 'DK' }, { code: '+31', country: 'NL' },
    { code: '+41', country: 'CH' }, { code: '+48', country: 'PL' },
    { code: '+90', country: 'TR' }, { code: '+20', country: 'EG' },
];

/** Parse a stored phone string like '+66 81xxx' into { countryCode, digits } */
function parsePhone(raw: string): { countryCode: string; digits: string } {
    if (!raw) return { countryCode: '+66', digits: '' };
    const trimmed = raw.trim();
    // Try to match a known country code prefix
    for (const cc of COUNTRY_CODES) {
        if (trimmed.startsWith(cc.code)) {
            return { countryCode: cc.code, digits: trimmed.slice(cc.code.length).trim() };
        }
    }
    // If starts with + but not matched, take first segment
    if (trimmed.startsWith('+')) {
        const spaceIdx = trimmed.indexOf(' ');
        if (spaceIdx > 0) {
            return { countryCode: trimmed.slice(0, spaceIdx), digits: trimmed.slice(spaceIdx + 1).trim() };
        }
        return { countryCode: trimmed, digits: '' };
    }
    return { countryCode: '+66', digits: trimmed };
}

interface Profile {
    user_id: string;
    email: string;
    full_name: string;
    phone: string;
    avatar_url: string;
    language: string;
    providers: string[];
    role: string;
    tenant_id: string;
    has_membership: boolean;
}

export default function AdminProfilePage() {
    const [profile, setProfile] = useState<Profile | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState('');
    const [editMode, setEditMode] = useState(false);
    const [form, setForm] = useState({ full_name: '', phone: '', countryCode: '+66', language: '' });
    const { setLang } = useLanguage();
    const [addPasswordMode, setAddPasswordMode] = useState(false);
    const [newPassword, setNewPassword] = useState('');
    const [confirmNewPassword, setConfirmNewPassword] = useState('');
    const [passwordFocused, setPasswordFocused] = useState(false);
    const pwRules = usePasswordRules(newPassword);
    const allPwRulesPass = pwRules.every(r => r.pass);
    const [hasSupabaseSession, setHasSupabaseSession] = useState(false);

    useEffect(() => {
        if (!supabase) return;
        supabase.auth.getSession().then(({ data }) => {
            if (data.session) setHasSupabaseSession(true);
        });
    }, []);

    const fetchProfile = useCallback(async () => {
        try {
            const token = typeof window !== 'undefined'
                ? (localStorage.getItem('ihouse_token') ||
                    document.cookie.split('; ').find(c => c.startsWith('ihouse_token='))?.split('=')[1])
                : null;

            if (!token) { setLoading(false); return; }

            const apiBase = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
            const res = await fetch(`${apiBase}/auth/profile`, {
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (!res.ok) { setMessage('Failed to load profile'); setLoading(false); return; }

            const data = await res.json();
            const p = data.data || data;
            setProfile(p);
            const parsed = parsePhone(p.phone || '');
            setForm({ full_name: p.full_name || '', phone: parsed.digits, countryCode: parsed.countryCode, language: p.language || '' });
        } catch {
            setMessage('Error loading profile');
        }
        setLoading(false);
    }, []);

    useEffect(() => { fetchProfile(); }, [fetchProfile]);

    const handleSave = async () => {
        setSaving(true);
        setMessage('');
        try {
            const token = typeof window !== 'undefined'
                ? (localStorage.getItem('ihouse_token') ||
                    document.cookie.split('; ').find(c => c.startsWith('ihouse_token='))?.split('=')[1])
                : null;

            const apiBase = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
            const res = await fetch(`${apiBase}/auth/profile`, {
                method: 'PATCH',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    full_name: form.full_name.trim() || undefined,
                    phone: form.phone.trim() ? `${form.countryCode} ${form.phone.trim()}` : undefined,
                    language: form.language.trim() || undefined,
                }),
            });

            if (res.ok) {
                setMessage('Profile updated ✓');
                setEditMode(false);
                // Persist language to localStorage so the app reacts immediately
                if (form.language && form.language.trim()) {
                    localStorage.setItem('domaniqo_lang', form.language.trim());
                    setLang(form.language.trim() as 'en' | 'th' | 'he');
                }
                fetchProfile();
            } else {
                setMessage('Failed to save');
            }
        } catch {
            setMessage('Error saving profile');
        }
        setSaving(false);
    };

    // --- Shared styles (admin light theme) ---
    const sectionStyle: React.CSSProperties = {
        background: 'var(--color-surface, #fff)',
        border: '1px solid var(--color-border, #e5e7eb)',
        borderRadius: 'var(--radius-lg, 16px)',
        padding: 'var(--space-6, 24px)',
        marginBottom: 'var(--space-5, 20px)',
    };
    const labelStyle: React.CSSProperties = {
        fontSize: 'var(--text-xs, 12px)',
        color: 'var(--color-text-faint, #9ca3af)',
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        marginBottom: 6,
        display: 'block',
    };
    const inputStyle: React.CSSProperties = {
        width: '100%',
        boxSizing: 'border-box',
        background: 'var(--color-surface-2, #f9fafb)',
        border: '1px solid var(--color-border, #e5e7eb)',
        borderRadius: 'var(--radius-sm, 8px)',
        color: 'var(--color-text, #1f2937)',
        fontSize: 'var(--text-sm, 14px)',
        padding: '10px 14px',
    };
    const btnPrimary: React.CSSProperties = {
        background: 'var(--color-primary, #334036)',
        color: '#fff',
        border: 'none',
        borderRadius: 'var(--radius-md, 12px)',
        padding: '10px 24px',
        fontSize: 'var(--text-sm, 14px)',
        fontWeight: 600,
        cursor: 'pointer',
    };
    const btnSecondary: React.CSSProperties = {
        ...btnPrimary,
        background: 'var(--color-surface-2, #f3f4f6)',
        color: 'var(--color-text, #1f2937)',
    };

    const sectionHeader = (title: string) => (
        <div style={{
            fontSize: 'var(--text-xs, 12px)',
            fontWeight: 700,
            color: 'var(--color-text-faint, #9ca3af)',
            textTransform: 'uppercase',
            letterSpacing: '0.07em',
            marginBottom: 'var(--space-5, 20px)',
        }}>
            {title}
        </div>
    );

    if (loading) {
        return (
            <div style={{ maxWidth: 640, padding: 'var(--space-6, 24px)' }}>
                <div style={{ color: 'var(--color-text-dim, #6b7280)' }}>Loading…</div>
            </div>
        );
    }

    return (
        <div style={{ maxWidth: 640 }}>
            {/* Page header */}
            <div style={{ marginBottom: 'var(--space-8, 32px)' }}>
                <p style={{ fontSize: 'var(--text-xs, 12px)', color: 'var(--color-text-faint, #9ca3af)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4, marginTop: 0 }}>
                    Admin
                </p>
                <h1 style={{ fontSize: 'var(--text-2xl, 24px)', fontWeight: 700, color: 'var(--color-text, #1f2937)', letterSpacing: '-0.03em', margin: 0 }}>
                    My Profile
                </h1>
            </div>

            {/* Notice */}
            {message && (
                <div style={{
                    padding: '10px 16px',
                    borderRadius: 'var(--radius-md, 12px)',
                    background: message.includes('✓') ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
                    border: `1px solid ${message.includes('✓') ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`,
                    color: message.includes('✓') ? '#16a34a' : '#dc2626',
                    fontSize: 'var(--text-sm, 14px)',
                    marginBottom: 'var(--space-4, 16px)',
                }}>
                    {message}
                </div>
            )}

            {/* Account Info */}
            <div style={sectionStyle}>
                {sectionHeader('Account Details')}

                <div style={{ marginBottom: 16 }}>
                    <label style={labelStyle}>Email</label>
                    <div style={{ ...inputStyle, opacity: 0.7, cursor: 'not-allowed' }}>
                        {profile?.email || '—'}
                    </div>
                </div>

                <div style={{ marginBottom: 16 }}>
                    <label style={labelStyle}>Full Name</label>
                    {editMode ? (
                        <input style={inputStyle} value={form.full_name}
                            onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))}
                            placeholder="Your name" />
                    ) : (
                        <div style={inputStyle}>{profile?.full_name || '—'}</div>
                    )}
                </div>

                <div style={{ marginBottom: 16 }}>
                    <label style={labelStyle}>Phone</label>
                    {editMode ? (
                        <div style={{
                            display: 'flex',
                            alignItems: 'stretch',
                            background: 'var(--color-surface-2, #f9fafb)',
                            border: '1px solid var(--color-border, #e5e7eb)',
                            borderRadius: 'var(--radius-sm, 8px)',
                            overflow: 'hidden',
                        }}>
                            {/* Country code selector */}
                            <div style={{ position: 'relative', flexShrink: 0, display: 'flex', alignItems: 'center', borderRight: '1px solid var(--color-border, #e5e7eb)' }}>
                                <span style={{
                                    padding: '10px 4px 10px 12px',
                                    fontSize: 'var(--text-sm, 14px)',
                                    color: 'var(--color-text, #1f2937)',
                                    pointerEvents: 'none',
                                    whiteSpace: 'nowrap',
                                    fontWeight: 500,
                                }}>
                                    {form.countryCode}
                                </span>
                                <span style={{ color: 'var(--color-text-faint, #9ca3af)', fontSize: 10, pointerEvents: 'none', marginRight: 6 }}>▾</span>
                                <select
                                    value={form.countryCode}
                                    onChange={e => setForm(f => ({ ...f, countryCode: e.target.value }))}
                                    style={{
                                        position: 'absolute', inset: 0,
                                        opacity: 0, cursor: 'pointer',
                                        width: '100%', height: '100%',
                                    }}
                                >
                                    {COUNTRY_CODES.map(cc => (
                                        <option key={cc.code} value={cc.code}>{cc.code} {cc.country}</option>
                                    ))}
                                </select>
                            </div>
                            {/* Phone digits */}
                            <input
                                type="tel"
                                style={{
                                    flex: 1,
                                    minWidth: 0,
                                    border: 'none',
                                    background: 'transparent',
                                    color: 'var(--color-text, #1f2937)',
                                    fontSize: 'var(--text-sm, 14px)',
                                    padding: '10px 14px 10px 10px',
                                    outline: 'none',
                                }}
                                value={form.phone}
                                onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                                placeholder="81 xxx xxxx"
                            />
                        </div>
                    ) : (
                        <div style={inputStyle}>{profile?.phone || '—'}</div>
                    )}
                </div>

                <div style={{ marginBottom: 20 }}>
                    <label style={labelStyle}>Language</label>
                    {editMode ? (
                        <select style={{ ...inputStyle, appearance: 'auto' as unknown as undefined }} value={form.language}
                            onChange={e => setForm(f => ({ ...f, language: e.target.value }))}>
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

                <div style={{ display: 'flex', gap: '10px' }}>
                    {editMode ? (
                        <>
                            <button style={btnPrimary} onClick={handleSave} disabled={saving}>
                                {saving ? 'Saving…' : 'Save Changes'}
                            </button>
                            <button style={btnSecondary} onClick={() => {
                                setEditMode(false);
                                const parsed2 = parsePhone(profile?.phone || '');
                                setForm({ full_name: profile?.full_name || '', phone: parsed2.digits, countryCode: parsed2.countryCode, language: profile?.language || '' });
                            }}>Cancel</button>
                        </>
                    ) : (
                        <button style={btnPrimary} onClick={() => setEditMode(true)}>Edit Profile</button>
                    )}
                </div>
            </div>

            {/* Role & Tenant */}
            <div style={sectionStyle}>
                {sectionHeader('Organization')}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    <div>
                        <label style={labelStyle}>Role</label>
                        <div style={{
                            ...inputStyle,
                            display: 'flex', alignItems: 'center', gap: 8,
                        }}>
                            <span style={{
                                width: 8, height: 8, borderRadius: '50%',
                                background: profile?.role === 'admin' ? '#16a34a' : '#f59e0b',
                            }} />
                            {(profile?.role || '—').charAt(0).toUpperCase() + (profile?.role || '—').slice(1)}
                        </div>
                    </div>
                    <div>
                        <label style={labelStyle}>Tenant</label>
                        <div style={inputStyle}>{profile?.tenant_id || '—'}</div>
                    </div>
                </div>
            </div>

            {/* Linked Login Methods */}
            <div style={sectionStyle}>
                {sectionHeader('Linked Login Methods')}

                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px' }}>
                    {(profile?.providers || []).map(provider => (
                        <span key={provider} style={{
                            background: 'var(--color-surface-2, #f3f4f6)',
                            border: '1px solid var(--color-border, #e5e7eb)',
                            borderRadius: '8px',
                            padding: '8px 14px',
                            fontSize: '14px',
                            color: 'var(--color-text, #1f2937)',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '8px',
                            fontWeight: 500,
                        }}>
                            {provider === 'email' ? '📧 Email/Password' : provider === 'google' ? <><GoogleIcon /> Google</> : provider}
                            {(profile?.providers?.length || 0) > 1 && (
                                <button
                                    onClick={async () => {
                                        if (!confirm(`Unlink ${provider} login? You'll still have other login methods.`)) return;
                                        const result = await unlinkProvider(provider);
                                        if (result.success) {
                                            setMessage(`${provider} unlinked ✓`);
                                            fetchProfile();
                                        } else {
                                            setMessage(result.error || 'Failed to unlink provider');
                                        }
                                    }}
                                    style={{
                                        background: 'none', border: 'none',
                                        color: 'var(--color-text-faint, #9ca3af)',
                                        fontSize: '11px', cursor: 'pointer',
                                    }}
                                    title={`Unlink ${provider}`}
                                >✕</button>
                            )}
                        </span>
                    ))}
                    {(profile?.providers || []).length === 0 && (
                        <span style={{ fontSize: 14, color: 'var(--color-text-faint, #9ca3af)' }}>
                            No linked providers found
                        </span>
                    )}
                </div>

                {/* Link Google */}
                {!(profile?.providers || []).includes('google') && (
                    <button
                        onClick={async () => {
                            const result = await linkGoogleAccount();
                            if (!result.success) {
                                setMessage(result.error || 'Failed to link Google account');
                            }
                        }}
                        style={{
                            ...btnSecondary,
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            width: '100%',
                            justifyContent: 'center',
                            marginBottom: '8px',
                        }}
                    >
                        <GoogleIcon /> Link Google Account
                    </button>
                )}

                {/* Add Email+Password */}
                {!(profile?.providers || []).includes('email') && (
                    addPasswordMode ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px' }}>
                            {/* Show which email the password will be linked to */}
                            <div style={{
                                padding: '10px 14px',
                                background: 'rgba(59,130,246,0.04)',
                                border: '1px solid rgba(59,130,246,0.12)',
                                borderRadius: 'var(--radius-sm, 8px)',
                                fontSize: 'var(--text-sm, 14px)',
                                color: 'var(--color-text, #1f2937)',
                            }}>
                                <span style={{ color: 'var(--color-text-faint, #9ca3af)', fontSize: 'var(--text-xs, 12px)', display: 'block', marginBottom: 4 }}>
                                    Adding password for:
                                </span>
                                <strong>{profile?.email || '—'}</strong>
                            </div>
                            <PasswordInput
                                id="admin-add-password"
                                value={newPassword}
                                onChange={e => setNewPassword(e.target.value)}
                                onFocus={() => setPasswordFocused(true)}
                                onBlur={() => setPasswordFocused(false)}
                                placeholder="Create a password"
                                autoComplete="new-password"
                            />
                            <PasswordInput
                                id="admin-confirm-password"
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
                                                ? 'var(--color-text-faint, #9ca3af)'
                                                : r.pass ? '#16a34a' : 'var(--color-text-faint, #9ca3af)',
                                            transition: 'color 0.2s',
                                        }}>
                                            {newPassword.length > 0 && r.pass ? '✓' : '○'} {r.label}
                                        </span>
                                    ))}
                                </div>
                            )}
                            {confirmNewPassword.length > 0 && newPassword !== confirmNewPassword && (
                                <div style={{ fontSize: 12, color: '#dc2626' }}>✗ Passwords do not match</div>
                            )}
                            {confirmNewPassword.length > 0 && newPassword === confirmNewPassword && newPassword.length > 0 && (
                                <div style={{ fontSize: 12, color: '#16a34a' }}>✓ Passwords match</div>
                            )}
                            <div style={{ display: 'flex', gap: '8px' }}>
                                <button
                                    onClick={async () => {
                                        if (!allPwRulesPass || newPassword !== confirmNewPassword) return;
                                        const result = await addPasswordShared(newPassword);
                                        if (result.success) {
                                            setMessage('Password added ✓ — you can now login with email + password');
                                            setAddPasswordMode(false);
                                            setNewPassword('');
                                            setConfirmNewPassword('');
                                            fetchProfile();
                                        } else {
                                            setMessage(result.error || 'Failed to add password');
                                        }
                                    }}
                                    disabled={!allPwRulesPass || newPassword !== confirmNewPassword}
                                    style={{
                                        ...btnPrimary,
                                        opacity: allPwRulesPass && newPassword === confirmNewPassword ? 1 : 0.4,
                                        flex: 1,
                                    }}
                                >
                                    Save Password
                                </button>
                                <button
                                    onClick={() => { setAddPasswordMode(false); setNewPassword(''); setConfirmNewPassword(''); }}
                                    style={btnSecondary}
                                >
                                    Cancel
                                </button>
                            </div>
                        </div>
                    ) : (
                        <button
                            onClick={() => setAddPasswordMode(true)}
                            style={{
                                ...btnSecondary,
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

            {/* User ID (debug) */}
            <div style={{
                color: 'var(--color-text-faint, #9ca3af)',
                fontSize: '11px',
                fontFamily: 'monospace',
                marginTop: 'var(--space-4, 16px)',
            }}>
                ID: {profile?.user_id || '—'}
            </div>

            <div style={{
                marginTop: 'var(--space-8, 32px)',
                paddingTop: 'var(--space-5, 20px)',
                borderTop: '1px solid var(--color-border, #e5e7eb)',
                fontSize: 'var(--text-xs, 12px)',
                color: 'var(--color-text-faint, #9ca3af)',
            }}>
                Domaniqo · Admin Profile
            </div>
        </div>
    );
}
