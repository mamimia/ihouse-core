'use client';

/**
 * Phase 581 — Loading State Standardization
 *
 * PageLoader component that wraps page-level loading states
 * with the Skeleton component for consistent UX.
 *
 * Usage:
 *   <PageLoader loading={loading} variant="table" rows={5}>
 *     <YourContent />
 *   </PageLoader>
 */

import React, { ReactNode } from 'react';

// ---------------------------------------------------------------------------
// Skeleton Presets for common page layouts
// ---------------------------------------------------------------------------

function SkeletonLine({ width = '100%' }: { width?: string }) {
    return (
        <div style={{
            height: 14,
            width,
            background: 'var(--color-surface-3)',
            borderRadius: 'var(--radius-sm)',
            animation: 'shimmer 1.5s infinite',
        }} />
    );
}

function SkeletonCard() {
    return (
        <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-5)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-3)',
        }}>
            <SkeletonLine width="60%" />
            <SkeletonLine width="80%" />
            <SkeletonLine width="40%" />
        </div>
    );
}

function SkeletonTableRow({ cols = 4 }: { cols?: number }) {
    return (
        <div style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${cols}, 1fr)`,
            gap: 'var(--space-3)',
            padding: 'var(--space-3) 0',
            borderBottom: '1px solid var(--color-border)',
        }}>
            {Array.from({ length: cols }).map((_, i) => (
                <SkeletonLine key={i} width={`${60 + Math.random() * 30}%`} />
            ))}
        </div>
    );
}

// ---------------------------------------------------------------------------
// PageLoader — standard loading wrapper
// ---------------------------------------------------------------------------

interface PageLoaderProps {
    loading: boolean;
    children: ReactNode;
    /** Layout variant: cards, table, list, detail */
    variant?: 'cards' | 'table' | 'list' | 'detail';
    /** Number of skeleton items */
    rows?: number;
    /** Number of table columns */
    cols?: number;
}

export function PageLoader({
    loading,
    children,
    variant = 'list',
    rows = 3,
    cols = 4,
}: PageLoaderProps) {
    if (!loading) return <>{children}</>;

    if (variant === 'cards') {
        return (
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
                gap: 'var(--space-4)',
            }}>
                {Array.from({ length: rows }).map((_, i) => (
                    <SkeletonCard key={i} />
                ))}
            </div>
        );
    }

    if (variant === 'table') {
        return (
            <div>
                {/* Header */}
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: `repeat(${cols}, 1fr)`,
                    gap: 'var(--space-3)',
                    padding: 'var(--space-3) 0',
                    borderBottom: '2px solid var(--color-border)',
                }}>
                    {Array.from({ length: cols }).map((_, i) => (
                        <SkeletonLine key={i} width="50%" />
                    ))}
                </div>
                {Array.from({ length: rows }).map((_, i) => (
                    <SkeletonTableRow key={i} cols={cols} />
                ))}
            </div>
        );
    }

    if (variant === 'detail') {
        return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                <SkeletonLine width="40%" />
                <SkeletonLine width="100%" />
                <SkeletonLine width="80%" />
                <div style={{ height: 'var(--space-4)' }} />
                <SkeletonCard />
                <SkeletonCard />
            </div>
        );
    }

    // Default: list
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            {Array.from({ length: rows }).map((_, i) => (
                <div key={i} style={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-md)',
                    padding: 'var(--space-4)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 'var(--space-2)',
                }}>
                    <SkeletonLine width="50%" />
                    <SkeletonLine width="70%" />
                </div>
            ))}
        </div>
    );
}
