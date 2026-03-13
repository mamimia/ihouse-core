'use client';

/**
 * Phase 566 — Next.js App Router Error Boundary
 *
 * Catches rendering errors in (app) routes and shows
 * a recovery UI with retry button.
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
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '60vh',
            gap: 'var(--space-4)',
            padding: 'var(--space-8)',
            textAlign: 'center',
        }}>
            <div style={{ fontSize: 48, marginBottom: 'var(--space-2)' }}>⚠️</div>
            <h2 style={{
                fontSize: 'var(--text-xl)',
                fontWeight: 700,
                color: 'var(--color-text)',
                letterSpacing: '-0.02em',
            }}>
                Something went wrong
            </h2>
            <p style={{
                fontSize: 'var(--text-sm)',
                color: 'var(--color-text-dim)',
                maxWidth: 420,
            }}>
                {error?.message || 'An unexpected error occurred. Please try again.'}
            </p>
            {error?.digest && (
                <code style={{
                    fontSize: 'var(--text-xs)',
                    color: 'var(--color-text-faint)',
                    fontFamily: 'var(--font-mono)',
                    background: 'var(--color-surface-2)',
                    padding: '4px 12px',
                    borderRadius: 'var(--radius-md)',
                }}>
                    Error ID: {error.digest}
                </code>
            )}
            <button
                onClick={reset}
                style={{
                    marginTop: 'var(--space-4)',
                    background: 'var(--color-primary)',
                    color: '#fff',
                    border: 'none',
                    borderRadius: 'var(--radius-md)',
                    padding: 'var(--space-3) var(--space-6)',
                    fontSize: 'var(--text-sm)',
                    fontWeight: 600,
                    cursor: 'pointer',
                }}
            >
                Try Again
            </button>
        </div>
    );
}
