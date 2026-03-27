'use client';

import { Suspense, useEffect, useState, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface Property {
    property_id: string;
    tenant_id: string;
    display_name: string | null;
    timezone: string;
    base_currency: string;
    property_type: string | null;
    city: string | null;
    country: string | null;
    max_guests: number | null;
    bedrooms: number | null;
    beds: number | null;
    bathrooms: number | null;
    address: string | null;
    description: string | null;
    source_url: string | null;
    source_platform: string | null;
    status: string;
    approved_at: string | null;
    approved_by: string | null;
    archived_at: string | null;
    archived_by: string | null;
    created_at: string;
}

interface StatusSummary {
    pending: number;
    approved: number;
    rejected: number;
    archived: number;
}

/* ------------------------------------------------------------------ */
/* API helpers                                                         */
/* ------------------------------------------------------------------ */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function fetchAPI(path: string, options?: RequestInit) {
    // Read JWT from cookie (matches middleware.ts auth pattern)
    const token = typeof document !== 'undefined'
        ? document.cookie.split('; ').find(c => c.startsWith('ihouse_token='))?.split('=')[1] ?? ''
        : '';
    const res = await fetch(`${API_BASE}${path}`, {
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        ...options,
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    const body = await res.json();
    // Unwrap {ok, data} envelope if present
    if (body && typeof body === 'object' && body.ok === true && 'data' in body) return body.data;
    return body;
}

/* ------------------------------------------------------------------ */
/* Reusable components                                                 */
/* ------------------------------------------------------------------ */

function StatusBadge({ status }: { status: string }) {
    const colors: Record<string, { bg: string; text: string; border: string }> = {
        pending:  { bg: '#f59e0b15', text: '#f59e0b', border: '#f59e0b33' },
        approved: { bg: '#22c55e15', text: '#22c55e', border: '#22c55e33' },
        rejected: { bg: '#ef444415', text: '#ef4444', border: '#ef444433' },
        archived: { bg: '#6b728015', text: '#6b7280', border: '#6b728033' },
    };
    const c = colors[status] || colors.pending;
    return (
        <span style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 700,
            padding: '2px 10px',
            borderRadius: 'var(--radius-full)',
            background: c.bg,
            color: c.text,
            border: `1px solid ${c.border}`,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            fontFamily: 'var(--font-mono)',
        }}>{status}</span>
    );
}

function StatCard({ label, value, active }: { label: string; value: number; active?: boolean }) {
    return (
        <button
            style={{
                background: active ? 'var(--color-primary)' : 'var(--color-surface)',
                border: active ? '1px solid var(--color-primary)' : '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)',
                padding: 'var(--space-4) var(--space-5)',
                textAlign: 'center',
                cursor: 'pointer',
                transition: 'all var(--transition-fast)',
                minWidth: 100,
            }}
        >
            <div style={{
                fontSize: 'var(--text-2xl)',
                fontWeight: 700,
                color: active ? '#fff' : 'var(--color-text)',
                fontFamily: 'var(--font-mono)',
            }}>{value}</div>
            <div style={{
                fontSize: 'var(--text-xs)',
                color: active ? 'rgba(255,255,255,0.8)' : 'var(--color-text-dim)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                marginTop: 2,
            }}>{label}</div>
        </button>
    );
}

function ActionBtn({ label, icon, color, onClick, disabled }: {
    label: string; icon: string; color: string; onClick: () => void; disabled?: boolean;
}) {
    return (
        <button
            onClick={onClick}
            disabled={disabled}
            title={label}
            style={{
                background: `${color}15`,
                border: `1px solid ${color}33`,
                color,
                borderRadius: 'var(--radius-md)',
                padding: 'var(--space-1) var(--space-3)',
                fontSize: 'var(--text-xs)',
                fontWeight: 600,
                cursor: disabled ? 'not-allowed' : 'pointer',
                opacity: disabled ? 0.4 : 1,
                transition: 'all var(--transition-fast)',
                display: 'flex',
                alignItems: 'center',
                gap: 4,
            }}
        >
            <span>{icon}</span> {label}
        </button>
    );
}

/* ------------------------------------------------------------------ */
/* Property row                                                        */
/* ------------------------------------------------------------------ */

function PropertyRow({ p, onAction }: {
    p: Property;
    onAction: (id: string, action: string) => Promise<void>;
}) {
    const [acting, setActing] = useState(false);

    const handle = async (action: string) => {
        setActing(true);
        try { await onAction(p.property_id, action); }
        finally { setActing(false); }
    };

    const created = p.created_at ? new Date(p.created_at).toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
    }) : '—';

    return (
        <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 100px 100px 90px 180px',
            alignItems: 'center',
            gap: 'var(--space-3)',
            padding: 'var(--space-4) var(--space-5)',
            background: 'var(--color-surface-2)',
            borderRadius: 'var(--radius-md)',
            marginBottom: 'var(--space-2)',
            transition: 'background var(--transition-fast)',
        }}>
            {/* Name + meta */}
            <div>
                <a
                    href={`/admin/properties/${p.property_id}`}
                    style={{
                        fontWeight: 600,
                        fontSize: 'var(--text-sm)',
                        color: 'var(--color-primary)',
                        marginBottom: 2,
                        textDecoration: 'none',
                        display: 'block',
                    }}
                >
                    {p.display_name || p.property_id}
                </a>
                <div style={{
                    fontSize: 'var(--text-xs)',
                    color: 'var(--color-text-dim)',
                    display: 'flex',
                    gap: 'var(--space-3)',
                }}>
                    {p.city && <span>📍 {p.city}{p.country ? `, ${p.country}` : ''}</span>}
                    {p.property_type && <span>🏠 {p.property_type}</span>}
                    {p.source_platform && <span>🔗 {p.source_platform}</span>}
                </div>
            </div>

            {/* Status */}
            <div><StatusBadge status={p.status} /></div>

            {/* Created */}
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)' }}>
                {created}
            </div>

            {/* Capacity */}
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                {p.max_guests ? `${p.max_guests} guests` : '—'}
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: 'var(--space-2)', justifyContent: 'flex-end' }}>
                {p.status === 'pending' && (
                    <>
                        <ActionBtn label="Approve" icon="✓" color="#22c55e" onClick={() => handle('approve')} disabled={acting} />
                        <ActionBtn label="Reject" icon="✗" color="#ef4444" onClick={() => handle('reject')} disabled={acting} />
                    </>
                )}
                {p.status === 'approved' && (
                    <ActionBtn label="Archive" icon="📦" color="#6b7280" onClick={() => handle('archive')} disabled={acting} />
                )}
            </div>
        </div>
    );
}

/* ------------------------------------------------------------------ */
/* Add Property Modal                                                  */
/* ------------------------------------------------------------------ */

function AddPropertyModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
    const [propertyId, setPropertyId] = useState('');
    const [displayName, setDisplayName] = useState('');
    const [tz, setTz] = useState('Asia/Bangkok');
    const [currency, setCurrency] = useState('THB');
    const [sourceUrl, setSourceUrl] = useState('');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async () => {
        if (!propertyId.trim()) { setError('Property ID is required'); return; }
        setSaving(true);
        setError(null);
        try {
            const body: Record<string, string> = {
                property_id: propertyId.trim().toLowerCase().replace(/\s+/g, '-'),
                timezone: tz,
                base_currency: currency,
            };
            if (displayName.trim()) body.display_name = displayName.trim();
            if (sourceUrl.trim()) body.source_url = sourceUrl.trim();
            await fetchAPI('/properties', {
                method: 'POST',
                body: JSON.stringify(body),
            });
            onCreated();
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : 'Failed to create property';
            setError(msg.includes('409') ? 'Property ID already exists' : msg);
        } finally {
            setSaving(false);
        }
    };

    const inputStyle: React.CSSProperties = {
        width: '100%',
        padding: 'var(--space-3) var(--space-4)',
        background: 'var(--color-surface-2)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)',
        color: 'var(--color-text)',
        fontSize: 'var(--text-sm)',
        fontFamily: 'inherit',
    };

    const labelStyle: React.CSSProperties = {
        fontSize: 'var(--text-xs)',
        color: 'var(--color-text-dim)',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        marginBottom: 4,
        display: 'block',
    };

    return (
        <div style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200,
        }} onClick={onClose}>
            <div style={{
                background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)',
                padding: 'var(--space-8)', width: 480, maxHeight: '80vh', overflow: 'auto',
                border: '1px solid var(--color-border)', boxShadow: '0 16px 64px rgba(0,0,0,0.5)',
            }} onClick={e => e.stopPropagation()}>
                <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, marginBottom: 'var(--space-6)' }}>
                    Add <span style={{ color: 'var(--color-primary)' }}>Property</span>
                </h2>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                    <div>
                        <label style={labelStyle}>Property ID *</label>
                        <input style={inputStyle} placeholder="e.g. samui-villa-03" value={propertyId}
                               onChange={e => setPropertyId(e.target.value)} />
                    </div>
                    <div>
                        <label style={labelStyle}>Display Name</label>
                        <input style={inputStyle} placeholder="e.g. Villa Sunset 3BR" value={displayName}
                               onChange={e => setDisplayName(e.target.value)} />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                        <div>
                            <label style={labelStyle}>Timezone</label>
                            <select style={inputStyle} value={tz} onChange={e => setTz(e.target.value)}>
                                <option value="Asia/Bangkok">Asia/Bangkok</option>
                                <option value="UTC">UTC</option>
                                <option value="Europe/London">Europe/London</option>
                                <option value="America/New_York">America/New_York</option>
                                <option value="America/Los_Angeles">America/Los_Angeles</option>
                            </select>
                        </div>
                        <div>
                            <label style={labelStyle}>Currency</label>
                            <select style={inputStyle} value={currency} onChange={e => setCurrency(e.target.value)}>
                                <option value="THB">THB</option>
                                <option value="USD">USD</option>
                                <option value="EUR">EUR</option>
                                <option value="GBP">GBP</option>
                                <option value="SGD">SGD</option>
                            </select>
                        </div>
                    </div>
                    <div>
                        <label style={labelStyle}>Listing URL (optional — for future enrichment)</label>
                        <input style={inputStyle} placeholder="https://airbnb.com/rooms/..." value={sourceUrl}
                               onChange={e => setSourceUrl(e.target.value)} />
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 2, display: 'block' }}>
                            URL will be saved. Auto-enrichment coming soon.
                        </span>
                    </div>
                </div>

                {error && (
                    <div style={{
                        marginTop: 'var(--space-4)', padding: 'var(--space-3)',
                        background: '#ef444415', border: '1px solid #ef444433',
                        borderRadius: 'var(--radius-md)', color: '#ef4444',
                        fontSize: 'var(--text-sm)',
                    }}>✗ {error}</div>
                )}

                <div style={{ display: 'flex', gap: 'var(--space-3)', marginTop: 'var(--space-6)', justifyContent: 'flex-end' }}>
                    <button onClick={onClose} style={{
                        padding: 'var(--space-2) var(--space-5)', borderRadius: 'var(--radius-md)',
                        background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                        color: 'var(--color-text)', fontWeight: 600, cursor: 'pointer',
                    }}>Cancel</button>
                    <button onClick={handleSubmit} disabled={saving || !propertyId.trim()} style={{
                        padding: 'var(--space-2) var(--space-5)', borderRadius: 'var(--radius-md)',
                        background: 'var(--color-primary)', border: 'none',
                        color: '#fff', fontWeight: 600, cursor: saving ? 'not-allowed' : 'pointer',
                        opacity: saving || !propertyId.trim() ? 0.6 : 1,
                    }}>{saving ? 'Creating…' : 'Create Property'}</button>
                </div>
            </div>
        </div>
    );
}

/* ------------------------------------------------------------------ */
/* Main page                                                           */
/* ------------------------------------------------------------------ */

function AdminPropertiesContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const [properties, setProperties] = useState<Property[]>([]);
    const [summary, setSummary] = useState<StatusSummary>({ pending: 0, approved: 0, rejected: 0, archived: 0 });
    const [statusFilter, setStatusFilter] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [notice, setNotice] = useState<string | null>(null);

    const showNotice = (msg: string) => {
        setNotice(msg);
        setTimeout(() => setNotice(null), 3000);
    };

    // Toast from redirect after create
    useEffect(() => {
        if (searchParams?.get('created') === '1') showNotice('✓ Property created successfully');
    }, [searchParams]);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const params = statusFilter ? `?status=${statusFilter}` : '';
            const data = await fetchAPI(`/admin/properties${params}`);
            setProperties(data.properties || []);
            if (data.status_summary) setSummary(data.status_summary);
        } catch {
            showNotice('✗ Failed to load properties');
        } finally {
            setLoading(false);
        }
    }, [statusFilter]);

    useEffect(() => { load(); }, [load]);

    const handleAction = async (propertyId: string, action: string) => {
        try {
            await fetchAPI(`/admin/properties/${propertyId}/${action}`, { method: 'POST' });
            showNotice(`✓ Property ${action}d`);
            await load();
        } catch {
            showNotice(`✗ Failed to ${action} property`);
        }
    };

    const filters = [
        { key: null, label: 'All', count: summary.pending + summary.approved },
        { key: 'pending', label: 'Pending', count: summary.pending },
        { key: 'approved', label: 'Approved', count: summary.approved },
        { key: 'rejected', label: 'Rejected', count: summary.rejected },
    ];

    // Phase 397s: Exclude archived and rejected from the default 'All' list
    const visibleProperties = properties.filter(p => {
        if (p.status === 'archived') return false;
        if (!statusFilter && p.status === 'rejected') return false;
        return true;
    });

    return (
        <div style={{ maxWidth: 1100 }}>

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
                        Property <span style={{ color: 'var(--color-primary)' }}>Approvals</span>
                    </h1>
                    <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
                        <button
                            onClick={() => router.push('/admin/properties/new')}
                            style={{
                                background: 'var(--color-primary)',
                                color: '#fff',
                                border: 'none',
                                borderRadius: 'var(--radius-md)',
                                padding: 'var(--space-2) var(--space-5)',
                                fontSize: 'var(--text-sm)',
                                fontWeight: 600,
                                cursor: 'pointer',
                                transition: 'all var(--transition-fast)',
                            }}
                        >
                            + Add Property
                        </button>
                        <button
                            onClick={() => router.push('/admin/intake')}
                            style={{
                                background: '#f59e0b18',
                                color: '#f59e0b',
                                border: '1px solid #f59e0b40',
                                borderRadius: 'var(--radius-md)',
                                padding: 'var(--space-2) var(--space-5)',
                                fontSize: 'var(--text-sm)',
                                fontWeight: 600,
                                cursor: 'pointer',
                                transition: 'all var(--transition-fast)',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6,
                            }}
                        >
                            <span style={{ fontSize: '1.05em' }}>📋</span> Intake Queue
                        </button>
                        <button
                            onClick={() => router.push('/admin/properties/archived')}
                            style={{
                                background: 'none',
                                color: 'var(--color-warn)',
                                border: '1px solid rgba(181,110,69,0.35)',
                                borderRadius: 'var(--radius-md)',
                                padding: 'var(--space-2) var(--space-5)',
                                fontSize: 'var(--text-sm)',
                                fontWeight: 500,
                                cursor: 'pointer',
                            }}
                        >
                            🗄 Archived{summary.archived > 0 ? ` (${summary.archived})` : ''}
                        </button>
                        <button
                            onClick={load}
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

            {/* Status summary cards */}
            <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-6)', flexWrap: 'wrap' }}>
                {filters.map(f => (
                    <div key={f.label} onClick={() => setStatusFilter(f.key)}>
                        <StatCard label={f.label} value={f.count} active={statusFilter === f.key} />
                    </div>
                ))}
            </div>

            {/* Table header */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 100px 100px 90px 180px',
                gap: 'var(--space-3)',
                padding: '0 var(--space-5)',
                marginBottom: 'var(--space-2)',
            }}>
                {['Property', 'Status', 'Created', 'Capacity', 'Actions'].map(h => (
                    <span key={h} style={{
                        fontSize: 'var(--text-xs)',
                        color: 'var(--color-text-faint)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                    }}>{h}</span>
                ))}
            </div>

            {/* Property rows */}
            {loading && visibleProperties.length === 0 ? (
                <div style={{
                    padding: 'var(--space-8)',
                    textAlign: 'center',
                    color: 'var(--color-text-dim)',
                    fontSize: 'var(--text-sm)',
                }}>
                    Loading properties…
                </div>
            ) : visibleProperties.length === 0 ? (
                <div style={{
                    padding: 'var(--space-8)',
                    textAlign: 'center',
                    background: 'var(--color-surface)',
                    borderRadius: 'var(--radius-lg)',
                    border: '1px solid var(--color-border)',
                }}>
                    <div style={{ fontSize: '2em', marginBottom: 'var(--space-3)' }}>🏘️</div>
                    <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                        {statusFilter
                            ? `No ${statusFilter} properties found.`
                            : 'No properties submitted yet. Properties created via the onboarding wizard will appear here.'}
                    </div>
                </div>
            ) : (
                visibleProperties.map(p => (
                    <PropertyRow key={p.property_id} p={p} onAction={handleAction} />
                ))
            )}

            {/* Toast */}
            {notice && (
                <div style={{
                    position: 'fixed',
                    bottom: 'var(--space-6)',
                    right: 'var(--space-6)',
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-md)',
                    padding: 'var(--space-3) var(--space-5)',
                    fontSize: 'var(--text-sm)',
                    color: 'var(--color-text)',
                    boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
                    zIndex: 100,
                }}>{notice}</div>
            )}

            {/* Add Property Modal removed — Phase 844: navigate to /admin/properties/new */}

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
                <span>Domaniqo — Property Admin · Phase 396</span>
                <span>Onboarding: Phase 395 · Admin API: Phase 396</span>
            </div>
        </div>
    );
}

export default function AdminPropertiesPage() {
    return (
        <Suspense fallback={
            <div style={{ padding: 'var(--space-8)', textAlign: 'center', color: 'var(--color-text-dim)' }}>
                Loading properties…
            </div>
        }>
            <AdminPropertiesContent />
        </Suspense>
    );
}
