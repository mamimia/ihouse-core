'use client';

/**
 * Phase 525 — Admin Sub-Navigation
 * Phase 840 — Refactored: removed sidebar duplicates (Properties, Manage Staff),
 *             converted to compact flat pill row, removed verbose group headers.
 *
 * Design rule: AdminNav shows ONLY items that are NOT already in the main sidebar.
 * Sidebar handles: Dashboard, Tasks, Bookings, Calendar, Financial, Owner,
 *                  Manager, Guests, Properties, Manage Staff, Admin.
 */

import { usePathname } from 'next/navigation';
import Link from 'next/link';

interface NavItem {
    href: string;
    label: string;
    icon: string;
    group: 'ops' | 'finance' | 'integration' | 'system';
}

const ITEMS: NavItem[] = [
    // Ops — admin-only tools not in main sidebar
    { href: '/admin',             label: 'Overview',        icon: '📊', group: 'ops' },
    { href: '/admin/intake',      label: 'Intake Queue',    icon: '📥', group: 'ops' },
    { href: '/admin/owners',      label: 'Owners',          icon: '🏠', group: 'ops' },
    { href: '/admin/templates',   label: 'Task Templates',  icon: '📝', group: 'ops' },
    { href: '/admin/feedback',    label: 'Guest Feedback',  icon: '⭐', group: 'ops' },
    { href: '/admin/conflicts',   label: 'Conflicts',       icon: '⚠',  group: 'ops' },
    { href: '/admin/bulk',        label: 'Bulk Ops',        icon: '⚡', group: 'ops' },
    // Finance
    { href: '/admin/pricing',     label: 'Rate Cards',      icon: '💰', group: 'finance' },
    { href: '/admin/currencies',  label: 'Exchange Rates',  icon: '💱', group: 'finance' },
    { href: '/admin/portfolio',   label: 'Portfolio',       icon: '🏢', group: 'finance' },
    // Integration
    { href: '/admin/integrations',label: 'OTA Channels',    icon: '🔗', group: 'integration' },
    { href: '/admin/webhooks',    label: 'Webhook Log',     icon: '📡', group: 'integration' },
    { href: '/admin/notifications',label:'Notifications',   icon: '🔔', group: 'integration' },
    // System
    { href: '/admin/jobs',        label: 'Scheduled Jobs',  icon: '⏰', group: 'system' },
    { href: '/admin/health',      label: 'System Health',   icon: '💚', group: 'system' },
    { href: '/admin/audit',       label: 'Audit Trail',     icon: '📋', group: 'system' },
    { href: '/admin/settings',    label: 'Settings',        icon: '⚙', group: 'system' },
    { href: '/admin/profile',     label: 'My Profile',      icon: '👤', group: 'system' },
];

const GROUP_SEPARATOR: Array<NavItem['group']> = ['finance', 'integration', 'system'];

export default function AdminNav() {
    const pathname = usePathname();

    const isActive = (href: string) =>
        href === '/admin' ? pathname === '/admin' : pathname?.startsWith(href);

    let prevGroup: NavItem['group'] | null = null;

    return (
        <nav style={{
            display: 'flex',
            alignItems: 'center',
            gap: 2,
            padding: 'var(--space-3) 0 var(--space-5)',
            borderBottom: '1px solid var(--color-border)',
            marginBottom: 'var(--space-6)',
            overflowX: 'auto',
            flexWrap: 'wrap',
            rowGap: 'var(--space-1)',
        }}>
            {ITEMS.map(item => {
                const active = isActive(item.href);
                const showSep = GROUP_SEPARATOR.includes(item.group) && prevGroup !== item.group;
                prevGroup = item.group;

                return (
                    <div key={item.href} style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        {showSep && (
                            <span style={{
                                width: 1,
                                height: 16,
                                background: 'var(--color-border)',
                                margin: '0 6px',
                                flexShrink: 0,
                            }} />
                        )}
                        <Link
                            href={item.href}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 4,
                                padding: '4px 10px',
                                borderRadius: 'var(--radius-md)',
                                fontSize: 'var(--text-xs)',
                                fontWeight: active ? 600 : 400,
                                color: active ? 'var(--color-primary)' : 'var(--color-text-dim)',
                                background: active
                                    ? 'var(--color-primary-faint, rgba(59,130,246,0.08))'
                                    : 'transparent',
                                border: active
                                    ? '1px solid rgba(59,130,246,0.2)'
                                    : '1px solid transparent',
                                textDecoration: 'none',
                                transition: 'all var(--transition-fast)',
                                whiteSpace: 'nowrap',
                            }}
                        >
                            <span style={{ fontSize: '0.85em' }}>{item.icon}</span>
                            {item.label}
                        </Link>
                    </div>
                );
            })}
        </nav>
    );
}
