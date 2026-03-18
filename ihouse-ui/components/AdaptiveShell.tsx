'use client';

/**
 * Phase 376 — AdaptiveShell Component
 *
 * Context-appropriate navigation shell for authenticated surfaces.
 * - Desktop (≥1024px): full sidebar on left + content with marginInlineStart
 * - Tablet (768–1023px): collapsible sidebar (toggle via hamburger)
 * - Mobile (<768px): no sidebar, bottom navigation bar
 *
 * RTL-aware via CSS logical properties.
 * Uses Domaniqo design tokens.
 */

import { useState, useCallback } from 'react';
import { useIsMobile, useIsDesktop } from '../hooks/useMediaQuery';
import Sidebar from './Sidebar';
import BottomNav from './BottomNav';
import CompactLangSwitcher from './CompactLangSwitcher';

interface AdaptiveShellProps {
    children: React.ReactNode;
}

export default function AdaptiveShell({ children }: AdaptiveShellProps) {
    const isMobile = useIsMobile();
    const isDesktop = useIsDesktop();
    const isTablet = !isMobile && !isDesktop;

    const [sidebarOpen, setSidebarOpen] = useState(false);
    const toggleSidebar = useCallback(() => setSidebarOpen(prev => !prev), []);

    // Mobile: no sidebar, bottom nav, full-width content
    if (isMobile) {
        return (
            <>
                {/* Phase 838 — language always reachable on mobile */}
                <div style={{ position: 'fixed', top: 10, right: 12, zIndex: 200 }}>
                    <CompactLangSwitcher theme="auto" position="inline" />
                </div>
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
            </>
        );
    }

    // Tablet: collapsible sidebar + overlay
    if (isTablet) {
        return (
            <>
                {/* Phase 838 — language accessible on tablet (top-right, opposite hamburger) */}
                <div style={{ position: 'fixed', top: 10, right: 12, zIndex: 200 }}>
                    <CompactLangSwitcher theme="auto" position="inline" />
                </div>

                {/* Hamburger toggle */}
                <button
                    id="sidebar-toggle"
                    onClick={toggleSidebar}
                    aria-label="Toggle navigation"
                    style={{
                        position: 'fixed',
                        top: 12,
                        insetInlineStart: 12,
                        zIndex: 60,
                        background: 'var(--color-surface, #fff)',
                        border: '1px solid var(--color-border, #DDD8D0)',
                        borderRadius: 'var(--radius-md, 8px)',
                        width: 44,
                        height: 44,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        fontSize: 20,
                        color: 'var(--color-text, #171A1F)',
                        boxShadow: 'var(--shadow-sm)',
                    }}
                >
                    {sidebarOpen ? '✕' : '☰'}
                </button>

                {/* Overlay */}
                {sidebarOpen && (
                    <div
                        onClick={() => setSidebarOpen(false)}
                        style={{
                            position: 'fixed',
                            inset: 0,
                            background: 'rgba(0,0,0,0.3)',
                            zIndex: 38,
                            backdropFilter: 'blur(2px)',
                        }}
                    />
                )}

                {/* Sidebar (slides in) */}
                <div style={{
                    position: 'fixed',
                    top: 0,
                    insetInlineStart: 0,
                    height: '100vh',
                    zIndex: 40,
                    transform: sidebarOpen ? 'translateX(0)' : 'translateX(-100%)',
                    transition: 'transform var(--transition-base, 220ms)',
                }}>
                    <Sidebar />
                </div>

                {/* Content */}
                <main style={{
                    flex: 1,
                    padding: 'var(--space-8)',
                    paddingInlineStart: 'calc(var(--space-8) + 56px)',
                    maxWidth: 'var(--content-max)',
                }}>
                    {children}
                </main>
            </>
        );
    }

    // Desktop: full sidebar + content with margin
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
        </>
    );
}
