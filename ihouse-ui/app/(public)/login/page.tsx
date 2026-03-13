'use client';

/**
 * Phase 378 — Login Page (Platform Threshold)
 * Phase 397 — JWT Role Claim + Role Selector
 * Route: /login
 *
 * The deliberate boundary between public and protected surfaces.
 * Dark background (Midnight Graphite), D monogram, Instrument Serif headline.
 * Using Domaniqo design tokens. No sidebar hack needed (public route group).
 */

import { useState, useEffect } from 'react';
import { api, setToken } from '../../../lib/api';
import DMonogram from '../../../components/DMonogram';
import { getRoleRoute } from '../../../lib/roleRoute';

export default function LoginPage() {
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
                @keyframes monogramGlow { 0%,100% { opacity:0.7 } 50% { opacity:1 } }
                .login-card { animation: fadeUp 400ms ease forwards }
                .login-input:focus { outline: none; border-color: var(--color-copper) !important; box-shadow: 0 0 0 3px rgba(181,110,69,0.15) }
                .login-btn:hover:not(:disabled) { opacity: 0.92 !important; box-shadow: var(--shadow-glow-moss) !important }
                .login-btn:active:not(:disabled) { transform: scale(0.985) }
            `}</style>

            <div
                className="grain-overlay"
                style={{
                    minHeight: '100vh',
                    background: 'var(--color-midnight)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: 'var(--space-6)',
                    fontFamily: 'var(--font-sans)',
                }}
            >
                <div className="login-card" style={{ width: '100%', maxWidth: 420 }}>

                    {/* Monogram + Brand */}
                    <div style={{
                        textAlign: 'center',
                        marginBottom: 'var(--space-10)',
                    }}>
                        <div style={{
                            display: 'inline-flex',
                            animation: 'monogramGlow 4s ease-in-out infinite',
                            marginBottom: 'var(--space-4)',
                        }}>
                            <DMonogram size={52} color="var(--color-stone)" strokeWidth={1.8} />
                        </div>
                        <div style={{
                            fontFamily: 'var(--font-display)',
                            fontSize: 'var(--text-3xl)',
                            fontWeight: 400,
                            color: 'var(--color-stone)',
                            letterSpacing: '-0.02em',
                            lineHeight: 1.1,
                            marginBottom: 'var(--space-2)',
                        }}>
                            Domaniqo
                        </div>
                        <div style={{
                            fontSize: 'var(--text-sm)',
                            color: 'var(--color-olive)',
                            fontFamily: 'var(--font-sans)',
                            letterSpacing: '0.04em',
                            textTransform: 'uppercase',
                        }}>
                            Operations Platform
                        </div>
                    </div>

                    {/* Card */}
                    <div style={{
                        background: 'var(--color-elevated)',
                        border: '1px solid rgba(234,229,222,0.06)',
                        borderRadius: 'var(--radius-xl)',
                        padding: 'var(--space-8) var(--space-6)',
                        boxShadow: 'var(--shadow-lg)',
                    }}>
                        <h1 style={{
                            fontFamily: 'var(--font-brand)',
                            fontSize: 'var(--text-lg)',
                            fontWeight: 700,
                            color: 'var(--color-stone)',
                            margin: '0 0 var(--space-1)',
                            letterSpacing: '-0.02em',
                        }}>
                            Sign in
                        </h1>
                        <p style={{
                            fontSize: 'var(--text-sm)',
                            color: 'rgba(234,229,222,0.4)',
                            margin: '0 0 var(--space-6)',
                        }}>
                            Enter your credentials to continue
                        </p>

                        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                            {/* Tenant ID */}
                            <div>
                                <label style={{
                                    display: 'block',
                                    fontSize: 'var(--text-xs)',
                                    fontWeight: 600,
                                    color: 'rgba(234,229,222,0.5)',
                                    marginBottom: 'var(--space-2)',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.06em',
                                }}>
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
                                    style={{
                                        width: '100%',
                                        padding: '12px 14px',
                                        background: 'var(--color-midnight)',
                                        border: '1px solid rgba(234,229,222,0.1)',
                                        borderRadius: 'var(--radius-md)',
                                        color: 'var(--color-stone)',
                                        fontSize: 'var(--text-sm)',
                                        transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
                                        fontFamily: 'var(--font-mono)',
                                    }}
                                />
                            </div>

                            {/* Secret */}
                            <div>
                                <label style={{
                                    display: 'block',
                                    fontSize: 'var(--text-xs)',
                                    fontWeight: 600,
                                    color: 'rgba(234,229,222,0.5)',
                                    marginBottom: 'var(--space-2)',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.06em',
                                }}>
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
                                    style={{
                                        width: '100%',
                                        padding: '12px 14px',
                                        background: 'var(--color-midnight)',
                                        border: '1px solid rgba(234,229,222,0.1)',
                                        borderRadius: 'var(--radius-md)',
                                        color: 'var(--color-stone)',
                                        fontSize: 'var(--text-sm)',
                                        transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
                                    }}
                                />
                                <div style={{
                                    fontSize: 'var(--text-xs)',
                                    color: 'rgba(234,229,222,0.3)',
                                    marginTop: 'var(--space-2)',
                                }}>
                                    Default: <code style={{ color: 'var(--color-olive)' }}>dev</code> (local only)
                                </div>
                            </div>

                            {/* Role Selector — Phase 397 */}
                            <div>
                                <label style={{
                                    display: 'block',
                                    fontSize: 'var(--text-xs)',
                                    fontWeight: 600,
                                    color: 'rgba(234,229,222,0.5)',
                                    marginBottom: 'var(--space-2)',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.06em',
                                }}>
                                    Role
                                </label>
                                <select
                                    id="select-role"
                                    value={role}
                                    onChange={e => setRole(e.target.value)}
                                    disabled={loading}
                                    style={{
                                        width: '100%',
                                        padding: '12px 14px',
                                        background: 'var(--color-midnight)',
                                        border: '1px solid rgba(234,229,222,0.1)',
                                        borderRadius: 'var(--radius-md)',
                                        color: 'var(--color-stone)',
                                        fontSize: 'var(--text-sm)',
                                        fontFamily: 'var(--font-sans)',
                                        transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
                                        cursor: 'pointer',
                                        appearance: 'none',
                                        WebkitAppearance: 'none',
                                        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239ca3af' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`,
                                        backgroundRepeat: 'no-repeat',
                                        backgroundPosition: 'right 14px center',
                                    }}
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
                                <div style={{
                                    background: 'rgba(155,58,58,0.1)',
                                    border: '1px solid rgba(155,58,58,0.25)',
                                    borderRadius: 'var(--radius-md)',
                                    padding: '10px 14px',
                                    fontSize: 'var(--text-sm)',
                                    color: '#EF4444',
                                }}>
                                    ⚠ {error}
                                </div>
                            )}

                            {/* Submit */}
                            <button
                                id="btn-login"
                                type="submit"
                                className="login-btn"
                                disabled={loading || !tenantId.trim()}
                                style={{
                                    padding: '14px',
                                    background: 'var(--color-moss)',
                                    border: 'none',
                                    borderRadius: 'var(--radius-md)',
                                    color: 'var(--color-white)',
                                    fontSize: 'var(--text-base)',
                                    fontWeight: 600,
                                    fontFamily: 'var(--font-brand)',
                                    letterSpacing: '-0.01em',
                                    cursor: loading || !tenantId.trim() ? 'not-allowed' : 'pointer',
                                    opacity: loading || !tenantId.trim() ? 0.4 : 1,
                                    transition: 'all var(--transition-fast)',
                                    boxShadow: 'var(--shadow-glow-moss)',
                                    marginTop: 'var(--space-2)',
                                    minHeight: 48,
                                }}
                            >
                                {loading ? 'Signing in…' : 'Sign in →'}
                            </button>
                        </form>
                    </div>

                    {/* Footer */}
                    <p style={{
                        textAlign: 'center',
                        fontSize: 'var(--text-xs)',
                        color: 'rgba(234,229,222,0.2)',
                        marginTop: 'var(--space-6)',
                    }}>
                        Domaniqo · See every stay.
                    </p>
                </div>
            </div>
        </>
    );
}
