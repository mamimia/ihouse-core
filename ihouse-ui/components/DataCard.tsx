'use client';

/**
 * Phase 389 — DataCard shared component
 * Stat card used across dashboard, owner portal, manager, ops.
 */

import React from 'react';

interface DataCardProps {
    label: string;
    value: string | number;
    sub?: string;
    icon?: string;
    color?: string;
    trend?: 'up' | 'down' | 'flat';
}

export default function DataCard({ label, value, sub, icon, color, trend }: DataCardProps) {
    return (
        <div style={{
            background: 'var(--color-surface, #1a1f2e)',
            border: '1px solid var(--color-border, #ffffff12)',
            borderRadius: 'var(--radius-lg, 16px)',
            padding: 'var(--space-4, 16px)',
            display: 'flex', flexDirection: 'column', gap: 'var(--space-1, 4px)',
        }}>
            <div style={{
                fontSize: 'var(--text-xs, 11px)',
                color: 'var(--color-text-dim, #6b7280)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                display: 'flex', alignItems: 'center', gap: 'var(--space-1, 4px)',
            }}>
                {icon && <span>{icon}</span>}
                {label}
            </div>
            <div style={{
                fontSize: 'var(--text-2xl, 28px)', fontWeight: 800,
                color: color ?? 'var(--color-text, #f9fafb)',
                fontVariantNumeric: 'tabular-nums',
            }}>
                {value}
                {trend && (
                    <span style={{
                        fontSize: 'var(--text-sm, 14px)', marginInlineStart: 'var(--space-2, 8px)',
                        color: trend === 'up' ? '#22c55e' : trend === 'down' ? '#ef4444' : '#6b7280',
                    }}>
                        {trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→'}
                    </span>
                )}
            </div>
            {sub && (
                <div style={{
                    fontSize: 'var(--text-xs, 11px)',
                    color: 'var(--color-text-faint, #4b5563)',
                }}>
                    {sub}
                </div>
            )}
        </div>
    );
}
