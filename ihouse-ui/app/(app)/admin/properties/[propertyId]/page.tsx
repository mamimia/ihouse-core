'use client';

/**
 * Operational Core — Phase A: Property Detail (6-Tab View)
 * Architecture source: .agent/architecture/property-detail.md
 *
 * Tabs: Overview | Reference Photos | House Info | Tasks | Issues | Audit
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getToken } from '@/lib/api';
import { uploadPropertyPhoto, ACCEPTED_IMAGE_TYPES } from '@/lib/uploadPhoto';
import OtaSettingsTab from './OtaSettingsTab';

type Tab = 'overview' | 'photos' | 'house-info' | 'tasks' | 'issues' | 'audit' | 'edit' | 'gallery' | 'ota';

const TAB_LABELS: Record<Tab, string> = {
    overview: 'Overview',
    photos: 'Reference Photos',
    'house-info': 'House Info',
    tasks: 'Tasks',
    issues: 'Issues',
    audit: 'Audit',
    edit: '✎ Edit Details',
    gallery: '🖼 Gallery',
    ota: '📡 OTA Settings',
};

const BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

async function apiFetch<T = any>(path: string, init?: RequestInit): Promise<T> {
    const token = getToken();
    const res = await fetch(`${BASE}${path}`, {
        ...init,
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(init?.headers || {}),
        },
    });
    if (!res.ok) throw new Error(`${res.status}`);
    return res.json();
}

// Status badge component
function StatusBadge({ status }: { status?: string }) {
    const colors: Record<string, { bg: string; text: string; border: string }> = {
        available: { bg: 'rgba(46,160,67,0.12)', text: '#3fb950', border: '#23863630' },
        occupied: { bg: 'rgba(130,80,223,0.12)', text: '#a371f7', border: '#8b5cf630' },
        cleaning: { bg: 'rgba(56,158,214,0.12)', text: '#58a6ff', border: '#388bfd30' },
        ready: { bg: 'rgba(46,160,67,0.18)', text: '#3fb950', border: '#3fb95040' },
        atrisk: { bg: 'rgba(210,153,34,0.18)', text: '#d29922', border: '#d2992240' },
        blocked: { bg: 'rgba(248,81,73,0.18)', text: '#f85149', border: '#f8514940' },
        archived: { bg: 'rgba(110,118,129,0.12)', text: '#8b949e', border: '#8b949e30' },
    };
    const s = (status || 'available').toLowerCase().replace(/[\s_-]/g, '');
    const c = colors[s] || colors.available;
    return (
        <span style={{
            display: 'inline-block', padding: '2px 10px', borderRadius: 12,
            background: c.bg, color: c.text, border: `1px solid ${c.border}`,
            fontSize: 'var(--text-xs)', fontWeight: 600, textTransform: 'capitalize',
        }}>
            {status || 'Available'}
        </span>
    );
}

// Editable field component for House Info
function EditableField({ label, value, fieldKey, onSave }: {
    label: string; value: string; fieldKey: string;
    onSave: (key: string, val: string) => void;
}) {
    const [editing, setEditing] = useState(false);
    const [v, setV] = useState(value || '');
    useEffect(() => setV(value || ''), [value]);

    if (editing) {
        return (
            <div style={{ background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3)' }}>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 4 }}>{label}</div>
                <input
                    value={v} onChange={e => setV(e.target.value)} autoFocus
                    onKeyDown={e => { if (e.key === 'Enter') { onSave(fieldKey, v); setEditing(false); } if (e.key === 'Escape') setEditing(false); }}
                    style={{
                        width: '100%', background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-sm)', padding: '6px 10px', color: 'var(--color-text)',
                        fontSize: 'var(--text-sm)', outline: 'none',
                    }}
                />
                <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                    <button onClick={() => { onSave(fieldKey, v); setEditing(false); }}
                        style={{ fontSize: 'var(--text-xs)', padding: '3px 10px', background: 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer' }}>Save</button>
                    <button onClick={() => setEditing(false)}
                        style={{ fontSize: 'var(--text-xs)', padding: '3px 10px', background: 'transparent', color: 'var(--color-text-dim)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', cursor: 'pointer' }}>Cancel</button>
                </div>
            </div>
        );
    }

    return (
        <div onClick={() => setEditing(true)} style={{
            background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3)',
            cursor: 'pointer', transition: 'border-color 0.15s', border: '1px solid transparent',
        }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}
            onMouseLeave={e => (e.currentTarget.style.borderColor = 'transparent')}>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 2 }}>{label}</div>
            <div style={{ fontSize: 'var(--text-sm)', color: v ? 'var(--color-text)' : 'var(--color-text-faint)', fontStyle: v ? 'normal' : 'italic' }}>
                {v || 'Click to set'}
            </div>
        </div>
    );
}

export default function PropertyDetailPage() {
    const params = useParams();
    const router = useRouter();
    const propertyId = params?.propertyId as string;
    const [tab, setTab] = useState<Tab>('overview');
    const [property, setProperty] = useState<any>(null);
    const [photos, setPhotos] = useState<any[]>([]);
    const [galleryPhotos, setGalleryPhotos] = useState<any[]>([]);
    const [tasks, setTasks] = useState<any[]>([]);
    const [auditEntries, setAuditEntries] = useState<any[]>([]);
    const [issues, setIssues] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [notice, setNotice] = useState<string | null>(null);

    // Edit Details tab — structured form state (Phase 844)
    const [editDisplayName, setEditDisplayName] = useState('');
    const [editPropertyType, setEditPropertyType] = useState('');
    const [editCity, setEditCity] = useState('');
    const [editCountry, setEditCountry] = useState('');
    const [editAddress, setEditAddress] = useState('');
    const [editLat, setEditLat] = useState('');
    const [editLng, setEditLng] = useState('');
    const [editBedrooms, setEditBedrooms] = useState('');
    const [editBeds, setEditBeds] = useState('');
    const [editBathrooms, setEditBathrooms] = useState('');
    const [editMaxGuests, setEditMaxGuests] = useState('');
    const [editCheckinTime, setEditCheckinTime] = useState('');
    const [editCheckoutTime, setEditCheckoutTime] = useState('');
    const [editDescription, setEditDescription] = useState('');
    const [editSourceUrl, setEditSourceUrl] = useState('');
    // Deposit fields (Phase 844 correction)
    const [editDepositRequired, setEditDepositRequired] = useState(false);
    const [editDepositAmount, setEditDepositAmount] = useState('');
    const [editDepositCurrency, setEditDepositCurrency] = useState('THB');
    // Geolocation feedback
    const [geoStatus, setGeoStatus] = useState<'idle' | 'loading' | 'ok' | 'err'>('idle');
    const [editSaving, setEditSaving] = useState(false);
    // Gallery (marketing photos) — Phase 844
    const [galleryUrl, setGalleryUrl] = useState('');
    const [galleryCaption, setGalleryCaption] = useState('');
    const [galleryAdding, setGalleryAdding] = useState(false);
    const [galleryUploading, setGalleryUploading] = useState(false);
    const galleryFileRef = useRef<HTMLInputElement>(null);
    // Reference photo add — Phase 844 (file upload + URL fallback)
    const [refPhotoUrl, setRefPhotoUrl] = useState('');
    const [refPhotoRoom, setRefPhotoRoom] = useState('living-room');
    const [refPhotoAdding, setRefPhotoAdding] = useState(false);
    const [refPhotoUploading, setRefPhotoUploading] = useState(false);
    const refFileRef = useRef<HTMLInputElement>(null);
    // House Rules — Phase 844
    const [editHouseRules, setEditHouseRules] = useState<string[]>([]);
    const [newRule, setNewRule] = useState('');
    // Owner Contact Snapshot — Phase 844
    const [editOwnerPhone, setEditOwnerPhone] = useState('');
    const [editOwnerEmail, setEditOwnerEmail] = useState('');
    // Amenities — Phase 844
    const [editAmenities, setEditAmenities] = useState<string[]>([]);
    // Listing URL Pull — Phase 844 v3
    const [listingPulling, setListingPulling] = useState(false);
    const [listingResult, setListingResult] = useState<null | { imported: Record<string, any>, could_not_import: string[], warning?: string }>(null);

    const showNotice = (msg: string) => { setNotice(msg); setTimeout(() => setNotice(null), 3000); };

    // Archive / Unarchive
    const [archiving, setArchiving] = useState(false);
    const handleArchive = async () => {
        if (!confirm('Archive this property? It will be hidden from all active lists.')) return;
        setArchiving(true);
        try {
            await apiFetch(`/properties/${propertyId}/archive`, { method: 'POST' });
            router.push('/admin/properties');
        } catch { showNotice('Archive failed'); }
        setArchiving(false);
    };
    const handleUnarchive = async () => {
        setArchiving(true);
        try {
            await apiFetch(`/properties/${propertyId}/unarchive`, { method: 'POST' });
            await load(); // reload page — property returns to approved status
            showNotice('✓ Property restored to active');
        } catch { showNotice('Unarchive failed'); }
        setArchiving(false);
    };

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [propRes, photosRes, galleryRes, tasksRes, auditRes, issuesRes] = await Promise.allSettled([
                apiFetch(`/properties/${propertyId}`),
                apiFetch(`/properties/${propertyId}/reference-photos`),
                apiFetch(`/properties/${propertyId}/marketing-photos`),
                apiFetch(`/tasks?property_id=${propertyId}&limit=50`),
                apiFetch(`/admin/audit?entity_id=${propertyId}&limit=100`),
                apiFetch(`/problem-reports?property_id=${propertyId}&limit=50`),
            ]);
            if (propRes.status === 'fulfilled') {
                const pp = propRes.value;
                setProperty(pp);
                // Pre-fill Edit Details form
                setEditDisplayName(pp.display_name || '');
                setEditPropertyType(pp.property_type || '');
                setEditCity(pp.city || '');
                setEditCountry(pp.country || '');
                setEditAddress(pp.address || '');
                setEditLat(pp.latitude != null ? String(pp.latitude) : '');
                setEditLng(pp.longitude != null ? String(pp.longitude) : '');
                setEditBedrooms(pp.bedrooms != null ? String(pp.bedrooms) : '');
                setEditBeds(pp.beds != null ? String(pp.beds) : '');
                setEditBathrooms(pp.bathrooms != null ? String(pp.bathrooms) : '');
                setEditMaxGuests(pp.max_guests != null ? String(pp.max_guests) : '');
                setEditCheckinTime(pp.checkin_time || '15:00');
                setEditCheckoutTime(pp.checkout_time || '11:00');
                setEditDescription(pp.description || '');
                setEditSourceUrl(pp.source_url || '');
                // Deposit (Phase 844)
                setEditDepositRequired(!!pp.deposit_required);
                setEditDepositAmount(pp.deposit_amount != null ? String(pp.deposit_amount) : '');
                setEditDepositCurrency(pp.deposit_currency || 'THB');
                // House Rules, Owner Contact, Amenities (Phase 844 v2)
                setEditHouseRules(Array.isArray(pp.house_rules) ? pp.house_rules : []);
                setEditOwnerPhone(pp.owner_phone || '');
                setEditOwnerEmail(pp.owner_email || '');
                setEditAmenities(Array.isArray(pp.amenities) ? pp.amenities : []);
            }
            if (photosRes.status === 'fulfilled') setPhotos(photosRes.value?.photos || []);
            if (galleryRes.status === 'fulfilled') setGalleryPhotos(galleryRes.value?.photos || []);
            if (tasksRes.status === 'fulfilled') {
                const all = tasksRes.value?.tasks || [];
                setTasks(all.filter((t: any) => t.property_id === propertyId));
            }
            if (auditRes.status === 'fulfilled') setAuditEntries(auditRes.value?.entries || auditRes.value?.events || []);
            if (issuesRes.status === 'fulfilled') setIssues(issuesRes.value?.reports || issuesRes.value?.data || []);
        } catch { /* graceful */ }
        setLoading(false);
    }, [propertyId]);

    useEffect(() => { load(); }, [load]);

    const saveField = async (key: string, value: any) => {
        setSaving(true);
        try {
            const updated = await apiFetch(`/properties/${propertyId}`, {
                method: 'PATCH',
                body: JSON.stringify({ [key]: value }),
            });
            setProperty(updated);
            showNotice(`${key} saved`);
        } catch { showNotice('Save failed'); }
        setSaving(false);
    };

    const tabStyle = (t: Tab) => ({
        padding: 'var(--space-2) var(--space-4)',
        fontSize: 'var(--text-sm)',
        fontWeight: tab === t ? 600 : 400,
        color: tab === t ? 'var(--color-primary)' : 'var(--color-text-dim)',
        borderBottom: tab === t ? '2px solid var(--color-primary)' : '2px solid transparent',
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        whiteSpace: 'nowrap' as const,
    });

    const cardStyle = {
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)',
        padding: 'var(--space-5)',
    };

    const p = property || {};

    return (
        <div style={{ maxWidth: 1100 }}>
            {/* Notice toast */}
            {notice && (
                <div style={{
                    position: 'fixed', top: 20, right: 20, zIndex: 999,
                    background: 'var(--color-surface)', border: '1px solid var(--color-primary)',
                    borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)',
                    fontSize: 'var(--text-sm)', color: 'var(--color-primary)', boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
                }}>
                    {notice}
                </div>
            )}

            {/* Archived banner */}
            {p.status === 'archived' && (
                <div style={{
                    background: 'rgba(181,110,69,0.1)', border: '1px solid rgba(181,110,69,0.4)',
                    borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)',
                    marginBottom: 'var(--space-4)', display: 'flex', alignItems: 'center',
                    justifyContent: 'space-between', gap: 'var(--space-4)',
                }}>
                    <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-warn)', fontWeight: 600 }}>
                        ⚠ This property is archived — hidden from all active lists, owners linking, and task assignment.
                    </span>
                    <button
                        onClick={handleUnarchive}
                        disabled={archiving}
                        style={{
                            background: 'var(--color-warn)', color: '#fff', border: 'none',
                            borderRadius: 'var(--radius-md)', padding: '6px 16px',
                            fontSize: 'var(--text-xs)', fontWeight: 700, cursor: archiving ? 'not-allowed' : 'pointer',
                            flexShrink: 0,
                        }}
                    >{archiving ? 'Restoring…' : '↩ Unarchive Property'}</button>
                </div>
            )}

            {/* Header */}
            <div style={{ marginBottom: 'var(--space-4)', display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
                <button onClick={() => router.push('/admin/properties')} style={{
                    background: 'none', border: 'none', color: 'var(--color-text-dim)', cursor: 'pointer',
                    fontSize: 'var(--text-lg)', padding: 0,
                }}>←</button>

                {/* Hero thumbnail — uses cover_photo_url, falls back to first gallery photo */}
                <div style={{
                    width: 56, height: 56, borderRadius: 'var(--radius-md)', flexShrink: 0,
                    overflow: 'hidden', border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                    {(p.cover_photo_url || (galleryPhotos.length > 0 && galleryPhotos[0].photo_url)) ? (
                        <img src={p.cover_photo_url || galleryPhotos[0].photo_url} alt="Property hero" style={{ width: '100%', height: '100%', objectFit: 'cover' }} onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }} />
                    ) : (
                        <span style={{ fontSize: 24, opacity: 0.4 }}>🏠</span>
                    )}
                </div>

                <div style={{ flex: 1 }}>
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>
                        Property Detail
                    </p>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                        <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text)', letterSpacing: '-0.03em', margin: 0 }}>
                            {p.display_name || propertyId}
                        </h1>
                        <StatusBadge status={p.status} />
                    </div>
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                        {propertyId}
                    </p>
                </div>
                {p.latitude && p.longitude && (
                    <a href={`https://maps.google.com/?q=${p.latitude},${p.longitude}`} target="_blank" rel="noopener"
                        style={{
                            padding: 'var(--space-2) var(--space-4)', borderRadius: 'var(--radius-md)',
                            background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                            color: 'var(--color-text)', fontSize: 'var(--text-xs)', textDecoration: 'none', fontWeight: 500,
                        }}>
                        📍 Open in Maps
                    </a>
                )}
                {/* Add Booking button */}
                <button
                    onClick={() => router.push(`/admin/bookings/intake?property=${propertyId}`)}
                    style={{
                        padding: 'var(--space-2) var(--space-4)', borderRadius: 'var(--radius-md)',
                        background: 'var(--color-primary)', border: 'none',
                        color: '#fff', fontSize: 'var(--text-xs)', cursor: 'pointer', fontWeight: 600,
                    }}
                >✍️ Add Booking</button>
                {/* Archive / Unarchive button */}
                {p.status !== 'archived' ? (
                    <button
                        onClick={handleArchive}
                        disabled={archiving}
                        style={{
                            padding: 'var(--space-2) var(--space-4)', borderRadius: 'var(--radius-md)',
                            background: 'none', border: '1px solid var(--color-border)',
                            color: 'var(--color-text-faint)', fontSize: 'var(--text-xs)', cursor: 'pointer', fontWeight: 500,
                        }}
                    >{archiving ? '…' : '🗄 Archive'}</button>
                ) : (
                    <button
                        onClick={handleUnarchive}
                        disabled={archiving}
                        style={{
                            padding: 'var(--space-2) var(--space-4)', borderRadius: 'var(--radius-md)',
                            background: 'rgba(181,110,69,0.15)', border: '1px solid rgba(181,110,69,0.4)',
                            color: 'var(--color-warn)', fontSize: 'var(--text-xs)', cursor: 'pointer', fontWeight: 700,
                        }}
                    >{archiving ? '…' : '↩ Unarchive'}</button>
                )}
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: 'var(--space-1)', borderBottom: '1px solid var(--color-border)', marginBottom: 'var(--space-6)', overflowX: 'auto' }}>
                {(Object.keys(TAB_LABELS) as Tab[]).map(t => (
                    <button key={t} onClick={() => setTab(t)} style={tabStyle(t)}>{TAB_LABELS[t]}</button>
                ))}
            </div>

            {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p>}

            {/* ============ TAB 1: Overview ============ */}
            {tab === 'overview' && !loading && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 'var(--space-4)' }}>

                    {/* ── Row 1: Check-in/out · Active Tasks · Location ── */}

                    <div style={{ ...cardStyle, minHeight: 110, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>Check-in / Check-out</div>
                        <div style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--color-text)' }}>
                            {p.checkin_time || '15:00'} → {p.checkout_time || '11:00'}
                        </div>
                    </div>

                    <div style={{ ...cardStyle, minHeight: 110, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>Active Tasks</div>
                        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: tasks.filter(t => t.status !== 'completed' && t.status !== 'cancelled').length > 0 ? 'var(--color-warn)' : 'var(--color-ok)' }}>
                            {tasks.filter(t => t.status !== 'completed' && t.status !== 'cancelled').length}
                        </div>
                    </div>

                    {/* Location — interactive map */}
                    {p.latitude && p.longitude ? (() => {
                        const lat = Number(p.latitude);
                        const lng = Number(p.longitude);
                        const d = 0.005;
                        const bbox = `${lng - d},${lat - d},${lng + d},${lat + d}`;
                        const osmUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lng}`;
                        return (
                            <div style={{ ...cardStyle, padding: 0, overflow: 'hidden', minHeight: 110 }}>
                                <iframe src={osmUrl} style={{ width: '100%', height: 110, border: 'none', display: 'block' }} loading="lazy" title="Property location" />
                            </div>
                        );
                    })() : (
                        <div style={{ ...cardStyle, minHeight: 110, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>Location</div>
                            <div style={{ color: 'var(--color-warn)', fontSize: 'var(--text-sm)', fontStyle: 'italic' }}>⚠ GPS not set</div>
                        </div>
                    )}

                    {/* ── Row 2: Deposit · Reference Photos · House Rules ── */}

                    <div style={{ ...cardStyle, minHeight: 110, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>Deposit</div>
                        <div style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: p.deposit_required ? 'var(--color-warn)' : 'var(--color-text-faint)' }}>
                            {p.deposit_required ? `${p.deposit_currency || 'THB'} ${p.deposit_amount || '—'}` : 'Not required'}
                        </div>
                        {p.deposit_required && (
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 4 }}>Method: {p.deposit_method || 'cash'}</div>
                        )}
                    </div>

                    <div style={{ ...cardStyle, minHeight: 110, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>Reference Photos</div>
                        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: photos.length > 0 ? 'var(--color-text)' : 'var(--color-warn)' }}>
                            {photos.length}
                        </div>
                        {photos.length === 0 && (
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-warn)', marginTop: 4, fontStyle: 'italic' }}>Setup required before activation</div>
                        )}
                    </div>

                    <div style={{ ...cardStyle, minHeight: 110, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>House Rules</div>
                        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text)' }}>
                            {Array.isArray(p.house_rules) ? p.house_rules.length : 0}
                        </div>
                    </div>
                </div>
            )}

            {/* ============ TAB 2: Reference Photos ============ */}
            {tab === 'photos' && !loading && (
                <div>
                    {/* Phase 844 v2: Real file upload — supabase.storage (property-photos bucket) */}
                    <div style={{
                        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', marginBottom: 'var(--space-5)',
                    }}>
                        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-4)' }}>
                            Add Reference Photo
                        </div>

                        {/* Room label selector */}
                        <div style={{ marginBottom: 'var(--space-3)' }}>
                            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', display: 'block', marginBottom: 4 }}>Room / Area</label>
                            <select
                                value={refPhotoRoom} onChange={e => setRefPhotoRoom(e.target.value)}
                                style={{
                                    background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                                    borderRadius: 'var(--radius-sm)', padding: '8px 12px',
                                    color: 'var(--color-text)', fontSize: 'var(--text-sm)', cursor: 'pointer',
                                }}
                            >
                                {['living-room','bedroom','bathroom','kitchen','dining','balcony','pool','exterior','entrance','garage','general'].map(r => (
                                    <option key={r} value={r}>{r.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</option>
                                ))}
                            </select>
                        </div>

                        {/* PRIMARY: File upload button */}
                        <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
                            <input
                                type="file"
                                accept={ACCEPTED_IMAGE_TYPES}
                                ref={refFileRef}
                                style={{ display: 'none' }}
                                onChange={async (e) => {
                                    const file = e.target.files?.[0];
                                    if (!file) return;
                                    setRefPhotoUploading(true);
                                    try {
                                        const tok = getToken() ?? '';
                                        const { url } = await uploadPropertyPhoto(file, propertyId, 'reference', tok);
                                        await apiFetch(`/properties/${propertyId}/reference-photos`, {
                                            method: 'POST',
                                            body: JSON.stringify({ photo_url: url, room_label: refPhotoRoom }),
                                        });
                                        showNotice('📷 Photo uploaded and saved');
                                        load();
                                    } catch (err: any) {
                                        showNotice(`Upload failed: ${err.message || 'Unknown error'}`);
                                    }
                                    setRefPhotoUploading(false);
                                    if (refFileRef.current) refFileRef.current.value = '';
                                }}
                            />
                            <button
                                onClick={() => refFileRef.current?.click()}
                                disabled={refPhotoUploading}
                                style={{
                                    display: 'flex', alignItems: 'center', gap: 8,
                                    padding: '10px 20px', borderRadius: 'var(--radius-md)', border: '2px dashed var(--color-border)',
                                    background: refPhotoUploading ? 'var(--color-surface-2)' : 'transparent',
                                    color: refPhotoUploading ? 'var(--color-text-faint)' : 'var(--color-text)',
                                    fontWeight: 600, fontSize: 'var(--text-sm)', cursor: refPhotoUploading ? 'wait' : 'pointer',
                                    transition: 'all 0.15s',
                                }}
                                onMouseEnter={e => !refPhotoUploading && (e.currentTarget.style.borderColor = 'var(--color-primary)')}
                                onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}
                            >
                                <span style={{ fontSize: 18 }}>{refPhotoUploading ? '⏳' : '📷'}</span>
                                {refPhotoUploading ? 'Uploading…' : 'Pick Photo / Take Photo'}
                            </button>
                            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>
                                Opens device gallery, camera, or file picker
                            </span>
                        </div>

                        {/* SECONDARY: URL input (collapsed by default) */}
                        <details style={{ marginTop: 'var(--space-2)' }}>
                            <summary style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', cursor: 'pointer', userSelect: 'none' }}>
                                Or paste a URL instead
                            </summary>
                            <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
                                <input
                                    value={refPhotoUrl} onChange={e => setRefPhotoUrl(e.target.value)}
                                    placeholder="https://example.com/room.jpg"
                                    style={{
                                        flex: 1, background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                                        borderRadius: 'var(--radius-sm)', padding: '7px 10px',
                                        color: 'var(--color-text)', fontSize: 'var(--text-sm)', outline: 'none',
                                    }}
                                />
                                <button
                                    onClick={async () => {
                                        if (!refPhotoUrl.trim()) return;
                                        setRefPhotoAdding(true);
                                        try {
                                            await apiFetch(`/properties/${propertyId}/reference-photos`, {
                                                method: 'POST',
                                                body: JSON.stringify({ photo_url: refPhotoUrl.trim(), room_label: refPhotoRoom }),
                                            });
                                            setRefPhotoUrl('');
                                            showNotice('📷 Reference photo added');
                                            load();
                                        } catch { showNotice('Failed to add photo'); }
                                        setRefPhotoAdding(false);
                                    }}
                                    disabled={refPhotoAdding || !refPhotoUrl.trim()}
                                    style={{
                                        padding: '7px 16px', borderRadius: 'var(--radius-sm)', border: 'none',
                                        background: 'var(--color-primary)', color: '#fff', fontWeight: 600,
                                        fontSize: 'var(--text-xs)', cursor: 'pointer',
                                    }}
                                >
                                    {refPhotoAdding ? 'Adding…' : 'Add'}
                                </button>
                            </div>
                        </details>
                    </div>
                    {photos.length === 0 ? (
                        <div style={{ ...cardStyle, textAlign: 'center', padding: 'var(--space-8)' }}>
                            <div style={{ fontSize: 'var(--text-lg)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>No Reference Photos</div>
                            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-faint)' }}>
                                Add photo URLs above. Operational reference photos help staff know how each room should look after cleaning.
                            </p>
                        </div>
                    ) : (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 'var(--space-3)' }}>
                            {photos.map((photo: any) => (
                                <div key={photo.id} style={{
                                    borderRadius: 'var(--radius-md)', overflow: 'hidden',
                                    border: '1px solid var(--color-border)', aspectRatio: '4/3',
                                    background: 'var(--color-surface-2)', position: 'relative',
                                }}>
                                    <img src={photo.photo_url} alt={photo.room_label || 'Reference'}
                                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                        onError={e => (e.currentTarget.style.display = 'none')} />
                                    {/* Room badge */}
                                    <div style={{
                                        position: 'absolute', bottom: 4, left: 4,
                                        background: 'rgba(0,0,0,0.65)', color: '#fff',
                                        fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 4,
                                        textTransform: 'capitalize',
                                    }}>{(photo.room_label || 'other').replace(/-/g, ' ')}</div>
                                    <button onClick={async (e) => {
                                        e.stopPropagation();
                                        try {
                                            await apiFetch(`/properties/${propertyId}/reference-photos/${photo.id}`, { method: 'DELETE' });
                                            showNotice('Photo deleted');
                                            load();
                                        } catch { showNotice('Delete failed'); }
                                    }} style={{
                                        position: 'absolute', top: 4, right: 4,
                                        background: 'rgba(0,0,0,0.6)', color: '#fff', border: 'none',
                                        borderRadius: '50%', width: 24, height: 24, cursor: 'pointer',
                                        fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    }}>×</button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* ============ TAB 3: House Info ============ */}
            {tab === 'house-info' && !loading && (
                <div>
                    {saving && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-primary)', marginBottom: 'var(--space-3)' }}>Saving…</div>}

                    {/* Access */}
                    <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                        Access
                    </h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 'var(--space-3)', marginBottom: 'var(--space-6)' }}>
                        <EditableField label="Door Code" value={p.door_code} fieldKey="door_code" onSave={saveField} />
                        <EditableField label="Key Location" value={p.key_location} fieldKey="key_location" onSave={saveField} />
                        <EditableField label="Safe Code" value={p.safe_code} fieldKey="safe_code" onSave={saveField} />
                    </div>

                    {/* Connectivity */}
                    <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                        Connectivity
                    </h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 'var(--space-3)', marginBottom: 'var(--space-6)' }}>
                        <EditableField label="WiFi Name" value={p.wifi_name} fieldKey="wifi_name" onSave={saveField} />
                        <EditableField label="WiFi Password" value={p.wifi_password} fieldKey="wifi_password" onSave={saveField} />
                        <EditableField label="TV Info" value={p.tv_info} fieldKey="tv_info" onSave={saveField} />
                    </div>

                    {/* Appliances */}
                    <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                        Appliances & Utilities
                    </h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 'var(--space-3)', marginBottom: 'var(--space-6)' }}>
                        <EditableField label="AC Instructions" value={p.ac_instructions} fieldKey="ac_instructions" onSave={saveField} />
                        <EditableField label="Hot Water Info" value={p.hot_water_info} fieldKey="hot_water_info" onSave={saveField} />
                        <EditableField label="Stove Instructions" value={p.stove_instructions} fieldKey="stove_instructions" onSave={saveField} />
                        <EditableField label="Breaker Location" value={p.breaker_location} fieldKey="breaker_location" onSave={saveField} />
                    </div>

                    {/* Property */}
                    <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                        Property
                    </h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 'var(--space-3)', marginBottom: 'var(--space-6)' }}>
                        <EditableField label="Trash Instructions" value={p.trash_instructions} fieldKey="trash_instructions" onSave={saveField} />
                        <EditableField label="Parking Info" value={p.parking_info} fieldKey="parking_info" onSave={saveField} />
                        <EditableField label="Pool Instructions" value={p.pool_instructions} fieldKey="pool_instructions" onSave={saveField} />
                        <EditableField label="Laundry Info" value={p.laundry_info} fieldKey="laundry_info" onSave={saveField} />
                    </div>

                    {/* Emergency */}
                    <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                        Emergency & Notes
                    </h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 'var(--space-3)', marginBottom: 'var(--space-6)' }}>
                        <EditableField label="Emergency Contact" value={p.emergency_contact} fieldKey="emergency_contact" onSave={saveField} />
                        <EditableField label="Extra Notes" value={p.extra_notes} fieldKey="extra_notes" onSave={saveField} />
                    </div>
                </div>
            )}

            {/* ============ TAB 4: Tasks ============ */}
            {tab === 'tasks' && !loading && (
                <div>
                    {tasks.length === 0 ? (
                        <div style={{ ...cardStyle, textAlign: 'center', padding: 'var(--space-6)' }}>
                            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>No tasks for this property</p>
                        </div>
                    ) : (
                        <>
                            {/* Active */}
                            <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                                Active ({tasks.filter(t => t.status !== 'completed' && t.status !== 'cancelled').length})
                            </h3>
                            {tasks.filter(t => t.status !== 'completed' && t.status !== 'cancelled').map(t => (
                                <div key={t.task_id} style={{
                                    ...cardStyle, marginBottom: 'var(--space-2)',
                                    display: 'flex', alignItems: 'center', gap: 'var(--space-3)',
                                }}>
                                    <div style={{ flex: 1 }}>
                                        <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{t.title || t.kind}</div>
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                                            {t.status} · {t.priority} · {t.deadline || '—'}
                                        </div>
                                    </div>
                                    <div style={{ display: 'flex', gap: 4 }}>
                                        {t.status === 'PENDING' && (
                                            <button onClick={async () => {
                                                try {
                                                    await apiFetch(`/worker/tasks/${t.task_id}/acknowledge`, { method: 'PATCH' });
                                                    showNotice('Task acknowledged');
                                                    load();
                                                } catch { showNotice('Acknowledge failed'); }
                                            }} style={{
                                                padding: '4px 10px', fontSize: 'var(--text-xs)', fontWeight: 600,
                                                background: 'rgba(88,166,255,0.1)', color: '#58a6ff',
                                                border: '1px solid rgba(88,166,255,0.3)', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                                            }}>Ack</button>
                                        )}
                                        {(t.status === 'ACKNOWLEDGED' || t.status === 'IN_PROGRESS') && (
                                            <button onClick={async () => {
                                                try {
                                                    await apiFetch(`/worker/tasks/${t.task_id}/complete`, { method: 'PATCH' });
                                                    showNotice('Task completed');
                                                    load();
                                                } catch { showNotice('Complete failed'); }
                                            }} style={{
                                                padding: '4px 10px', fontSize: 'var(--text-xs)', fontWeight: 600,
                                                background: 'rgba(63,185,80,0.1)', color: '#3fb950',
                                                border: '1px solid rgba(63,185,80,0.3)', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                                            }}>Complete</button>
                                        )}
                                    </div>
                                    <StatusBadge status={t.status} />
                                </div>
                            ))}

                            {/* Completed */}
                            {tasks.filter(t => t.status === 'completed').length > 0 && (
                                <>
                                    <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 'var(--space-5)', marginBottom: 'var(--space-3)' }}>
                                        Completed ({tasks.filter(t => t.status === 'completed').length})
                                    </h3>
                                    {tasks.filter(t => t.status === 'completed').map(t => (
                                        <div key={t.task_id} style={{
                                            ...cardStyle, marginBottom: 'var(--space-2)', opacity: 0.6,
                                            display: 'flex', alignItems: 'center', gap: 'var(--space-3)',
                                        }}>
                                            <div style={{ flex: 1 }}>
                                                <div style={{ fontWeight: 500, fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>{t.title || t.kind}</div>
                                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 2 }}>
                                                    Completed · {t.priority}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </>
                            )}
                        </>
                    )}
                </div>
            )}

            {/* ============ TAB 5: Issues ============ */}
            {tab === 'issues' && !loading && (
                <div>
                    {issues.length === 0 ? (
                        <div style={{ ...cardStyle, textAlign: 'center', padding: 'var(--space-6)' }}>
                            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>No open issues for this property</p>
                            <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-2)' }}>
                                Issues will appear here when reported by cleaning staff or maintenance teams
                            </p>
                        </div>
                    ) : (
                        <>
                            {issues.map((issue: any) => (
                                <div key={issue.id || issue.report_id} style={{
                                    ...cardStyle, marginBottom: 'var(--space-2)',
                                    borderLeft: `3px solid ${issue.severity === 'CRITICAL' ? '#f85149' : issue.severity === 'HIGH' ? '#d29922' : 'var(--color-border)'}`,
                                }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                        <div>
                                            <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
                                                {issue.title || issue.description?.substring(0, 60) || 'Issue'}
                                            </div>
                                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                                                {issue.category || '—'} · {issue.severity || '—'} · {issue.status || '—'}
                                            </div>
                                            {issue.description && (
                                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 4, maxWidth: 500 }}>
                                                    {issue.description.substring(0, 120)}{issue.description.length > 120 ? '…' : ''}
                                                </div>
                                            )}
                                        </div>
                                        <StatusBadge status={issue.status} />
                                    </div>
                                    {issue.created_at && (
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-2)', fontFamily: 'var(--font-mono)' }}>
                                            {new Date(issue.created_at).toLocaleString('en-GB', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </>
                    )}
                </div>
            )}

            {/* ============ TAB 6: Audit ============ */}
            {tab === 'audit' && !loading && (
                <div>
                    {auditEntries.length === 0 ? (
                        <div style={{ ...cardStyle, textAlign: 'center', padding: 'var(--space-6)' }}>
                            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>No audit entries for this property</p>
                        </div>
                    ) : (
                        <div style={{ ...cardStyle, overflow: 'hidden', padding: 0 }}>
                            <div style={{
                                display: 'grid', gridTemplateColumns: '140px 1fr 120px 80px',
                                gap: 'var(--space-2)', padding: 'var(--space-3) var(--space-4)',
                                borderBottom: '1px solid var(--color-border)',
                                fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase',
                            }}>
                                <div>Time</div><div>Action</div><div>Entity</div><div>Role</div>
                            </div>
                            {auditEntries.slice(0, 100).map((e: any, i: number) => (
                                <div key={e.id || i} style={{
                                    display: 'grid', gridTemplateColumns: '140px 1fr 120px 80px',
                                    gap: 'var(--space-2)', padding: 'var(--space-2) var(--space-4)',
                                    borderBottom: '1px solid var(--color-border)',
                                    fontSize: 'var(--text-xs)',
                                }}>
                                    <div style={{ color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)' }}>
                                        {e.occurred_at ? new Date(e.occurred_at).toLocaleString('en-GB', { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' }) : '—'}
                                    </div>
                                    <div style={{ color: 'var(--color-text)' }}>{e.action || e.event_type || '—'}</div>
                                    <div style={{ color: 'var(--color-text-dim)' }}>{e.entity_type || '—'}</div>
                                    <div style={{ color: 'var(--color-text-faint)' }}>{e.actor_role || '—'}</div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* ============ TAB 7: Edit Details (Phase 844) ============ */}
            {tab === 'edit' && !loading && (() => {
                const iStyle: React.CSSProperties = {
                    width: '100%', background: 'var(--color-surface-2)',
                    border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)',
                    padding: '9px 12px', color: 'var(--color-text)',
                    fontSize: 'var(--text-sm)', outline: 'none', boxSizing: 'border-box' as const,
                };
                const lStyle: React.CSSProperties = {
                    fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)',
                    display: 'block', marginBottom: 6, fontWeight: 500,
                    textTransform: 'uppercase' as const, letterSpacing: '0.04em',
                };
                const sHead: React.CSSProperties = {
                    fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)',
                    textTransform: 'uppercase' as const, letterSpacing: '0.07em',
                    marginTop: 'var(--space-5)', marginBottom: 'var(--space-3)',
                    paddingBottom: 'var(--space-2)', borderBottom: '1px solid var(--color-border)',
                };
                const PROPERTY_TYPES = ['apartment','villa','house','condo','studio','resort','hostel','hotel','other'];
                const DEPOSIT_CURRENCIES = ['THB','USD','EUR','GBP','SGD','AUD','HKD','JPY','AED'];

                const handleEditSave = async () => {
                    setEditSaving(true);
                    try {
                        const body: Record<string, any> = {
                            display_name: editDisplayName.trim() || undefined,
                            property_type: editPropertyType || undefined,
                            city: editCity.trim() || undefined,
                            country: editCountry.trim() || undefined,
                            address: editAddress.trim() || undefined,
                            latitude: editLat ? parseFloat(editLat) : undefined,
                            longitude: editLng ? parseFloat(editLng) : undefined,
                            bedrooms: editBedrooms ? parseInt(editBedrooms) : undefined,
                            beds: editBeds ? parseInt(editBeds) : undefined,
                            bathrooms: editBathrooms ? parseInt(editBathrooms) : undefined, // integer-only
                            max_guests: editMaxGuests ? parseInt(editMaxGuests) : undefined,
                            checkin_time: editCheckinTime || undefined,
                            checkout_time: editCheckoutTime || undefined,
                            description: editDescription.trim() || undefined,
                            source_url: editSourceUrl.trim() || undefined,
                            // Deposit (Phase 844)
                            deposit_required: editDepositRequired,
                            deposit_amount: editDepositRequired && editDepositAmount ? parseFloat(editDepositAmount) : null,
                            deposit_currency: editDepositRequired ? editDepositCurrency : null,
                            // House Rules, Owner Contact, Amenities (Phase 844 v2)
                            house_rules: editHouseRules,
                            owner_phone: editOwnerPhone.trim() || null,
                            owner_email: editOwnerEmail.trim() || null,
                            amenities: editAmenities,
                        };
                        Object.keys(body).forEach(k => body[k] === undefined && delete body[k]);
                        const updated = await apiFetch(`/properties/${propertyId}`, { method: 'PATCH', body: JSON.stringify(body) });
                        setProperty(updated);
                        showNotice('✓ Property details saved');
                    } catch { showNotice('Save failed'); }
                    setEditSaving(false);
                };

                const handleGeoLocate = () => {
                    if (!navigator.geolocation) { setGeoStatus('err'); return; }
                    setGeoStatus('loading');
                    navigator.geolocation.getCurrentPosition(
                        pos => {
                            setEditLat(String(pos.coords.latitude));
                            setEditLng(String(pos.coords.longitude));
                            setGeoStatus('ok');
                            setTimeout(() => setGeoStatus('idle'), 4000);
                        },
                        () => { setGeoStatus('err'); setTimeout(() => setGeoStatus('idle'), 4000); },
                        { enableHighAccuracy: true, timeout: 10000 }
                    );
                };

                return (
                    <div style={{ maxWidth: 680 }}>

                        {/* ── Section: Core Identity ─────────────────────────────── */}
                        <div style={sHead}>Core Identity</div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
                                <div><label style={lStyle}>Display Name</label>
                                    <input style={iStyle} value={editDisplayName} onChange={e => setEditDisplayName(e.target.value)} />
                                </div>
                                <div><label style={lStyle}>Property Type</label>
                                    <select style={{ ...iStyle, cursor: 'pointer' }} value={editPropertyType} onChange={e => setEditPropertyType(e.target.value)}>
                                        <option value="">— Select —</option>
                                        {PROPERTY_TYPES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase()+t.slice(1)}</option>)}
                                    </select>
                                </div>
                            </div>
                        </div>

                        {/* ── Section: Location & Capacity ──────────────────────── */}
                        <div style={sHead}>Location &amp; Capacity</div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
                                <div><label style={lStyle}>City</label><input style={iStyle} value={editCity} onChange={e => setEditCity(e.target.value)} /></div>
                                <div><label style={lStyle}>Country</label><input style={iStyle} value={editCountry} onChange={e => setEditCountry(e.target.value)} placeholder="TH" /></div>
                            </div>
                            <div><label style={lStyle}>Address</label>
                                <textarea style={{ ...iStyle, resize: 'vertical', minHeight: 60 }} value={editAddress} onChange={e => setEditAddress(e.target.value)} />
                            </div>

                            {/* GPS: manual fields + geolocation capture */}
                            <div>
                                <label style={lStyle}>GPS Coordinates</label>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 'var(--space-3)', alignItems: 'end' }}>
                                    <div>
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginBottom: 4 }}>Latitude</div>
                                        <input style={iStyle} value={editLat} onChange={e => setEditLat(e.target.value)} type="number" step="any" placeholder="e.g. 9.527" />
                                    </div>
                                    <div>
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginBottom: 4 }}>Longitude</div>
                                        <input style={iStyle} value={editLng} onChange={e => setEditLng(e.target.value)} type="number" step="any" placeholder="e.g. 100.062" />
                                    </div>
                                    <button onClick={handleGeoLocate} disabled={geoStatus === 'loading'} style={{
                                        padding: '9px 14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)',
                                        background: geoStatus === 'ok' ? 'rgba(34,197,94,0.15)' : geoStatus === 'err' ? 'rgba(248,81,73,0.1)' : 'var(--color-surface-2)',
                                        color: geoStatus === 'ok' ? '#22c55e' : geoStatus === 'err' ? '#f85149' : 'var(--color-text-dim)',
                                        fontSize: 'var(--text-xs)', fontWeight: 600, cursor: geoStatus === 'loading' ? 'wait' : 'pointer',
                                        whiteSpace: 'nowrap' as const,
                                    }}>
                                        {geoStatus === 'loading' ? '⏳ Locating…' : geoStatus === 'ok' ? '✓ Location saved' : geoStatus === 'err' ? '✕ Access denied' : '📍 Use Current Location'}
                                    </button>
                                </div>
                            </div>

                            {/* Capacity: integer-only bathrooms */}
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 'var(--space-3)' }}>
                                <div><label style={lStyle}>Bedrooms</label><input style={iStyle} value={editBedrooms} onChange={e => setEditBedrooms(e.target.value)} type="number" min="0" step="1" /></div>
                                <div><label style={lStyle}>Beds</label><input style={iStyle} value={editBeds} onChange={e => setEditBeds(e.target.value)} type="number" min="0" step="1" /></div>
                                <div><label style={lStyle}>Bathrooms</label><input style={iStyle} value={editBathrooms} onChange={e => setEditBathrooms(e.target.value)} type="number" min="0" step="1" /></div>
                                <div><label style={lStyle}>Max Guests</label><input style={iStyle} value={editMaxGuests} onChange={e => setEditMaxGuests(e.target.value)} type="number" min="1" step="1" /></div>
                            </div>
                        </div>

                        {/* ── Section: Operation ─────────────────────────────────── */}
                        <div style={sHead}>Operation</div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
                                <div><label style={lStyle}>Check-in Time</label><input style={iStyle} value={editCheckinTime} onChange={e => setEditCheckinTime(e.target.value)} type="time" /></div>
                                <div><label style={lStyle}>Check-out Time</label><input style={iStyle} value={editCheckoutTime} onChange={e => setEditCheckoutTime(e.target.value)} type="time" /></div>
                            </div>
                            <div><label style={lStyle}>Description</label>
                                <textarea style={{ ...iStyle, resize: 'vertical', minHeight: 80 }} value={editDescription} onChange={e => setEditDescription(e.target.value)} />
                            </div>
                            <div>
                                <label style={lStyle}>Listing URL <span style={{ fontWeight: 400, color: 'var(--color-text-faint)' }}>(pull available data below)</span></label>
                                <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                                    <input style={{ flex: 1, ...iStyle }} value={editSourceUrl} onChange={e => { setEditSourceUrl(e.target.value); setListingResult(null); }} placeholder="https://airbnb.com/rooms/..." />
                                    <button
                                        disabled={listingPulling || !editSourceUrl.trim()}
                                        onClick={async () => {
                                            if (!editSourceUrl.trim()) return;
                                            setListingPulling(true);
                                            setListingResult(null);
                                            try {
                                                const res = await apiFetch(`/properties/${propertyId}/fetch-listing`, {
                                                    method: 'POST',
                                                    body: JSON.stringify({ listing_url: editSourceUrl }),
                                                });
                                                setListingResult(res);
                                                // Auto-apply non-empty imported fields
                                                const im = res.imported || {};
                                                if (im.name) setEditDisplayName(im.name);
                                                if (im.description) setEditDescription(im.description);
                                                if (im.city) setEditCity(im.city);
                                                if (im.country) setEditCountry(im.country);
                                                if (im.address) setEditAddress(im.address);
                                                if (im.latitude) setEditLat(String(im.latitude));
                                                if (im.longitude) setEditLng(String(im.longitude));
                                                if (im.amenities?.length) setEditAmenities(im.amenities);
                                            } catch (err: any) {
                                                setListingResult({ imported: {}, could_not_import: [], warning: `Could not fetch: ${err.message}` });
                                            }
                                            setListingPulling(false);
                                        }}
                                        style={{
                                            padding: '0 16px', borderRadius: 'var(--radius-sm)', border: 'none',
                                            background: listingPulling ? 'var(--color-border)' : 'var(--color-primary)',
                                            color: '#fff', fontWeight: 700, fontSize: 'var(--text-sm)',
                                            cursor: listingPulling ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
                                        }}
                                    >{listingPulling ? '⟳ Pulling…' : '↓ Pull'}</button>
                                </div>
                            </div>
                            {listingResult && (
                                <div style={{
                                    background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                                    borderRadius: 'var(--radius-md)', padding: 'var(--space-4)', fontSize: 'var(--text-xs)',
                                    display: 'flex', flexDirection: 'column', gap: 'var(--space-2)',
                                }}>
                                    {listingResult.warning && (
                                        <div style={{ color: 'var(--color-warn)', fontWeight: 600 }}>⚠ {listingResult.warning}</div>
                                    )}
                                    {Object.keys(listingResult.imported).length > 0 && (
                                        <div style={{ color: 'var(--color-ok)' }}>
                                            ✓ Imported: {Object.keys(listingResult.imported).join(', ')}
                                        </div>
                                    )}
                                    {listingResult.could_not_import.length > 0 && (
                                        <div style={{ color: 'var(--color-text-faint)' }}>
                                            ✗ Could not import: {listingResult.could_not_import.join(', ')}
                                        </div>
                                    )}
                                    {Object.keys(listingResult.imported).length === 0 && !listingResult.warning && (
                                        <div style={{ color: 'var(--color-text-faint)' }}>No data found at this URL.</div>
                                    )}
                                </div>
                            )}
                        </div>{/* ── close Operation column ── */}

                        {/* ── Section: Deposit ───────────────────────────────────── */}
                        <div style={sHead}>Deposit</div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                            {/* Toggle */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                                <button
                                    onClick={() => setEditDepositRequired(v => !v)}
                                    style={{
                                        position: 'relative', width: 44, height: 24, borderRadius: 12,
                                        background: editDepositRequired ? 'var(--color-primary)' : 'var(--color-border)',
                                        border: 'none', cursor: 'pointer', transition: 'background 0.2s', flexShrink: 0,
                                    }}
                                >
                                    <span style={{
                                        position: 'absolute', top: 3, left: editDepositRequired ? 22 : 3,
                                        width: 18, height: 18, borderRadius: '50%', background: '#fff',
                                        transition: 'left 0.2s', display: 'block',
                                    }} />
                                </button>
                                <div>
                                    <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>
                                        {editDepositRequired ? 'Deposit Required' : 'Deposit Not Required'}
                                    </div>
                                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>
                                        Workers will be prompted to collect a deposit during check-in when enabled
                                    </div>
                                </div>
                            </div>

                            {/* Amount + currency — shown only when enabled */}
                            {editDepositRequired && (
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 'var(--space-3)' }}>
                                    <div>
                                        <label style={lStyle}>Deposit Amount</label>
                                        <input style={iStyle} value={editDepositAmount} onChange={e => setEditDepositAmount(e.target.value)} type="number" min="0" step="1" placeholder="e.g. 5000" />
                                    </div>
                                    <div>
                                        <label style={lStyle}>Currency</label>
                                        <select style={{ ...iStyle, cursor: 'pointer', minWidth: 90 }} value={editDepositCurrency} onChange={e => setEditDepositCurrency(e.target.value)}>
                                            {DEPOSIT_CURRENCIES.map(c => <option key={c} value={c}>{c}</option>)}
                                        </select>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* ── Section: House Rules ────────────────────────────────── */}
                        <div style={sHead}>House Rules</div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                            {editHouseRules.length > 0 && (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                                    {editHouseRules.map((rule, idx) => (
                                        <div key={idx} style={{
                                            display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
                                            background: 'var(--color-surface-2)', borderRadius: 'var(--radius-sm)',
                                            padding: '6px 10px', border: '1px solid var(--color-border)',
                                        }}>
                                            <span style={{ flex: 1, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
                                                {rule}
                                            </span>
                                            <button
                                                onClick={() => setEditHouseRules(prev => prev.filter((_, i) => i !== idx))}
                                                style={{ background: 'none', border: 'none', color: 'var(--color-text-faint)', cursor: 'pointer', fontSize: 16, lineHeight: 1 }}
                                            >✕</button>
                                        </div>
                                    ))}
                                </div>
                            )}
                            <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                                <input
                                    value={newRule}
                                    onChange={e => setNewRule(e.target.value)}
                                    onKeyDown={e => {
                                        if (e.key === 'Enter' && newRule.trim()) {
                                            setEditHouseRules(prev => [...prev, newRule.trim()]);
                                            setNewRule('');
                                        }
                                    }}
                                    placeholder="Add a rule — e.g. No smoking, No parties, Shoes off indoors…"
                                    style={{ flex: 1, ...iStyle }}
                                />
                                <button
                                    onClick={() => {
                                        if (!newRule.trim()) return;
                                        setEditHouseRules(prev => [...prev, newRule.trim()]);
                                        setNewRule('');
                                    }}
                                    style={{
                                        padding: '0 16px', borderRadius: 'var(--radius-sm)', border: 'none',
                                        background: 'var(--color-primary)', color: '#fff', fontWeight: 700,
                                        fontSize: 'var(--text-sm)', cursor: 'pointer',
                                    }}
                                >+</button>
                            </div>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>
                                Press Enter or + to add. ✕ to remove. Saved when you click Save Changes.
                            </div>
                        </div>

                        {/* ── Section: Owner Contact Snapshot ────────────────────── */}
                        <div style={sHead}>Owner Contact (Snapshot)</div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
                            <div>
                                <label style={lStyle}>Owner Phone</label>
                                <input style={iStyle} value={editOwnerPhone} onChange={e => setEditOwnerPhone(e.target.value)} placeholder="+66 81 234 5678" type="tel" />
                            </div>
                            <div>
                                <label style={lStyle}>Owner Email</label>
                                <input style={iStyle} value={editOwnerEmail} onChange={e => setEditOwnerEmail(e.target.value)} placeholder="owner@example.com" type="email" />
                            </div>
                        </div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-1)' }}>
                            Operational snapshot only — not canonical owner linkage. Used for quick staff reference.
                        </div>

                        {/* ── Section: Amenities ──────────────────────────────────── */}
                        <div style={sHead}>Amenities</div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
                            {[
                                'WiFi','Air Conditioning','Swimming Pool','Kitchen','Washing Machine','Dryer',
                                'Dishwasher','Parking','TV','Netflix','BBQ','Garden','Gym','Hot Tub',
                                'Balcony','Ocean View','Mountain View','Breakfast','Coffee Machine',
                                'Hair Dryer','Iron','Safe','Elevator','Wheelchair Access',
                            ].map(amenity => {
                                const active = editAmenities.includes(amenity);
                                return (
                                    <button
                                        key={amenity}
                                        onClick={() => setEditAmenities(prev =>
                                            active ? prev.filter(a => a !== amenity) : [...prev, amenity]
                                        )}
                                        style={{
                                            padding: '5px 12px', borderRadius: 20,
                                            border: `1px solid ${active ? 'var(--color-primary)' : 'var(--color-border)'}`,
                                            background: active ? 'rgba(99,102,241,0.15)' : 'var(--color-surface-2)',
                                            color: active ? 'var(--color-primary)' : 'var(--color-text-dim)',
                                            fontSize: 'var(--text-xs)', fontWeight: active ? 600 : 400,
                                            cursor: 'pointer', transition: 'all 0.15s',
                                        }}
                                    >
                                        {amenity}
                                    </button>
                                );
                            })}
                        </div>

                        {/* Save button */}
                        <div style={{ marginTop: 'var(--space-6)', display: 'flex', justifyContent: 'flex-end' }}>
                            <button onClick={handleEditSave} disabled={editSaving} style={{
                                padding: '10px 28px', borderRadius: 'var(--radius-md)',
                                background: editSaving ? 'var(--color-border)' : 'var(--color-primary)',
                                color: '#fff', border: 'none',
                                cursor: editSaving ? 'not-allowed' : 'pointer',
                                fontWeight: 700, fontSize: 'var(--text-sm)',
                                boxShadow: editSaving ? 'none' : '0 2px 12px rgba(99,102,241,0.4)',
                            }}>{editSaving ? 'Saving…' : 'Save Changes'}</button>
                        </div>
                    </div>
                );
            })()}

            {/* ============ TAB 8: Gallery — Marketing Photos (Phase 844) ============ */}
            {tab === 'gallery' && !loading && (
                <div>
                    {/* Phase 844 v2: Real file upload for gallery */}
                    <div style={{
                        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', marginBottom: 'var(--space-5)',
                    }}>
                        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-4)' }}>
                            Add Gallery Photo
                        </div>

                        {/* Optional caption */}
                        <div style={{ marginBottom: 'var(--space-3)' }}>
                            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', display: 'block', marginBottom: 4 }}>Caption (optional)</label>
                            <input
                                value={galleryCaption} onChange={e => setGalleryCaption(e.target.value)}
                                placeholder="e.g. Pool area, Living room, Property facade…"
                                style={{
                                    width: '100%', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                                    borderRadius: 'var(--radius-sm)', padding: '8px 12px', boxSizing: 'border-box' as const,
                                    color: 'var(--color-text)', fontSize: 'var(--text-sm)', outline: 'none',
                                }}
                            />
                        </div>

                        {/* PRIMARY: File upload */}
                        <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
                            <input
                                type="file"
                                accept={ACCEPTED_IMAGE_TYPES}
                                ref={galleryFileRef}
                                style={{ display: 'none' }}
                                onChange={async (e) => {
                                    const file = e.target.files?.[0];
                                    if (!file) return;
                                    setGalleryUploading(true);
                                    try {
                                        const tok = getToken() ?? '';
                                        const { url } = await uploadPropertyPhoto(file, propertyId, 'gallery', tok);
                                        const result = await apiFetch(`/properties/${propertyId}/marketing-photos`, {
                                            method: 'POST',
                                            body: JSON.stringify({ photo_url: url, caption: galleryCaption.trim() || null, source: 'upload' }),
                                        });
                                        setGalleryPhotos(prev => [...prev, result]);
                                        setGalleryCaption('');
                                        showNotice('🖼 Gallery photo uploaded and saved');
                                    } catch (err: any) {
                                        showNotice(`Upload failed: ${err.message || 'Unknown error'}`);
                                    }
                                    setGalleryUploading(false);
                                    if (galleryFileRef.current) galleryFileRef.current.value = '';
                                }}
                            />
                            <button
                                onClick={() => galleryFileRef.current?.click()}
                                disabled={galleryUploading}
                                style={{
                                    display: 'flex', alignItems: 'center', gap: 8,
                                    padding: '10px 20px', borderRadius: 'var(--radius-md)', border: '2px dashed var(--color-border)',
                                    background: galleryUploading ? 'var(--color-surface-2)' : 'transparent',
                                    color: galleryUploading ? 'var(--color-text-faint)' : 'var(--color-text)',
                                    fontWeight: 600, fontSize: 'var(--text-sm)', cursor: galleryUploading ? 'wait' : 'pointer',
                                    transition: 'all 0.15s',
                                }}
                                onMouseEnter={e => !galleryUploading && (e.currentTarget.style.borderColor = 'var(--color-primary)')}
                                onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}
                            >
                                <span style={{ fontSize: 18 }}>{galleryUploading ? '⏳' : '🖼'}</span>
                                {galleryUploading ? 'Uploading…' : 'Add Gallery Photo'}
                            </button>
                            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>
                                Opens device gallery, camera, or file picker
                            </span>
                        </div>

                        {/* SECONDARY: URL input */}
                        <details style={{ marginTop: 'var(--space-2)' }}>
                            <summary style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', cursor: 'pointer', userSelect: 'none' }}>
                                Or paste a URL instead
                            </summary>
                            <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
                                <input
                                    value={galleryUrl} onChange={e => setGalleryUrl(e.target.value)}
                                    placeholder="https://example.com/pool.jpg"
                                    style={{
                                        flex: 1, background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                                        borderRadius: 'var(--radius-sm)', padding: '7px 10px',
                                        color: 'var(--color-text)', fontSize: 'var(--text-sm)', outline: 'none',
                                    }}
                                />
                                <button
                                    onClick={async () => {
                                        if (!galleryUrl.trim()) return;
                                        setGalleryAdding(true);
                                        try {
                                            const result = await apiFetch(`/properties/${propertyId}/marketing-photos`, {
                                                method: 'POST',
                                                body: JSON.stringify({ photo_url: galleryUrl.trim(), caption: galleryCaption.trim() || null, source: 'upload' }),
                                            });
                                            setGalleryPhotos(prev => [...prev, result]);
                                            setGalleryUrl('');
                                            setGalleryCaption('');
                                            showNotice('🖼 Gallery photo added');
                                        } catch { showNotice('Failed to add gallery photo'); }
                                        setGalleryAdding(false);
                                    }}
                                    disabled={galleryAdding || !galleryUrl.trim()}
                                    style={{
                                        padding: '7px 16px', borderRadius: 'var(--radius-sm)', border: 'none',
                                        background: 'var(--color-primary)', color: '#fff', fontWeight: 600,
                                        fontSize: 'var(--text-xs)', cursor: 'pointer',
                                    }}
                                >
                                    {galleryAdding ? 'Adding…' : 'Add'}
                                </button>
                            </div>
                        </details>
                    </div>

                    {galleryPhotos.length === 0 ? (
                        <div style={{ ...cardStyle, textAlign: 'center', padding: 'var(--space-8)' }}>
                            <div style={{ fontSize: 40, marginBottom: 'var(--space-3)' }}>🖼</div>
                            <div style={{ fontSize: 'var(--text-lg)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>No Gallery Photos</div>
                            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-faint)', maxWidth: 400, margin: '0 auto' }}>
                                Gallery photos represent this property visually — facade, pool, living room, etc.
                                Use "Set as Cover" to choose which photo appears as the property hero image.
                            </p>
                        </div>
                    ) : (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 'var(--space-3)' }}>
                            {galleryPhotos.map((photo: any, idx: number) => {
                                const isCover = p.cover_photo_url === photo.photo_url;
                                return (
                                    <div key={photo.id || idx} style={{ position: 'relative', borderRadius: 'var(--radius-md)', overflow: 'hidden', border: isCover ? '2px solid var(--color-primary)' : '1px solid var(--color-border)', background: 'var(--color-surface)' }}>
                                        {isCover && (
                                            <div style={{
                                                position: 'absolute', top: 6, left: 6, zIndex: 2,
                                                background: 'var(--color-primary)', color: '#fff',
                                                fontSize: 10, fontWeight: 700, letterSpacing: '0.05em',
                                                padding: '2px 8px', borderRadius: 4,
                                            }}>COVER</div>
                                        )}
                                        <img src={photo.photo_url} alt={photo.caption || `Gallery ${idx + 1}`} style={{ width: '100%', height: 150, objectFit: 'cover', display: 'block' }} onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }} />
                                        <div style={{ padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 4 }}>
                                            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{photo.caption || 'No caption'}</span>
                                            <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                                                {!isCover && (
                                                    <button onClick={async () => {
                                                        try {
                                                            await apiFetch(`/properties/${propertyId}`, {
                                                                method: 'PATCH',
                                                                body: JSON.stringify({ cover_photo_url: photo.photo_url }),
                                                            });
                                                            setProperty((prev: any) => ({ ...prev, cover_photo_url: photo.photo_url }));
                                                            showNotice('✓ Cover photo updated');
                                                        } catch { showNotice('Failed to set cover'); }
                                                    }} style={{
                                                        background: 'none', border: '1px solid var(--color-border)',
                                                        borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                                                        color: 'var(--color-primary)', fontSize: 10, fontWeight: 600,
                                                        padding: '2px 6px', whiteSpace: 'nowrap',
                                                    }}>Set as Cover</button>
                                                )}
                                                <button onClick={async () => {
                                                    try {
                                                        await apiFetch(`/properties/${propertyId}/marketing-photos/${photo.id}`, { method: 'DELETE' });
                                                        setGalleryPhotos(prev => prev.filter((_: any, i: number) => i !== idx));
                                                        if (isCover) setProperty((prev: any) => ({ ...prev, cover_photo_url: null }));
                                                        showNotice('Photo removed');
                                                    } catch { showNotice('Delete failed'); }
                                                }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-faint)', fontSize: 14, padding: '2px 4px' }}>✕</button>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            )}

            {/* ============ TAB 9: OTA Settings ============ */}
            {tab === 'ota' && !loading && (
                <OtaSettingsTab propertyId={propertyId} />
            )}
        </div>
    );
}
