'use client';

import Link from 'next/link';

const ITEMS = [
    // Ops
    { href: '/admin',             label: 'Overview',        icon: '📊', group: 'Operations' },
    { href: '/admin/owners',      label: 'Owners',          icon: '🏠', group: 'Operations' },
    { href: '/admin/templates',   label: 'Task Templates',  icon: '📝', group: 'Operations' },
    { href: '/admin/feedback',    label: 'Guest Feedback',  icon: '⭐', group: 'Operations' },
    { href: '/admin/conflicts',   label: 'Conflicts',       icon: '⚠',  group: 'Operations' },
    { href: '/admin/bulk',        label: 'Bulk Ops',        icon: '⚡', group: 'Operations' },
    // Finance
    { href: '/admin/pricing',     label: 'Rate Cards',      icon: '💰', group: 'Finance' },
    { href: '/admin/currencies',  label: 'Exchange Rates',  icon: '💱', group: 'Finance' },
    { href: '/admin/portfolio',   label: 'Portfolio',       icon: '🏢', group: 'Finance' },
    // Integration
    { href: '/admin/integrations',label: 'OTA Channels',    icon: '🔗', group: 'Integrations' },
    { href: '/admin/webhooks',    label: 'Webhook Log',     icon: '📡', group: 'Integrations' },
    { href: '/admin/notifications',label:'Notifications',   icon: '🔔', group: 'Integrations' },
    // System
    { href: '/admin/jobs',        label: 'Scheduled Jobs',  icon: '⏰', group: 'System' },
    { href: '/admin/health',      label: 'System Health',   icon: '💚', group: 'System' },
    { href: '/admin/audit',       label: 'Audit Trail',     icon: '📋', group: 'System' },
    { href: '/admin/settings',    label: 'Settings',        icon: '⚙', group: 'System' },
];

export default function MoreOptionsPage() {
    const groups = Array.from(new Set(ITEMS.map(i => i.group)));

    return (
        <div style={{ maxWidth: 800, paddingBottom: 'var(--space-8)' }}>
            <h1 style={{
                fontSize: 'var(--text-2xl)',
                fontWeight: 700,
                color: 'var(--color-midnight)',
                marginBottom: 'var(--space-2)',
            }}>More Admin Options</h1>
            <p style={{
                fontSize: 'var(--text-sm)',
                color: 'var(--color-text-dim)',
                marginBottom: 'var(--space-6)',
            }}>Additional operational, financial, and system settings.</p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
                {groups.map(group => (
                    <div key={group}>
                        <h2 style={{
                            fontSize: 'var(--text-xs)',
                            fontWeight: 600,
                            textTransform: 'uppercase',
                            letterSpacing: '0.05em',
                            color: 'var(--color-text-faint)',
                            marginBottom: 'var(--space-3)',
                            paddingBottom: 'var(--space-2)',
                            borderBottom: '1px solid var(--color-border)'
                        }}>{group}</h2>
                        <div style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                            gap: 'var(--space-3)'
                        }}>
                            {ITEMS.filter(i => i.group === group).map(item => (
                                <Link
                                    key={item.href}
                                    href={item.href}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 'var(--space-3)',
                                        padding: 'var(--space-4)',
                                        background: 'var(--color-surface)',
                                        border: '1px solid var(--color-border)',
                                        borderRadius: 'var(--radius-md)',
                                        textDecoration: 'none',
                                        transition: 'all var(--transition-fast)',
                                        color: 'var(--color-text)'
                                    }}
                                    className="hover-card"
                                >
                                    <span style={{ fontSize: '1.2em' }}>{item.icon}</span>
                                    <span style={{ fontSize: 'var(--text-sm)', fontWeight: 500 }}>{item.label}</span>
                                </Link>
                            ))}
                        </div>
                    </div>
                ))}
            </div>

            <style>{`
                .hover-card:hover {
                    border-color: var(--color-primary);
                    background: var(--color-surface-2);
                    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
                }
            `}</style>
        </div>
    );
}
