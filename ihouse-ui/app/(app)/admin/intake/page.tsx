'use client';

/**
 * Admin Intake Queue — Property Review Dashboard
 *
 * Shows all submitted properties awaiting admin review.
 * Approve → sets status to 'active', Reject → sets status to 'rejected'.
 * Route: /admin/intake
 *
 * Now in (app) layout group — inherits AdaptiveShell sidebar + ForceLight.
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

const STATUS_COLORS: Record<string, { label: string; bg: string; color: string; border: string }> = {
    draft:          { label: 'Draft',          bg: '#6b728015', color: '#6b7280', border: '#6b728033' },
    pending_review: { label: 'Pending Review', bg: '#f59e0b15', color: '#f59e0b', border: '#f59e0b33' },
    pending:        { label: 'Pending Review', bg: '#f59e0b15', color: '#f59e0b', border: '#f59e0b33' },
    active:         { label: 'Active',         bg: '#22c55e15', color: '#22c55e', border: '#22c55e33' },
    approved:       { label: 'Approved',       bg: '#22c55e15', color: '#22c55e', border: '#22c55e33' },
    rejected:       { label: 'Rejected',       bg: '#ef444415', color: '#ef4444', border: '#ef444433' },
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

    return (
        <div style={{ maxWidth: 900 }}>
            {/* Notice toast */}
            {notice && (
                <div style={{
                    position: 'fixed', top: 20, right: 20, zIndex: 999,
                    background: notice.type === 'success' ? '#22c55e15' : '#ef444415',
                    border: `1px solid ${notice.type === 'success' ? '#22c55e33' : '#ef444433'}`,
                    borderRadius: 'var(--radius-md)', padding: '12px 20px',
                    fontSize: 'var(--text-sm)', color: notice.type === 'success' ? '#22c55e' : '#ef4444',
                    boxShadow: '0 4px 20px rgba(0,0,0,0.1)',
                }}>
                    {notice.text}
                </div>
            )}

            {/* Header */}
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-1)' }}>
                    Property management
                </p>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <h1 style={{
                        fontSize: 'var(--text-3xl)',
                        fontWeight: 700,
                        letterSpacing: '-0.03em',
                        color: 'var(--color-text)',
                    }}>
                        Intake <span style={{ color: 'var(--color-primary)' }}>Queue</span>
                    </h1>
                    <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
                        <button
                            onClick={() => window.location.href = '/admin/properties'}
                            style={{
                                background: 'none',
                                color: 'var(--color-text-dim)',
                                border: '1px solid var(--color-border)',
                                borderRadius: 'var(--radius-md)',
                                padding: 'var(--space-2) var(--space-5)',
                                fontSize: 'var(--text-sm)',
                                fontWeight: 500,
                                cursor: 'pointer',
                            }}
                        >
                            ← Back to Properties
                        </button>
                        <button
                            onClick={fetchProperties}
                            disabled={loading}
                            style={{
                                background: loading ? 'var(--color-surface-3)' : 'var(--color-surface)',
                                color: 'var(--color-text)',
                                border: '1px solid var(--color-border)',
                                borderRadius: 'var(--radius-md)',
                                padding: 'var(--space-2) var(--space-5)',
                                fontSize: 'var(--text-sm)',
                                fontWeight: 600,
                                opacity: loading ? 0.7 : 1,
                                cursor: loading ? 'not-allowed' : 'pointer',
                                transition: 'all var(--transition-fast)',
                            }}
                        >
                            {loading ? '⟳  Refreshing…' : '↺  Refresh'}
                        </button>
                    </div>
                </div>
            </div>

            {/* Filter tabs */}
            <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-6)', flexWrap: 'wrap' }}>
                {([
                    { key: 'pending' as const, label: `Pending (${pending.length})` },
                    { key: 'all' as const, label: 'All' },
                    { key: 'rejected' as const, label: 'Rejected' },
                ]).map(tab => (
                    <button
                        key={tab.key}
                        onClick={() => setFilter(tab.key)}
                        style={{
                            background: filter === tab.key ? 'var(--color-primary)' : 'var(--color-surface)',
                            border: filter === tab.key ? '1px solid var(--color-primary)' : '1px solid var(--color-border)',
                            borderRadius: 'var(--radius-lg)',
                            padding: 'var(--space-2) var(--space-5)',
                            textAlign: 'center',
                            cursor: 'pointer',
                            transition: 'all var(--transition-fast)',
                            fontSize: 'var(--text-xs)',
                            fontWeight: 700,
                            color: filter === tab.key ? '#fff' : 'var(--color-text-dim)',
                            textTransform: 'uppercase',
                            letterSpacing: '0.06em',
                        }}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Table header */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 120px 100px 100px',
                gap: 'var(--space-3)',
                padding: '0 var(--space-5)',
                marginBottom: 'var(--space-2)',
            }}>
                {['Property', 'Status', 'Submitted', 'Actions'].map(h => (
                    <span key={h} style={{
                        fontSize: 'var(--text-xs)',
                        color: 'var(--color-text-faint)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                    }}>{h}</span>
                ))}
            </div>

            {/* Content */}
            {loading && properties.length === 0 ? (
                <div style={{
                    padding: 'var(--space-8)',
                    textAlign: 'center',
                    color: 'var(--color-text-dim)',
                    fontSize: 'var(--text-sm)',
                }}>
                    Loading intake queue…
                </div>
            ) : properties.length === 0 ? (
                <div style={{
                    padding: 'var(--space-8)',
                    textAlign: 'center',
                    background: 'var(--color-surface)',
                    borderRadius: 'var(--radius-lg)',
                    border: '1px solid var(--color-border)',
                }}>
                    <div style={{ fontSize: '2em', marginBottom: 'var(--space-3)' }}>✨</div>
                    <div style={{ fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text)', marginBottom: 'var(--space-2)' }}>
                        Queue is clear
                    </div>
                    <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                        No properties waiting for review.
                    </div>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                    {properties.map(prop => {
                        const sc = STATUS_COLORS[prop.status] || STATUS_COLORS.draft;
                        const isExpanded = expandedId === prop.property_id;
                        const submitted = (prop.submitted_at || prop.created_at)
                            ? new Date(prop.submitted_at || prop.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                            : '—';

                        return (
                            <div key={prop.property_id} style={{
                                background: 'var(--color-surface-2)',
                                borderRadius: 'var(--radius-md)',
                                transition: 'background var(--transition-fast)',
                            }}>
                                {/* Row */}
                                <div
                                    style={{
                                        display: 'grid',
                                        gridTemplateColumns: '1fr 120px 100px 100px',
                                        alignItems: 'center',
                                        gap: 'var(--space-3)',
                                        padding: 'var(--space-4) var(--space-5)',
                                        cursor: 'pointer',
                                    }}
                                    onClick={() => setExpandedId(isExpanded ? null : prop.property_id)}
                                >
                                    {/* Property name + meta */}
                                    <div>
                                        <div style={{
                                            fontWeight: 600,
                                            fontSize: 'var(--text-sm)',
                                            color: 'var(--color-primary)',
                                            marginBottom: 2,
                                        }}>
                                            {prop.display_name || 'Untitled Property'}
                                        </div>
                                        <div style={{
                                            fontSize: 'var(--text-xs)',
                                            color: 'var(--color-text-dim)',
                                            display: 'flex',
                                            gap: 'var(--space-3)',
                                        }}>
                                            {prop.city && <span>📍 {[prop.city, prop.country].filter(Boolean).join(', ')}</span>}
                                            {prop.property_type && <span>🏠 {prop.property_type}</span>}
                                            {prop.submitter_email && <span>👤 {prop.submitter_email}</span>}
                                        </div>
                                    </div>

                                    {/* Status */}
                                    <div>
                                        <span style={{
                                            fontSize: 'var(--text-xs)',
                                            fontWeight: 700,
                                            padding: '2px 10px',
                                            borderRadius: 'var(--radius-full)',
                                            background: sc.bg,
                                            color: sc.color,
                                            border: `1px solid ${sc.border}`,
                                            textTransform: 'uppercase',
                                            letterSpacing: '0.05em',
                                            fontFamily: 'var(--font-mono)',
                                        }}>
                                            {sc.label}
                                        </span>
                                    </div>

                                    {/* Submitted date */}
                                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)' }}>
                                        {submitted}
                                    </div>

                                    {/* Expand indicator */}
                                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textAlign: 'right' }}>
                                        {isExpanded ? '▾ Less' : '▸ Details'}
                                    </div>
                                </div>

                                {/* Expanded details */}
                                {isExpanded && (
                                    <div style={{
                                        padding: '0 var(--space-5) var(--space-5)',
                                        borderTop: '1px solid var(--color-border)',
                                        marginTop: 0,
                                    }}>
                                        <div style={{
                                            display: 'grid', gridTemplateColumns: '1fr 1fr',
                                            gap: '8px 24px', fontSize: 'var(--text-sm)',
                                            paddingTop: 'var(--space-4)',
                                        }}>
                                            <Detail label="Property ID" value={prop.property_id} />
                                            <Detail label="Type" value={prop.property_type} />
                                            <Detail label="Max Guests" value={prop.max_guests?.toString()} />
                                            <Detail label="Bedrooms" value={prop.bedrooms?.toString()} />
                                            <Detail label="Platform" value={prop.source_platform} />
                                            {prop.source_url && (
                                                <div style={{ gridColumn: '1 / -1' }}>
                                                    <span style={{ color: 'var(--color-text-faint)' }}>Source: </span>
                                                    <a href={prop.source_url} target="_blank" rel="noreferrer"
                                                        style={{ color: 'var(--color-primary)', textDecoration: 'underline', wordBreak: 'break-all' }}>
                                                        {prop.source_url}
                                                    </a>
                                                </div>
                                            )}
                                            {prop.description && (
                                                <div style={{ gridColumn: '1 / -1' }}>
                                                    <span style={{ color: 'var(--color-text-faint)' }}>Description: </span>
                                                    <span style={{ color: 'var(--color-text)' }}>{prop.description}</span>
                                                </div>
                                            )}
                                        </div>

                                        {/* Actions for pending */}
                                        {['draft', 'pending_review', 'pending'].includes(prop.status) && (
                                            <div style={{ marginTop: 'var(--space-4)', display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap', alignItems: 'center' }}>
                                                <button
                                                    onClick={() => handleAction(prop.property_id, 'approve')}
                                                    disabled={actionLoading === prop.property_id}
                                                    style={{
                                                        padding: 'var(--space-2) var(--space-5)',
                                                        background: '#22c55e15',
                                                        border: '1px solid #22c55e33',
                                                        color: '#22c55e',
                                                        borderRadius: 'var(--radius-md)',
                                                        fontSize: 'var(--text-sm)',
                                                        fontWeight: 600,
                                                        cursor: actionLoading === prop.property_id ? 'not-allowed' : 'pointer',
                                                        opacity: actionLoading === prop.property_id ? 0.5 : 1,
                                                    }}
                                                >
                                                    {actionLoading === prop.property_id ? '…' : '✓ Approve'}
                                                </button>
                                                <input
                                                    placeholder="Rejection reason (optional)"
                                                    value={rejectReason}
                                                    onChange={e => setRejectReason(e.target.value)}
                                                    style={{
                                                        flex: 1, minWidth: 160, padding: 'var(--space-2) var(--space-3)',
                                                        background: 'var(--color-surface)',
                                                        border: '1px solid var(--color-border)',
                                                        borderRadius: 'var(--radius-md)', color: 'var(--color-text)',
                                                        fontSize: 'var(--text-sm)', fontFamily: 'inherit',
                                                    }}
                                                />
                                                <button
                                                    onClick={() => handleAction(prop.property_id, 'reject')}
                                                    disabled={actionLoading === prop.property_id}
                                                    style={{
                                                        padding: 'var(--space-2) var(--space-5)',
                                                        background: '#ef444415',
                                                        border: '1px solid #ef444433',
                                                        color: '#ef4444',
                                                        borderRadius: 'var(--radius-md)',
                                                        fontSize: 'var(--text-sm)',
                                                        fontWeight: 600,
                                                        cursor: actionLoading === prop.property_id ? 'not-allowed' : 'pointer',
                                                        opacity: actionLoading === prop.property_id ? 0.5 : 1,
                                                    }}
                                                >
                                                    {actionLoading === prop.property_id ? '…' : '✗ Reject'}
                                                </button>
                                            </div>
                                        )}

                                        {prop.status === 'rejected' && (
                                            <div style={{
                                                marginTop: 'var(--space-3)', padding: 'var(--space-3) var(--space-4)', fontSize: 'var(--text-sm)',
                                                background: '#ef444410', borderRadius: 'var(--radius-md)',
                                                color: '#ef4444',
                                                border: '1px solid #ef444425',
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

            {/* Footer */}
            <div style={{
                paddingTop: 'var(--space-6)',
                marginTop: 'var(--space-6)',
                borderTop: '1px solid var(--color-border)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-faint)',
                display: 'flex',
                justifyContent: 'space-between',
            }}>
                <span>Domaniqo — Admin Intake Queue · Phase 859</span>
                <span>Properties pending review are shown here</span>
            </div>
        </div>
    );
}

function Detail({ label, value }: { label: string; value?: string | null }) {
    if (!value) return null;
    return (
        <div>
            <span style={{ color: 'var(--color-text-faint)' }}>{label}: </span>
            <span style={{ color: 'var(--color-text)' }}>{value}</span>
        </div>
    );
}
