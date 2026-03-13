'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';

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
    channels?: Channel[];
}

interface Channel {
    provider: string;
    external_channel_id: string;
    active: boolean;
    source_url: string | null;
}

/* ------------------------------------------------------------------ */
/* API helper                                                          */
/* ------------------------------------------------------------------ */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function fetchAPI(path: string, options?: RequestInit) {
    const res = await fetch(`${API_BASE}${path}`, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    return res.json();
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
            padding: '3px 12px',
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

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
    return (
        <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            padding: 'var(--space-3) 0',
            borderBottom: '1px solid var(--color-border)',
        }}>
            <span style={{
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-dim)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                minWidth: 120,
            }}>{label}</span>
            <span style={{
                fontSize: 'var(--text-sm)',
                color: 'var(--color-text)',
                textAlign: 'right',
            }}>{value || '—'}</span>
        </div>
    );
}

function EditField({ label, name, value, onChange, type = 'text' }: {
    label: string;
    name: string;
    value: string;
    onChange: (name: string, value: string) => void;
    type?: string;
}) {
    return (
        <div style={{ marginBottom: 'var(--space-4)' }}>
            <label style={{
                display: 'block',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-dim)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                marginBottom: 'var(--space-1)',
            }}>{label}</label>
            <input
                type={type}
                name={name}
                value={value}
                onChange={(e) => onChange(name, e.target.value)}
                style={{
                    width: '100%',
                    padding: 'var(--space-2) var(--space-3)',
                    fontSize: 'var(--text-sm)',
                    background: 'var(--color-surface-2)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--color-text)',
                    outline: 'none',
                    transition: 'border-color var(--transition-fast)',
                }}
            />
        </div>
    );
}

/* ------------------------------------------------------------------ */
/* Main page                                                           */
/* ------------------------------------------------------------------ */

export default function PropertyDetailPage() {
    const params = useParams();
    const router = useRouter();
    const propertyId = params.id as string;

    const [property, setProperty] = useState<Property | null>(null);
    const [loading, setLoading] = useState(true);
    const [editing, setEditing] = useState(false);
    const [saving, setSaving] = useState(false);
    const [notice, setNotice] = useState<string | null>(null);

    // Edit form state
    const [formData, setFormData] = useState<Record<string, string>>({});

    const showNotice = (msg: string) => {
        setNotice(msg);
        setTimeout(() => setNotice(null), 3000);
    };

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const data = await fetchAPI(`/admin/properties/${propertyId}`);
            if (data.property_id) {
                setProperty(data);
                setFormData({
                    display_name: data.display_name || '',
                    timezone: data.timezone || '',
                    base_currency: data.base_currency || '',
                    property_type: data.property_type || '',
                    city: data.city || '',
                    country: data.country || '',
                    max_guests: data.max_guests?.toString() || '',
                    bedrooms: data.bedrooms?.toString() || '',
                    beds: data.beds?.toString() || '',
                    bathrooms: data.bathrooms?.toString() || '',
                    address: data.address || '',
                    description: data.description || '',
                });
            } else {
                setProperty(null);
            }
        } catch {
            showNotice('✗ Failed to load property');
        } finally {
            setLoading(false);
        }
    }, [propertyId]);

    useEffect(() => { load(); }, [load]);

    const handleFieldChange = (name: string, value: string) => {
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            // Build patch body — only send changed fields
            const patch: Record<string, string | number | null> = {};
            for (const [key, value] of Object.entries(formData)) {
                const original = property?.[key as keyof Property];
                const originalStr = original?.toString() || '';
                if (value !== originalStr) {
                    patch[key] = value || null;
                }
            }

            if (Object.keys(patch).length === 0) {
                showNotice('No changes to save');
                setEditing(false);
                return;
            }

            const result = await fetchAPI(`/admin/properties/${propertyId}`, {
                method: 'PATCH',
                body: JSON.stringify(patch),
            });

            if (result.detail?.property_id) {
                showNotice(`✓ Updated ${result.updated_fields?.length || 0} field(s)`);
                setEditing(false);
                await load();
            } else {
                showNotice('✗ Failed to save changes');
            }
        } catch {
            showNotice('✗ Failed to save changes');
        } finally {
            setSaving(false);
        }
    };

    const handleAction = async (action: string) => {
        try {
            await fetchAPI(`/admin/properties/${propertyId}/${action}`, { method: 'POST' });
            showNotice(`✓ Property ${action}d`);
            await load();
        } catch {
            showNotice(`✗ Failed to ${action} property`);
        }
    };

    const isEditable = property?.status === 'pending' || property?.status === 'approved';

    if (loading) {
        return (
            <div style={{ padding: 'var(--space-8)', textAlign: 'center', color: 'var(--color-text-dim)' }}>
                Loading property…
            </div>
        );
    }

    if (!property) {
        return (
            <div style={{ padding: 'var(--space-8)', textAlign: 'center' }}>
                <div style={{ fontSize: '2em', marginBottom: 'var(--space-3)' }}>🏘️</div>
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                    Property not found.
                </div>
                <button
                    onClick={() => router.push('/admin/properties')}
                    style={{
                        marginTop: 'var(--space-4)',
                        background: 'var(--color-primary)',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 'var(--radius-md)',
                        padding: 'var(--space-2) var(--space-4)',
                        cursor: 'pointer',
                    }}
                >← Back to Properties</button>
            </div>
        );
    }

    return (
        <div style={{ maxWidth: 900 }}>

            {/* Header */}
            <div style={{ marginBottom: 'var(--space-6)' }}>
                <button
                    onClick={() => router.push('/admin/properties')}
                    style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--color-text-dim)',
                        fontSize: 'var(--text-sm)',
                        cursor: 'pointer',
                        padding: 0,
                        marginBottom: 'var(--space-3)',
                    }}
                >← Back to Properties</button>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-4)' }}>
                    <div>
                        <h1 style={{
                            fontSize: 'var(--text-2xl)',
                            fontWeight: 700,
                            color: 'var(--color-text)',
                            letterSpacing: '-0.02em',
                        }}>
                            {property.display_name || property.property_id}
                        </h1>
                        <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center', marginTop: 'var(--space-2)' }}>
                            <StatusBadge status={property.status} />
                            {property.source_platform && (
                                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                                    via {property.source_platform}
                                </span>
                            )}
                        </div>
                    </div>

                    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                        {isEditable && !editing && (
                            <button
                                onClick={() => setEditing(true)}
                                style={{
                                    background: 'var(--color-primary)',
                                    color: '#fff',
                                    border: 'none',
                                    borderRadius: 'var(--radius-md)',
                                    padding: 'var(--space-2) var(--space-4)',
                                    fontSize: 'var(--text-sm)',
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                }}
                            >✏️ Edit</button>
                        )}
                        {property.status === 'pending' && (
                            <>
                                <button
                                    onClick={() => handleAction('approve')}
                                    style={{
                                        background: '#22c55e15',
                                        border: '1px solid #22c55e33',
                                        color: '#22c55e',
                                        borderRadius: 'var(--radius-md)',
                                        padding: 'var(--space-2) var(--space-4)',
                                        fontSize: 'var(--text-sm)',
                                        fontWeight: 600,
                                        cursor: 'pointer',
                                    }}
                                >✓ Approve</button>
                                <button
                                    onClick={() => handleAction('reject')}
                                    style={{
                                        background: '#ef444415',
                                        border: '1px solid #ef444433',
                                        color: '#ef4444',
                                        borderRadius: 'var(--radius-md)',
                                        padding: 'var(--space-2) var(--space-4)',
                                        fontSize: 'var(--text-sm)',
                                        fontWeight: 600,
                                        cursor: 'pointer',
                                    }}
                                >✗ Reject</button>
                            </>
                        )}
                        {property.status === 'approved' && (
                            <button
                                onClick={() => handleAction('archive')}
                                style={{
                                    background: '#6b728015',
                                    border: '1px solid #6b728033',
                                    color: '#6b7280',
                                    borderRadius: 'var(--radius-md)',
                                    padding: 'var(--space-2) var(--space-4)',
                                    fontSize: 'var(--text-sm)',
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                }}
                            >📦 Archive</button>
                        )}
                    </div>
                </div>
            </div>

            {/* Content */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-6)' }}>

                {/* Left column — property info */}
                <div style={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-lg)',
                    padding: 'var(--space-6)',
                }}>
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--space-2)',
                        marginBottom: 'var(--space-4)',
                        paddingBottom: 'var(--space-3)',
                        borderBottom: '1px solid var(--color-border)',
                    }}>
                        <span>🏠</span>
                        <h2 style={{
                            fontSize: 'var(--text-sm)',
                            fontWeight: 600,
                            color: 'var(--color-text-dim)',
                            textTransform: 'uppercase',
                            letterSpacing: '0.08em',
                        }}>Property Details</h2>
                    </div>

                    {editing ? (
                        <>
                            <EditField label="Display Name" name="display_name" value={formData.display_name} onChange={handleFieldChange} />
                            <EditField label="Property Type" name="property_type" value={formData.property_type} onChange={handleFieldChange} />
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                                <EditField label="City" name="city" value={formData.city} onChange={handleFieldChange} />
                                <EditField label="Country" name="country" value={formData.country} onChange={handleFieldChange} />
                            </div>
                            <EditField label="Address" name="address" value={formData.address} onChange={handleFieldChange} />
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                                <EditField label="Timezone" name="timezone" value={formData.timezone} onChange={handleFieldChange} />
                                <EditField label="Currency" name="base_currency" value={formData.base_currency} onChange={handleFieldChange} />
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 'var(--space-3)' }}>
                                <EditField label="Max Guests" name="max_guests" value={formData.max_guests} onChange={handleFieldChange} type="number" />
                                <EditField label="Bedrooms" name="bedrooms" value={formData.bedrooms} onChange={handleFieldChange} type="number" />
                                <EditField label="Beds" name="beds" value={formData.beds} onChange={handleFieldChange} type="number" />
                                <EditField label="Bathrooms" name="bathrooms" value={formData.bathrooms} onChange={handleFieldChange} type="number" />
                            </div>
                            <div style={{ marginBottom: 'var(--space-4)' }}>
                                <label style={{
                                    display: 'block',
                                    fontSize: 'var(--text-xs)',
                                    color: 'var(--color-text-dim)',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.06em',
                                    marginBottom: 'var(--space-1)',
                                }}>Description</label>
                                <textarea
                                    value={formData.description}
                                    onChange={(e) => handleFieldChange('description', e.target.value)}
                                    rows={4}
                                    style={{
                                        width: '100%',
                                        padding: 'var(--space-2) var(--space-3)',
                                        fontSize: 'var(--text-sm)',
                                        background: 'var(--color-surface-2)',
                                        border: '1px solid var(--color-border)',
                                        borderRadius: 'var(--radius-md)',
                                        color: 'var(--color-text)',
                                        outline: 'none',
                                        resize: 'vertical',
                                    }}
                                />
                            </div>

                            <div style={{ display: 'flex', gap: 'var(--space-3)', marginTop: 'var(--space-4)' }}>
                                <button
                                    onClick={handleSave}
                                    disabled={saving}
                                    style={{
                                        background: 'var(--color-primary)',
                                        color: '#fff',
                                        border: 'none',
                                        borderRadius: 'var(--radius-md)',
                                        padding: 'var(--space-2) var(--space-5)',
                                        fontSize: 'var(--text-sm)',
                                        fontWeight: 600,
                                        cursor: saving ? 'not-allowed' : 'pointer',
                                        opacity: saving ? 0.7 : 1,
                                    }}
                                >{saving ? 'Saving…' : '💾 Save Changes'}</button>
                                <button
                                    onClick={() => { setEditing(false); load(); }}
                                    style={{
                                        background: 'var(--color-surface-3)',
                                        color: 'var(--color-text)',
                                        border: '1px solid var(--color-border)',
                                        borderRadius: 'var(--radius-md)',
                                        padding: 'var(--space-2) var(--space-5)',
                                        fontSize: 'var(--text-sm)',
                                        cursor: 'pointer',
                                    }}
                                >Cancel</button>
                            </div>
                        </>
                    ) : (
                        <>
                            <InfoRow label="Property ID" value={<code style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)' }}>{property.property_id}</code>} />
                            <InfoRow label="Type" value={property.property_type} />
                            <InfoRow label="Location" value={[property.city, property.country].filter(Boolean).join(', ') || null} />
                            <InfoRow label="Address" value={property.address} />
                            <InfoRow label="Timezone" value={property.timezone} />
                            <InfoRow label="Currency" value={property.base_currency} />
                            <InfoRow label="Max Guests" value={property.max_guests} />
                            <InfoRow label="Bedrooms" value={property.bedrooms} />
                            <InfoRow label="Beds" value={property.beds} />
                            <InfoRow label="Bathrooms" value={property.bathrooms} />
                            <InfoRow label="Description" value={property.description} />
                            {property.source_url && (
                                <InfoRow label="Source URL" value={
                                    <a href={property.source_url} target="_blank" rel="noopener noreferrer"
                                        style={{ color: 'var(--color-primary)', textDecoration: 'none', fontSize: 'var(--text-xs)' }}>
                                        {property.source_url.substring(0, 50)}…
                                    </a>
                                } />
                            )}
                        </>
                    )}
                </div>

                {/* Right column — channels + lifecycle */}
                <div>
                    {/* Channel map */}
                    <div style={{
                        background: 'var(--color-surface)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-lg)',
                        padding: 'var(--space-6)',
                        marginBottom: 'var(--space-6)',
                    }}>
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--space-2)',
                            marginBottom: 'var(--space-4)',
                            paddingBottom: 'var(--space-3)',
                            borderBottom: '1px solid var(--color-border)',
                        }}>
                            <span>🔗</span>
                            <h2 style={{
                                fontSize: 'var(--text-sm)',
                                fontWeight: 600,
                                color: 'var(--color-text-dim)',
                                textTransform: 'uppercase',
                                letterSpacing: '0.08em',
                            }}>OTA Channels</h2>
                        </div>

                        {(property.channels?.length ?? 0) === 0 ? (
                            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                                No channels mapped yet.
                            </p>
                        ) : (
                            property.channels?.map((ch, i) => (
                                <div key={i} style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    padding: 'var(--space-3) var(--space-4)',
                                    background: 'var(--color-surface-2)',
                                    borderRadius: 'var(--radius-md)',
                                    marginBottom: 'var(--space-2)',
                                }}>
                                    <div>
                                        <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
                                            {ch.provider}
                                        </span>
                                        <span style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-xs)', marginLeft: 'var(--space-2)' }}>
                                            {ch.external_channel_id}
                                        </span>
                                    </div>
                                    <span style={{
                                        fontSize: 'var(--text-xs)',
                                        fontWeight: 700,
                                        padding: '2px 8px',
                                        borderRadius: 'var(--radius-full)',
                                        background: ch.active ? '#22c55e15' : '#ef444415',
                                        color: ch.active ? '#22c55e' : '#ef4444',
                                        border: `1px solid ${ch.active ? '#22c55e33' : '#ef444433'}`,
                                    }}>{ch.active ? 'ACTIVE' : 'INACTIVE'}</span>
                                </div>
                            ))
                        )}
                    </div>

                    {/* Lifecycle info */}
                    <div style={{
                        background: 'var(--color-surface)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-lg)',
                        padding: 'var(--space-6)',
                    }}>
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--space-2)',
                            marginBottom: 'var(--space-4)',
                            paddingBottom: 'var(--space-3)',
                            borderBottom: '1px solid var(--color-border)',
                        }}>
                            <span>📋</span>
                            <h2 style={{
                                fontSize: 'var(--text-sm)',
                                fontWeight: 600,
                                color: 'var(--color-text-dim)',
                                textTransform: 'uppercase',
                                letterSpacing: '0.08em',
                            }}>Lifecycle</h2>
                        </div>
                        <InfoRow label="Created" value={property.created_at ? new Date(property.created_at).toLocaleString() : null} />
                        {property.approved_at && <InfoRow label="Approved" value={new Date(property.approved_at).toLocaleString()} />}
                        {property.approved_by && <InfoRow label="Approved By" value={property.approved_by} />}
                        {property.archived_at && <InfoRow label="Archived" value={new Date(property.archived_at).toLocaleString()} />}
                        {property.archived_by && <InfoRow label="Archived By" value={property.archived_by} />}
                    </div>
                </div>
            </div>

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
                <span>iHouse Core — Property Detail · Phase 397</span>
                <span>Admin API: Phase 396 · Detail/Edit: Phase 397</span>
            </div>
        </div>
    );
}
