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
    // Phase 1019: Self Check-in mode
    self_checkin_config?: { mode?: string } | null;
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

// ---------------------------------------------------------------------------
// Phase 1019 — Self Check-in mode badge
// ---------------------------------------------------------------------------

const CHECKIN_MODE_BADGE: Record<string, { label: string; bg: string; text: string; border: string }> = {
    default:  { label: '🔓 Self Check-in', bg: '#6366f115', text: '#6366f1', border: '#6366f133' },
    late_only:{ label: '🌙 Late Only',      bg: '#f59e0b15', text: '#d97706', border: '#f59e0b33' },
    disabled: { label: '👤 Staffed',         bg: '#6b728015', text: '#6b7280', border: '#6b728033' },
};

function CheckinModeBadge({ mode }: { mode?: string | null }) {
    const m = mode || 'disabled';
    const cfg = CHECKIN_MODE_BADGE[m] || CHECKIN_MODE_BADGE.disabled;
    return (
        <span style={{
            display: 'inline-block', padding: '2px 8px', borderRadius: 10,
            background: cfg.bg, color: cfg.text, border: `1px solid ${cfg.border}`,
            fontSize: 10, fontWeight: 700, letterSpacing: '0.03em', whiteSpace: 'nowrap',
        }}>
            {cfg.label}
        </span>
    );
}

// ---------------------------------------------------------------------------
// Phase 1019b — Property Status Guide modal
// ---------------------------------------------------------------------------

const PROPERTY_STATUS_GUIDE = [
    {
        label: 'Approved',
        bg: '#22c55e15', color: '#22c55e', border: '#22c55e33',
        desc: 'Property is live and fully operational. Bookings and tasks are being managed.',
    },
    {
        label: 'Pending',
        bg: '#f59e0b15', color: '#f59e0b', border: '#f59e0b33',
        desc: 'Property has been submitted and awaits admin review before going live.',
    },
    {
        label: 'Rejected',
        bg: '#ef444415', color: '#ef4444', border: '#ef444433',
        desc: 'Property was reviewed and not approved. Can be resubmitted after corrections.',
    },
    {
        label: 'Archived',
        bg: '#6b728015', color: '#6b7280', border: '#6b728033',
        desc: 'Property has been deactivated. No new bookings. Historical data is preserved.',
    },
];

const CHECKIN_MODE_GUIDE = [
    {
        label: '🔓 Self Check-in',
        bg: '#6366f115', color: '#6366f1', border: '#6366f133',
        desc: 'Default check-in mode. All bookings use self check-in. Guest portal link sent automatically before arrival.',
    },
    {
        label: '🌙 Late Only',
        bg: '#f59e0b15', color: '#d97706', border: '#f59e0b33',
        desc: 'Property normally uses staffed check-in. Self check-in is available only as an exception for guests arriving outside staffed hours.',
    },
    {
        label: '👤 Staffed',
        bg: '#6b728015', color: '#6b7280', border: '#6b728033',
        desc: 'All check-ins are handled by staff. No self check-in portal is issued to guests.',
    },
];

function PropertyStatusGuide() {
    const [open, setOpen] = useState(false);

    return (
        <>
            <button
                id="property-status-guide-btn"
                onClick={() => setOpen(o => !o)}
                aria-expanded={open}
                title="What do these badges mean?"
                style={{
                    background: open ? 'var(--color-surface-3)' : 'var(--color-surface-2)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-full)', color: 'var(--color-text-dim)',
                    fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer',
                    padding: '3px 10px', display: 'flex', alignItems: 'center', gap: 4,
                    transition: 'background var(--transition-fast)',
                }}
            >ⓘ Property Guide</button>

            {open && (
                <div
                    onClick={() => setOpen(false)}
                    style={{
                        position: 'fixed', inset: 0, zIndex: 1000,
                        background: 'rgba(0,0,0,0.45)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        padding: '16px',
                    }}
                >
                    <div
                        onClick={e => e.stopPropagation()}
                        role="dialog"
                        aria-modal="true"
                        aria-label="Property Status Guide"
                        style={{
                            background: 'var(--color-surface)',
                            border: '1px solid var(--color-border)',
                            borderRadius: 'var(--radius-xl)',
                            width: '100%', maxWidth: 500,
                            maxHeight: 'calc(100vh - 48px)',
                            overflowY: 'auto',
                            boxShadow: '0 24px 64px rgba(0,0,0,0.6)',
                            padding: 'var(--space-5)',
                        }}
                    >
                        {/* Header */}
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-4)' }}>
                            <span style={{ fontWeight: 700, fontSize: 'var(--text-base)', color: 'var(--color-text)' }}>
                                Property Status Guide
                            </span>
                            <button
                                id="property-guide-close"
                                onClick={() => setOpen(false)}
                                aria-label="Close"
                                style={{
                                    background: 'none', border: 'none', cursor: 'pointer',
                                    color: 'var(--color-text-dim)', fontSize: '1.2rem', lineHeight: 1,
                                    padding: '2px 6px', borderRadius: 'var(--radius-md)',
                                }}
                            >✕</button>
                        </div>

                        {/* Property Statuses */}
                        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
                            Property Status
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)', marginBottom: 'var(--space-5)' }}>
                            {PROPERTY_STATUS_GUIDE.map(s => (
                                <div key={s.label} style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-start' }}>
                                    <span style={{
                                        fontSize: 'var(--text-xs)', fontWeight: 700, whiteSpace: 'nowrap',
                                        background: s.bg, color: s.color, border: `1px solid ${s.border}`,
                                        borderRadius: 'var(--radius-full)', padding: '3px 10px',
                                        flexShrink: 0, minWidth: 80, textAlign: 'center',
                                        textTransform: 'uppercase', letterSpacing: '0.05em',
                                        fontFamily: 'var(--font-mono)',
                                    }}>{s.label}</span>
                                    <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', lineHeight: 1.55 }}>{s.desc}</span>
                                </div>
                            ))}
                        </div>

                        {/* Divider */}
                        <div style={{ borderTop: '1px solid var(--color-border)', marginBottom: 'var(--space-4)' }} />

                        {/* Check-in Mode */}
                        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
                            Check-in Mode
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
                            {CHECKIN_MODE_GUIDE.map(m => (
                                <div key={m.label} style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-start' }}>
                                    <span style={{
                                        fontSize: 10, fontWeight: 700, whiteSpace: 'nowrap',
                                        background: m.bg, color: m.color, border: `1px solid ${m.border}`,
                                        borderRadius: 10, padding: '3px 8px',
                                        flexShrink: 0, minWidth: 100, textAlign: 'center',
                                    }}>{m.label}</span>
                                    <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', lineHeight: 1.55 }}>{m.desc}</span>
                                </div>
                            ))}
                        </div>

                        {/* Footer */}
                        <div style={{
                            marginTop: 'var(--space-3)', paddingTop: 'var(--space-3)',
                            borderTop: '1px solid var(--color-border)',
                            fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', lineHeight: 1.5,
                        }}>
                            Check-in mode is configured per-property under Settings → Self Check-in.
                            Properties default to Staffed until configured.
                        </div>
                    </div>
                </div>
            )}
        </>
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
            gridTemplateColumns: '1fr 100px 120px 90px 180px',
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

            {/* Check-in Mode — Phase 1019b: dedicated column */}
            <div><CheckinModeBadge mode={p.self_checkin_config?.mode} /></div>

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

    // Phase 954s: Real Intake Queue Count across boundaries (un-scoped to admin tenant)
    const [intakeCount, setIntakeCount] = useState<number>(0);

    const showNotice = (msg: string) => {
        setNotice(msg);
        setTimeout(() => setNotice(null), 3000);
    };

    // Toast from redirect after create
    useEffect(() => {
        if (searchParams?.get('created') === '1') showNotice('✓ Property created successfully');
    }, [searchParams]);

    const loadIntakeCount = useCallback(async () => {
        try {
            const token = typeof window !== 'undefined' ? document.cookie.split('; ').find(c => c.startsWith('ihouse_token='))?.split('=')[1] ?? '' : '';
            if (!token) return;
            const res = await fetch(`/api/admin/intake?status=pending_review`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setIntakeCount(data.count || 0);
            }
        } catch { /* non-fatal, fail silently */ }
    }, []);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const params = statusFilter ? `?status=${statusFilter}` : '';
            const data = await fetchAPI(`/admin/properties${params}`);
            setProperties(data.properties || []);
            if (data.status_summary) setSummary(data.status_summary);

            // Phase 954s: Fetch actual Intake Queue count independent of tenant scoping
            await loadIntakeCount();
        } catch {
            showNotice('✗ Failed to load properties');
        } finally {
            setLoading(false);
        }
    }, [statusFilter, loadIntakeCount]);

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
                        {/* Phase 1019b: Property Status Guide */}
                        <PropertyStatusGuide />
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

                {/* Phase 953s/954s: Actionable Stat Cards for Queues */}
                <div onClick={() => router.push('/admin/intake')}>
                    <StatCard label="Intake Queue" value={intakeCount} active={false} />
                </div>
                <div onClick={() => router.push('/admin/properties/archived')}>
                    <StatCard label="Archive" value={summary.archived} active={false} />
                </div>
            </div>

            {/* Table header */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 100px 120px 90px 180px',
                gap: 'var(--space-3)',
                padding: '0 var(--space-5)',
                marginBottom: 'var(--space-2)',
            }}>
                {['Property', 'Status', 'Check-in Mode', 'Created', 'Actions'].map(h => (
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
