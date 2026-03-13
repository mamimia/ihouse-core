'use client';

/**
 * Phase 540 — Global Error Page
 */

export default function GlobalError({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
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
            background: '#0a0f1c',
        }}>
            <div style={{ fontSize: 64, marginBottom: 8 }}>⚠️</div>
            <h1 style={{
                fontSize: 24,
                fontWeight: 800,
                color: '#f9fafb',
                margin: 0,
            }}>
                Something went wrong
            </h1>
            <p style={{
                fontSize: 14,
                color: '#6b7280',
                maxWidth: 380,
                lineHeight: 1.5,
            }}>
                An unexpected error occurred. You can try again or navigate back to the dashboard.
            </p>
            {error?.message && (
                <code style={{
                    fontSize: 12,
                    color: '#ef4444',
                    background: 'rgba(239,68,68,0.08)',
                    padding: '8px 16px',
                    borderRadius: 8,
                    maxWidth: 400,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                }}>
                    {error.message}
                </code>
            )}
            <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
                <button onClick={reset} style={{
                    background: '#3b82f6',
                    color: '#fff',
                    border: 'none',
                    borderRadius: 12,
                    padding: '10px 24px',
                    fontSize: 14,
                    fontWeight: 600,
                    cursor: 'pointer',
                }}>
                    Try Again
                </button>
                <a href="/dashboard" style={{
                    background: 'transparent',
                    color: '#6b7280',
                    border: '1px solid #374151',
                    borderRadius: 12,
                    padding: '10px 24px',
                    fontSize: 14,
                    fontWeight: 600,
                    textDecoration: 'none',
                }}>
                    Dashboard
                </a>
            </div>
        </div>
    );
}
