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

    // Full-screen native mobile routes where the shell shouldn't render its own navigation
    if (pathname.startsWith('/worker') || pathname.startsWith('/ops/cleaner')) {
        return (
            <div style={{ 
                flex: 1, display: 'flex', justifyContent: 'center', 
                background: isDesktop ? 'var(--color-bg, #0d1117)' : 'transparent',
                minHeight: '100vh', width: '100%' 
            }}>
                <main style={{ 
                    flex: 1, 
                    width: '100%', 
                    maxWidth: isDesktop ? '480px' : '100%', 
                    minHeight: '100vh', 
                    padding: 0, 
                    margin: 0,
                    position: 'relative',
                    overflowX: 'hidden',
                    boxShadow: isDesktop ? '0 0 50px rgba(0,0,0,0.4), 0 0 10px rgba(0,0,0,0.5)' : 'none',
                    borderLeft: isDesktop ? '1px solid #1f2937' : 'none',
                    borderRight: isDesktop ? '1px solid #1f2937' : 'none',
                }}>
                    {children}
                </main>
            </div>
        );
    }

    // ── Mobile (<768px): hamburger drawer + bottom nav ──
    if (isMobile) {
        return (
            <>
                {/* Language switcher */}
                <div style={{ position: 'fixed', top: 10, right: 12, zIndex: 200 }}>
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
                        background: 'rgba(248, 246, 242, 0.65)',
                        backdropFilter: 'blur(12px)',
                        WebkitBackdropFilter: 'blur(12px)',
                        border: '1px solid rgba(221, 216, 208, 0.5)',
                        borderRadius: 'var(--radius-md, 8px)',
                        width: 40,
                        height: 40,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        fontSize: 18,
                        color: 'var(--color-text, #171A1F)',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
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
                {/* Language switcher — top right */}
                <div style={{ position: 'fixed', top: 10, right: 12, zIndex: 200 }}>
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
