'use client';

/**
 * Phase 376 — BottomNav Component
 *
 * Generalized bottom navigation for mobile surfaces.
 * Extracted from /worker page pattern, using Domaniqo design tokens.
 * Supports role-based tab configuration.
 * RTL-aware, i18n-ready, safe-area-inset-bottom.
 */

import { usePathname } from 'next/navigation';
import Link from 'next/link';

export interface BottomNavItem {
    href: string;
    label: string;
    icon: string;
    badge?: number;
}

const DEFAULT_ITEMS: BottomNavItem[] = [
    { href: '/dashboard', label: 'Home',     icon: '▪' },
    { href: '/tasks',     label: 'Tasks',    icon: '✓' },
    { href: '/bookings',  label: 'Bookings', icon: '📅' },
    { href: '/financial', label: 'Finance',  icon: '₿' },
    { href: '/admin',     label: 'More',     icon: '⚙' },
];

/**
 * Phase 864 — Canonical staff bottom nav for all worker-facing ops surfaces.
 * Used by: /ops/cleaner, /ops/maintenance, /ops/checkin, /ops/checkout
 */
export const STAFF_BOTTOM_NAV: BottomNavItem[] = [
    { href: '/dashboard',       label: 'Home',     icon: '🏠' },
    { href: '/tasks',           label: 'Tasks',    icon: '✓' },
    { href: '/ops/cleaner',     label: 'Cleaning', icon: '🧹' },
    { href: '/ops/maintenance', label: 'Maint.',   icon: '🔧' },
    { href: '/worker',          label: 'More',     icon: '⚙' },
];

interface BottomNavProps {
    items?: BottomNavItem[];
}

export default function BottomNav({ items = DEFAULT_ITEMS }: BottomNavProps) {
    const pathname = usePathname();

    return (
        <nav
            id="mobile-bottom-nav"
            style={{
                position: 'fixed',
                bottom: 0,
                insetInline: 0,
                background: 'var(--color-surface, #fff)',
                borderTop: '1px solid var(--color-border, #DDD8D0)',
                display: 'flex',
                paddingBottom: 'env(safe-area-inset-bottom, 8px)',
                paddingTop: 6,
                zIndex: 50,
            }}
        >
            {items.map(item => {
                const isActive = pathname === item.href || pathname?.startsWith(item.href + '/');
                return (
                    <Link
                        key={item.href}
                        href={item.href}
                        id={`bnav-${item.href.replace(/\//g, '-').slice(1)}`}
                        style={{
                            flex: 1,
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            gap: 2,
                            textDecoration: 'none',
                            color: isActive
                                ? 'var(--color-primary, #334036)'
                                : 'var(--color-text-faint, #9A958E)',
                            transition: 'color var(--transition-fast, 120ms)',
                            position: 'relative',
                            padding: '4px 0',
                            minHeight: 44,
                            justifyContent: 'center',
                        }}
                    >
                        <span style={{ fontSize: 20, lineHeight: 1 }}>{item.icon}</span>
                        <span style={{
                            fontSize: 10,
                            fontWeight: isActive ? 600 : 400,
                            fontFamily: 'var(--font-sans, Inter, sans-serif)',
                            letterSpacing: '0.02em',
                        }}>
                            {item.label}
                        </span>
                        {item.badge != null && item.badge > 0 && (
                            <span style={{
                                position: 'absolute',
                                top: 2,
                                insetInlineEnd: '50%',
                                transform: 'translateX(18px)',
                                background: 'var(--color-danger, #9B3A3A)',
                                color: '#fff',
                                borderRadius: 99,
                                fontSize: 9,
                                fontWeight: 700,
                                padding: '1px 5px',
                                minWidth: 14,
                                textAlign: 'center',
                            }}>
                                {item.badge}
                            </span>
                        )}
                    </Link>
                );
            })}
        </nav>
    );
}
