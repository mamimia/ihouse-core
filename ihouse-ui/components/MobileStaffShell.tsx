'use client';

/**
 * MobileStaffShell — Canonical mobile staff frame
 *
 * Owns the full shared mobile-first experience for field staff surfaces:
 *   - /worker, /ops/cleaner, /ops/checkin, /ops/checkout, /ops/maintenance
 *
 * Responsibilities:
 *   - Dark theme (forced)
 *   - Phone simulation on desktop (480px centered)
 *   - Top header (shared or custom)
 *   - Bottom navigation (shared BottomNav with per-flow items)
 *   - Safe-area handling (notch + home indicator)
 *   - Content area spacing rhythm
 *   - Sticky action area (above bottom nav)
 *   - Page transitions (350ms fade per Brand Handoff §17)
 *
 * Brand Handoff compliance:
 *   - Colors: var(--color-*) tokens only, dark mode
 *   - Typography: var(--font-brand) for headings, var(--font-sans) for body
 *   - Spacing: var(--space-*) tokens only
 *   - Radius: var(--radius-*) tokens
 *   - Motion: var(--transition-base), 280ms ease-out entrance, 350ms fade transitions
 *   - Touch targets: var(--touch-target-min) = 44px
 */

import { useEffect, useState } from 'react';
import { useIsMobile, useIsDesktop } from '../hooks/useMediaQuery';
import BottomNav, { BottomNavItem } from './BottomNav';
import { useLanguage } from '../lib/LanguageContext';
import { getToken } from '../lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MobileStaffShellProps {
    children: React.ReactNode;
    /** Custom header — replaces the default minimal header */
    header?: React.ReactNode;
    /** Title for the default header (ignored if custom header is provided) */
    title?: string;
    /** Back button handler for default header */
    onBack?: () => void;
    /** Right-side action in the default header */
    headerAction?: React.ReactNode;
    /** Per-flow bottom nav items — if omitted, no bottom nav is rendered */
    bottomNavItems?: BottomNavItem[];
    /** Sticky action element above bottom nav (e.g., primary CTA button) */
    stickyAction?: React.ReactNode;
    /** Whether to hide the default header entirely */
    hideHeader?: boolean;
}

// ---------------------------------------------------------------------------
// Default Header
// ---------------------------------------------------------------------------

function DefaultHeader({
    title,
    onBack,
    headerAction,
}: {
    title?: string;
    onBack?: () => void;
    headerAction?: React.ReactNode;
}) {
    return (
        <div
            style={{
                position: 'sticky',
                top: 0,
                zIndex: 30,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                height: 56,
                paddingInline: 'var(--space-4)',
                paddingTop: 'env(safe-area-inset-top, 0px)',
                background: 'var(--color-bg)',
                borderBottom: '1px solid var(--color-border)',
            }}
        >
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                {onBack && (
                    <button
                        onClick={onBack}
                        aria-label="Go back"
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: 36,
                            height: 36,
                            border: 'none',
                            background: 'none',
                            color: 'var(--color-text-dim)',
                            fontSize: 'var(--text-lg)',
                            cursor: 'pointer',
                            borderRadius: 'var(--radius-md)',
                            transition: 'var(--transition-fast)',
                            padding: 0,
                            minHeight: 36,
                            minWidth: 36,
                        }}
                    >
                        ←
                    </button>
                )}
                {title && (
                    <h1
                        style={{
                            fontSize: 'var(--text-lg)',
                            fontWeight: 600,
                            fontFamily: 'var(--font-brand)',
                            color: 'var(--color-text)',
                            margin: 0,
                            letterSpacing: '-0.01em',
                        }}
                    >
                        {title}
                    </h1>
                )}
            </div>
            {headerAction && (
                <div style={{ display: 'flex', alignItems: 'center' }}>
                    {headerAction}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// MobileStaffShell
// ---------------------------------------------------------------------------

export default function MobileStaffShell({
    children,
    header,
    title,
    onBack,
    headerAction,
    bottomNavItems,
    stickyAction,
    hideHeader,
}: MobileStaffShellProps) {
    const isMobile = useIsMobile();
    const isDesktop = useIsDesktop();
    const { t } = useLanguage();
    
    // First-time welcome state
    const [showWelcome, setShowWelcome] = useState(false);
    const [welcomeName, setWelcomeName] = useState('');

    useEffect(() => {
        if (typeof window !== 'undefined' && sessionStorage.getItem('ihouse_welcome') === 'true') {
            sessionStorage.removeItem('ihouse_welcome');
            
            const token = getToken();
            if (token) {
                try {
                    const payload = JSON.parse(atob(token.split('.')[1]));
                    // Extract first name or use a default
                    const fullName = payload.full_name || payload.display_name || payload.name || '';
                    setWelcomeName(fullName.split(' ')[0] || '');
                } catch { /* ignore */ }
            }
            setShowWelcome(true);
        }
    }, []);

    const hasBottomNav = bottomNavItems && bottomNavItems.length > 0;
    const bottomNavHeight = hasBottomNav ? 72 : 0;

    // Shared content padding
    const contentPaddingBottom = hasBottomNav
        ? `calc(${bottomNavHeight}px + env(safe-area-inset-bottom, 8px)${stickyAction ? ' + 64px' : ''})`
        : stickyAction
          ? '72px'
          : 'var(--space-4)';

    return (
        <div
            data-theme="dark"
            style={{
                flex: 1,
                display: 'flex',
                justifyContent: 'center',
                background: isDesktop ? 'var(--color-midnight, #0d1117)' : 'transparent',
                minHeight: '100vh',
                width: '100%',
            }}
        >
            <div
                style={{
                    flex: 1,
                    width: '100%',
                    maxWidth: isDesktop ? '480px' : '100%',
                    minHeight: '100vh',
                    position: 'relative',
                    overflowX: 'hidden',
                    display: 'flex',
                    flexDirection: 'column',
                    background: 'var(--color-bg)',
                    color: 'var(--color-text)',
                    fontFamily: 'var(--font-sans)',
                    // Phone simulation on desktop
                    boxShadow: isDesktop
                        ? '0 0 50px rgba(0,0,0,0.4), 0 0 10px rgba(0,0,0,0.5)'
                        : 'none',
                    borderLeft: isDesktop ? '1px solid var(--color-border)' : 'none',
                    borderRight: isDesktop ? '1px solid var(--color-border)' : 'none',
                }}
            >
                {/* Header */}
                {!hideHeader && (
                    header || (
                        <DefaultHeader
                            title={title}
                            onBack={onBack}
                            headerAction={headerAction}
                        />
                    )
                )}

                {/* Scrollable content area */}
                <main
                    style={{
                        flex: 1,
                        overflowY: 'auto',
                        paddingBottom: contentPaddingBottom,
                    }}
                >
                    {children}
                </main>

                {/* Sticky action area (above bottom nav) */}
                {stickyAction && (
                    <div
                        style={{
                            position: 'fixed',
                            bottom: hasBottomNav
                                ? `calc(${bottomNavHeight}px + env(safe-area-inset-bottom, 8px))`
                                : 'env(safe-area-inset-bottom, 8px)',
                            left: 0,
                            right: 0,
                            maxWidth: isDesktop ? '480px' : '100%',
                            margin: isDesktop ? '0 auto' : '0',
                            padding: 'var(--space-3) var(--space-4)',
                            background: 'linear-gradient(transparent, var(--color-bg) 30%)',
                            zIndex: 20,
                        }}
                    >
                        {stickyAction}
                    </div>
                )}

                {/* Bottom navigation */}
                {hasBottomNav && (
                    <BottomNav items={bottomNavItems} />
                )}

                {/* Phase 945: First-time Welcome Overlay */}
                {showWelcome && (
                    <div style={{
                        position: 'fixed', inset: 0, zIndex: 9999,
                        background: 'rgba(13, 17, 23, 0.9)',
                        backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        animation: 'fadeIn 400ms ease',
                    }}>
                        <div style={{
                            background: 'var(--color-surface, #1F2329)',
                            borderRadius: 'var(--radius-lg, 24px)',
                            padding: 'var(--space-8, 32px) var(--space-6, 24px)',
                            maxWidth: 340, width: '90%',
                            textAlign: 'center',
                            boxShadow: '0 24px 48px rgba(0,0,0,0.5)',
                            border: '1px solid rgba(248,246,242,0.1)',
                            animation: 'slideUp 500ms cubic-bezier(0.16, 1, 0.3, 1)',
                        }}>
                            <div style={{ fontSize: 48, marginBottom: 'var(--space-4, 16px)' }}>🎉</div>
                            <h2 style={{
                                fontSize: 'var(--text-2xl, 24px)', fontWeight: 800,
                                color: 'var(--color-text, #F8F6F2)', marginBottom: 'var(--space-2, 8px)',
                                fontFamily: 'var(--font-brand, inherit)', letterSpacing: '-0.02em',
                            }}>
                                {t('worker.welcome_first_time').replace('{name}', welcomeName)}
                            </h2>
                            <p style={{
                                fontSize: 'var(--text-base, 16px)', color: 'var(--color-sage, #8C9990)',
                                marginBottom: 'var(--space-8, 32px)', lineHeight: 1.5,
                            }}>
                                {t('worker.welcome_first_time_sub')}
                            </p>
                            <button
                                onClick={() => setShowWelcome(false)}
                                className="auth-btn"
                                style={{
                                    width: '100%', padding: '16px',
                                    background: 'var(--color-copper, #B56E45)',
                                    color: 'var(--color-white, #FFF)', border: 'none',
                                    borderRadius: 'var(--radius-md, 12px)', fontSize: 'var(--text-base, 16px)',
                                    fontWeight: 700, cursor: 'pointer', transition: 'background 0.2s',
                                }}
                            >
                                Let's get started
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
