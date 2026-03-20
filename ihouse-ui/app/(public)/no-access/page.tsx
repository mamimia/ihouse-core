'use client';

/**
 * Phase 856B — No Access Page
 * Route: /no-access
 *
 * Shown to authenticated users who have no tenant binding.
 * Replaces the previous inline error in /auth/callback.
 * Also reachable from any other "you're authenticated but have no access" state.
 */

import DMonogram from '../../../components/DMonogram';

export default function NoAccessPage() {
    return (
        <div
            className="grain-overlay"
            style={{
                minHeight: '100vh',
                background: 'var(--color-midnight)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: 'var(--space-6, 24px)',
            }}
        >
            <div style={{
                maxWidth: 480,
                width: '100%',
                textAlign: 'center',
            }}>
                <div style={{ marginBottom: 'var(--space-6, 24px)', opacity: 0.7 }}>
                    <DMonogram size={56} color="var(--color-stone)" strokeWidth={1.2} />
                </div>

                <h1 style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'clamp(var(--text-xl), 4vw, var(--text-2xl))',
                    fontWeight: 400,
                    color: 'var(--color-stone)',
                    marginBottom: 'var(--space-4, 16px)',
                    lineHeight: 1.3,
                }}>
                    Account not yet activated
                </h1>

                <p style={{
                    fontSize: 'var(--text-base, 16px)',
                    color: 'rgba(234,229,222,0.5)',
                    lineHeight: 1.7,
                    marginBottom: 'var(--space-8, 32px)',
                    maxWidth: 380,
                    marginInline: 'auto',
                }}>
                    Your account exists but has not been assigned to an organization yet.
                    An administrator needs to invite you or approve your request before you can access the platform.
                </p>

                <div style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 'var(--space-3, 12px)',
                    alignItems: 'center',
                }}>
                    {/* Primary: request access */}
                    <a
                        href="/get-started"
                        style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            padding: '14px 32px',
                            background: 'var(--color-moss, #334036)',
                            borderRadius: 'var(--radius-full)',
                            color: 'var(--color-white, #F8F6F2)',
                            fontSize: 'var(--text-base, 16px)',
                            fontWeight: 600,
                            fontFamily: 'var(--font-brand)',
                            textDecoration: 'none',
                            boxShadow: 'var(--shadow-glow-moss)',
                            transition: 'opacity 0.2s',
                            minHeight: 48,
                        }}
                    >
                        Request Access →
                    </a>

                    {/* Secondary: try different account */}
                    <a
                        href="/login"
                        style={{
                            fontSize: 'var(--text-sm, 14px)',
                            color: 'rgba(234,229,222,0.4)',
                            textDecoration: 'none',
                            padding: '8px 0',
                            transition: 'color 0.2s',
                        }}
                    >
                        Sign in with a different account
                    </a>
                </div>

                <div style={{
                    marginTop: 'var(--space-10, 40px)',
                    fontSize: 'var(--text-xs, 12px)',
                    color: 'rgba(234,229,222,0.2)',
                }}>
                    Need help? Contact info@domaniqo.com
                </div>
            </div>
        </div>
    );
}
