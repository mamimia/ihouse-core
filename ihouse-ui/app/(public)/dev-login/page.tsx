'use client';

/**
 * Dev Login Page — Internal/Debug Only
 * Route: /dev-login
 *
 * Original tenant_id + secret + role selector login.
 * For production login, use /login (email + password).
 *
 * This page is NOT linked from the production UI.
 */

import { useState, useEffect } from 'react';
import { api, setToken } from '../../../lib/api';
import DMonogram from '../../../components/DMonogram';
import { getRoleRoute } from '../../../lib/roleRoute';

export default function DevLoginPage() {
    const [tenantId, setTenantId] = useState('');
    const [secret, setSecret] = useState('');
    const [role, setRole] = useState('manager');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
        if (typeof window !== 'undefined' && localStorage.getItem('ihouse_token')) {
            window.location.href = getRoleRoute(localStorage.getItem('ihouse_token') ?? undefined);
        }
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!tenantId.trim()) { setError('Tenant ID is required'); return; }
        setError(null);
        setLoading(true);
        try {
            const resp = await api.login(tenantId.trim(), secret, role);
            setToken(resp.token);
            document.cookie = `ihouse_token=${resp.token}; path=/; max-age=${resp.expires_in}; SameSite=Lax`;
            window.location.href = getRoleRoute(resp.token);
        } catch (err: unknown) {
            if (err instanceof Error && err.message.includes('401')) {
                setError('Invalid credentials. Check your tenant ID and secret.');
            } else if (err instanceof Error && err.message.includes('503')) {
                setError('Auth not configured. Contact your administrator.');
            } else {
                setError(err instanceof Error ? err.message : 'Login failed');
            }
        } finally {
            setLoading(false);
        }
    };

    if (!mounted) return null;

    return (
        <>
            <style>{`
                @keyframes fadeUp { from { opacity:0; transform:translateY(16px) } to { opacity:1; transform:translateY(0) } }
                .login-card { animation: fadeUp 400ms ease forwards }
                .login-input:focus { outline: none; border-color: #f59e0b !important; box-shadow: 0 0 0 3px rgba(245,158,11,0.15) }
                .login-btn:hover:not(:disabled) { opacity: 0.92 !important }
                .login-btn:active:not(:disabled) { transform: scale(0.985) }
            `}</style>

            <div
                style={{
                    minHeight: '100vh',
                    background: '#1a1a2e',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '24px',
                    fontFamily: 'var(--font-sans, system-ui)',
                }}
            >
                <div className="login-card" style={{ width: '100%', maxWidth: 420 }}>

                    {/* Header — clearly marked as dev */}
                    <div style={{ textAlign: 'center', marginBottom: '32px' }}>
                        <DMonogram size={40} color="#f59e0b" strokeWidth={1.8} />
                        <div style={{
                            fontSize: '11px',
                            fontWeight: 700,
                            color: '#f59e0b',
                            marginTop: '12px',
                            letterSpacing: '0.1em',
                            textTransform: 'uppercase',
                            background: 'rgba(245,158,11,0.1)',
                            border: '1px solid rgba(245,158,11,0.25)',
                            borderRadius: '4px',
                            padding: '4px 10px',
                            display: 'inline-block',
                        }}>
                            ⚙ Dev / Internal Login
                        </div>
                    </div>

                    {/* Card */}
                    <div style={{
                        background: '#16213e',
                        border: '1px solid rgba(245,158,11,0.15)',
                        borderRadius: '12px',
                        padding: '32px 24px',
                    }}>
                        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                            {/* Tenant ID */}
                            <div>
                                <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: '#9ca3af', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                                    Tenant ID
                                </label>
                                <input
                                    id="input-tenant-id"
                                    className="login-input"
                                    type="text"
                                    value={tenantId}
                                    onChange={e => setTenantId(e.target.value)}
                                    placeholder="my-property-group"
                                    autoComplete="username"
                                    disabled={loading}
                                    style={{ width: '100%', padding: '10px 12px', background: '#0f3460', border: '1px solid rgba(245,158,11,0.1)', borderRadius: '8px', color: '#e5e7eb', fontSize: '14px', fontFamily: 'monospace' }}
                                />
                            </div>

                            {/* Secret */}
                            <div>
                                <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: '#9ca3af', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                                    Secret
                                </label>
                                <input
                                    id="input-secret"
                                    className="login-input"
                                    type="password"
                                    value={secret}
                                    onChange={e => setSecret(e.target.value)}
                                    placeholder="••••••••"
                                    autoComplete="current-password"
                                    disabled={loading}
                                    style={{ width: '100%', padding: '10px 12px', background: '#0f3460', border: '1px solid rgba(245,158,11,0.1)', borderRadius: '8px', color: '#e5e7eb', fontSize: '14px' }}
                                />
                                <div style={{ fontSize: '11px', color: '#6b7280', marginTop: '4px' }}>
                                    Default: <code style={{ color: '#f59e0b' }}>dev</code>
                                </div>
                            </div>

                            {/* Role Selector */}
                            <div>
                                <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: '#9ca3af', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                                    Role
                                </label>
                                <select
                                    id="select-role"
                                    value={role}
                                    onChange={e => setRole(e.target.value)}
                                    disabled={loading}
                                    style={{ width: '100%', padding: '10px 12px', background: '#0f3460', border: '1px solid rgba(245,158,11,0.1)', borderRadius: '8px', color: '#e5e7eb', fontSize: '14px', cursor: 'pointer' }}
                                >
                                    <option value="manager">Manager</option>
                                    <option value="admin">Admin</option>
                                    <option value="owner">Owner</option>
                                    <option value="ops">Operations</option>
                                    <option value="worker">Worker</option>
                                    <option value="checkin">Check-in Staff</option>
                                    <option value="checkout">Check-out Staff</option>
                                    <option value="maintenance">Maintenance</option>
                                </select>
                            </div>

                            {/* Error */}
                            {error && (
                                <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: '8px', padding: '10px 14px', fontSize: '13px', color: '#EF4444' }}>
                                    ⚠ {error}
                                </div>
                            )}

                            {/* Submit */}
                            <button
                                id="btn-dev-login"
                                type="submit"
                                className="login-btn"
                                disabled={loading || !tenantId.trim()}
                                style={{ padding: '12px', background: '#f59e0b', border: 'none', borderRadius: '8px', color: '#111', fontSize: '14px', fontWeight: 700, cursor: loading || !tenantId.trim() ? 'not-allowed' : 'pointer', opacity: loading || !tenantId.trim() ? 0.4 : 1, transition: 'all 150ms', marginTop: '8px' }}
                            >
                                {loading ? 'Signing in…' : '⚙ Dev Sign In'}
                            </button>
                        </form>
                    </div>

                    <p style={{ textAlign: 'center', fontSize: '11px', color: '#4b5563', marginTop: '20px' }}>
                        Not for production use. <a href="/login" style={{ color: '#f59e0b', textDecoration: 'underline' }}>Use production login →</a>
                    </p>
                </div>
            </div>
        </>
    );
}
