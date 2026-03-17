'use client';

/**
 * Operational Core — Phase A: Property Detail (6-Tab View)
 * Architecture source: .agent/architecture/property-detail.md
 *
 * Tabs: Overview | Reference Photos | House Info | Tasks | Issues | Audit
 */

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getToken } from '@/lib/api';

type Tab = 'overview' | 'photos' | 'house-info' | 'tasks' | 'issues' | 'audit';

const TAB_LABELS: Record<Tab, string> = {
    overview: 'Overview',
    photos: 'Reference Photos',
    'house-info': 'House Info',
    tasks: 'Tasks',
    issues: 'Issues',
    audit: 'Audit',
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
    const [tasks, setTasks] = useState<any[]>([]);
    const [auditEntries, setAuditEntries] = useState<any[]>([]);
    const [issues, setIssues] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [notice, setNotice] = useState<string | null>(null);

    const showNotice = (msg: string) => { setNotice(msg); setTimeout(() => setNotice(null), 3000); };

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [propRes, photosRes, tasksRes, auditRes, issuesRes] = await Promise.allSettled([
                apiFetch(`/properties/${propertyId}`),
                apiFetch(`/properties/${propertyId}/reference-photos`),
                apiFetch(`/tasks?property_id=${propertyId}&limit=50`),
                apiFetch(`/admin/audit?entity_id=${propertyId}&limit=100`),
                apiFetch(`/problem-reports?property_id=${propertyId}&limit=50`),
            ]);
            if (propRes.status === 'fulfilled') setProperty(propRes.value);
            if (photosRes.status === 'fulfilled') setPhotos(photosRes.value?.photos || []);
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

            {/* Header */}
            <div style={{ marginBottom: 'var(--space-4)', display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
                <button onClick={() => router.push('/admin/properties')} style={{
                    background: 'none', border: 'none', color: 'var(--color-text-dim)', cursor: 'pointer',
                    fontSize: 'var(--text-lg)', padding: 0,
                }}>←</button>
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
                    {/* Check-in/out times */}
                    <div style={cardStyle}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>Check-in / Check-out</div>
                        <div style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--color-text)' }}>
                            {p.checkin_time || '15:00'} → {p.checkout_time || '11:00'}
                        </div>
                    </div>

                    {/* Deposit */}
                    <div style={cardStyle}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>Deposit</div>
                        <div style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: p.deposit_required ? 'var(--color-warn)' : 'var(--color-text-faint)' }}>
                            {p.deposit_required ? `${p.deposit_currency || 'THB'} ${p.deposit_amount || '—'}` : 'Not required'}
                        </div>
                        {p.deposit_required && (
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 4 }}>
                                Method: {p.deposit_method || 'cash'}
                            </div>
                        )}
                    </div>

                    {/* GPS */}
                    <div style={cardStyle}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>Location</div>
                        {p.latitude && p.longitude ? (
                            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)', fontFamily: 'var(--font-mono)' }}>
                                {Number(p.latitude).toFixed(6)}, {Number(p.longitude).toFixed(6)}
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 2 }}>
                                    Source: {p.gps_source || '—'}
                                </div>
                            </div>
                        ) : (
                            <div style={{ color: 'var(--color-warn)', fontSize: 'var(--text-sm)', fontStyle: 'italic' }}>
                                ⚠ GPS not set — setup required
                            </div>
                        )}
                    </div>

                    {/* Tasks summary */}
                    <div style={cardStyle}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>Active Tasks</div>
                        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: tasks.length > 0 ? 'var(--color-warn)' : 'var(--color-ok)' }}>
                            {tasks.filter(t => t.status !== 'completed' && t.status !== 'cancelled').length}
                        </div>
                    </div>

                    {/* Reference photos count */}
                    <div style={cardStyle}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>Reference Photos</div>
                        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: photos.length > 0 ? 'var(--color-text)' : 'var(--color-warn)' }}>
                            {photos.length}
                        </div>
                        {photos.length === 0 && (
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-warn)', marginTop: 4, fontStyle: 'italic' }}>
                                Setup required before activation
                            </div>
                        )}
                    </div>

                    {/* House Rules */}
                    <div style={cardStyle}>
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
                    {/* Upload button */}
                    <div style={{ marginBottom: 'var(--space-4)' }}>
                        <label style={{
                            display: 'inline-flex', alignItems: 'center', gap: 8,
                            padding: 'var(--space-2) var(--space-4)', borderRadius: 'var(--radius-md)',
                            background: 'var(--color-primary)', color: '#fff',
                            fontSize: 'var(--text-sm)', fontWeight: 600, cursor: 'pointer',
                        }}>
                            📷 Upload Photo
                            <input type="file" accept="image/*" multiple style={{ display: 'none' }}
                                onChange={async (e) => {
                                    const files = e.target.files;
                                    if (!files || files.length === 0) return;
                                    for (const file of Array.from(files)) {
                                        try {
                                            const formData = new FormData();
                                            formData.append('file', file);
                                            formData.append('room_label', 'general');
                                            const token = getToken();
                                            await fetch(`${BASE}/properties/${propertyId}/reference-photos`, {
                                                method: 'POST',
                                                headers: token ? { Authorization: `Bearer ${token}` } : {},
                                                body: formData,
                                            });
                                        } catch { /* best-effort */ }
                                    }
                                    showNotice(`📷 ${files.length} photo(s) uploaded`);
                                    load();
                                }}
                            />
                        </label>
                    </div>
                    {photos.length === 0 ? (
                        <div style={{ ...cardStyle, textAlign: 'center', padding: 'var(--space-8)' }}>
                            <div style={{ fontSize: 'var(--text-lg)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>No Reference Photos</div>
                            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-faint)' }}>
                                Reference photos are required before a property can become Active.
                                Upload photos for each room area.
                            </p>
                        </div>
                    ) : (
                        <>
                            {/* Group by room_label */}
                            {Object.entries(
                                photos.reduce((acc: Record<string, any[]>, photo) => {
                                    const room = photo.room_label || 'Other';
                                    (acc[room] = acc[room] || []).push(photo);
                                    return acc;
                                }, {})
                            ).map(([room, roomPhotos]) => (
                                <div key={room} style={{ marginBottom: 'var(--space-5)' }}>
                                    <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)', marginBottom: 'var(--space-3)', textTransform: 'capitalize' }}>
                                        {room}
                                    </h3>
                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 'var(--space-3)' }}>
                                        {(roomPhotos as any[]).map((photo: any) => (
                                            <div key={photo.id} style={{
                                                borderRadius: 'var(--radius-md)', overflow: 'hidden',
                                                border: '1px solid var(--color-border)', aspectRatio: '4/3',
                                                background: 'var(--color-surface-2)', position: 'relative',
                                            }}>
                                                <img src={photo.photo_url} alt={room}
                                                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                                    onError={e => (e.currentTarget.style.display = 'none')} />
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
                                </div>
                            ))}
                        </>
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
        </div>
    );
}
