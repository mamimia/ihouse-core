'use client';

/**
 * Phase 179 — Login Page
 * Route: /login
 *
 * Collects tenant_id + secret → POST /auth/token → stores JWT → redirects.
 * Role-based redirect: workers → /worker, others → /dashboard.
 */

import { useState, useEffect } from 'react';
import { api, setToken } from '../../lib/api';

export default function LoginPage() {
    const [tenantId, setTenantId] = useState('');
    const [secret, setSecret] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
        // If already logged in, redirect away
        if (typeof window !== 'undefined' && localStorage.getItem('ihouse_token')) {
            window.location.href = '/dashboard';
        }
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!tenantId.trim()) { setError('Tenant ID is required'); return; }
        setError(null);
        setLoading(true);
        try {
            const resp = await api.login(tenantId.trim(), secret);
            setToken(resp.token);
            // Write cookie for middleware (edge runtime cannot read localStorage)
            document.cookie = `ihouse_token=${resp.token}; path=/; max-age=${resp.expires_in}; SameSite=Lax`;
            // Redirect
            window.location.href = '/dashboard';
        } catch (err: unknown) {
            if (err instanceof Error && err.message.includes('401')) {
                setError('Invalid credentials. Check your tenant ID and secret.');
            } else if (err instanceof Error && err.message.includes('503')) {
                setError('Auth not configured on server. Set IHOUSE_JWT_SECRET.');
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
        * { box-sizing: border-box }
        body { background: #0d1117 !important; margin: 0 }
        /* Hide desktop sidebar on login page */
        nav { display: none !important }
        main { margin-left: 0 !important; padding: 0 !important; max-width: 100% !important }
        @keyframes fadeUp { from { opacity:0; transform:translateY(16px) } to { opacity:1; transform:translateY(0) } }
        @keyframes shimmer {
          0% { background-position: -400px 0 }
          100% { background-position: 400px 0 }
        }
        .login-card { animation: fadeUp 300ms ease forwards }
        input:focus { outline: none; border-color: #3b82f6 !important; box-shadow: 0 0 0 3px rgba(59,130,246,0.15) }
        .login-btn:hover:not(:disabled) { background: linear-gradient(135deg,#2563eb,#1d4ed8) !important }
        .login-btn:active:not(:disabled) { transform: scale(0.98) }
      `}</style>
            <div style={{
                minHeight: '100vh', background: '#0d1117',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: '24px',
                fontFamily: "'Inter', -apple-system, sans-serif",
            }}>
                <div className="login-card" style={{ width: '100%', maxWidth: 420 }}>
                    {/* Logo */}
                    <div style={{ textAlign: 'center', marginBottom: 40 }}>
                        <div style={{
                            fontSize: 32, fontWeight: 800, color: '#f9fafb',
                            letterSpacing: '-0.04em', marginBottom: 8,
                        }}>
                            iHouse<span style={{ color: '#3b82f6' }}>Core</span>
                        </div>
                        <div style={{ fontSize: 14, color: '#6b7280' }}>
                            Operations Platform
                        </div>
                    </div>

                    {/* Card */}
                    <div style={{
                        background: '#111827',
                        border: '1px solid #1f2937',
                        borderRadius: 20,
                        padding: '32px 28px',
                        boxShadow: '0 24px 64px rgba(0,0,0,0.4)',
                    }}>
                        <h1 style={{
                            fontSize: 22, fontWeight: 700, color: '#f9fafb',
                            margin: '0 0 6px',
                        }}>Sign in</h1>
                        <p style={{ fontSize: 14, color: '#6b7280', margin: '0 0 28px' }}>
                            Enter your tenant credentials to continue
                        </p>

                        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                            {/* Tenant ID */}
                            <div>
                                <label style={{
                                    display: 'block', fontSize: 13, fontWeight: 600,
                                    color: '#9ca3af', marginBottom: 6,
                                }}>
                                    Tenant ID
                                </label>
                                <input
                                    id="input-tenant-id"
                                    type="text"
                                    value={tenantId}
                                    onChange={e => setTenantId(e.target.value)}
                                    placeholder="my-property-group"
                                    autoComplete="username"
                                    disabled={loading}
                                    style={{
                                        width: '100%', padding: '12px 14px',
                                        background: '#1a1f2e',
                                        border: '1px solid #374151',
                                        borderRadius: 10,
                                        color: '#f9fafb', fontSize: 15,
                                        transition: 'border-color 0.15s, box-shadow 0.15s',
                                        fontFamily: 'monospace',
                                    }}
                                />
                            </div>

                            {/* Secret */}
                            <div>
                                <label style={{
                                    display: 'block', fontSize: 13, fontWeight: 600,
                                    color: '#9ca3af', marginBottom: 6,
                                }}>
                                    Secret
                                </label>
                                <input
                                    id="input-secret"
                                    type="password"
                                    value={secret}
                                    onChange={e => setSecret(e.target.value)}
                                    placeholder="••••••••"
                                    autoComplete="current-password"
                                    disabled={loading}
                                    style={{
                                        width: '100%', padding: '12px 14px',
                                        background: '#1a1f2e',
                                        border: '1px solid #374151',
                                        borderRadius: 10,
                                        color: '#f9fafb', fontSize: 15,
                                        transition: 'border-color 0.15s, box-shadow 0.15s',
                                    }}
                                />
                                <div style={{ fontSize: 12, color: '#4b5563', marginTop: 6 }}>
                                    Default: <code style={{ color: '#6b7280' }}>dev</code> (local only)
                                </div>
                            </div>

                            {/* Error */}
                            {error && (
                                <div style={{
                                    background: '#ef444415',
                                    border: '1px solid #ef444440',
                                    borderRadius: 10, padding: '10px 14px',
                                    fontSize: 13, color: '#ef4444',
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
                                    background: 'linear-gradient(135deg,#3b82f6,#2563eb)',
                                    border: 'none', borderRadius: 12,
                                    color: '#fff', fontSize: 16, fontWeight: 700,
                                    cursor: loading || !tenantId.trim() ? 'not-allowed' : 'pointer',
                                    opacity: loading || !tenantId.trim() ? 0.6 : 1,
                                    transition: 'all 0.15s',
                                    boxShadow: '0 0 20px rgba(59,130,246,0.25)',
                                    marginTop: 4,
                                }}
                            >
                                {loading ? 'Signing in…' : 'Sign in →'}
                            </button>
                        </form>
                    </div>

                    {/* Footer note */}
                    <p style={{
                        textAlign: 'center', fontSize: 12, color: '#374151',
                        marginTop: 20,
                    }}>
                        iHouse Core · Property Operations Platform
                    </p>
                </div>
            </div>
        </>
    );
}
