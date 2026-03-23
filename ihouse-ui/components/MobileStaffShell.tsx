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

import { useIsMobile, useIsDesktop } from '../hooks/useMediaQuery';
import BottomNav, { BottomNavItem } from './BottomNav';

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
            </div>
        </div>
    );
}
