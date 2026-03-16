'use client';

/**
 * ProgressBar — Step indicator for multi-step auth flows (registration).
 */

interface ProgressBarProps {
    current: number;
    total: number;
}

export default function ProgressBar({ current, total }: ProgressBarProps) {
    return (
        <div style={{ marginBottom: 'var(--space-5, 20px)' }}>
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: 8,
            }}>
                <span style={{
                    fontSize: 'var(--text-xs, 12px)',
                    color: 'rgba(234,229,222,0.3)',
                }}>
                    Step {current} of {total}
                </span>
            </div>
            <div style={{
                height: 3,
                background: 'rgba(234,229,222,0.06)',
                borderRadius: 99,
                overflow: 'hidden',
            }}>
                <div style={{
                    height: '100%',
                    width: `${(current / total) * 100}%`,
                    background: 'var(--color-copper, #B56E45)',
                    borderRadius: 99,
                    transition: 'width 0.4s ease',
                }} />
            </div>
        </div>
    );
}
