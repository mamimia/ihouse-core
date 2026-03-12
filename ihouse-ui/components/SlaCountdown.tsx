'use client';

/**
 * Phase 389 — SlaCountdown shared component
 * SLA timer extracted from worker page, role-agnostic, Domaniqo tokens.
 */

import React, { useEffect, useState } from 'react';

interface SlaCountdownProps {
    /** ISO timestamp when the SLA started (e.g. created_at) */
    startedAt: string;
    /** SLA duration in minutes */
    slaMinutes?: number;
    /** Label to show (e.g. 'to ack', 'to respond') */
    label?: string;
}

export default function SlaCountdown({ startedAt, slaMinutes = 5, label = 'to ack' }: SlaCountdownProps) {
    const [ms, setMs] = useState<number | null>(null);

    useEffect(() => {
        const calc = () => {
            const deadline = new Date(startedAt).getTime() + slaMinutes * 60_000;
            return Math.max(0, deadline - Date.now());
        };
        setMs(calc());
        const iv = setInterval(() => setMs(calc()), 1000);
        return () => clearInterval(iv);
    }, [startedAt, slaMinutes]);

    if (ms === null) return null;

    const secs = Math.floor(ms / 1000);
    const mins = Math.floor(secs / 60);
    const s = secs % 60;
    const hot = ms < 60_000;
    const gone = ms === 0;

    return (
        <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            fontSize: 'var(--text-sm, 13px)',
            fontFamily: 'var(--font-mono, monospace)',
            color: gone ? 'var(--color-text-dim, #9ca3af)' : hot ? 'var(--color-danger, #ef4444)' : '#f97316',
            animation: hot && !gone ? 'slaPulse 1s infinite' : 'none',
            marginTop: 'var(--space-1, 6px)',
        }}>
            <span>⏱</span>
            <span>{gone ? 'SLA EXPIRED' : `${mins}:${String(s).padStart(2, '0')} ${label}`}</span>
            <style>{`@keyframes slaPulse { 0%,100% { opacity:1 } 50% { opacity:.5 } }`}</style>
        </div>
    );
}
