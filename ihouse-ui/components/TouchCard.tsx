'use client';

/**
 * Phase 389 — TouchCard shared component
 * Touch-interactive card with scale feedback, extracted from worker page.
 */

import React from 'react';

interface TouchCardProps {
    children: React.ReactNode;
    onClick?: () => void;
    borderColor?: string;
    glow?: string;
    id?: string;
}

export default function TouchCard({ children, onClick, borderColor, glow, id }: TouchCardProps) {
    return (
        <div
            id={id}
            onClick={onClick}
            style={{
                background: 'var(--color-surface, #1a1f2e)',
                border: `1px solid ${borderColor ?? 'var(--color-border, #ffffff12)'}`,
                borderRadius: 'var(--radius-lg, 16px)',
                padding: 'var(--space-4, 16px) var(--space-4, 16px) var(--space-4, 16px) var(--space-5, 20px)',
                position: 'relative',
                overflow: 'hidden',
                cursor: onClick ? 'pointer' : 'default',
                boxShadow: glow ?? '0 2px 8px rgba(0,0,0,0.3)',
                transition: 'transform 0.1s ease, box-shadow 0.15s ease',
            }}
            onTouchStart={e => { if (onClick) e.currentTarget.style.transform = 'scale(0.98)'; }}
            onTouchEnd={e => { if (onClick) e.currentTarget.style.transform = 'scale(1)'; }}
        >
            {children}
        </div>
    );
}
