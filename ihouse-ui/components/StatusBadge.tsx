'use client';

/**
 * Phase 389 — StatusBadge shared component
 * Extracted from dashboard/bookings/tasks inline status indicators.
 */

import React from 'react';

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
    active: { bg: 'rgba(34,197,94,0.1)', text: '#22c55e' },
    completed: { bg: 'rgba(34,197,94,0.1)', text: '#22c55e' },
    confirmed: { bg: 'rgba(34,197,94,0.1)', text: '#22c55e' },
    pending: { bg: 'rgba(245,158,11,0.1)', text: '#f59e0b' },
    acknowledged: { bg: 'rgba(59,130,246,0.1)', text: '#3b82f6' },
    in_progress: { bg: 'rgba(59,130,246,0.1)', text: '#3b82f6' },
    canceled: { bg: 'rgba(107,114,128,0.1)', text: '#6b7280' },
    cancelled: { bg: 'rgba(107,114,128,0.1)', text: '#6b7280' },
    failed: { bg: 'rgba(239,68,68,0.1)', text: '#ef4444' },
    overdue: { bg: 'rgba(239,68,68,0.1)', text: '#ef4444' },
};

interface StatusBadgeProps {
    status: string;
    size?: 'sm' | 'md';
    className?: string;
}

export default function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
    const key = status?.toLowerCase().replace(/\s+/g, '_');
    const colors = STATUS_COLORS[key] ?? STATUS_COLORS.pending;
    const label = status?.replace(/_/g, ' ') ?? 'unknown';

    return (
        <span style={{
            display: 'inline-block',
            fontSize: size === 'sm' ? 'var(--text-xs, 11px)' : 'var(--text-sm, 13px)',
            fontWeight: 700,
            color: colors.text,
            background: colors.bg,
            borderRadius: 99,
            padding: size === 'sm' ? '2px 9px' : '3px 12px',
            textTransform: 'capitalize',
            whiteSpace: 'nowrap',
        }}>
            {label}
        </span>
    );
}
