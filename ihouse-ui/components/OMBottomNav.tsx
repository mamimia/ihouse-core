'use client';

/**
 * Phase 1033 Step 3 — OMBottomNav
 *
 * Mobile bottom tab bar for the Operational Manager shell.
 * NOT a reuse of BottomNav.tsx (worker/admin model — wrong for OM).
 *
 * Primary tabs: Hub · Alerts · Stream · Team
 * Overflow:     More → bottom sheet with Bookings, Tasks, End Session / Close Preview
 *
 * Same product truth as OMSidebar: cockpit-first, manager shell, not admin clone.
 */

import React, { useState, useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { getTabToken } from '../lib/tokenStore';

// ---------------------------------------------------------------------------
// Mode detection (mirrors OMSidebar)
// ---------------------------------------------------------------------------

type OMMode = 'preview' | 'acting' | 'direct';

function getOMMode(): OMMode {
    if (typeof window === 'undefined') return 'direct';
    try {
        const previewRole = sessionStorage.getItem('ihouse_preview_role');
        if (previewRole === 'manager') return 'preview';
        const token = getTabToken();
        if (token) {
            const payload = JSON.parse(atob(token.split('.')[1] || '{}'));
            if (payload.token_type === 'act_as') return 'acting';
        }
    } catch { /* ignore */ }
    return 'direct';
}

// ---------------------------------------------------------------------------
// Primary tabs
// ---------------------------------------------------------------------------

type Tab = { label: string; href: string; icon: string };

const PRIMARY_TABS: Tab[] = [
    { label: 'Hub',    href: '/manager',        icon: '⚡' },
    { label: 'Alerts', href: '/manager/alerts', icon: '🔴' },
    { label: 'Stream', href: '/manager/stream', icon: '📡' },
    { label: 'Team',   href: '/manager/team',   icon: '👥' },
];

const LIVE_ROUTES = new Set(['/manager']);

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function OMBottomNav() {
    const pathname = usePathname() || '';
    const router = useRouter();
    const [sheetOpen, setSheetOpen] = useState(false);
    const [omMode, setOMMode] = useState<OMMode>('direct');

    useEffect(() => { setOMMode(getOMMode()); }, []);

    const isActive = (href: string) => {
        if (href === '/manager') return pathname === '/manager';
        return pathname.startsWith(href);
    };

    const handleNav = (href: string) => {
        setSheetOpen(false);
        if (!LIVE_ROUTES.has(href)) { router.push('/manager'); return; }
        router.push(href);
    };

    const handleEndSession = () => {
        setSheetOpen(false);
        if (omMode === 'preview') {
            sessionStorage.removeItem('ihouse_preview_role');
            window.close();
        } else if (omMode === 'acting') {
            window.location.href = '/login';
        }
    };

    const moreActive = ['/manager/bookings', '/manager/tasks'].some(h => pathname.startsWith(h));

    // ── Styles ─────────────────────────────────────────────────────────────

    const navStyle: React.CSSProperties = {
        position: 'fixed',
        bottom: 0,
        insetInlineStart: 0,
        insetInlineEnd: 0,
        zIndex: 50,
        background: 'var(--color-surface)',
        borderTop: '1px solid var(--color-border)',
        display: 'flex',
        alignItems: 'stretch',
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
        height: 'calc(56px + env(safe-area-inset-bottom, 0px))',
    };

    const tabStyle = (active: boolean): React.CSSProperties => ({
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 3,
        cursor: 'pointer',
        background: 'transparent',
        border: 'none',
        padding: '8px 0',
        color: active ? 'var(--color-primary)' : 'var(--color-text-dim)',
        transition: 'color 120ms ease',
        fontSize: 9,
        fontWeight: active ? 700 : 500,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        WebkitTapHighlightColor: 'transparent',
    });

    const iconStyle = (active: boolean): React.CSSProperties => ({
        fontSize: 18,
        lineHeight: 1,
        filter: active ? 'none' : 'grayscale(60%) opacity(0.7)',
    });

    // Active pip above tab
    const pipStyle: React.CSSProperties = {
        position: 'absolute',
        top: 0,
        width: 24,
        height: 2,
        borderRadius: '0 0 2px 2px',
        background: 'var(--color-primary)',
    };

    // Sheet overlay
    const overlayStyle: React.CSSProperties = {
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.4)',
        zIndex: 48,
        backdropFilter: 'blur(2px)',
    };

    const sheetStyle: React.CSSProperties = {
        position: 'fixed',
        bottom: 0,
        insetInlineStart: 0,
        insetInlineEnd: 0,
        zIndex: 49,
        background: 'var(--color-surface)',
        borderRadius: '16px 16px 0 0',
        padding: '16px 0 calc(72px + env(safe-area-inset-bottom, 8px))',
        boxShadow: '0 -4px 24px rgba(0,0,0,0.12)',
        transform: sheetOpen ? 'translateY(0)' : 'translateY(100%)',
        transition: 'transform 240ms cubic-bezier(0.32, 0.72, 0, 1)',
    };

    const sheetItemStyle: React.CSSProperties = {
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        padding: '14px 24px',
        cursor: 'pointer',
        fontSize: 15,
        fontWeight: 500,
        color: 'var(--color-text)',
        borderBottom: '1px solid var(--color-border)',
        transition: 'background 100ms ease',
    };

    const sheetEndStyle: React.CSSProperties = {
        ...sheetItemStyle,
        color: omMode === 'preview' ? '#ca8a04' : '#ef4444',
        fontWeight: 600,
        borderBottom: 'none',
        marginTop: 8,
    };

    return (
        <>
            {/* Overlay when More sheet is open */}
            {sheetOpen && (
                <div style={overlayStyle} onClick={() => setSheetOpen(false)} />
            )}

            {/* More sheet */}
            <div style={sheetStyle}>
                <div style={{
                    width: 32, height: 4, borderRadius: 2,
                    background: 'var(--color-border)',
                    margin: '0 auto 16px',
                }} />
                <div
                    style={sheetItemStyle}
                    onClick={() => handleNav('/manager/bookings')}
                >
                    <span style={{ fontSize: 18 }}>📋</span>
                    Bookings
                    {!LIVE_ROUTES.has('/manager/bookings') && (
                        <span style={{ marginInlineStart: 'auto', fontSize: 10, color: 'var(--color-text-faint)' }}>soon</span>
                    )}
                </div>
                <div
                    style={sheetItemStyle}
                    onClick={() => handleNav('/manager/tasks')}
                >
                    <span style={{ fontSize: 18 }}>⚡</span>
                    Tasks
                    {!LIVE_ROUTES.has('/manager/tasks') && (
                        <span style={{ marginInlineStart: 'auto', fontSize: 10, color: 'var(--color-text-faint)' }}>soon</span>
                    )}
                </div>
                {omMode !== 'direct' && (
                    <div style={sheetEndStyle} onClick={handleEndSession}>
                        <span style={{ fontSize: 18 }}>
                            {omMode === 'preview' ? '✕' : '↩'}
                        </span>
                        {omMode === 'preview' ? 'Close Preview' : 'End Session'}
                    </div>
                )}
            </div>

            {/* Bottom tab bar */}
            <nav style={navStyle} aria-label="Operational Manager navigation">
                {PRIMARY_TABS.map(tab => {
                    const active = isActive(tab.href);
                    return (
                        <button
                            key={tab.href}
                            style={{ ...tabStyle(active), position: 'relative' }}
                            onClick={() => handleNav(tab.href)}
                            aria-label={tab.label}
                            aria-current={active ? 'page' : undefined}
                        >
                            {active && <div style={pipStyle} />}
                            <span style={iconStyle(active)}>{tab.icon}</span>
                            {tab.label}
                        </button>
                    );
                })}
                {/* More tab */}
                <button
                    style={{ ...tabStyle(moreActive || sheetOpen), position: 'relative' }}
                    onClick={() => setSheetOpen(prev => !prev)}
                    aria-label="More"
                >
                    {(moreActive || sheetOpen) && <div style={pipStyle} />}
                    <span style={iconStyle(moreActive || sheetOpen)}>⋯</span>
                    More
                </button>
            </nav>
        </>
    );
}
