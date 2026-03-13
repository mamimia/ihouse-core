/**
 * Phase 540 — Custom Not Found Page
 */
import Link from 'next/link';

export default function NotFound() {
    return (
        <div style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexDirection: 'column',
            gap: 16,
            padding: 24,
            textAlign: 'center',
            background: 'var(--color-bg, #0a0f1c)',
        }}>
            <div style={{ fontSize: 64, marginBottom: 8 }}>🔍</div>
            <h1 style={{
                fontSize: 28,
                fontWeight: 800,
                color: 'var(--color-text, #f9fafb)',
                margin: 0,
                letterSpacing: '-0.03em',
            }}>
                Page Not Found
            </h1>
            <p style={{
                fontSize: 15,
                color: 'var(--color-text-dim, #6b7280)',
                maxWidth: 380,
                lineHeight: 1.5,
            }}>
                The page you're looking for doesn't exist or has been moved.
            </p>
            <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
                <Link href="/dashboard" style={{
                    background: 'var(--color-primary, #3b82f6)',
                    color: '#fff',
                    border: 'none',
                    borderRadius: 12,
                    padding: '10px 24px',
                    fontSize: 14,
                    fontWeight: 600,
                    textDecoration: 'none',
                }}>
                    Go to Dashboard
                </Link>
                <Link href="/admin" style={{
                    background: 'transparent',
                    color: 'var(--color-text-dim, #6b7280)',
                    border: '1px solid var(--color-border, #374151)',
                    borderRadius: 12,
                    padding: '10px 24px',
                    fontSize: 14,
                    fontWeight: 600,
                    textDecoration: 'none',
                }}>
                    Admin Panel
                </Link>
            </div>
            <div style={{ fontSize: 12, color: 'var(--color-text-faint, #374151)', marginTop: 24 }}>
                Domaniqo · Phase 540
            </div>
        </div>
    );
}
