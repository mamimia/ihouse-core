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

    const [sidebarOpen, setSidebarOpen] = useState(false);
    const toggleSidebar = useCallback(() => setSidebarOpen(prev => !prev), []);

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
                <WorkerTutorial />
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
                <WorkerTutorial />
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
            <WorkerTutorial />
        </>
    );
}
