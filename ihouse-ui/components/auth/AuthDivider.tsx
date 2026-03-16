'use client';

/**
 * AuthDivider — "— OR —" horizontal line divider for auth screens.
 */

export default function AuthDivider({ text = 'OR' }: { text?: string }) {
    return (
        <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            margin: 'var(--space-4, 16px) 0',
        }}>
            <div style={{ flex: 1, height: 1, background: 'rgba(234,229,222,0.08)' }} />
            <span style={{
                fontSize: 'var(--text-xs, 12px)',
                color: 'rgba(234,229,222,0.25)',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                fontWeight: 600,
            }}>
                {text}
            </span>
            <div style={{ flex: 1, height: 1, background: 'rgba(234,229,222,0.08)' }} />
        </div>
    );
}
