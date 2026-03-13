'use client';

/**
 * Phase 525 — Admin Sub-Navigation
 * 
 * Categorized navigation for all admin sub-pages.
 * Mounted in admin layout so every /admin/* page is discoverable.
 */

import { usePathname } from 'next/navigation';
import Link from 'next/link';

interface NavGroup {
    label: string;
    items: { href: string; label: string; icon: string }[];
}

const GROUPS: NavGroup[] = [
    {
        label: 'Operations',
        items: [
            { href: '/admin', label: 'Overview', icon: '📊' },
            { href: '/admin/staff', label: 'Staff Performance', icon: '👥' },
            { href: '/admin/templates', label: 'Task Templates', icon: '📝' },
            { href: '/admin/feedback', label: 'Guest Feedback', icon: '⭐' },
            { href: '/admin/conflicts', label: 'Conflicts', icon: '⚠' },
            { href: '/admin/bulk', label: 'Bulk Operations', icon: '⚡' },
        ],
    },
    {
        label: 'Financial',
        items: [
            { href: '/admin/pricing', label: 'Rate Cards', icon: '💰' },
            { href: '/admin/currencies', label: 'Exchange Rates', icon: '💱' },
            { href: '/admin/portfolio', label: 'Portfolio', icon: '🏢' },
        ],
    },
    {
        label: 'Integration',
        items: [
            { href: '/admin/integrations', label: 'OTA Channels', icon: '🔗' },
            { href: '/admin/webhooks', label: 'Webhook Log', icon: '📡' },
            { href: '/admin/notifications', label: 'Notifications', icon: '🔔' },
        ],
    },
    {
        label: 'System',
        items: [
            { href: '/admin/jobs', label: 'Scheduled Jobs', icon: '⏰' },
            { href: '/admin/health', label: 'System Health', icon: '💚' },
            { href: '/admin/audit', label: 'Audit Trail', icon: '📋' },
            { href: '/admin/properties', label: 'Properties', icon: '🏠' },
        ],
    },
];

export default function AdminNav() {
    const pathname = usePathname();

    const isActive = (href: string) =>
        href === '/admin' ? pathname === '/admin' : pathname?.startsWith(href);

    return (
        <nav style={{
            display: 'flex',
            gap: 'var(--space-6)',
            padding: 'var(--space-4) 0 var(--space-6)',
            borderBottom: '1px solid var(--color-border)',
            marginBottom: 'var(--space-6)',
            overflowX: 'auto',
            flexWrap: 'wrap',
        }}>
            {GROUPS.map(group => (
                <div key={group.label} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                    <span style={{
                        fontSize: 'var(--text-xs)',
                        color: 'var(--color-text-faint)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.08em',
                        fontWeight: 600,
                        paddingBottom: 'var(--space-1)',
                    }}>
                        {group.label}
                    </span>
                    <div style={{ display: 'flex', gap: 'var(--space-1)', flexWrap: 'wrap' }}>
                        {group.items.map(item => {
                            const active = isActive(item.href);
                            return (
                                <Link
                                    key={item.href}
                                    href={item.href}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 'var(--space-1)',
                                        padding: '4px 10px',
                                        borderRadius: 'var(--radius-md)',
                                        fontSize: 'var(--text-xs)',
                                        fontWeight: active ? 600 : 400,
                                        color: active ? 'var(--color-primary)' : 'var(--color-text-dim)',
                                        background: active ? 'var(--color-primary-faint, rgba(59,130,246,0.08))' : 'transparent',
                                        textDecoration: 'none',
                                        transition: 'all var(--transition-fast)',
                                        whiteSpace: 'nowrap',
                                    }}
                                >
                                    <span style={{ fontSize: '0.85em' }}>{item.icon}</span>
                                    {item.label}
                                </Link>
                            );
                        })}
                    </div>
                </div>
            ))}
        </nav>
    );
}
