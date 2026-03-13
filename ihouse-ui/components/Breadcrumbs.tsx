'use client';

/**
 * Phase 552 — Breadcrumb Navigation
 *
 * Auto-generates breadcrumbs from current pathname.
 * Usage: <Breadcrumbs /> — place in app layout.
 */

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const LABEL_MAP: Record<string, string> = {
    admin: 'Admin',
    ops: 'Operations',
    guests: 'Guests',
    bookings: 'Bookings',
    financial: 'Financial',
    calendar: 'Calendar',
    dashboard: 'Dashboard',
    settings: 'Settings',
    tasks: 'Tasks',
    worker: 'Worker',
    maintenance: 'Maintenance',
    owner: 'Owner',
    manager: 'Manager',
    health: 'System Health',
    audit: 'Audit Trail',
    notifications: 'Notifications',
    jobs: 'Scheduled Jobs',
    feedback: 'Feedback',
    conflicts: 'Conflicts',
    dlq: 'Dead Letter Queue',
    sync: 'Sync Status',
    integrations: 'Integrations',
    properties: 'Properties',
    staff: 'Staff',
    templates: 'Templates',
    currencies: 'Currencies',
    pricing: 'Pricing',
    portfolio: 'Portfolio',
    webhooks: 'Webhooks',
    bulk: 'Bulk Operations',
    messages: 'Messages',
    checkin: 'Check-In',
    checkout: 'Check-Out',
    statements: 'Statements',
};

function humanize(segment: string): string {
    return LABEL_MAP[segment] || segment.replace(/[-_]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export default function Breadcrumbs() {
    const pathname = usePathname();
    if (!pathname || pathname === '/dashboard') return null;

    const segments = pathname.split('/').filter(Boolean);
    if (segments.length <= 1) return null;

    // Skip dynamic segments like [id], [token]
    const crumbs = segments
        .filter(s => !s.startsWith('['))
        .map((seg, idx, arr) => ({
            label: humanize(seg),
            href: '/' + arr.slice(0, idx + 1).join('/'),
            isLast: idx === arr.length - 1,
        }));

    return (
        <nav aria-label="Breadcrumb" style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-faint)',
            marginBottom: 'var(--space-4)',
        }}>
            <Link href="/dashboard" style={{ color: 'var(--color-text-dim)', textDecoration: 'none' }}>Home</Link>
            {crumbs.map(c => (
                <span key={c.href} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ opacity: 0.4 }}>›</span>
                    {c.isLast ? (
                        <span style={{ color: 'var(--color-text)', fontWeight: 500 }}>{c.label}</span>
                    ) : (
                        <Link href={c.href} style={{ color: 'var(--color-text-dim)', textDecoration: 'none' }}>{c.label}</Link>
                    )}
                </span>
            ))}
        </nav>
    );
}
