/**
 * Phase 551 — Loading Skeleton Component
 *
 * Provides shimmer skeletons for loading states.
 * Usage:
 *   <Skeleton variant="line" />
 *   <Skeleton variant="card" />
 *   <Skeleton variant="table" rows={5} />
 */

import { CSSProperties } from 'react';

interface SkeletonProps {
    variant?: 'line' | 'card' | 'circle' | 'table';
    width?: string | number;
    height?: string | number;
    rows?: number;
    style?: CSSProperties;
}

const shimmerStyle: CSSProperties = {
    background: 'linear-gradient(90deg, var(--color-surface-2) 25%, var(--color-surface-3, #2a2f3d) 50%, var(--color-surface-2) 75%)',
    backgroundSize: '200% 100%',
    animation: 'shimmer 1.5s ease-in-out infinite',
    borderRadius: 'var(--radius-md)',
};

function SkeletonLine({ width = '100%', height = 14, style }: { width?: string | number; height?: string | number; style?: CSSProperties }) {
    return <div style={{ ...shimmerStyle, width, height, ...style }} />;
}

export default function Skeleton({ variant = 'line', width, height, rows = 3, style }: SkeletonProps) {
    if (variant === 'circle') {
        const size = width || height || 40;
        return <div style={{ ...shimmerStyle, width: size, height: size, borderRadius: '50%', ...style }} />;
    }

    if (variant === 'card') {
        return (
            <div style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)',
                padding: 'var(--space-6)',
                ...style,
            }}>
                <SkeletonLine width="40%" height={12} style={{ marginBottom: 16 }} />
                <SkeletonLine width="100%" height={28} style={{ marginBottom: 12 }} />
                <SkeletonLine width="70%" height={12} />
            </div>
        );
    }

    if (variant === 'table') {
        return (
            <div style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)',
                overflow: 'hidden',
                ...style,
            }}>
                {/* Header */}
                <div style={{ display: 'flex', gap: 16, padding: '12px 16px', borderBottom: '1px solid var(--color-border)' }}>
                    <SkeletonLine width="20%" height={10} />
                    <SkeletonLine width="25%" height={10} />
                    <SkeletonLine width="20%" height={10} />
                    <SkeletonLine width="35%" height={10} />
                </div>
                {Array.from({ length: rows }).map((_, i) => (
                    <div key={i} style={{ display: 'flex', gap: 16, padding: '10px 16px', borderBottom: '1px solid var(--color-border)' }}>
                        <SkeletonLine width="20%" height={12} />
                        <SkeletonLine width="25%" height={12} />
                        <SkeletonLine width="20%" height={12} />
                        <SkeletonLine width="35%" height={12} />
                    </div>
                ))}
            </div>
        );
    }

    // Default: single or multiple lines
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: width || '100%', ...style }}>
            {Array.from({ length: rows }).map((_, i) => (
                <SkeletonLine key={i} width={i === rows - 1 ? '60%' : '100%'} height={height || 14} />
            ))}
        </div>
    );
}

// CSS for shimmer — inject once
export function SkeletonStyles() {
    return <style>{`@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>;
}
