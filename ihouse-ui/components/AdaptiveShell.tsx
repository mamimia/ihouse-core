'use client';

/**
 * Phase 376 — AdaptiveShell Component
 * Phase 860 — 3-mode responsive navigation:
 *   Desktop (≥1024px): full sidebar (220px) — always visible, pushes content
 *   Tablet  (768–1023px): compact rail (64px) — icon-only, persistent, pushes content
 *   Mobile  (<768px): hamburger + slide-in drawer + bottom nav
 *
 * RTL-aware via CSS logical properties.
 * Uses Domaniqo design tokens.
 */

import { useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { usePathname } from 'next/navigation';
import { useIsMobile, useIsDesktop } from '../hooks/useMediaQuery';
import Sidebar from './Sidebar';
import BottomNav from './BottomNav';
import CompactLangSwitcher from './CompactLangSwitcher';
import ThemeToggle from './ThemeToggle';

const WorkerTutorial = dynamic(() => import('./WorkerTutorial'), { ssr: false });

interface AdaptiveShellProps {
    children: React.ReactNode;
}

export default function AdaptiveShell({ children }: AdaptiveShellProps) {
    const isMobile = useIsMobile();
    const isDesktop = useIsDesktop();
    const isTablet = !isMobile && !isDesktop;
    const pathname = usePathname() || '';

    const [drawerOpen, setDrawerOpen] = useState(false);
    const toggleDrawer = useCallback(() => setDrawerOpen(prev => !prev), []);
    const closeDrawer = useCallback(() => setDrawerOpen(false), []);

    // Full-screen mobile staff routes — bypass sidebar/breadcrumbs, use MobileStaffShell
    const MOBILE_STAFF_PREFIXES = ['/worker', '/ops/cleaner', '/ops/checkin', '/ops/checkout', '/ops/maintenance'];
    const isMobileStaffRoute = MOBILE_STAFF_PREFIXES.some(p => pathname.startsWith(p));

    // Phase 882b — Also bypass sidebar when preview role is active (staff preview context)
    // This prevents the admin sidebar from rendering on pages (like /tasks) that are
    // wrapped in MobileStaffShell by their own preview-aware logic.
    const isPreviewStaffContext = typeof window !== 'undefined' && (() => {
        try { return !!sessionStorage.getItem('ihouse_preview_role'); } catch { return false; }
    })();

    if (isMobileStaffRoute || isPreviewStaffContext) {
        // MobileStaffShell handles its own frame (dark theme, phone sim, header, nav)
        // Each page supplies its own header/bottomNav via MobileStaffShell props
        return (
            <div style={{ flex: 1, width: '100%', minHeight: '100vh' }}>
                {children}
            </div>
        );
    }

    // ── Mobile (<768px): hamburger drawer + bottom nav ──
    if (isMobile) {
        return (
            <>
                {/* Language switcher and theme toggle */}
                <div style={{ position: 'fixed', top: 10, right: 12, zIndex: 200, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <ThemeToggle />
                    <CompactLangSwitcher theme="auto" position="inline" />
                </div>

                {/* Hamburger button */}
                <button
                    id="sidebar-toggle"
                    onClick={toggleDrawer}
                    aria-label="Toggle navigation"
                    style={{
                        position: 'fixed',
                        top: 10,
                        insetInlineStart: 12,
                        zIndex: 60,
                        appearance: 'none',
                        WebkitAppearance: 'none',
                        background: 'rgba(255, 255, 255, 0.08)',
                        border: '1px solid rgba(0, 0, 0, 0.1)',
                        borderRadius: 'var(--radius-md, 8px)',
                        width: 40,
                        height: 40,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        fontSize: 18,
                        color: 'var(--color-text, #171A1F)',
                        boxShadow: 'none',
                    }}
                >
                    {drawerOpen ? '✕' : '☰'}
                </button>

                {/* Overlay backdrop */}
                {drawerOpen && (
                    <div
                        onClick={closeDrawer}
                        style={{
                            position: 'fixed',
                            inset: 0,
                            background: 'rgba(0,0,0,0.4)',
                            zIndex: 38,
                            backdropFilter: 'blur(2px)',
                        }}
                    />
                )}

                {/* Slide-in drawer (full sidebar) */}
                <div style={{
                    position: 'fixed',
                    top: 0,
                    insetInlineStart: 0,
                    height: '100vh',
                    zIndex: 40,
                    transform: drawerOpen ? 'translateX(0)' : 'translateX(-100%)',
                    transition: 'transform 220ms ease',
                }}>
                    <Sidebar mode="drawer" onClose={closeDrawer} />
                </div>

                {/* Content */}
                <main style={{
                    flex: 1,
                    padding: 'var(--space-4)',
                    paddingTop: 'calc(var(--space-4) + 44px)',
                    paddingBottom: 'calc(72px + env(safe-area-inset-bottom, 8px))',
                    maxWidth: '100%',
                }}>
                    {children}
                </main>
                <BottomNav />
                <WorkerTutorial />
            </>
        );
    }

    // ── Tablet (768–1023px): persistent compact rail ──
    if (isTablet) {
        return (
            <>
                {/* Language switcher and theme toggle — top right */}
                <div style={{ position: 'fixed', top: 10, right: 12, zIndex: 200, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <ThemeToggle />
                    <CompactLangSwitcher theme="auto" position="inline" />
                </div>

                {/* Compact rail sidebar — always visible, never overlays */}
                <Sidebar collapsed />

                {/* Content pushed by rail width */}
                <main style={{
                    marginInlineStart: '64px',
                    flex: 1,
                    padding: 'var(--space-6)',
                    maxWidth: 'var(--content-max)',
                }}>
                    {children}
                </main>
                <WorkerTutorial />
            </>
        );
    }

    // ── Desktop (≥1024px): full sidebar, always visible ──
    return (
        <>
            <Sidebar />
            <main style={{
                marginInlineStart: 'var(--sidebar-width)',
                flex: 1,
                padding: 'var(--space-8)',
                maxWidth: 'var(--content-max)',
            }}>
                {children}
            </main>
            <WorkerTutorial />
        </>
    );
}
