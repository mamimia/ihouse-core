'use client';

/**
 * AuthCard — Shared wrapper for all auth screens.
 * Dark theme, centered, with Domaniqo monogram branding.
 */

import DMonogram from '../DMonogram';

interface AuthCardProps {
    children: React.ReactNode;
    title?: string;
    subtitle?: string;
}

export default function AuthCard({ children, title = 'Welcome', subtitle }: AuthCardProps) {
    return (
        <>
            <style>{`
                @keyframes authFadeUp { from { opacity:0; transform:translateY(16px) } to { opacity:1; transform:translateY(0) } }
                @keyframes authGlow { 0%,100% { opacity:0.7 } 50% { opacity:1 } }
                .auth-card { animation: authFadeUp 400ms ease forwards }
                .auth-input:focus { outline: none; border-color: var(--color-copper, #B56E45) !important; box-shadow: 0 0 0 3px rgba(181,110,69,0.15) }
                .auth-btn:hover:not(:disabled) { opacity: 0.92 !important; box-shadow: var(--shadow-glow-moss) !important }
                .auth-btn:active:not(:disabled) { transform: scale(0.985) }
                .auth-link { color: rgba(234,229,222,0.4); text-decoration: none; transition: color 0.2s; }
                .auth-link:hover { color: var(--color-copper, #B56E45); }
            `}</style>

            <div
                className="grain-overlay"
                style={{
                    minHeight: '100vh',
                    background: 'var(--color-midnight, #171A1F)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: 'var(--space-6, 24px)',
                    fontFamily: 'var(--font-sans, system-ui, sans-serif)',
                }}
            >
                {/*
              * AUTH LAYOUT RULE (permanent):
              * English auth screens = LTR, left-aligned form layout.
              * Title/subtitle may be centered. All form elements must be left-aligned.
              * No RTL drift. No right-alignment on labels, inputs, checkboxes, or links.
              */}
            <div className="auth-card" style={{ width: '100%', maxWidth: 420, direction: 'ltr', textAlign: 'left' }}>
                    {/* Monogram + Brand */}
                    <div style={{ textAlign: 'center', marginBottom: 'var(--space-10, 40px)' }}>
                        <div style={{
                            display: 'inline-flex',
                            animation: 'authGlow 4s ease-in-out infinite',
                            marginBottom: 'var(--space-4, 16px)',
                        }}>
                            <DMonogram size={52} color="var(--color-stone, #EAE5DE)" strokeWidth={1.8} />
                        </div>
                        <div style={{
                            fontFamily: 'var(--font-display, Georgia, serif)',
                            fontSize: 'var(--text-3xl, 30px)',
                            fontWeight: 400,
                            color: 'var(--color-stone, #EAE5DE)',
                            letterSpacing: '-0.02em',
                            lineHeight: 1.1,
                            marginBottom: 'var(--space-2, 8px)',
                        }}>
                            Domaniqo
                        </div>
                        <div style={{
                            fontSize: 'var(--text-sm, 14px)',
                            color: 'var(--color-olive, #8B9466)',
                            fontFamily: 'var(--font-sans, inherit)',
                            letterSpacing: '0.04em',
                            textTransform: 'uppercase',
                        }}>
                            Operations Platform
                        </div>
                    </div>

                    {/* Card body */}
                    <div style={{
                        background: 'var(--color-elevated, #1E2127)',
                        border: '1px solid rgba(234,229,222,0.06)',
                        borderRadius: 'var(--radius-xl, 20px)',
                        padding: 'var(--space-8, 32px) var(--space-6, 24px)',
                        boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
                    }}>
                        <h1 style={{
                            fontFamily: 'var(--font-brand, "Inter", sans-serif)',
                            fontSize: 'var(--text-lg, 18px)',
                            fontWeight: 700,
                            color: 'var(--color-stone, #EAE5DE)',
                            margin: '0 0 var(--space-1, 4px)',
                            letterSpacing: '-0.02em',
                        }}>
                            {title}
                        </h1>
                        {subtitle && (
                            <p style={{
                                fontSize: 'var(--text-sm, 14px)',
                                color: 'rgba(234,229,222,0.4)',
                                margin: '0 0 var(--space-6, 24px)',
                            }}>
                                {subtitle}
                            </p>
                        )}
                        {children}
                    </div>

                    {/* Footer */}
                    <p style={{
                        textAlign: 'center',
                        fontSize: 'var(--text-xs, 12px)',
                        color: 'rgba(234,229,222,0.2)',
                        marginTop: 'var(--space-6, 24px)',
                    }}>
                        Domaniqo · See every stay.
                    </p>
                </div>
            </div>
        </>
    );
}
