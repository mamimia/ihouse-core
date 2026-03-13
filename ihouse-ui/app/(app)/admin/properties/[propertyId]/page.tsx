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
    check_in_time: string | null;
    check_out_time: string | null;
    wifi_name: string | null;
    wifi_password: string | null;
    access_code: string | null;
    weekly_discount_pct: number | null;
    monthly_discount_pct: number | null;
}

interface ChannelMap {
    channel_map_id: string;
    property_id: string;
    provider: string;
    external_property_id: string;
    enabled: boolean;
}

/* ------------------------------------------------------------------ */
/* API helpers                                                         */
/* ------------------------------------------------------------------ */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function fetchAPI(path: string, options?: RequestInit) {
    const res = await fetch(`${API_BASE}${path}`, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || res.statusText);
    }
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
            padding: '4px 14px',
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

function FieldGroup({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <div style={{ marginBottom: 'var(--space-5)' }}>
            <label style={{
                display: 'block',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-dim)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                marginBottom: 'var(--space-1)',
                fontWeight: 600,
            }}>{label}</label>
            {children}
        </div>
    );
}

function EditInput({ value, onChange, placeholder, type = 'text' }: {
    value: string;
    onChange: (v: string) => void;
    placeholder?: string;
    type?: string;
}) {
    return (
        <input
            type={type}
            value={value}
            onChange={e => onChange(e.target.value)}
            placeholder={placeholder}
            style={{
                width: '100%',
                background: 'var(--color-surface-2)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-md)',
                padding: 'var(--space-2) var(--space-3)',
                fontSize: 'var(--text-sm)',
                color: 'var(--color-text)',
                outline: 'none',
                transition: 'border var(--transition-fast)',
            }}
        />
    );
}

function ReadField({ label, value }: { label: string; value: string | null | undefined }) {
    return (
        <FieldGroup label={label}>
            <div style={{
                fontSize: 'var(--text-sm)',
                color: value ? 'var(--color-text)' : 'var(--color-text-faint)',
                fontFamily: 'var(--font-mono)',
                padding: 'var(--space-2) 0',
            }}>
                {value || '—'}
            </div>
        </FieldGroup>
    );
}

function SectionTitle({ title, icon }: { title: string; icon: string }) {
    return (
        <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-2)',
            marginBottom: 'var(--space-4)',
            paddingBottom: 'var(--space-2)',
            borderBottom: '1px solid var(--color-border)',
        }}>
            <span style={{ fontSize: '1.2em' }}>{icon}</span>
            <h2 style={{
                fontSize: 'var(--text-lg)',
                fontWeight: 700,
                color: 'var(--color-text)',
                letterSpacing: '-0.02em',
            }}>{title}</h2>
        </div>
    );
}

function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
    return (
        <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--space-6)',
            ...style,
        }}>
            {children}
        </div>
    );
}

/* ------------------------------------------------------------------ */
/* Main page                                                           */
/* ------------------------------------------------------------------ */

export default function PropertyDetailPage() {
    const params = useParams();
    const router = useRouter();
    const propertyId = params?.propertyId as string;

    const [property, setProperty] = useState<Property | null>(null);
    const [channels, setChannels] = useState<ChannelMap[]>([]);
    const [loading, setLoading] = useState(true);
    const [editing, setEditing] = useState(false);
    const [saving, setSaving] = useState(false);
    const [notice, setNotice] = useState<string | null>(null);

    // Editable fields
    const [form, setForm] = useState({
        display_name: '',
        property_type: '',
        city: '',
        country: '',
        address: '',
        description: '',
        timezone: '',
        base_currency: '',
        max_guests: '',
        bedrooms: '',
        beds: '',
        bathrooms: '',
        check_in_time: '',
        check_out_time: '',
        wifi_name: '',
        wifi_password: '',
        access_code: '',
        weekly_discount_pct: '',
        monthly_discount_pct: '',
    });

    const showNotice = (msg: string) => {
        setNotice(msg);
        setTimeout(() => setNotice(null), 4000);
    };

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const data = await fetchAPI(`/admin/properties/${propertyId}`);
            const p = data.property || data;
            setProperty(p);
            setChannels(data.channels || []);
            setForm({
                display_name: p.display_name || '',
                property_type: p.property_type || '',
                city: p.city || '',
                country: p.country || '',
                address: p.address || '',
                description: p.description || '',
                timezone: p.timezone || '',
                base_currency: p.base_currency || '',
                max_guests: p.max_guests?.toString() || '',
                bedrooms: p.bedrooms?.toString() || '',
                beds: p.beds?.toString() || '',
                bathrooms: p.bathrooms?.toString() || '',
                check_in_time: p.check_in_time || '',
                check_out_time: p.check_out_time || '',
                wifi_name: p.wifi_name || '',
                wifi_password: p.wifi_password || '',
                access_code: p.access_code || '',
                weekly_discount_pct: p.weekly_discount_pct?.toString() || '',
                monthly_discount_pct: p.monthly_discount_pct?.toString() || '',
            });
        } catch (err) {
            showNotice(`✗ ${err instanceof Error ? err.message : 'Failed to load property'}`);
        } finally {
            setLoading(false);
        }
    }, [propertyId]);

    useEffect(() => { load(); }, [load]);

    const handleSave = async () => {
        setSaving(true);
        try {
            const patch: Record<string, unknown> = {};
            if (form.display_name) patch.display_name = form.display_name;
            if (form.property_type) patch.property_type = form.property_type;
            if (form.city) patch.city = form.city;
            if (form.country) patch.country = form.country;
            if (form.address) patch.address = form.address;
            if (form.description) patch.description = form.description;
            if (form.timezone) patch.timezone = form.timezone;
            if (form.base_currency) patch.base_currency = form.base_currency;
            if (form.max_guests) patch.max_guests = parseInt(form.max_guests);
            if (form.bedrooms) patch.bedrooms = parseInt(form.bedrooms);
            if (form.beds) patch.beds = parseInt(form.beds);
            if (form.bathrooms) patch.bathrooms = parseInt(form.bathrooms);
            if (form.check_in_time) patch.check_in_time = form.check_in_time;
            if (form.check_out_time) patch.check_out_time = form.check_out_time;
            if (form.wifi_name) patch.wifi_name = form.wifi_name;
            if (form.wifi_password) patch.wifi_password = form.wifi_password;
            if (form.access_code) patch.access_code = form.access_code;
            if (form.weekly_discount_pct) patch.weekly_discount_pct = parseFloat(form.weekly_discount_pct);
            if (form.monthly_discount_pct) patch.monthly_discount_pct = parseFloat(form.monthly_discount_pct);

            await fetchAPI(`/admin/properties/${propertyId}`, {
                method: 'PATCH',
                body: JSON.stringify(patch),
            });
            showNotice('✓ Property updated');
            setEditing(false);
            await load();
        } catch (err) {
            showNotice(`✗ ${err instanceof Error ? err.message : 'Save failed'}`);
        } finally {
            setSaving(false);
        }
    };

    const handleAction = async (action: string) => {
        try {
            await fetchAPI(`/admin/properties/${propertyId}/${action}`, { method: 'POST' });
            showNotice(`✓ Property ${action}d`);
            await load();
        } catch (err) {
            showNotice(`✗ ${err instanceof Error ? err.message : `Failed to ${action}`}`);
        }
    };

    if (loading) {
        return (
            <div style={{
                padding: 'var(--space-12)',
                textAlign: 'center',
                color: 'var(--color-text-dim)',
            }}>
                Loading property…
            </div>
        );
    }

    if (!property) {
        return (
            <div style={{ padding: 'var(--space-12)', textAlign: 'center' }}>
                <div style={{ fontSize: '3em', marginBottom: 'var(--space-4)' }}>🏚️</div>
                <div style={{ color: 'var(--color-text-dim)' }}>Property not found</div>
                <button
                    onClick={() => router.push('/admin/properties')}
                    style={{
                        marginTop: 'var(--space-4)',
                        background: 'var(--color-primary)',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 'var(--radius-md)',
                        padding: 'var(--space-2) var(--space-5)',
                        cursor: 'pointer',
                    }}
                >
                    ← Back to Properties
                </button>
            </div>
        );
    }

    const p = property;
    const created = p.created_at ? new Date(p.created_at).toLocaleDateString('en-US', {
        month: 'long', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
    }) : '—';

    return (
        <div style={{ maxWidth: 960 }}>
            {/* Back + Header */}
            <div style={{ marginBottom: 'var(--space-6)' }}>
                <button
                    onClick={() => router.push('/admin/properties')}
                    style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--color-primary)',
                        fontSize: 'var(--text-sm)',
                        cursor: 'pointer',
                        padding: 0,
                        marginBottom: 'var(--space-3)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--space-1)',
                    }}
                >
                    ← All Properties
                </button>

                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)', flexWrap: 'wrap' }}>
                    <h1 style={{
                        fontSize: 'var(--text-2xl)',
                        fontWeight: 700,
                        letterSpacing: '-0.03em',
                        color: 'var(--color-text)',
                    }}>
                        {p.display_name || p.property_id}
                    </h1>
                    <StatusBadge status={p.status} />
                </div>

                <div style={{
                    display: 'flex',
                    gap: 'var(--space-4)',
                    marginTop: 'var(--space-2)',
                    fontSize: 'var(--text-xs)',
                    color: 'var(--color-text-dim)',
                    fontFamily: 'var(--font-mono)',
                }}>
                    <span>ID: {p.property_id}</span>
                    <span>•</span>
                    <span>Tenant: {p.tenant_id}</span>
                    <span>•</span>
                    <span>Created: {created}</span>
                </div>
            </div>

            {/* Action bar */}
            <div style={{
                display: 'flex',
                gap: 'var(--space-2)',
                marginBottom: 'var(--space-6)',
                flexWrap: 'wrap',
            }}>
                {!editing ? (
                    <button
                        onClick={() => setEditing(true)}
                        style={{
                            background: 'var(--color-primary)',
                            color: '#fff',
                            border: 'none',
                            borderRadius: 'var(--radius-md)',
                            padding: 'var(--space-2) var(--space-5)',
                            fontSize: 'var(--text-sm)',
                            fontWeight: 600,
                            cursor: 'pointer',
                        }}
                    >
                        ✏️ Edit Property
                    </button>
                ) : (
                    <>
                        <button
                            onClick={handleSave}
                            disabled={saving}
                            style={{
                                background: '#22c55e',
                                color: '#fff',
                                border: 'none',
                                borderRadius: 'var(--radius-md)',
                                padding: 'var(--space-2) var(--space-5)',
                                fontSize: 'var(--text-sm)',
                                fontWeight: 600,
                                cursor: saving ? 'not-allowed' : 'pointer',
                                opacity: saving ? 0.7 : 1,
                            }}
                        >
                            {saving ? '⟳ Saving…' : '✓ Save Changes'}
                        </button>
                        <button
                            onClick={() => { setEditing(false); load(); }}
                            style={{
                                background: 'var(--color-surface-2)',
                                color: 'var(--color-text)',
                                border: '1px solid var(--color-border)',
                                borderRadius: 'var(--radius-md)',
                                padding: 'var(--space-2) var(--space-5)',
                                fontSize: 'var(--text-sm)',
                                cursor: 'pointer',
                            }}
                        >
                            Cancel
                        </button>
                    </>
                )}

                {p.status === 'pending' && (
                    <>
                        <button
                            onClick={() => handleAction('approve')}
                            style={{
                                background: '#22c55e15',
                                color: '#22c55e',
                                border: '1px solid #22c55e33',
                                borderRadius: 'var(--radius-md)',
                                padding: 'var(--space-2) var(--space-4)',
                                fontSize: 'var(--text-sm)',
                                fontWeight: 600,
                                cursor: 'pointer',
                            }}
                        >
                            ✓ Approve
                        </button>
                        <button
                            onClick={() => handleAction('reject')}
                            style={{
                                background: '#ef444415',
                                color: '#ef4444',
                                border: '1px solid #ef444433',
                                borderRadius: 'var(--radius-md)',
                                padding: 'var(--space-2) var(--space-4)',
                                fontSize: 'var(--text-sm)',
                                fontWeight: 600,
                                cursor: 'pointer',
                            }}
                        >
                            ✗ Reject
                        </button>
                    </>
                )}

                {p.status === 'approved' && (
                    <button
                        onClick={() => handleAction('archive')}
                        style={{
                            background: '#6b728015',
                            color: '#6b7280',
                            border: '1px solid #6b728033',
                            borderRadius: 'var(--radius-md)',
                            padding: 'var(--space-2) var(--space-4)',
                            fontSize: 'var(--text-sm)',
                            fontWeight: 600,
                            cursor: 'pointer',
                        }}
                    >
                        📦 Archive
                    </button>
                )}
            </div>

            {/* Content grid */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
                gap: 'var(--space-5)',
            }}>
                {/* Basic Info */}
                <Card>
                    <SectionTitle title="Basic Information" icon="🏠" />
                    {editing ? (
                        <>
                            <FieldGroup label="Display Name">
                                <EditInput value={form.display_name} onChange={v => setForm({ ...form, display_name: v })} placeholder="Property name" />
                            </FieldGroup>
                            <FieldGroup label="Property Type">
                                <EditInput value={form.property_type} onChange={v => setForm({ ...form, property_type: v })} placeholder="apartment, villa, house…" />
                            </FieldGroup>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                                <FieldGroup label="City">
                                    <EditInput value={form.city} onChange={v => setForm({ ...form, city: v })} />
                                </FieldGroup>
                                <FieldGroup label="Country">
                                    <EditInput value={form.country} onChange={v => setForm({ ...form, country: v })} />
                                </FieldGroup>
                            </div>
                            <FieldGroup label="Address">
                                <EditInput value={form.address} onChange={v => setForm({ ...form, address: v })} />
                            </FieldGroup>
                            <FieldGroup label="Description">
                                <textarea
                                    value={form.description}
                                    onChange={e => setForm({ ...form, description: e.target.value })}
                                    rows={3}
                                    style={{
                                        width: '100%',
                                        background: 'var(--color-surface-2)',
                                        border: '1px solid var(--color-border)',
                                        borderRadius: 'var(--radius-md)',
                                        padding: 'var(--space-2) var(--space-3)',
                                        fontSize: 'var(--text-sm)',
                                        color: 'var(--color-text)',
                                        resize: 'vertical',
                                        outline: 'none',
                                    }}
                                />
                            </FieldGroup>
                        </>
                    ) : (
                        <>
                            <ReadField label="Display Name" value={p.display_name} />
                            <ReadField label="Property Type" value={p.property_type} />
                            <ReadField label="Location" value={[p.city, p.country].filter(Boolean).join(', ') || null} />
                            <ReadField label="Address" value={p.address} />
                            <ReadField label="Description" value={p.description} />
                        </>
                    )}
                </Card>

                {/* Capacity & Config */}
                <Card>
                    <SectionTitle title="Capacity & Configuration" icon="⚙️" />
                    {editing ? (
                        <>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                                <FieldGroup label="Max Guests">
                                    <EditInput value={form.max_guests} onChange={v => setForm({ ...form, max_guests: v })} type="number" />
                                </FieldGroup>
                                <FieldGroup label="Bedrooms">
                                    <EditInput value={form.bedrooms} onChange={v => setForm({ ...form, bedrooms: v })} type="number" />
                                </FieldGroup>
                                <FieldGroup label="Beds">
                                    <EditInput value={form.beds} onChange={v => setForm({ ...form, beds: v })} type="number" />
                                </FieldGroup>
                                <FieldGroup label="Bathrooms">
                                    <EditInput value={form.bathrooms} onChange={v => setForm({ ...form, bathrooms: v })} type="number" />
                                </FieldGroup>
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                                <FieldGroup label="Timezone">
                                    <EditInput value={form.timezone} onChange={v => setForm({ ...form, timezone: v })} placeholder="Asia/Bangkok" />
                                </FieldGroup>
                                <FieldGroup label="Base Currency">
                                    <EditInput value={form.base_currency} onChange={v => setForm({ ...form, base_currency: v })} placeholder="THB" />
                                </FieldGroup>
                            </div>
                        </>
                    ) : (
                        <>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                                <ReadField label="Max Guests" value={p.max_guests?.toString()} />
                                <ReadField label="Bedrooms" value={p.bedrooms?.toString()} />
                                <ReadField label="Beds" value={p.beds?.toString()} />
                                <ReadField label="Bathrooms" value={p.bathrooms?.toString()} />
                            </div>
                            <ReadField label="Timezone" value={p.timezone} />
                            <ReadField label="Base Currency" value={p.base_currency} />
                        </>
                    )}
                </Card>

                {/* Guest Access */}
                <Card>
                    <SectionTitle title="Guest Access" icon="🔑" />
                    {editing ? (
                        <>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                                <FieldGroup label="Check-in Time">
                                    <EditInput value={form.check_in_time} onChange={v => setForm({ ...form, check_in_time: v })} placeholder="15:00" />
                                </FieldGroup>
                                <FieldGroup label="Check-out Time">
                                    <EditInput value={form.check_out_time} onChange={v => setForm({ ...form, check_out_time: v })} placeholder="11:00" />
                                </FieldGroup>
                            </div>
                            <FieldGroup label="WiFi Name">
                                <EditInput value={form.wifi_name} onChange={v => setForm({ ...form, wifi_name: v })} />
                            </FieldGroup>
                            <FieldGroup label="WiFi Password">
                                <EditInput value={form.wifi_password} onChange={v => setForm({ ...form, wifi_password: v })} />
                            </FieldGroup>
                            <FieldGroup label="Access Code">
                                <EditInput value={form.access_code} onChange={v => setForm({ ...form, access_code: v })} />
                            </FieldGroup>
                        </>
                    ) : (
                        <>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                                <ReadField label="Check-in Time" value={p.check_in_time} />
                                <ReadField label="Check-out Time" value={p.check_out_time} />
                            </div>
                            <ReadField label="WiFi Name" value={p.wifi_name} />
                            <ReadField label="WiFi Password" value={p.wifi_password} />
                            <ReadField label="Access Code" value={p.access_code} />
                        </>
                    )}
                </Card>

                {/* OTA Channels */}
                <Card>
                    <SectionTitle title="OTA Channels" icon="🌐" />
                    {channels.length === 0 ? (
                        <div style={{
                            padding: 'var(--space-6)',
                            textAlign: 'center',
                            color: 'var(--color-text-dim)',
                            fontSize: 'var(--text-sm)',
                        }}>
                            No channels connected yet
                        </div>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                            {channels.map(ch => (
                                <div key={ch.channel_map_id} style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    padding: 'var(--space-3) var(--space-4)',
                                    background: 'var(--color-surface-2)',
                                    borderRadius: 'var(--radius-md)',
                                }}>
                                    <div>
                                        <div style={{
                                            fontWeight: 600,
                                            fontSize: 'var(--text-sm)',
                                            color: 'var(--color-text)',
                                            textTransform: 'capitalize',
                                        }}>
                                            {ch.provider}
                                        </div>
                                        <div style={{
                                            fontSize: 'var(--text-xs)',
                                            color: 'var(--color-text-dim)',
                                            fontFamily: 'var(--font-mono)',
                                        }}>
                                            {ch.external_property_id}
                                        </div>
                                    </div>
                                    <span style={{
                                        fontSize: 'var(--text-xs)',
                                        fontWeight: 600,
                                        padding: '2px 10px',
                                        borderRadius: 'var(--radius-full)',
                                        background: ch.enabled ? '#22c55e15' : '#ef444415',
                                        color: ch.enabled ? '#22c55e' : '#ef4444',
                                        border: `1px solid ${ch.enabled ? '#22c55e33' : '#ef444433'}`,
                                    }}>
                                        {ch.enabled ? 'Active' : 'Disabled'}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </Card>

                {/* Pricing */}
                <Card>
                    <SectionTitle title="Pricing & Discounts" icon="💰" />
                    {editing ? (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                            <FieldGroup label="Weekly Discount %">
                                <EditInput value={form.weekly_discount_pct} onChange={v => setForm({ ...form, weekly_discount_pct: v })} type="number" />
                            </FieldGroup>
                            <FieldGroup label="Monthly Discount %">
                                <EditInput value={form.monthly_discount_pct} onChange={v => setForm({ ...form, monthly_discount_pct: v })} type="number" />
                            </FieldGroup>
                        </div>
                    ) : (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                            <ReadField label="Weekly Discount" value={p.weekly_discount_pct ? `${p.weekly_discount_pct}%` : null} />
                            <ReadField label="Monthly Discount" value={p.monthly_discount_pct ? `${p.monthly_discount_pct}%` : null} />
                        </div>
                    )}
                </Card>

                {/* Admin Info */}
                <Card>
                    <SectionTitle title="Admin Info" icon="📋" />
                    <ReadField label="Source Platform" value={p.source_platform} />
                    <ReadField label="Source URL" value={p.source_url} />
                    {p.approved_at && <ReadField label="Approved At" value={new Date(p.approved_at).toLocaleString()} />}
                    {p.approved_by && <ReadField label="Approved By" value={p.approved_by} />}
                    {p.archived_at && <ReadField label="Archived At" value={new Date(p.archived_at).toLocaleString()} />}
                    {p.archived_by && <ReadField label="Archived By" value={p.archived_by} />}
                </Card>
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
                <span>iHouse Core — Property Detail · Phase 409</span>
                <span>API: GET/PATCH /admin/properties/{'{'}property_id{'}'}</span>
            </div>
        </div>
    );
}
