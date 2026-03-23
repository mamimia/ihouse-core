'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface FeedbackEntry {
    booking_id: string;
    property_id: string;
    rating: number;
    category: string;
    comment: string;
    created_at: string;
}

export default function GuestFeedbackPage() {
    const [feedback, setFeedback] = useState<FeedbackEntry[]>([]);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.getGuestFeedback({ limit: 100 });
            setFeedback((res.entries || []) as FeedbackEntry[]);
        } catch { /* graceful */ }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const avgRating = feedback.length
        ? (feedback.reduce((s, f) => s + (f.rating || 0), 0) / feedback.length).toFixed(1)
        : '—';

    const ratingDist = [1, 2, 3, 4, 5].map(r => ({
        star: r,
        count: feedback.filter(f => f.rating === r).length,
    }));

    return (
        <div style={{ maxWidth: 1000 }}>
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                    Guest experience insights
                </p>
                <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                    Guest <span style={{ color: 'var(--color-primary)' }}>Feedback</span>
                </h1>
            </div>

            {/* Stats row */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
                {[
                    { label: 'Average Rating', value: `⭐ ${avgRating}`, color: 'var(--color-accent)' },
                    { label: 'Total Reviews', value: String(feedback.length), color: 'var(--color-primary)' },
                    { label: 'Properties', value: String(new Set(feedback.map(f => f.property_id)).size), color: 'var(--color-ok)' },
                ].map(s => (
                    <div key={s.label} style={{
                        background: 'var(--color-surface)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-lg)',
                        padding: 'var(--space-5)',
                    }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{s.label}</div>
                        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: s.color, marginTop: 'var(--space-2)' }}>{s.value}</div>
                    </div>
                ))}
            </div>

            {/* Rating distribution */}
            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', marginBottom: 'var(--space-6)' }}>
                <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 'var(--space-4)' }}>Rating Distribution</h2>
                {ratingDist.reverse().map(d => (
                    <div key={d.star} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
                        <span style={{ width: 24, fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>{d.star}★</span>
                        <div style={{ flex: 1, height: 8, background: 'var(--color-surface-3)', borderRadius: 4 }}>
                            <div style={{ width: `${feedback.length ? (d.count / feedback.length * 100) : 0}%`, height: '100%', background: 'var(--color-primary)', borderRadius: 4, transition: 'width 0.3s' }} />
                        </div>
                        <span style={{ width: 30, fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', textAlign: 'right' }}>{d.count}</span>
                    </div>
                ))}
            </div>

            {/* Recent comments */}
            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 'var(--space-4)' }}>Recent Feedback</h2>
                {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p>}
                {!loading && feedback.length === 0 && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>No feedback yet.</p>}
                {feedback.slice(0, 20).map((f, i) => (
                    <div key={i} style={{ padding: 'var(--space-3) var(--space-4)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--space-2)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--space-1)' }}>
                            <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{'⭐'.repeat(f.rating)}</span>
                            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)' }}>{f.property_id}</span>
                        </div>
                        {f.comment && <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', margin: 0 }}>{f.comment}</p>}
                    </div>
                ))}
            </div>

            <div style={{ paddingTop: 'var(--space-6)', borderTop: '1px solid var(--color-border)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>
                Domaniqo — Guest Feedback Dashboard · Phase 510
            </div>
        </div>
    );
}
