'use client';

/**
 * Admin Intake Queue — Property Review Dashboard
 *
 * Shows all submitted properties awaiting admin review.
 * Approve → sets status to 'active', Reject → sets status to 'rejected'.
 * Route: /admin/intake
 */

import { useState, useEffect, useCallback } from 'react';
import { supabase } from '@/lib/supabaseClient';

interface IntakeProperty {
    property_id: string;
    display_name: string;
    property_type: string | null;
    city: string | null;
    country: string | null;
    status: string;
    created_at: string;
    submitted_at: string | null;
    submitter_email: string | null;
    submitter_user_id: string | null;
    max_guests: number | null;
    bedrooms: number | null;
    source_url: string | null;
    source_platform: string | null;
    description: string | null;
}

const STATUS_COLORS: Record<string, { label: string; bg: string; color: string }> = {
    draft:          { label: 'Draft',          bg: 'rgba(234,229,222,0.06)', color: 'rgba(234,229,222,0.5)' },
    pending_review: { label: 'Pending Review', bg: 'rgba(181,110,69,0.08)',  color: '#B56E45' },
    pending:        { label: 'Pending Review', bg: 'rgba(181,110,69,0.08)',  color: '#B56E45' },
    active:         { label: 'Active',         bg: 'rgba(74,124,89,0.08)',   color: '#4A7C59' },
    approved:       { label: 'Approved',       bg: 'rgba(74,124,89,0.08)',   color: '#4A7C59' },
    rejected:       { label: 'Rejected',       bg: 'rgba(196,91,74,0.08)',   color: '#C45B4A' },
};

export default function AdminIntakePage() {
    const [properties, setProperties] = useState<IntakeProperty[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState<'pending' | 'all' | 'rejected'>('pending');
    const [actionLoading, setActionLoading] = useState<string | null>(null);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [rejectReason, setRejectReason] = useState('');
    const [notice, setNotice] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

    const showNotice = (text: string, type: 'success' | 'error' = 'success') => {
        setNotice({ text, type });
        setTimeout(() => setNotice(null), 4000);
    };

    const fetchProperties = useCallback(async () => {
        setLoading(true);
        try {
            const session = await supabase?.auth.getSession();
            const token = session?.data?.session?.access_token;
            if (!token) { setLoading(false); return; }

            const statusParam = filter === 'pending' ? 'pending_review,draft'
                : filter === 'rejected' ? 'rejected'
                : 'pending_review,draft,active,approved,rejected';

            const res = await fetch(`/api/admin/intake?status=${statusParam}`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                setProperties(data.properties || []);
            } else if (res.status === 403) {
                showNotice('Access denied — admin role required.', 'error');
            }
        } catch { /* ignore */ }
        setLoading(false);
    }, [filter]);

    useEffect(() => { fetchProperties(); }, [fetchProperties]);

    const handleAction = async (propertyId: string, action: 'approve' | 'reject') => {
        setActionLoading(propertyId);
        try {
            const session = await supabase?.auth.getSession();
            const token = session?.data?.session?.access_token;
            if (!token) return;

            const res = await fetch('/api/admin/intake', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    propertyId,
                    action,
                    rejectionReason: action === 'reject' ? rejectReason : undefined,
                }),
            });

            if (res.ok) {
                showNotice(`Property ${action === 'approve' ? 'approved' : 'rejected'} successfully.`);
                setRejectReason('');
                setExpandedId(null);
                fetchProperties();
            } else {
                const data = await res.json();
                showNotice(data.error || 'Action failed', 'error');
            }
        } catch {
            showNotice('Network error', 'error');
        }
        setActionLoading(null);
    };

    const pending = properties.filter(p => ['draft', 'pending_review', 'pending'].includes(p.status));
    const decided = properties.filter(p => ['active', 'approved', 'rejected'].includes(p.status));

    const card: React.CSSProperties = {
        background: 'var(--color-elevated, #1E2127)',
        border: '1px solid rgba(234,229,222,0.06)',
        borderRadius: 16,
    };

    const btnBase: React.CSSProperties = {
        padding: '8px 16px', border: 'none', borderRadius: 10,
        fontSize: 13, fontWeight: 600, cursor: 'pointer',
        fontFamily: 'var(--font-brand, inherit)',
        transition: 'opacity 0.15s',
    };

    return (
        <>
            <style>{`
                @keyframes fadeIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
                .intake-fade { animation: fadeIn 300ms ease both; }
                .intake-row { transition: border-color 0.2s; }
                .intake-row:hover { border-color: rgba(234,229,222,0.12) !important; }
            `}</style>

            <div style={{
                minHeight: '100vh',
                background: 'var(--color-midnight, #171A1F)',
                paddingTop: 'var(--header-height, 72px)',
            }}>
                <div style={{ maxWidth: 720, margin: '0 auto', padding: '24px 16px' }}>
                    {/* Notice toast */}
                    {notice && (
                        <div style={{
                            position: 'fixed', top: 20, right: 20, zIndex: 999,
                            background: notice.type === 'success' ? 'rgba(74,124,89,0.15)' : 'rgba(196,91,74,0.15)',
                            border: `1px solid ${notice.type === 'success' ? 'rgba(74,124,89,0.3)' : 'rgba(196,91,74,0.3)'}`,
                            borderRadius: 12, padding: '12px 20px',
                            fontSize: 14, color: notice.type === 'success' ? '#4A7C59' : '#C45B4A',
                            boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
                        }}>
                            {notice.text}
                        </div>
                    )}

                    {/* Header */}
                    <div className="intake-fade" style={{ marginBottom: 24 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                            <span style={{ fontSize: 24 }}>📋</span>
                            <h1 style={{
                                fontFamily: 'var(--font-display, serif)',
                                fontSize: 24, color: 'var(--color-stone, #EAE5DE)',
                                margin: 0, fontWeight: 400,
                            }}>
                                Property Intake Queue
                            </h1>
                        </div>
                        <p style={{ fontSize: 14, color: 'rgba(234,229,222,0.35)', margin: '8px 0 0' }}>
                            Review and approve submitted properties.
                        </p>
                    </div>

                    {/* Filter tabs */}
                    <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
                        {([
                            { key: 'pending', label: `Pending (${pending.length})` },
                            { key: 'all', label: 'All' },
                            { key: 'rejected', label: 'Rejected' },
                        ] as const).map(tab => (
                            <button
                                key={tab.key}
                                onClick={() => setFilter(tab.key)}
                                style={{
                                    ...btnBase,
                                    padding: '6px 14px', fontSize: 12,
                                    background: filter === tab.key ? 'rgba(181,110,69,0.15)' : 'rgba(234,229,222,0.04)',
                                    color: filter === tab.key ? '#B56E45' : 'rgba(234,229,222,0.4)',
                                    border: `1px solid ${filter === tab.key ? 'rgba(181,110,69,0.2)' : 'rgba(234,229,222,0.06)'}`,
                                }}
                            >
                                {tab.label}
                            </button>
                        ))}
                    </div>

                    {/* Content */}
                    {loading ? (
                        <div style={{ textAlign: 'center', padding: '48px 0', color: 'rgba(234,229,222,0.3)' }}>
                            Loading intake queue…
                        </div>
                    ) : properties.length === 0 ? (
                        <div className="intake-fade" style={{ ...card, textAlign: 'center', padding: 48 }}>
                            <div style={{ fontSize: 48, marginBottom: 12 }}>✨</div>
                            <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--color-stone)', margin: '0 0 8px' }}>
                                Queue is clear
                            </h2>
                            <p style={{ fontSize: 14, color: 'rgba(234,229,222,0.4)', margin: 0 }}>
                                No properties waiting for review.
                            </p>
                        </div>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                            {properties.map((prop, i) => {
                                const sc = STATUS_COLORS[prop.status] || STATUS_COLORS.draft;
                                const isExpanded = expandedId === prop.property_id;

                                return (
                                    <div key={prop.property_id} className="intake-fade intake-row"
                                        style={{
                                            ...card, padding: '16px 18px',
                                            animationDelay: `${i * 40}ms`,
                                        }}
                                    >
                                        {/* Row header */}
                                        <div style={{
                                            display: 'flex', alignItems: 'flex-start',
                                            justifyContent: 'space-between', gap: 12,
                                            cursor: 'pointer',
                                        }}
                                            onClick={() => setExpandedId(isExpanded ? null : prop.property_id)}
                                        >
                                            <div style={{ flex: 1, minWidth: 0 }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                                                    <span style={{ fontSize: 14 }}>🏠</span>
                                                    <h3 style={{
                                                        fontSize: 15, fontWeight: 600,
                                                        color: 'var(--color-stone)', margin: 0,
                                                    }}>
                                                        {prop.display_name || 'Untitled'}
                                                    </h3>
                                                    <span style={{
                                                        fontSize: 10, fontWeight: 700,
                                                        color: sc.color, background: sc.bg,
                                                        padding: '2px 8px', borderRadius: 99,
                                                        textTransform: 'uppercase', letterSpacing: '0.04em',
                                                    }}>
                                                        {sc.label}
                                                    </span>
                                                </div>
                                                <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.35)', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                                                    <span>{prop.property_id}</span>
                                                    {prop.city && <span>📍 {[prop.city, prop.country].filter(Boolean).join(', ')}</span>}
                                                    {prop.submitter_email && <span>👤 {prop.submitter_email}</span>}
                                                    <span>📅 {new Date(prop.created_at).toLocaleDateString()}</span>
                                                </div>
                                            </div>
                                            <span style={{ fontSize: 14, color: 'rgba(234,229,222,0.2)', flexShrink: 0 }}>
                                                {isExpanded ? '▾' : '▸'}
                                            </span>
                                        </div>

                                        {/* Expanded details */}
                                        {isExpanded && (
                                            <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid rgba(234,229,222,0.06)' }}>
                                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 24px', fontSize: 13 }}>
                                                    <Detail label="Type" value={prop.property_type} />
                                                    <Detail label="Max Guests" value={prop.max_guests?.toString()} />
                                                    <Detail label="Bedrooms" value={prop.bedrooms?.toString()} />
                                                    <Detail label="Platform" value={prop.source_platform} />
                                                    {prop.source_url && (
                                                        <div style={{ gridColumn: '1 / -1' }}>
                                                            <span style={{ color: 'rgba(234,229,222,0.3)' }}>Source: </span>
                                                            <a href={prop.source_url} target="_blank" rel="noreferrer"
                                                                style={{ color: '#B56E45', textDecoration: 'underline', wordBreak: 'break-all' }}>
                                                                {prop.source_url}
                                                            </a>
                                                        </div>
                                                    )}
                                                    {prop.description && (
                                                        <div style={{ gridColumn: '1 / -1' }}>
                                                            <span style={{ color: 'rgba(234,229,222,0.3)' }}>Description: </span>
                                                            <span style={{ color: 'var(--color-stone)' }}>{prop.description}</span>
                                                        </div>
                                                    )}
                                                </div>

                                                {/* Actions */}
                                                {['draft', 'pending_review', 'pending'].includes(prop.status) && (
                                                    <div style={{ marginTop: 16, display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                                                        <button
                                                            onClick={() => handleAction(prop.property_id, 'approve')}
                                                            disabled={actionLoading === prop.property_id}
                                                            style={{
                                                                ...btnBase,
                                                                background: 'var(--color-moss, #334036)',
                                                                color: '#fff',
                                                                opacity: actionLoading === prop.property_id ? 0.5 : 1,
                                                            }}
                                                        >
                                                            {actionLoading === prop.property_id ? '…' : '✅ Approve'}
                                                        </button>
                                                        <input
                                                            placeholder="Rejection reason (optional)"
                                                            value={rejectReason}
                                                            onChange={e => setRejectReason(e.target.value)}
                                                            style={{
                                                                flex: 1, minWidth: 160, padding: '8px 12px',
                                                                background: 'rgba(234,229,222,0.04)',
                                                                border: '1px solid rgba(234,229,222,0.08)',
                                                                borderRadius: 10, color: 'var(--color-stone)',
                                                                fontSize: 13, fontFamily: 'inherit',
                                                            }}
                                                        />
                                                        <button
                                                            onClick={() => handleAction(prop.property_id, 'reject')}
                                                            disabled={actionLoading === prop.property_id}
                                                            style={{
                                                                ...btnBase,
                                                                background: 'rgba(196,91,74,0.12)',
                                                                color: '#C45B4A',
                                                                opacity: actionLoading === prop.property_id ? 0.5 : 1,
                                                            }}
                                                        >
                                                            {actionLoading === prop.property_id ? '…' : '✕ Reject'}
                                                        </button>
                                                    </div>
                                                )}

                                                {prop.status === 'rejected' && (
                                                    <div style={{
                                                        marginTop: 12, padding: '10px 14px', fontSize: 13,
                                                        background: 'rgba(196,91,74,0.06)', borderRadius: 10,
                                                        color: 'rgba(234,229,222,0.5)',
                                                        border: '1px solid rgba(196,91,74,0.1)',
                                                    }}>
                                                        Rejected. {(prop as any).rejection_reason && `Reason: ${(prop as any).rejection_reason}`}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}

function Detail({ label, value }: { label: string; value?: string | null }) {
    if (!value) return null;
    return (
        <div>
            <span style={{ color: 'rgba(234,229,222,0.3)' }}>{label}: </span>
            <span style={{ color: 'var(--color-stone, #EAE5DE)' }}>{value}</span>
        </div>
    );
}
