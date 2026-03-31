'use client';

/**
 * Phase 1033 Step 3 — OMSidebar
 *
 * Dedicated sidebar for the Operational Manager shell.
 * Replaces the shared admin Sidebar for manager role contexts.
 *
 * Product truth:
 *  - Cockpit-first: Hub → Alerts → Stream → Team
 *  - Supporting layers beneath: Bookings → Tasks
 *  - No admin surfaces (Financial, Properties, Guests, Manage Staff)
 *  - Mode-aware footer: End Session (Act As) | Close Preview (Preview As) | nothing (future direct login)
 *
 * Modes:
 *  - Preview As: read-only banner shown by PreviewContext; nav is functional (read-only enforced per-page)
 *  - Act As:     acting banner shown by ActAsContext; End Session button in footer
 */

import React, { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { getTabToken } from '../lib/tokenStore';

// ---------------------------------------------------------------------------
// Mode detection helpers
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

function getDisplayName(): string {
    if (typeof window === 'undefined') return 'Ops Manager';
    try {
        const token = getTabToken();
        if (!token) return 'Ops Manager';
        const payload = JSON.parse(atob(token.split('.')[1] || '{}'));
        return payload.display_name || payload.email?.split('@')[0] || 'Ops Manager';
    } catch { return 'Ops Manager'; }
}

// ---------------------------------------------------------------------------
// Nav item definitions — canonical OM structure
// ---------------------------------------------------------------------------

type NavItem = {
    label: string;
    href: string;
    icon: string;
    section: 'primary' | 'supporting';
};

const OM_NAV: NavItem[] = [
    // Primary — cockpit-first
    { label: 'Hub',      href: '/manager',          icon: '⚡', section: 'primary' },
    { label: 'Alerts',   href: '/manager/alerts',   icon: '🔴', section: 'primary' },
    { label: 'Stream',   href: '/manager/stream',   icon: '📡', section: 'primary' },
    { label: 'Team',     href: '/manager/team',     icon: '👥', section: 'primary' },
    // Supporting — intervention layers
    { label: 'Bookings', href: '/manager/bookings', icon: '📋', section: 'supporting' },
    { label: 'Tasks',    href: '/manager/tasks',    icon: '⚡', section: 'supporting' },
];

// Routes that exist as real pages in this phase (others are coming in later steps)
const LIVE_ROUTES = new Set(['/manager']);

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface OMSidebarProps {
    collapsed?: boolean; // tablet compact-rail mode
    mode?: 'drawer'; // mobile drawer mode
    onClose?: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function OMSidebar({ collapsed = false, mode, onClose }: OMSidebarProps) {
    const pathname = usePathname() || '';
    const router = useRouter();
    const [omMode, setOMMode] = useState<OMMode>('direct');
    const [displayName, setDisplayName] = useState('Ops Manager');

    useEffect(() => {
        setOMMode(getOMMode());
        setDisplayName(getDisplayName());
    }, []);

    const isActive = (href: string) => {
        if (href === '/manager') return pathname === '/manager';
        return pathname.startsWith(href);
    };

    const handleNav = (href: string) => {
        if (mode === 'drawer' && onClose) onClose();
        // If route not yet live, stay on Hub
        if (!LIVE_ROUTES.has(href)) {
            router.push('/manager');
            return;
        }
        router.push(href);
    };

    const handleEndSession = () => {
        if (omMode === 'preview') {
            // Clear preview role and redirect
            sessionStorage.removeItem('ihouse_preview_role');
            window.close();
        } else if (omMode === 'acting') {
            // Trigger act-as end — navigate to act-as end route
            window.location.href = '/login';
        }
    };

    // ── Styles ───────────────────────────────────────────────────────────────

    const sidebarStyle: React.CSSProperties = {
        width: collapsed ? 64 : 220,
        minHeight: '100vh',
        background: 'var(--color-surface)',
        borderRight: '1px solid var(--color-border)',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        overflow: 'hidden',
        transition: 'width 220ms ease',
        position: 'fixed',
        top: 0,
        insetInlineStart: 0,
        zIndex: 30,
    };

    const headerStyle: React.CSSProperties = {
        padding: collapsed ? '20px 0' : '20px 16px 16px',
        borderBottom: '1px solid var(--color-border)',
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        alignItems: collapsed ? 'center' : 'flex-start',
    };

    const logoStyle: React.CSSProperties = {
        fontSize: collapsed ? 22 : 16,
        fontWeight: 700,
        color: 'var(--color-text)',
        letterSpacing: '-0.03em',
        lineHeight: 1.1,
    };

    const roleTagStyle: React.CSSProperties = {
        fontSize: 10,
        fontWeight: 600,
        color: 'var(--color-text-dim)',
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        marginTop: 4,
    };

    const navStyle: React.CSSProperties = {
        flex: 1,
        padding: '12px 0',
        overflowY: 'auto',
    };

    const sectionLabelStyle: React.CSSProperties = {
        fontSize: 9,
        fontWeight: 700,
        color: 'var(--color-text-faint)',
        textTransform: 'uppercase',
        letterSpacing: '0.1em',
        padding: collapsed ? '12px 0 4px' : '12px 16px 4px',
        textAlign: collapsed ? 'center' : 'left',
    };

    const dividerStyle: React.CSSProperties = {
        height: 1,
        background: 'var(--color-border)',
        margin: '8px 12px',
    };

    const footerStyle: React.CSSProperties = {
        padding: collapsed ? '12px 0' : '12px 16px',
        borderTop: '1px solid var(--color-border)',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        alignItems: collapsed ? 'center' : 'stretch',
    };

    const modeBadgeStyle: React.CSSProperties = {
        fontSize: 10,
        fontWeight: 700,
        padding: '2px 10px',
        borderRadius: 'var(--radius-full)',
        letterSpacing: '0.06em',
        textAlign: 'center',
        background: omMode === 'preview' ? 'rgba(234,179,8,0.15)' : 'rgba(239,68,68,0.15)',
        color: omMode === 'preview' ? '#ca8a04' : '#ef4444',
        border: `1px solid ${omMode === 'preview' ? 'rgba(234,179,8,0.3)' : 'rgba(239,68,68,0.3)'}`,
    };

    const endBtnStyle: React.CSSProperties = {
        background: 'transparent',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)',
        padding: collapsed ? '6px 0' : '6px 12px',
        fontSize: 11,
        fontWeight: 600,
        color: 'var(--color-text-dim)',
        cursor: 'pointer',
        textAlign: 'center',
        transition: 'all 150ms ease',
        width: collapsed ? 40 : '100%',
    };

    const renderNavItem = (item: NavItem) => {
        const active = isActive(item.href);
        const live = LIVE_ROUTES.has(item.href);

        const itemStyle: React.CSSProperties = {
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: collapsed ? '9px 0' : '9px 16px',
            cursor: 'pointer',
            borderRadius: collapsed ? 0 : 'var(--radius-md)',
            margin: collapsed ? '1px 0' : '1px 8px',
            background: active
                ? 'var(--color-primary)15'
                : 'transparent',
            color: active
                ? 'var(--color-primary)'
                : live ? 'var(--color-text)' : 'var(--color-text-faint)',
            fontWeight: active ? 700 : 500,
            fontSize: 13,
            transition: 'background 120ms ease, color 120ms ease',
            position: 'relative',
            justifyContent: collapsed ? 'center' : 'flex-start',
            opacity: live ? 1 : 0.55,
        };

        const activePip: React.CSSProperties = {
            position: 'absolute',
            insetInlineStart: collapsed ? 0 : -8,
            top: '50%',
            transform: 'translateY(-50%)',
            width: 3,
            height: 18,
            borderRadius: '0 2px 2px 0',
            background: 'var(--color-primary)',
        };

        return (
            <div
                key={item.href}
                style={itemStyle}
                onClick={() => handleNav(item.href)}
                title={collapsed ? `${item.label}${!live ? ' (coming soon)' : ''}` : undefined}
            >
                {active && <div style={activePip} />}
                <span style={{ fontSize: 14, flexShrink: 0 }}>{item.icon}</span>
                {!collapsed && (
                    <span style={{ flex: 1 }}>
                        {item.label}
                        {!live && (
                            <span style={{ fontSize: 9, marginInlineStart: 6, color: 'var(--color-text-faint)', fontWeight: 400 }}>
                                soon
                            </span>
                        )}
                    </span>
                )}
            </div>
        );
    };

    const primaryItems = OM_NAV.filter(i => i.section === 'primary');
    const supportingItems = OM_NAV.filter(i => i.section === 'supporting');

    return (
        <aside style={sidebarStyle} aria-label="Operational Manager navigation">
            {/* Header */}
            <div style={headerStyle}>
                {!collapsed ? (
                    <>
                        <div style={logoStyle}>Domaniqo</div>
                        <div style={roleTagStyle}>Operations Platform</div>
                        <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginTop: 8, fontWeight: 500 }}>
                            {displayName}
                        </div>
                    </>
                ) : (
                    <div style={{ fontSize: 22, fontWeight: 800 }}>D</div>
                )}
            </div>

            {/* Nav */}
            <nav style={navStyle}>
                {!collapsed && (
                    <div style={sectionLabelStyle}>Cockpit</div>
                )}
                {primaryItems.map(renderNavItem)}

                <div style={dividerStyle} />

                {!collapsed && (
                    <div style={sectionLabelStyle}>Operations</div>
                )}
                {supportingItems.map(renderNavItem)}
            </nav>

            {/* Footer — mode-aware */}
            <div style={footerStyle}>
                {omMode !== 'direct' && (
                    <>
                        {!collapsed && (
                            <div style={modeBadgeStyle}>
                                {omMode === 'preview' ? '👁 PREVIEW MODE' : '🔴 ACTING AS'}
                            </div>
                        )}
                        <button
                            style={endBtnStyle}
                            onClick={handleEndSession}
                            title={omMode === 'preview' ? 'Close Preview' : 'End Session'}
                            onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--color-text-dim)')}
                            onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}
                        >
                            {collapsed
                                ? (omMode === 'preview' ? '✕' : '↩')
                                : (omMode === 'preview' ? 'Close Preview' : 'End Session')
                            }
                        </button>
                    </>
                )}
            </div>
        </aside>
    );
}
