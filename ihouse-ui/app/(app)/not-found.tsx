/**
 * Phase 566 — Not Found page for (app) routes
 */

import Link from 'next/link';

export default function NotFound() {
    return (
        <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '60vh',
            gap: 'var(--space-4)',
            padding: 'var(--space-8)',
            textAlign: 'center',
        }}>
            <div style={{ fontSize: 64, marginBottom: 'var(--space-2)' }}>404</div>
            <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--color-text)' }}>
                Page Not Found
            </h2>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', maxWidth: 400 }}>
                The page you&apos;re looking for doesn&apos;t exist or has been moved.
            </p>
            <Link href="/dashboard" style={{
                marginTop: 'var(--space-4)',
                background: 'var(--color-primary)',
                color: '#fff',
                borderRadius: 'var(--radius-md)',
                padding: 'var(--space-3) var(--space-6)',
                fontSize: 'var(--text-sm)',
                fontWeight: 600,
                textDecoration: 'none',
            }}>
                Back to Dashboard
            </Link>
        </div>
    );
}
