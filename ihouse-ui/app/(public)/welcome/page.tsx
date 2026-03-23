'use client';

/**
 * Phase 872 — Welcome / Home Route Resolver
 * Route: /welcome
 *
 * This is NOT a decorative page. It is a real signed-in route resolver.
 *
 * Routing rules:
 *   1. Guest with active stay context → /guest/current-stay (future)
 *   2. Worker → /worker (existing worker app)
 *   3. Manager/admin with workspace → /dashboard
 *   4. Owner with property → /owner
 *   5. Owner without property → show welcome + Get Started CTA
 *   6. Identity-only / basic signed-in → show welcome home (My Pocket + profile + small Get Started card)
 *   7. No auth → /login
 *
 * Principle: workers land in their existing app, not a generic welcome.
 */

import { useRouter } from 'next/navigation';
import { useIdentity } from '@/hooks/useIdentity';
import DMonogram from '@/components/DMonogram';
import { useEffect, useState } from 'react';
import SignedInShell, { SHELL_TOP_PADDING } from '@/components/SignedInShell';

export default function WelcomePage() {
    const router = useRouter();
    const { identity, loading, error } = useIdentity();
    const [resolved, setResolved] = useState(false);

    // ─── Route resolution ───
    useEffect(() => {
        if (loading) return;

        // No token / no auth → login
        if (error === 'NO_TOKEN' || (!identity && error)) {
            router.replace('/login');
            return;
        }

        if (!identity) return;

        // Staff member → staff task dashboard
        if (identity.role === 'worker' || identity.role === 'cleaner' || identity.role === 'maintenance') {
            router.replace('/worker');
            return;
        }

        // Checkin/checkout specialized roles
        if (identity.role === 'checkin') { router.replace('/checkin'); return; }
        if (identity.role === 'checkout') { router.replace('/checkout'); return; }

        // Manager/admin with workspace
        if ((identity.role === 'admin' || identity.role === 'manager') && identity.has_membership) {
            router.replace('/dashboard');
            return;
        }

        // Ops with workspace
        if (identity.role === 'ops' && identity.has_membership) {
            router.replace('/ops');
            return;
        }

        // Owner with workspace → owner portal
        if (identity.role === 'owner' && identity.has_membership) {
            router.replace('/owner');
            return;
        }

        // Everyone else stays on welcome: identity-only, owner without property, basic signed-in
        setResolved(true);
    }, [identity, loading, error, router]);

    // ─── Loading state ───
    if (loading || (!resolved && !error)) {
        return (
            <div style={{
                minHeight: '100vh',
                background: 'var(--color-midnight, #0D0F14)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
            }}>
                <div style={{
                    width: 40, height: 40,
                    border: '3px solid rgba(234,229,222,0.1)',
                    borderTopColor: 'var(--color-copper, #B56E45)',
                    borderRadius: '50%',
                    animation: 'spin 0.8s linear infinite',
                }} />
                <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
            </div>
        );
    }

    // ─── Welcome Home (for identity-only / basic signed-in / owner without property) ───
    const userName = identity?.full_name || identity?.email?.split('@')[0] || 'there';
    const showGetStartedProminent = !identity?.has_membership;
    const intakePending = identity?.intake_status === 'pending_review';

    return (
        <>
            <style>{`
                @keyframes welcomeFade { from { opacity:0; transform:translateY(16px) } to { opacity:1; transform:translateY(0) } }
                .welcome-card { animation: welcomeFade 400ms ease both; }
                .welcome-card-hover { transition: border-color 0.2s, box-shadow 0.2s; }
                .welcome-card-hover:hover { border-color: rgba(234,229,222,0.15) !important; box-shadow: 0 4px 24px rgba(0,0,0,0.15) !important; }
            `}</style>

            <SignedInShell />

            <div
                className="grain-overlay"
                style={{
                    minHeight: '100vh',
                    background: 'var(--color-midnight, #0D0F14)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    padding: `${SHELL_TOP_PADDING} var(--space-6, 24px) var(--space-10, 40px)`,
                }}
            >
                <div className="welcome-card" style={{ maxWidth: 560, width: '100%' }}>
                    {/* Greeting */}
                    <div style={{ textAlign: 'center', marginBottom: 'var(--space-10, 40px)' }}>
                        <div style={{ marginBottom: 'var(--space-4, 16px)', opacity: 0.7 }}>
                            <DMonogram size={48} color="var(--color-stone)" strokeWidth={1.2} />
                        </div>
                        <h1 style={{
                            fontFamily: 'var(--font-display)',
                            fontSize: 'clamp(var(--text-xl, 20px), 4vw, var(--text-2xl, 28px))',
                            fontWeight: 400,
                            color: 'var(--color-stone, #EAE5DE)',
                            marginBottom: 'var(--space-2, 8px)',
                            lineHeight: 1.3,
                        }}>
                            Welcome, {userName}
                        </h1>
                        <p style={{
                            fontSize: 'var(--text-sm, 14px)',
                            color: 'rgba(234,229,222,0.4)',
                        }}>
                            {identity?.email}
                        </p>
                    </div>

                    {/* Intake pending banner */}
                    {intakePending && (
                        <div className="welcome-card" style={{
                            background: 'rgba(181,110,69,0.08)',
                            border: '1px solid rgba(181,110,69,0.2)',
                            borderRadius: 'var(--radius-lg, 16px)',
                            padding: 'var(--space-5, 20px)',
                            marginBottom: 'var(--space-5, 20px)',
                            textAlign: 'center',
                        }}>
                            <div style={{ fontSize: 24, marginBottom: 8 }}>⏳</div>
                            <div style={{ fontSize: 'var(--text-sm, 14px)', color: 'var(--color-stone, #EAE5DE)', fontWeight: 600 }}>
                                Your submission is under review
                            </div>
                            <div style={{ fontSize: 'var(--text-xs, 12px)', color: 'rgba(234,229,222,0.4)', marginTop: 4 }}>
                                We'll notify you once your property is approved.
                            </div>
                        </div>
                    )}

                    {/* Cards grid */}
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
                        gap: 'var(--space-4, 16px)',
                        marginBottom: 'var(--space-6, 24px)',
                    }}>
                        {/* Profile / Settings */}
                        <a href="/profile" className="welcome-card-hover" style={{
                            display: 'block',
                            background: 'var(--color-elevated, #1E2127)',
                            border: '1px solid rgba(234,229,222,0.06)',
                            borderRadius: 'var(--radius-lg, 16px)',
                            padding: 'var(--space-5, 20px)',
                            textDecoration: 'none',
                            cursor: 'pointer',
                        }}>
                            <div style={{ fontSize: 24, marginBottom: 10 }}>👤</div>
                            <div style={{
                                fontSize: 'var(--text-sm, 14px)',
                                fontWeight: 600,
                                color: 'var(--color-stone, #EAE5DE)',
                                marginBottom: 4,
                            }}>
                                Profile & Settings
                            </div>
                            <div style={{
                                fontSize: 'var(--text-xs, 12px)',
                                color: 'rgba(234,229,222,0.35)',
                                lineHeight: 1.5,
                            }}>
                                Name, email, connected accounts, language
                            </div>
                        </a>

                        {/* My Pocket */}
                        <div className="welcome-card-hover" style={{
                            background: 'var(--color-elevated, #1E2127)',
                            border: '1px solid rgba(234,229,222,0.06)',
                            borderRadius: 'var(--radius-lg, 16px)',
                            padding: 'var(--space-5, 20px)',
                        }}>
                            <div style={{ fontSize: 24, marginBottom: 10 }}>🔖</div>
                            <div style={{
                                fontSize: 'var(--text-sm, 14px)',
                                fontWeight: 600,
                                color: 'var(--color-stone, #EAE5DE)',
                                marginBottom: 4,
                            }}>
                                My Pocket
                            </div>
                            <div style={{
                                fontSize: 'var(--text-xs, 12px)',
                                color: 'rgba(234,229,222,0.35)',
                                lineHeight: 1.5,
                            }}>
                                Saved stays, places, services, and details
                            </div>
                            <div style={{
                                marginTop: 12,
                                fontSize: 'var(--text-xs, 12px)',
                                color: 'rgba(234,229,222,0.2)',
                                fontStyle: 'italic',
                            }}>
                                Coming soon
                            </div>
                        </div>

                        {/* My Properties */}
                        <a href="/my-properties" className="welcome-card-hover" style={{
                            display: 'block',
                            background: 'var(--color-elevated, #1E2127)',
                            border: '1px solid rgba(234,229,222,0.06)',
                            borderRadius: 'var(--radius-lg, 16px)',
                            padding: 'var(--space-5, 20px)',
                            textDecoration: 'none',
                            cursor: 'pointer',
                        }}>
                            <div style={{ fontSize: 24, marginBottom: 10 }}>🏠</div>
                            <div style={{
                                fontSize: 'var(--text-sm, 14px)',
                                fontWeight: 600,
                                color: 'var(--color-stone, #EAE5DE)',
                                marginBottom: 4,
                            }}>
                                {intakePending ? 'My Properties' : 'My Properties'}
                            </div>
                            <div style={{
                                fontSize: 'var(--text-xs, 12px)',
                                color: 'rgba(234,229,222,0.35)',
                                lineHeight: 1.5,
                            }}>
                                {intakePending
                                    ? 'View and track your submitted properties'
                                    : 'View submitted properties or draft submissions'
                                }
                            </div>
                        </a>
                    </div>

                    {/* Get Started CTA */}
                    {showGetStartedProminent && !intakePending && (
                        <a href="/get-started" style={{
                            display: 'block',
                            background: 'linear-gradient(135deg, var(--color-moss, #334036) 0%, rgba(51,64,54,0.8) 100%)',
                            border: '1px solid rgba(74,124,89,0.15)',
                            borderRadius: 'var(--radius-lg, 16px)',
                            padding: 'var(--space-6, 24px)',
                            textDecoration: 'none',
                            textAlign: 'center',
                            marginBottom: 'var(--space-6, 24px)',
                            transition: 'all 0.2s',
                        }}>
                            <div style={{ fontSize: 28, marginBottom: 8 }}>🚀</div>
                            <div style={{
                                fontSize: 'var(--text-base, 16px)',
                                fontWeight: 600,
                                color: 'var(--color-white, #F8F6F2)',
                                marginBottom: 4,
                            }}>
                                Get Started — Onboard a Property
                            </div>
                            <div style={{
                                fontSize: 'var(--text-xs, 12px)',
                                color: 'rgba(248,246,242,0.5)',
                            }}>
                                Set up your first property on Domaniqo
                            </div>
                        </a>
                    )}

                    {/* Footer */}
                    <div style={{
                        textAlign: 'center',
                        fontSize: 'var(--text-xs, 12px)',
                        color: 'rgba(234,229,222,0.15)',
                        marginTop: 'var(--space-8, 32px)',
                    }}>
                        Domaniqo — Hospitality Operations
                    </div>
                </div>
            </div>
        </>
    );
}
