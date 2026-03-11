'use client';

/**
 * Phase 257 — Login Page (Domaniqo Rebrand)
 * Route: /login
 *
 * Domaniqo brand: Midnight Graphite, Stone Mist, Cloud White, Deep Moss, Signal Copper.
 * Typography: Manrope (brand headlines) + Inter (UI body).
 * Tone: calm, precise, premium, architectural.
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
            document.cookie = `ihouse_token=${resp.token}; path=/; max-age=${resp.expires_in}; SameSite=Lax`;
            window.location.href = '/dashboard';
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
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&family=Inter:wght@400;500&display=swap');
        * { box-sizing: border-box }
        body { background: #F8F6F2 !important; margin: 0 }
        /* Hide desktop sidebar on login page */
        nav { display: none !important }
        main { margin-left: 0 !important; padding: 0 !important; max-width: 100% !important }
        @keyframes fadeUp { from { opacity:0; transform:translateY(12px) } to { opacity:1; transform:translateY(0) } }
        .login-card { animation: fadeUp 280ms ease forwards }
        input:focus { outline: none; border-color: #334036 !important; box-shadow: 0 0 0 3px rgba(51,64,54,0.12) }
        .login-btn:hover:not(:disabled) { background: #2a3630 !important; box-shadow: 0 4px 20px rgba(51,64,54,0.28) !important }
        .login-btn:active:not(:disabled) { transform: scale(0.985) }
      `}</style>
            <div style={{
                minHeight: '100vh', background: '#F8F6F2',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: '24px',
                fontFamily: "'Inter', -apple-system, sans-serif",
            }}>
                <div className="login-card" style={{ width: '100%', maxWidth: 400 }}>

                    {/* Brand wordmark */}
                    <div style={{ textAlign: 'center', marginBottom: 44 }}>
                        <div style={{
                            fontFamily: "'Manrope', sans-serif",
                            fontSize: 28, fontWeight: 800,
                            color: '#171A1F',
                            letterSpacing: '-0.04em', marginBottom: 10,
                        }}>
                            Domaniqo
                        </div>
                        <div style={{
                            fontSize: 13, color: '#66715F',
                            fontFamily: "'Inter', sans-serif",
                            letterSpacing: '0.01em',
                        }}>
                            Calm command for modern hospitality.
                        </div>
                    </div>

                    {/* Card */}
                    <div style={{
                        background: '#FFFFFF',
                        border: '1px solid #DDD8D0',
                        borderRadius: 16,
                        padding: '32px 28px',
                        boxShadow: '0 8px 32px rgba(23,26,31,0.10)',
                    }}>
                        <h1 style={{
                            fontFamily: "'Manrope', sans-serif",
                            fontSize: 20, fontWeight: 700, color: '#171A1F',
                            margin: '0 0 6px',
                            letterSpacing: '-0.02em',
                        }}>Sign in</h1>
                        <p style={{ fontSize: 13, color: '#9A958E', margin: '0 0 28px', fontFamily: "'Inter', sans-serif" }}>
                            Enter your credentials to continue
                        </p>

                        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                            {/* Tenant ID */}
                            <div>
                                <label style={{
                                    display: 'block', fontSize: 12, fontWeight: 600,
                                    color: '#5A5A52', marginBottom: 6,
                                    textTransform: 'uppercase', letterSpacing: '0.06em',
                                    fontFamily: "'Inter', sans-serif",
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
                                        background: '#F8F6F2',
                                        border: '1px solid #DDD8D0',
                                        borderRadius: 10,
                                        color: '#171A1F', fontSize: 14,
                                        transition: 'border-color 0.15s, box-shadow 0.15s',
                                        fontFamily: 'monospace',
                                    }}
                                />
                            </div>

                            {/* Secret */}
                            <div>
                                <label style={{
                                    display: 'block', fontSize: 12, fontWeight: 600,
                                    color: '#5A5A52', marginBottom: 6,
                                    textTransform: 'uppercase', letterSpacing: '0.06em',
                                    fontFamily: "'Inter', sans-serif",
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
                                        background: '#F8F6F2',
                                        border: '1px solid #DDD8D0',
                                        borderRadius: 10,
                                        color: '#171A1F', fontSize: 14,
                                        transition: 'border-color 0.15s, box-shadow 0.15s',
                                    }}
                                />
                                <div style={{ fontSize: 12, color: '#9A958E', marginTop: 6, fontFamily: "'Inter', sans-serif" }}>
                                    Default: <code style={{ color: '#66715F' }}>dev</code> (local only)
                                </div>
                            </div>

                            {/* Error */}
                            {error && (
                                <div style={{
                                    background: '#9B3A3A15',
                                    border: '1px solid #9B3A3A30',
                                    borderRadius: 10, padding: '10px 14px',
                                    fontSize: 13, color: '#9B3A3A',
                                    fontFamily: "'Inter', sans-serif",
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
                                    background: '#334036',
                                    border: 'none', borderRadius: 10,
                                    color: '#F8F6F2', fontSize: 15, fontWeight: 600,
                                    fontFamily: "'Manrope', sans-serif",
                                    letterSpacing: '-0.01em',
                                    cursor: loading || !tenantId.trim() ? 'not-allowed' : 'pointer',
                                    opacity: loading || !tenantId.trim() ? 0.5 : 1,
                                    transition: 'all 0.15s',
                                    boxShadow: '0 2px 12px rgba(51,64,54,0.20)',
                                    marginTop: 4,
                                }}
                            >
                                {loading ? 'Signing in…' : 'Sign in →'}
                            </button>
                        </form>
                    </div>

                    {/* Footer */}
                    <p style={{
                        textAlign: 'center', fontSize: 12, color: '#9A958E',
                        marginTop: 20, fontFamily: "'Inter', sans-serif",
                    }}>
                        Domaniqo · See every stay.
                    </p>
                </div>
            </div>
        </>
    );
}
