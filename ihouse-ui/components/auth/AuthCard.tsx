'use client';

/**
 * AuthCard — Shared wrapper for all auth screens.
 * Phase 839 — Full localization (EN / TH / HE)
 *
 * Auth layout rule (permanent):
 *   Form elements always direction: ltr, text-align: left.
 *   RTL is NOT applied here — auth is not yet fully RTL-aware.
 *   title/subtitle content will be translated per language via t().
 */

import DMonogram from '../DMonogram';
import { useLanguage } from '../../lib/LanguageContext';
import { TranslationKey } from '../../lib/translations';

interface AuthCardProps {
    children: React.ReactNode;
    /** Translation key for the card heading (e.g. 'auth.welcome') */
    titleKey?: TranslationKey;
    /** Translation key for the subtitle (e.g. 'auth.subtitle') */
    subtitleKey?: TranslationKey;
    /** Raw string override — used by non-login screens that haven't been localized yet */
    title?: string;
    subtitle?: string;
}

export default function AuthCard({
    children,
    titleKey,
    subtitleKey,
    title,
    subtitle,
}: AuthCardProps) {
    const { t } = useLanguage();

    const resolvedTitle = titleKey ? t(titleKey) : (title ?? 'Welcome');
    const resolvedSubtitle = subtitleKey ? t(subtitleKey) : subtitle;

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
                            {t('auth.ops_platform')}
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
                            {resolvedTitle}
                        </h1>
                        {resolvedSubtitle && (
                            <p style={{
                                fontSize: 'var(--text-sm, 14px)',
                                color: 'rgba(234,229,222,0.4)',
                                margin: '0 0 var(--space-6, 24px)',
                            }}>
                                {resolvedSubtitle}
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
                        {t('auth.footer')}
                    </p>
                </div>
            </div>
        </>
    );
}
