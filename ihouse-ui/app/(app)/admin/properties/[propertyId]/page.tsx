'use client';

/**
 * Phase 969 — Property Detail: 5-Section IA
 *
 * Primary: Overview | Operations | Media | Settings | History
 * Operations sub-tabs:  Tasks | Issues
 * Media sub-tabs:       Reference Photos | Gallery
 * Settings sub-tabs:    General | House & Access | Rules | Integrations
 * History sub-tabs:     Audit | Settlements (future)
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getToken } from '@/lib/api';
import { uploadPropertyPhoto, ACCEPTED_IMAGE_TYPES } from '@/lib/uploadPhoto';
import OtaSettingsTab from './OtaSettingsTab';

type PrimaryTab = 'overview' | 'operations' | 'media' | 'settings' | 'history';

const PRIMARY_TABS: { key: PrimaryTab; label: string }[] = [
    { key: 'overview',    label: 'Overview' },
    { key: 'operations', label: 'Operations' },
    { key: 'media',      label: 'Media' },
    { key: 'settings',   label: 'Settings' },
    { key: 'history',    label: 'History' },
];

const SUB_TABS: Partial<Record<PrimaryTab, { key: string; label: string; disabled?: boolean }[]>> = {
    operations: [
        { key: 'tasks',  label: 'Tasks' },
        { key: 'issues', label: 'Issues' },
    ],
    media: [
        { key: 'ref-photos', label: 'Reference Photos' },
        { key: 'gallery',    label: 'Gallery' },
    ],
    settings: [
        { key: 'general',      label: 'General' },
        { key: 'house-access', label: 'House & Access' },
        { key: 'rules',        label: 'Rules' },
        { key: 'self-checkin', label: '🔓 Self Check-in' },
        { key: 'integrations', label: 'Integrations' },
    ],
    history: [
        { key: 'audit',       label: 'Audit' },
        { key: 'settlements', label: 'Settlements', disabled: true },
    ],
};

// Default sub-tab for each primary tab
const DEFAULT_SUB: Partial<Record<PrimaryTab, string>> = {
    operations:  'tasks',
    media:       'ref-photos',
    settings:    'general',
    history:     'audit',
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

// Status badge component — covers all property lifecycle states
function StatusBadge({ status }: { status?: string }) {
    const s = (status || 'available').toLowerCase().replace(/[\s_-]/g, '');
    const colors: Record<string, { bg: string; text: string; border: string }> = {
        // Operational — green family
        available:   { bg: 'rgba(46,160,67,0.12)',   text: '#3fb950', border: '#23863630' },
        ready:       { bg: 'rgba(46,160,67,0.18)',   text: '#3fb950', border: '#3fb95040' },
        occupied:    { bg: 'rgba(130,80,223,0.12)',  text: '#a371f7', border: '#8b5cf630' },
        cleaning:    { bg: 'rgba(56,158,214,0.12)',  text: '#58a6ff', border: '#388bfd30' },
        atrisk:      { bg: 'rgba(210,153,34,0.18)',  text: '#d29922', border: '#d2992240' },
        blocked:     { bg: 'rgba(248,81,73,0.18)',   text: '#f85149', border: '#f8514940' },
        // Non-operational lifecycle statuses — NEVER green
        approved:    { bg: 'rgba(46,160,67,0.12)',   text: '#3fb950', border: '#23863630' },
        pending:     { bg: 'rgba(245,158,11,0.15)',  text: '#f59e0b', border: '#f59e0b40' },
        pendingreview: { bg: 'rgba(245,158,11,0.15)', text: '#f59e0b', border: '#f59e0b40' },
        draft:       { bg: 'rgba(110,118,129,0.12)', text: '#8b949e', border: '#8b949e30' },
        rejected:    { bg: 'rgba(248,81,73,0.10)',   text: '#f85149', border: '#f8514930' },
        archived:    { bg: 'rgba(110,118,129,0.12)', text: '#8b949e', border: '#8b949e30' },
    };
    const c = colors[s] || { bg: 'rgba(110,118,129,0.12)', text: '#8b949e', border: '#8b949e30' };
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

// Phase 1019 — Self Check-in mode badge (shared with list page)
const CHECKIN_MODE_BADGE_CFG: Record<string, { label: string; bg: string; text: string; border: string }> = {
    default:   { label: '🔓 Self Check-in', bg: '#6366f115', text: '#6366f1', border: '#6366f133' },
    late_only: { label: '🌙 Late Only',      bg: '#f59e0b15', text: '#d97706', border: '#f59e0b33' },
    disabled:  { label: '👤 Staffed',         bg: '#6b728015', text: '#6b7280', border: '#6b728033' },
};
function CheckinModeBadge({ mode }: { mode?: string | null }) {
    const cfg = CHECKIN_MODE_BADGE_CFG[mode || 'disabled'] || CHECKIN_MODE_BADGE_CFG.disabled;
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
    const [tab, setTab] = useState<PrimaryTab>('overview');
    const [subTab, setSubTab] = useState<string>('');
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
    // (Phase 969: old deposit_required fields removed — Settlement Rules is the source of truth)
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

    // Settlement charge rules — Phase 968 (wires property_charge_rules table into UI)
    const [crDepositEnabled, setCrDepositEnabled] = useState(false);
    const [crDepositAmount, setCrDepositAmount] = useState('');
    const [crDepositCurrency, setCrDepositCurrency] = useState('THB');
    const [crDepositNotes, setCrDepositNotes] = useState('');
    const [crElecEnabled, setCrElecEnabled] = useState(false);
    const [crElecRate, setCrElecRate] = useState('');
    const [crElecCurrency, setCrElecCurrency] = useState('THB');
    const [crElecNotes, setCrElecNotes] = useState('');
    const [crSaving, setCrSaving] = useState(false);
    const [crLoaded, setCrLoaded] = useState(false); // false = not yet fetched

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

    // Phase 887d: Permanent Delete — only for rejected/archived properties.
    // Requires admin to type the property name to confirm intent.
    const [deleting, setDeleting] = useState(false);
    const handlePermanentDelete = async () => {
        const name = p.display_name || propertyId;
        const typed = window.prompt(
            `⚠ PERMANENT DELETE\n\nThis will remove "${name}" and ALL associated tasks, bookings, and records from the system. This cannot be undone.\n\nType the property name to confirm:`
        );
        if (typed === null) return; // cancelled
        if (typed.trim() !== name.trim()) {
            alert('Name did not match. Delete cancelled.');
            return;
        }
        setDeleting(true);
        try {
            await apiFetch(`/properties/${propertyId}`, { method: 'DELETE' });
            router.push('/admin/properties');
        } catch {
            showNotice('Delete failed — contact support if this persists');
            setDeleting(false);
        }
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
                // (Phase 969: deposit fields moved to Settlement Rules / charge-rules API)
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

            // Load charge rules — Phase 968 (404 = no rule configured yet, that's fine)
            try {
                const cr = await apiFetch(`/admin/properties/${propertyId}/charge-rules`);
                setCrDepositEnabled(!!cr.deposit_enabled);
                setCrDepositAmount(cr.deposit_amount != null ? String(cr.deposit_amount) : '');
                setCrDepositCurrency(cr.deposit_currency || 'THB');
                setCrDepositNotes(cr.deposit_notes || '');
                setCrElecEnabled(!!cr.electricity_enabled);
                setCrElecRate(cr.electricity_rate_kwh != null ? String(cr.electricity_rate_kwh) : '');
                setCrElecCurrency(cr.electricity_currency || 'THB');
                setCrElecNotes(cr.electricity_notes || '');
                setCrLoaded(true);
            } catch {
                // 404 = no charge rule yet — leave defaults, still allow save
                setCrLoaded(true);
            }
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

    const primaryTabStyle = (t: PrimaryTab): React.CSSProperties => ({
        padding: 'var(--space-2) var(--space-4)',
        fontSize: 'var(--text-sm)',
        fontWeight: tab === t ? 700 : 400,
        color: tab === t ? 'var(--color-primary)' : 'var(--color-text-dim)',
        borderBottom: tab === t ? '2px solid var(--color-primary)' : '2px solid transparent',
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        whiteSpace: 'nowrap' as const,
        flexShrink: 0,
    });

    const subTabStyle = (s: string): React.CSSProperties => ({
        padding: '6px 14px',
        fontSize: 'var(--text-xs)',
        fontWeight: subTab === s ? 600 : 400,
        color: subTab === s ? 'var(--color-text)' : 'var(--color-text-faint)',
        background: subTab === s ? 'var(--color-surface)' : 'transparent',
        border: `1px solid ${subTab === s ? 'var(--color-border)' : 'transparent'}`,
        borderRadius: 'var(--radius-md)',
        cursor: 'pointer',
        whiteSpace: 'nowrap' as const,
        flexShrink: 0,
        boxShadow: subTab === s ? 'var(--shadow-sm)' : 'none',
        transition: 'all 0.15s',
    });

    const switchTab = (t: PrimaryTab) => {
        setTab(t);
        setSubTab(DEFAULT_SUB[t] ?? '');
    };

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

            {/* Phase 887d — Pending/Draft/Rejected non-operational warning banner */}
            {['pending', 'draft', 'rejected', 'pending_review'].includes(p.status) && (
                <div style={{
                    background: p.status === 'rejected'
                        ? 'rgba(248,81,73,0.08)'
                        : 'rgba(245,158,11,0.08)',
                    border: `1px solid ${ p.status === 'rejected' ? 'rgba(248,81,73,0.35)' : 'rgba(245,158,11,0.35)'}`,
                    borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)',
                    marginBottom: 'var(--space-4)',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-4)',
                }}>
                    <span style={{
                        fontSize: 'var(--text-sm)',
                        color: p.status === 'rejected' ? '#f85149' : '#f59e0b',
                        fontWeight: 600,
                    }}>
                        {p.status === 'rejected'
                            ? '🚫 This property has been rejected and is not operational. It cannot be assigned to staff, generate tasks, or participate in any booking flows.'
                            : `⏳ This property is ${p.status === 'pending_review' ? 'pending review' : p.status} and is NOT yet operational. It cannot participate in staff assignments, task generation, or booking flows until approved.`
                        }
                    </span>
                    {p.status === 'rejected' && (
                        <button
                            onClick={handlePermanentDelete}
                            disabled={deleting}
                            style={{
                                background: 'rgba(248,81,73,0.15)', color: '#f85149',
                                border: '1px solid rgba(248,81,73,0.4)',
                                borderRadius: 'var(--radius-md)', padding: '6px 16px',
                                fontSize: 'var(--text-xs)', fontWeight: 700,
                                cursor: deleting ? 'not-allowed' : 'pointer', flexShrink: 0,
                                whiteSpace: 'nowrap',
                            }}
                        >{deleting ? 'Deleting…' : '🗑 Permanently Delete'}</button>
                    )}
                </div>
            )}

            {/* Header */}
            <div style={{ marginBottom: 'var(--space-4)', display: 'flex', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
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

                <div style={{ flex: '1 1 240px', minWidth: 0 }}>
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>
                        Property Detail
                    </p>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                        <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text)', letterSpacing: '-0.03em', margin: 0 }}>
                            {p.display_name || propertyId}
                        </h1>
                        <StatusBadge status={p.status} />
                        {/* Phase 1019: Self Check-in mode badge in header */}
                        <CheckinModeBadge mode={p.self_checkin_config?.mode} />
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
                {/* Add Booking button — only for operational (approved) properties */}
                {p.status === 'approved' && (
                <button
                    onClick={() => router.push(`/admin/bookings/intake?property=${propertyId}`)}
                    style={{
                        padding: 'var(--space-2) var(--space-4)', borderRadius: 'var(--radius-md)',
                        background: 'var(--color-primary)', border: 'none',
                        color: '#fff', fontSize: 'var(--text-xs)', cursor: 'pointer', fontWeight: 600,
                    }}
                >✍️ Add Booking</button>
                )}
                {/* Archive / Unarchive / Permanent Delete button */}
                {p.status !== 'archived' && p.status !== 'rejected' ? (
                    <button
                        onClick={handleArchive}
                        disabled={archiving}
                        style={{
                            padding: 'var(--space-2) var(--space-4)', borderRadius: 'var(--radius-md)',
                            background: 'none', border: '1px solid var(--color-border)',
                            color: 'var(--color-text-faint)', fontSize: 'var(--text-xs)', cursor: 'pointer', fontWeight: 500,
                        }}
                    >{archiving ? '…' : '🗄 Archive'}</button>
                ) : p.status === 'archived' ? (
                    <button
                        onClick={handleUnarchive}
                        disabled={archiving}
                        style={{
                            padding: 'var(--space-2) var(--space-4)', borderRadius: 'var(--radius-md)',
                            background: 'rgba(181,110,69,0.15)', border: '1px solid rgba(181,110,69,0.4)',
                            color: 'var(--color-warn)', fontSize: 'var(--text-xs)', cursor: 'pointer', fontWeight: 700,
                        }}
                    >{archiving ? '…' : '↩ Unarchive'}</button>
                ) : (
                    // Rejected: show permanent delete in header action area too
                    <button
                        onClick={handlePermanentDelete}
                        disabled={deleting}
                        style={{
                            padding: 'var(--space-2) var(--space-4)', borderRadius: 'var(--radius-md)',
                            background: 'rgba(248,81,73,0.12)', border: '1px solid rgba(248,81,73,0.35)',
                            color: '#f85149', fontSize: 'var(--text-xs)', cursor: deleting ? 'not-allowed' : 'pointer', fontWeight: 700,
                        }}
                    >{deleting ? 'Deleting…' : '🗑 Delete'}</button>
                )}
            </div>

            {/* Primary Tab Bar */}
            <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--color-border)', marginBottom: SUB_TABS[tab] ? 'var(--space-3)' : 'var(--space-6)', overflowX: 'auto' }}>
                {PRIMARY_TABS.map(t => (
                    <button key={t.key} onClick={() => switchTab(t.key)} style={primaryTabStyle(t.key)}>{t.label}</button>
                ))}
            </div>

            {/* Sub-Tab Bar — shown only for tabs that have sub-tabs */}
            {SUB_TABS[tab] && (
                <div style={{ display: 'flex', gap: 'var(--space-2)', marginBottom: 'var(--space-5)', padding: '4px', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-lg)', width: 'fit-content', flexWrap: 'wrap' }}>
                    {SUB_TABS[tab]!.map(s => (
                        <button
                            key={s.key}
                            onClick={() => !s.disabled && setSubTab(s.key)}
                            title={s.disabled ? 'Coming soon' : undefined}
                            style={{
                                ...subTabStyle(s.key),
                                ...(s.disabled ? { opacity: 0.45, cursor: 'not-allowed' } : {}),
                            }}
                        >
                            {s.label}{s.disabled ? ' ·· soon' : ''}
                        </button>
                    ))}
                </div>
            )}

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
                        {/* Phase 887d: compare uppercase CANCELED (DB) and lowercase cancelled (legacy) */}
                        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: tasks.filter(t => !['completed','cancelled','canceled','COMPLETED','CANCELLED','CANCELED'].includes(t.status)).length > 0 ? 'var(--color-warn)' : 'var(--color-ok)' }}>
                            {tasks.filter(t => !['completed','cancelled','canceled','COMPLETED','CANCELLED','CANCELED'].includes(t.status)).length}
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

                    {/* ── Row 2: Settlement Policy · Reference Photos · House Rules ── */}

                    <div style={{ ...cardStyle, minHeight: 110, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 'var(--space-2)' }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-1)' }}>Settlement Policy</div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <span style={{
                                    width: 8, height: 8, borderRadius: '50%', flexShrink: 0, display: 'inline-block',
                                    background: crDepositEnabled ? 'var(--color-primary)' : 'var(--color-border)',
                                }} />
                                <span style={{ fontSize: 'var(--text-xs)', color: crDepositEnabled ? 'var(--color-text)' : 'var(--color-text-faint)', fontWeight: crDepositEnabled ? 600 : 400 }}>
                                    {crDepositEnabled ? `Deposit: ${crDepositAmount || '—'} ${crDepositCurrency}` : 'No deposit'}
                                </span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <span style={{
                                    width: 8, height: 8, borderRadius: '50%', flexShrink: 0, display: 'inline-block',
                                    background: crElecEnabled ? '#f59e0b' : 'var(--color-border)',
                                }} />
                                <span style={{ fontSize: 'var(--text-xs)', color: crElecEnabled ? 'var(--color-text)' : 'var(--color-text-faint)', fontWeight: crElecEnabled ? 600 : 400 }}>
                                    {crElecEnabled ? `Electricity: ${crElecRate || '—'} ${crElecCurrency}/kWh` : 'Electricity not billed'}
                                </span>
                            </div>
                        </div>
                        {!crLoaded && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', fontStyle: 'italic' }}>Loading…</div>}
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

            {/* ============ MEDIA / Reference Photos ============ */}
            {tab === 'media' && subTab === 'ref-photos' && !loading && (
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

            {/* ============ SETTINGS / House & Access ============ */}
            {tab === 'settings' && subTab === 'house-access' && !loading && (
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

            {/* ============ OPERATIONS / Tasks ============ */}
            {tab === 'operations' && subTab === 'tasks' && !loading && (
                <div>
                    {tasks.length === 0 ? (
                        <div style={{ ...cardStyle, textAlign: 'center', padding: 'var(--space-6)' }}>
                            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>No tasks for this property</p>
                        </div>
                    ) : (
                        <>
                            {/* Active — Phase 887d: cover both CANCELED (uppercase DB) and cancelled (legacy) */}
                            <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                                Active ({tasks.filter(t => !['completed','cancelled','canceled','COMPLETED','CANCELLED','CANCELED'].includes(t.status)).length})
                            </h3>
                            {tasks.filter(t => !['completed','cancelled','canceled','COMPLETED','CANCELLED','CANCELED'].includes(t.status)).map(t => (
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

            {/* ============ OPERATIONS / Issues ============ */}
            {tab === 'operations' && subTab === 'issues' && !loading && (
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

            {/* ============ HISTORY / Audit ============ */}
            {tab === 'history' && subTab === 'audit' && !loading && (
                <div>
                    {/* Section header */}
                    <div style={{ marginBottom: 'var(--space-4)' }}>
                        <div style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--color-text)' }}>Audit Log</div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 2 }}>
                            All admin actions on this property — changes to settings, photos, tasks, and charge rules
                        </div>
                    </div>
                    {auditEntries.length === 0 ? (
                        <div style={{ ...cardStyle, textAlign: 'center', padding: 'var(--space-6)' }}>
                            <div style={{ fontSize: 20, marginBottom: 'var(--space-2)' }}>📋</div>
                            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', fontWeight: 600 }}>No audit entries yet</p>
                            <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 4 }}>
                                Actions on this property will appear here automatically.
                            </p>
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

            {/* ============ HISTORY / Settlements (future) ============ */}
            {tab === 'history' && subTab === 'settlements' && !loading && (
                <div>
                    <div style={{ marginBottom: 'var(--space-4)' }}>
                        <div style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--color-text)' }}>Settlement History</div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 2 }}>
                            Per-booking settlement records: deposit, electricity, damage, refunds
                        </div>
                    </div>
                    <div style={{ ...cardStyle, textAlign: 'center', padding: 'var(--space-8)' }}>
                        <div style={{ fontSize: 28, marginBottom: 'var(--space-3)' }}>🔒</div>
                        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--color-text)', marginBottom: 'var(--space-2)' }}>Coming soon</div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', maxWidth: 340, margin: '0 auto', lineHeight: 1.6 }}>
                            Full settlement history — deposit collection status, meter readings, electricity charges,
                            damage deductions, and refund amounts — will be visible here once the settlement engine is active.
                        </div>
                    </div>
                </div>
            )}

            {/* ============ SETTINGS / General ============ */}
            {tab === 'settings' && subTab === 'general' && !loading && (() => {
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
                            // Phase 969: deposit fields removed (now in Settlement Rules)
                            // House rules saved separately in Settings/Rules tab
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

                        {/* Deposit + House Rules + Settlement Rules moved to Settings → Rules tab */}



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



                        {/* Save button — General property details */}
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

            {/* ============ SETTINGS / Rules ============ */}
            {tab === 'settings' && subTab === 'rules' && !loading && (() => {
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
                return (
                    <div style={{ maxWidth: 680 }}>

                        {/* ── Settlement Rules (Phase 968) ─────────────────────────── */}
                        {/* NOTE: Settlement Rules are above House Rules intentionally.
                             Settlement Rules = operational/property policy engine.
                             House Rules = guest-facing behavioural rules.
                             They are different in nature and the operational one leads. */}
                        <div style={sHead}>Settlement Rules</div>
                        <div style={{
                            background: 'var(--color-surface-2)',
                            border: '1px solid var(--color-border)',
                            borderRadius: 'var(--radius-md)',
                            padding: 'var(--space-4)',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 'var(--space-5)',
                        }}>
                            {!crLoaded && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>Loading settlement rules…</div>}

                            {/* Deposit */}
                            <div>
                                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-3)' }}>Deposit</div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-3)' }}>
                                    <button onClick={() => setCrDepositEnabled(v => !v)} style={{ position: 'relative', width: 44, height: 24, borderRadius: 12, background: crDepositEnabled ? 'var(--color-primary)' : 'var(--color-border)', border: 'none', cursor: 'pointer', transition: 'background 0.2s', flexShrink: 0 }}>
                                        <span style={{ position: 'absolute', top: 3, left: crDepositEnabled ? 22 : 3, width: 18, height: 18, borderRadius: '50%', background: '#fff', transition: 'left 0.2s', display: 'block' }} />
                                    </button>
                                    <div>
                                        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>{crDepositEnabled ? 'Deposit Required' : 'No Deposit'}</div>
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>Worker must collect deposit at check-in when enabled</div>
                                    </div>
                                </div>
                                {crDepositEnabled && (
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 'var(--space-3)' }}>
                                            <div>
                                                <label style={lStyle}>Deposit Amount</label>
                                                <input style={iStyle} value={crDepositAmount} onChange={e => setCrDepositAmount(e.target.value)} type="number" min="0" step="1" placeholder="e.g. 5000" />
                                            </div>
                                            <div>
                                                <label style={lStyle}>Currency</label>
                                                <select style={{ ...iStyle, cursor: 'pointer', minWidth: 90 }} value={crDepositCurrency} onChange={e => setCrDepositCurrency(e.target.value)}>
                                                    {['THB','USD','EUR','GBP','SGD','AUD','HKD','JPY','AED'].map(c => <option key={c} value={c}>{c}</option>)}
                                                </select>
                                            </div>
                                        </div>
                                        <div>
                                            <label style={lStyle}>Notes (optional)</label>
                                            <input style={iStyle} value={crDepositNotes} onChange={e => setCrDepositNotes(e.target.value)} placeholder="e.g. Refundable by bank transfer within 7 days" />
                                        </div>
                                    </div>
                                )}
                            </div>

                            <div style={{ borderTop: '1px solid var(--color-border)' }} />

                            {/* Electricity Billing */}
                            <div>
                                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-3)' }}>Electricity Billing</div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-3)' }}>
                                    <button onClick={() => setCrElecEnabled(v => !v)} style={{ position: 'relative', width: 44, height: 24, borderRadius: 12, background: crElecEnabled ? 'var(--color-primary)' : 'var(--color-border)', border: 'none', cursor: 'pointer', transition: 'background 0.2s', flexShrink: 0 }}>
                                        <span style={{ position: 'absolute', top: 3, left: crElecEnabled ? 22 : 3, width: 18, height: 18, borderRadius: '50%', background: '#fff', transition: 'left 0.2s', display: 'block' }} />
                                    </button>
                                    <div>
                                        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>{crElecEnabled ? 'Electricity Billed to Guest' : 'Electricity Not Billed'}</div>
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>Worker captures meter readings at check-in/out when enabled</div>
                                    </div>
                                </div>
                                {crElecEnabled && (
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 'var(--space-3)' }}>
                                            <div>
                                                <label style={lStyle}>Rate per kWh</label>
                                                <input style={iStyle} value={crElecRate} onChange={e => setCrElecRate(e.target.value)} type="number" min="0" step="0.01" placeholder="e.g. 8.50" />
                                            </div>
                                            <div>
                                                <label style={lStyle}>Currency</label>
                                                <select style={{ ...iStyle, cursor: 'pointer', minWidth: 90 }} value={crElecCurrency} onChange={e => setCrElecCurrency(e.target.value)}>
                                                    {['THB','USD','EUR','GBP','SGD','AUD','HKD','JPY','AED'].map(c => <option key={c} value={c}>{c}</option>)}
                                                </select>
                                            </div>
                                        </div>
                                        <div>
                                            <label style={lStyle}>Notes (optional)</label>
                                            <input style={iStyle} value={crElecNotes} onChange={e => setCrElecNotes(e.target.value)} placeholder="e.g. Bill split based on days occupied" />
                                        </div>
                                    </div>
                                )}
                            </div>

                            <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: 'var(--space-2)', borderTop: '1px solid var(--color-border)' }}>
                                <button
                                    title="Saves deposit and electricity rules only"
                                    onClick={async () => {
                                        setCrSaving(true);
                                        try {
                                            await apiFetch(`/admin/properties/${propertyId}/charge-rules`, {
                                                method: 'PUT',
                                                body: JSON.stringify({
                                                    deposit_enabled: crDepositEnabled,
                                                    deposit_amount: crDepositEnabled && crDepositAmount ? parseFloat(crDepositAmount) : null,
                                                    deposit_currency: crDepositCurrency,
                                                    deposit_notes: crDepositNotes.trim() || null,
                                                    electricity_enabled: crElecEnabled,
                                                    electricity_rate_kwh: crElecEnabled && crElecRate ? parseFloat(crElecRate) : null,
                                                    electricity_currency: crElecCurrency,
                                                    electricity_notes: crElecNotes.trim() || null,
                                                }),
                                            });
                                            showNotice('✓ Settlement rules saved');
                                        } catch { showNotice('Save failed — check your inputs'); }
                                        setCrSaving(false);
                                    }}
                                    disabled={crSaving}
                                    style={{ padding: '9px 22px', borderRadius: 'var(--radius-md)', background: crSaving ? 'var(--color-border)' : 'var(--color-primary)', color: '#fff', border: 'none', cursor: crSaving ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: 'var(--text-sm)', boxShadow: crSaving ? 'none' : '0 2px 12px rgba(99,102,241,0.35)' }}
                                >{crSaving ? 'Saving…' : 'Save Settlement Rules'}</button>
                            </div>
                        </div>

                        {/* ── House Rules ──────────────────────────────────────────── */}
                        <div style={{ ...sHead, marginTop: 'var(--space-7)' }}>House Rules</div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginBottom: 'var(--space-3)' }}>
                            Guest-facing behavioural guidelines shown on booking confirmation.
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
                            {editHouseRules.length > 0 && (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                                    {editHouseRules.map((rule, idx) => (
                                        <div key={idx} style={{
                                            display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
                                            background: 'var(--color-surface-2)', borderRadius: 'var(--radius-sm)',
                                            padding: '6px 10px', border: '1px solid var(--color-border)',
                                        }}>
                                            <span style={{ flex: 1, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{rule}</span>
                                            <button
                                                onClick={() => setEditHouseRules((prev: string[]) => prev.filter((_: string, i: number) => i !== idx))}
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
                                    onKeyDown={e => { if (e.key === 'Enter' && newRule.trim()) { setEditHouseRules((prev: string[]) => [...prev, newRule.trim()]); setNewRule(''); } }}
                                    placeholder="e.g. No smoking · No parties · Shoes off indoors"
                                    style={{ flex: 1, ...iStyle }}
                                />
                                <button
                                    onClick={() => { if (!newRule.trim()) return; setEditHouseRules((prev: string[]) => [...prev, newRule.trim()]); setNewRule(''); }}
                                    style={{ padding: '0 16px', borderRadius: 'var(--radius-sm)', border: 'none', background: 'var(--color-primary)', color: '#fff', fontWeight: 700, fontSize: 'var(--text-sm)', cursor: 'pointer' }}
                                >+</button>
                            </div>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>Press Enter or + to add. ✕ to remove.</div>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 'var(--space-2)' }}>
                            <button
                                title="Saves house rules only"
                                onClick={async () => {
                                    setEditSaving(true);
                                    try {
                                        await apiFetch(`/properties/${propertyId}`, { method: 'PATCH', body: JSON.stringify({ house_rules: editHouseRules }) });
                                        showNotice('✓ House rules saved');
                                    } catch { showNotice('Save failed'); }
                                    setEditSaving(false);
                                }}
                                disabled={editSaving}
                                style={{ padding: '8px 22px', borderRadius: 'var(--radius-md)', background: editSaving ? 'var(--color-border)' : 'var(--color-primary)', color: '#fff', border: 'none', cursor: editSaving ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: 'var(--text-sm)', boxShadow: editSaving ? 'none' : '0 2px 10px rgba(99,102,241,0.35)' }}
                            >{editSaving ? 'Saving…' : 'Save House Rules'}</button>
                        </div>

                    </div>
                );
            })()}

            {/* ============ MEDIA / Gallery ============ */}
            {tab === 'media' && subTab === 'gallery' && !loading && (
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

            {/* ============ SETTINGS / Integrations ============ */}
            {tab === 'settings' && subTab === 'integrations' && !loading && (
                <OtaSettingsTab propertyId={propertyId} />
            )}

            {/* ============ SETTINGS / Self Check-in — Phase 1018 ============ */}
            {tab === 'settings' && subTab === 'self-checkin' && !loading && (
            <SelfCheckinConfigPanel
                    propertyId={propertyId}
                    property={p}
                    inheritedDeposit={crDepositEnabled}
                    inheritedElec={crElecEnabled}
                    onSaved={(updated) => { setProperty(updated); showNotice('✓ Self check-in configuration saved'); }}
                />
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Phase 1018 — Self Check-in Property Configuration Panel
// ---------------------------------------------------------------------------

const MODE_OPTIONS = [
    {
        key: 'disabled',
        label: 'Disabled',
        desc: 'No self check-in. Property uses staffed check-in only.',
        color: '#64748b',
    },
    {
        key: 'default',
        label: 'Default Self Check-in',
        desc: 'All bookings use self check-in by default. Portal link sent automatically 1–3 days before arrival. Individual bookings can be overridden back to staffed.',
        color: '#6366f1',
    },
    {
        key: 'late_only',
        label: 'Late Only (Exception)',
        desc: 'Property uses staffed check-in. Self check-in is available only as an explicit exception for guests arriving outside staffed hours.',
        color: '#f59e0b',
    },
];

const PRE_ACCESS_STEP_OPTIONS = [
    // 'deposit' intentionally NOT here — always rendered as locked inherited row from Settlement Rules
    { key: 'agreement', label: '📋 House Rules Agreement' },
    { key: 'id_photo',  label: '🪪 ID / Passport Photo' },
    { key: 'selfie',    label: '🤳 Selfie Verification' },
];

const POST_ENTRY_STEP_OPTIONS = [
    // 'electricity_meter' intentionally NOT here — always rendered as locked inherited row from Settlement Rules
    { key: 'arrival_photos', label: '📷 Arrival Photos' },
];


function SelfCheckinConfigPanel({
    propertyId, property, inheritedDeposit, inheritedElec, onSaved,
}: {
    propertyId: string;
    property: any;
    inheritedDeposit: boolean;   // from parent crDepositEnabled — charge-rules API
    inheritedElec: boolean;      // from parent crElecEnabled — charge-rules API
    onSaved: (updated: any) => void;
}) {
    const cfg = property?.self_checkin_config || {};
    // inheritedDeposit and inheritedElec come directly from parent props (crDepositEnabled / crElecEnabled)
    // They are NOT derived from property?.charge_rules (that field doesn't exist in the API response).



    const [mode, setMode] = useState<string>(cfg.mode || 'disabled');
    // Pre-access steps: never include 'deposit' as a manual checkbox
    const [preSteps, setPreSteps] = useState<string[]>(
        (cfg.pre_access_steps || ['agreement']).filter((s: string) => s !== 'deposit')
    );
    // Post-entry steps: never include 'electricity_meter' as a manual checkbox
    const [postSteps, setPostSteps] = useState<string[]>(
        (cfg.post_entry_steps || ['arrival_photos']).filter((s: string) => s !== 'electricity_meter')
    );
    const [tokenTtl, setTokenTtl] = useState<string>(String(cfg.token_ttl_hours ?? 72));
    // Arrival guide
    const [entryInstructions, setEntryInstructions] = useState<string>(cfg.arrival_guide?.entry_instructions || '');
    const [onArrival, setOnArrival] = useState<string>(cfg.arrival_guide?.on_arrival_what_to_do || '');
    const [electricity, setElectricity] = useState<string>(cfg.arrival_guide?.electricity_instructions || '');
    const [keyLocations, setKeyLocations] = useState<string>(cfg.arrival_guide?.key_locations || '');
    const [emergencyContact, setEmergencyContact] = useState<string>(cfg.arrival_guide?.emergency_contact || '');

    const [saving, setSaving] = useState(false);
    const [err, setErr] = useState<string | null>(null);

    const toggleStep = (list: string[], setList: (v: string[]) => void, key: string) => {
        setList(list.includes(key) ? list.filter(k => k !== key) : [...list, key]);
    };

    const handleSave = async () => {
        setSaving(true);
        setErr(null);
        try {
            const BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';
            const tok = getToken();
            const payload = {
                mode,
                // Pre-access: free steps + deposit appended if inherited from Rules
                pre_access_steps: inheritedDeposit ? [...preSteps, 'deposit'] : preSteps,
                // Post-entry: free steps + electricity_meter appended if inherited from Rules
                post_entry_steps: inheritedElec ? [...postSteps, 'electricity_meter'] : postSteps,
                token_ttl_hours: parseInt(tokenTtl) || 72,
                arrival_guide: {
                    entry_instructions: entryInstructions.trim() || null,
                    on_arrival_what_to_do: onArrival.trim() || null,
                    electricity_instructions: electricity.trim() || null,
                    key_locations: keyLocations.trim() || null,
                    emergency_contact: emergencyContact.trim() || null,
                },
            };
            const res = await fetch(`${BASE}/properties/${propertyId}/self-checkin-config`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
                },
                body: JSON.stringify(payload),
            });
            if (!res.ok) {
                const e = await res.json().catch(() => ({}));
                throw new Error(e.detail || `HTTP ${res.status}`);
            }
            const updated = await res.json();
            onSaved(updated);
        } catch (e: any) {
            setErr(e.message || 'Save failed');
        } finally {
            setSaving(false);
        }
    };

    const isSel = (k: string) => mode === k;

    return (
        <div style={{ maxWidth: 720 }}>
            <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)', marginBottom: 4 }}>
                Self Check-in Configuration
            </h2>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginBottom: 24 }}>
                Controls how guests check themselves in for this property.
                Mode affects all new bookings. Existing bookings can be overridden individually.
            </p>

            {/* Mode selector */}
            <div style={{ marginBottom: 28 }}>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
                    Check-in Mode
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {MODE_OPTIONS.map(opt => (
                        <div
                            key={opt.key}
                            onClick={() => setMode(opt.key)}
                            style={{
                                display: 'flex', alignItems: 'flex-start', gap: 14,
                                padding: '14px 16px', borderRadius: 'var(--radius-lg)', cursor: 'pointer',
                                border: `2px solid ${isSel(opt.key) ? opt.color : 'var(--color-border)'}`,
                                background: isSel(opt.key) ? `${opt.color}12` : 'var(--color-surface)',
                                transition: 'all 0.15s',
                            }}
                        >
                            <div style={{
                                width: 18, height: 18, borderRadius: '50%', flexShrink: 0, marginTop: 2,
                                border: `2px solid ${isSel(opt.key) ? opt.color : 'var(--color-border)'}`,
                                background: isSel(opt.key) ? opt.color : 'transparent',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                            }}>
                                {isSel(opt.key) && <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#fff' }} />}
                            </div>
                            <div>
                                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: isSel(opt.key) ? opt.color : 'var(--color-text)', marginBottom: 2 }}>
                                    {opt.label}
                                </div>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', lineHeight: 1.5 }}>
                                    {opt.desc}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Step requirements — only shown when mode is not disabled */}
            {mode !== 'disabled' && (
                <>
                    <div style={{ marginBottom: 24 }}>
                        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                            Gate 1 — Pre-Access Steps
                        </div>
                        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 10 }}>
                            Guest must complete all checked steps before the access code is released.
                        </p>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                            {/* Free user-configurable steps */}
                            {PRE_ACCESS_STEP_OPTIONS.map(opt => (
                                <label key={opt.key} style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
                                    <input
                                        type="checkbox"
                                        checked={preSteps.includes(opt.key)}
                                        onChange={() => toggleStep(preSteps, setPreSteps, opt.key)}
                                        style={{ width: 16, height: 16, accentColor: 'var(--color-primary)' }}
                                    />
                                    {opt.label}
                                </label>
                            ))}
                            {/* Phase 1019b: Deposit — inherited from Settlement Rules.
                                This IS the real Deposit Acknowledgement step row.
                                No duplicate row. Shows locked ON or locked OFF based on Rules. */}
                            <div style={{
                                display: 'flex', alignItems: 'center', gap: 10,
                                padding: '6px 10px', borderRadius: 8,
                                background: inheritedDeposit ? '#6366f108' : 'transparent',
                                border: `1px solid ${inheritedDeposit ? '#6366f133' : 'var(--color-border)'}`,
                                opacity: inheritedDeposit ? 1 : 0.5,
                            }}>
                                <input type="checkbox" checked={inheritedDeposit} readOnly
                                    style={{ width: 16, height: 16, accentColor: 'var(--color-primary)', cursor: 'not-allowed' }} />
                                <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)', flex: 1 }}>
                                    💳 Deposit Acknowledgement
                                </span>
                                <span style={{
                                    fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 6,
                                    background: inheritedDeposit ? '#6366f118' : '#6b728018',
                                    color: inheritedDeposit ? '#6366f1' : '#6b7280',
                                    border: `1px solid ${inheritedDeposit ? '#6366f133' : '#6b728033'}`,
                                    whiteSpace: 'nowrap',
                                }}>
                                    🔒 From Rules — {inheritedDeposit ? 'ON' : 'OFF'}
                                </span>
                            </div>
                        </div>
                    </div>

                    <div style={{ marginBottom: 28 }}>
                        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                            Gate 2 — Post-Entry Steps
                        </div>
                        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 10 }}>
                            Non-blocking. Guest completes these after arriving. Incomplete items create a follow-up task after 2h.
                        </p>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                            {/* Phase 1019b: Electricity Meter — inherited from Settlement Rules.
                                This IS the real Electricity Meter Reading step row.
                                No duplicate row. Shows locked ON or locked OFF based on Rules. */}
                            <div style={{
                                display: 'flex', alignItems: 'center', gap: 10,
                                padding: '6px 10px', borderRadius: 8,
                                background: inheritedElec ? '#f59e0b08' : 'transparent',
                                border: `1px solid ${inheritedElec ? '#f59e0b33' : 'var(--color-border)'}`,
                                opacity: inheritedElec ? 1 : 0.5,
                            }}>
                                <input type="checkbox" checked={inheritedElec} readOnly
                                    style={{ width: 16, height: 16, accentColor: '#f59e0b', cursor: 'not-allowed' }} />
                                <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)', flex: 1 }}>
                                    ⚡ Electricity Meter Reading
                                </span>
                                <span style={{
                                    fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 6,
                                    background: inheritedElec ? '#f59e0b18' : '#6b728018',
                                    color: inheritedElec ? '#d97706' : '#6b7280',
                                    border: `1px solid ${inheritedElec ? '#f59e0b33' : '#6b728033'}`,
                                    whiteSpace: 'nowrap',
                                }}>
                                    🔒 From Rules — {inheritedElec ? 'ON' : 'OFF'}
                                </span>
                            </div>
                            {/* Free user-configurable steps */}
                            {POST_ENTRY_STEP_OPTIONS.map(opt => (
                                <label key={opt.key} style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
                                    <input
                                        type="checkbox"
                                        checked={postSteps.includes(opt.key)}
                                        onChange={() => toggleStep(postSteps, setPostSteps, opt.key)}
                                        style={{ width: 16, height: 16, accentColor: 'var(--color-primary)' }}
                                    />
                                    {opt.label}
                                </label>
                            ))}
                        </div>
                    </div>

                    {/* Arrival guide */}
                    <div style={{ marginBottom: 28, background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 14 }}>
                            Arrival Guide
                        </div>
                        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 14 }}>
                            Shown to the guest in the self check-in portal. Fill only what's relevant — blank fields are hidden.
                        </p>
                        {[
                            { label: '🚪 Entry Instructions', val: entryInstructions, set: setEntryInstructions, placeholder: 'e.g. Gate code is 1234. Enter through the main gate and proceed to Unit 3B.' },
                            { label: '📋 On Arrival – What To Do', val: onArrival, set: setOnArrival, placeholder: 'e.g. Check in at the front desk, leave shoes at the door…' },
                            { label: '⚡ Electricity & Utilities', val: electricity, set: setElectricity, placeholder: 'e.g. Breaker box is in the kitchen. A/C remote is on the bed.' },
                            { label: '🔑 Key / Lockbox Locations', val: keyLocations, set: setKeyLocations, placeholder: 'e.g. Key fob is in the lockbox by the gate. Code: 5678.' },
                            { label: '🆘 Emergency Contact', val: emergencyContact, set: setEmergencyContact, placeholder: 'e.g. Property manager: +66 81 234 5678 (Line / WhatsApp)' },
                        ].map(f => (
                            <div key={f.label} style={{ marginBottom: 14 }}>
                                <label style={{ display: 'block', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 4, fontWeight: 600 }}>{f.label}</label>
                                <textarea
                                    value={f.val}
                                    onChange={e => f.set(e.target.value)}
                                    placeholder={f.placeholder}
                                    rows={2}
                                    style={{
                                        width: '100%', background: 'var(--color-surface-2)',
                                        border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)',
                                        padding: '8px 10px', color: 'var(--color-text)',
                                        fontSize: 'var(--text-sm)', resize: 'vertical', outline: 'none',
                                        lineHeight: 1.5,
                                    }}
                                />
                            </div>
                        ))}
                    </div>

                    {/* Token TTL */}
                    <div style={{ marginBottom: 24 }}>
                        <label style={{ display: 'block', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 6, fontWeight: 600 }}>
                            Portal Link Validity (hours)
                        </label>
                        <input
                            type="number" min={1} max={720}
                            value={tokenTtl}
                            onChange={e => setTokenTtl(e.target.value)}
                            style={{
                                width: 100, background: 'var(--color-surface-2)',
                                border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)',
                                padding: '8px 10px', color: 'var(--color-text)', fontSize: 'var(--text-sm)', outline: 'none',
                            }}
                        />
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginLeft: 8 }}>
                            Default: 72h. The guest portal link expires after this time.
                        </span>
                    </div>
                </>
            )}

            {/* Error */}
            {err && (
                <div style={{
                    background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                    borderRadius: 'var(--radius-md)', padding: '10px 14px',
                    fontSize: 'var(--text-sm)', color: '#f87171', marginBottom: 16,
                }}>
                    {err}
                </div>
            )}

            {/* Save */}
            <button
                id="btn-save-self-checkin-config"
                onClick={handleSave}
                disabled={saving}
                style={{
                    padding: '12px 28px', borderRadius: 'var(--radius-md)', border: 'none',
                    background: saving ? 'var(--color-surface-2)' : 'var(--color-primary)',
                    color: saving ? 'var(--color-text-faint)' : '#fff', fontWeight: 700,
                    fontSize: 'var(--text-sm)', cursor: saving ? 'not-allowed' : 'pointer',
                    transition: 'all 0.2s',
                }}
            >
                {saving ? 'Saving…' : 'Save Self Check-in Config'}
            </button>

            {mode === 'disabled' && (
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 12 }}>
                    When mode is Disabled, no self check-in panel will appear on bookings for this property.
                </p>
            )}
        </div>
    );
}
