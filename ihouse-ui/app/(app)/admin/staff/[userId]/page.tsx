'use client';
/**
 * Phase 843 — Staff Full-Page Edit/Detail
 * /admin/staff/[userId]
 *
 * Loads existing staff record, normalizes legacy roles on read,
 * saves in canonical model on write.
 *
 * Legacy normalization:
 *   cleaner       → role=worker, worker_roles=[cleaner]
 *   checkin_staff → role=worker, worker_roles=[checkin]
 *   maintenance   → role=worker, worker_roles=[maintenance]
 *
 * Layout: back=top-left, save=sticky bottom-right footer
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { getToken } from '@/lib/api';
import { uploadPropertyPhoto, ACCEPTED_IMAGE_TYPES } from '@/lib/uploadPhoto';

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

// ── Legacy Role Normalization ────────────────────────────────────────────────

const LEGACY_ROLE_MAP: Record<string, { role: string; worker_roles: string[] }> = {
  cleaner:        { role: 'worker', worker_roles: ['cleaner'] },
  checkin_staff:  { role: 'worker', worker_roles: ['checkin'] },
  checkout_staff: { role: 'worker', worker_roles: ['checkout'] },
  maintenance:    { role: 'worker', worker_roles: ['maintenance'] },
};

type RawRecord = {
  user_id: string;
  role: string;
  display_name?: string;
  phone?: string;
  address?: string;
  emergency_contact?: string;
  photo_url?: string;
  language?: string;
  is_active?: boolean;
  notes?: string;
  worker_roles?: string[];
  maintenance_specializations?: string[];
  comm_preference?: Record<string, string>;
  permissions?: Record<string, any>;
  created_at?: string;
  updated_at?: string;
};

type NormalizedRecord = RawRecord & {
  _legacyRole?: string; // set if the original role was a legacy value
};

function normalizeLegacyRole(raw: RawRecord): NormalizedRecord {
  const mapped = LEGACY_ROLE_MAP[raw.role];
  if (!mapped) return raw; // already canonical
  return {
    ...raw,
    role: mapped.role,
    // Only backfill worker_roles if the row has none yet
    worker_roles: raw.worker_roles?.length ? raw.worker_roles : mapped.worker_roles,
    _legacyRole: raw.role,
  };
}

// ── Constants ──────────────────────────────────────────────────────────────

const CANONICAL_ROLES = [
  { value: 'admin',   label: 'Admin' },
  { value: 'manager', label: 'Operational Manager' },
  { value: 'worker',  label: 'Worker' },
  { value: 'owner',   label: 'Owner' },
];
const WORKER_ROLES = [
  { value: 'cleaner',     label: 'Cleaner' },
  { value: 'checkin',     label: 'Check-in' },
  { value: 'checkout',    label: 'Check-out' },
  { value: 'maintenance', label: 'Maintenance' },
];
const MAINTENANCE_SPECS = [
  { value: 'general',      label: 'General' },
  { value: 'gardener',     label: 'Gardener' },
  { value: 'pool',         label: 'Pool' },
  { value: 'plumber',      label: 'Plumber' },
  { value: 'painter',      label: 'Painter' },
  { value: 'electrician',  label: 'Electrician' },
  { value: 'ac',           label: 'AC' },
  { value: 'other',        label: 'Other' },
];
const LANGUAGES = [
  { value: 'en', label: 'English (EN)' },
  { value: 'th', label: 'Thai (TH)' },
  { value: 'he', label: 'Hebrew (HE)' },
  { value: 'zh', label: 'Mandarin (ZH)' },
  { value: 'es', label: 'Spanish (ES)' },
  { value: 'fr', label: 'French (FR)' },
  { value: 'ru', label: 'Russian (RU)' },
  { value: 'ar', label: 'Arabic (AR)' },
  { value: 'ja', label: 'Japanese (JA)' },
  { value: 'pt', label: 'Portuguese (PT)' },
  { value: 'hi', label: 'Hindi (HI)' },
  { value: 'de', label: 'German (DE)' },
];

const COUNTRY_CODES_OPTS = [
  { code: '+66', label: '🇹🇭 +66' },
  { code: '+1', label: '🇺🇸 +1' },
  { code: '+44', label: '🇬🇧 +44' },
  { code: '+972', label: '🇮🇱 +972' },
  { code: '+95', label: '🇲🇲 +95' },
  { code: '+856', label: '🇱🇦 +856' },
  { code: '+855', label: '🇰🇭 +855' },
  { code: '+60', label: '🇲🇾 +60' },
  { code: '+65', label: '🇸🇬 +65' },
  { code: '+81', label: '🇯🇵 +81' },
  { code: '+7', label: '🇷🇺 +7' },
  { code: '+86', label: '🇨🇳 +86' },
  { code: '+91', label: '🇮🇳 +91' },
  { code: '+49', label: '🇩🇪 +49' },
  { code: '+33', label: '🇫🇷 +33' },
  { code: '+34', label: '🇪🇸 +34' },
];

// ── Styles ──────────────────────────────────────────────────────────────────

const inputStyle: React.CSSProperties = {
  width: '100%', background: 'var(--color-surface-2)',
  border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)',
  padding: '9px 12px', color: 'var(--color-text)',
  fontSize: 'var(--text-sm)', outline: 'none', boxSizing: 'border-box',
};
const labelStyle: React.CSSProperties = {
  fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)',
  display: 'block', marginBottom: 6, fontWeight: 500,
  textTransform: 'uppercase', letterSpacing: '0.04em',
};
const sectionHeadStyle: React.CSSProperties = {
  fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)',
  textTransform: 'uppercase', letterSpacing: '0.07em',
  marginTop: 'var(--space-5)', marginBottom: 'var(--space-3)',
  paddingBottom: 'var(--space-2)', borderBottom: '1px solid var(--color-border)',
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <label style={labelStyle}>{label}</label>
      {children}
    </div>
  );
}

function CheckGroup({ options, selected, onChange }: {
  options: { value: string; label: string }[];
  selected: string[];
  onChange: (v: string[]) => void;
}) {
  const toggle = (v: string) =>
    onChange(selected.includes(v) ? selected.filter(x => x !== v) : [...selected, v]);
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px 20px' }}>
      {options.map(o => (
        <label key={o.value} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
          <input type="checkbox" checked={selected.includes(o.value)} onChange={() => toggle(o.value)}
            style={{ accentColor: 'var(--color-primary)', width: 16, height: 16 }} />
          {o.label}
        </label>
      ))}
    </div>
  );
}

function Avatar({ name, photoUrl }: { name: string; photoUrl: string }) {
  const initials = name?.trim()
    ? name.trim().split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase()
    : '?';
  return (
    <div style={{
      width: 80, height: 80, borderRadius: '50%', flexShrink: 0,
      background: photoUrl ? 'transparent' : 'var(--color-primary)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 28, fontWeight: 700, color: '#fff', overflow: 'hidden',
      border: '2px solid var(--color-border)',
    }}>
      {photoUrl
        ? <img src={photoUrl} alt="avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        : initials}
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function EditStaffPage() {
  const router = useRouter();
  const params = useParams();
  const rawUserId = decodeURIComponent(params.userId as string);

  // Loading state
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [legacyRole, setLegacyRole] = useState<string | undefined>(undefined);

  // Tab state
  const [activeTab, setActiveTab] = useState<0 | 1 | 2>(0);

  // Tab 1 — Profile
  const [fullName, setFullName] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [photoUrl, setPhotoUrl] = useState('');
  const [phoneCode, setPhoneCode] = useState('+66');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [address, setAddress] = useState('');
  const [emergencyName, setEmergencyName] = useState('');
  const [emergencyCode, setEmergencyCode] = useState('+66');
  const [emergencyNumber, setEmergencyNumber] = useState('');
  const [language, setLanguage] = useState('en');
  const [isActive, setIsActive] = useState(true);
  const [notes, setNotes] = useState('');

  // Tab 2 — Role & Assignment
  const [role, setRole] = useState('worker');
  const [workerRoles, setWorkerRoles] = useState<string[]>([]);
  const [maintenanceSpecs, setMaintenanceSpecs] = useState<string[]>([]);
  const [assignedProperties, setAssignedProperties] = useState<string[]>([]);
  const [originalAssignments, setOriginalAssignments] = useState<string[]>([]);
  const [availableProperties, setAvailableProperties] = useState<{ id: string; name: string }[]>([]);

  // Tab 3 — Comms
  const [whatsapp, setWhatsapp] = useState('');
  const [telegram, setTelegram] = useState('');
  const [line, setLine] = useState('');
  const [sms, setSms] = useState('');

  // UI state
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const [createdAt, setCreatedAt] = useState<string | undefined>();
  const [updatedAt, setUpdatedAt] = useState<string | undefined>();
  
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [raw, assignmentsRes, propsRes] = await Promise.all([
        apiFetch<RawRecord>(`/permissions/${encodeURIComponent(rawUserId)}`),
        apiFetch<any>(`/staff/assignments/${encodeURIComponent(rawUserId)}`).catch(() => ({ property_ids: [] })),
        apiFetch<any>('/admin/properties').catch(() => ({ properties: [] })),
      ]);

      const record = normalizeLegacyRole(raw);
      setLegacyRole(record._legacyRole);

      // Populate Tab 1
      setDisplayName(record.display_name || '');
      setFullName(record.display_name || '');
      setPhotoUrl(record.photo_url || '');

      const pMatch = (record.phone || '').match(/^(\+\d{1,3})\s*(.*)$/);
      if (pMatch) {
        setPhoneCode(pMatch[1]);
        setPhoneNumber(pMatch[2].replace(/\s+/g, ''));
      } else {
        setPhoneCode('+66');
        setPhoneNumber((record.phone || '').replace(/\s+/g, ''));
      }

      setAddress(record.address || '');

      const eParts = (record.emergency_contact || '').split('|');
      if (eParts.length === 2) {
        setEmergencyName(eParts[0].trim());
        const eMatch = eParts[1].trim().match(/^(\+\d{1,3})\s*(.*)$/);
        if (eMatch) {
          setEmergencyCode(eMatch[1]);
          setEmergencyNumber(eMatch[2].replace(/\s+/g, ''));
        } else {
          setEmergencyCode('+66');
          setEmergencyNumber(eParts[1].trim().replace(/\s+/g, ''));
        }
      } else {
        setEmergencyName(record.emergency_contact || '');
        setEmergencyCode('+66');
        setEmergencyNumber('');
      }
      setLanguage(record.language || 'en');
      setIsActive(record.is_active !== false);
      setNotes(record.notes || '');
      setCreatedAt(record.created_at);
      setUpdatedAt(record.updated_at);

      // Populate Tab 2
      setRole(record.role);
      setWorkerRoles(record.worker_roles || []);
      setMaintenanceSpecs(record.maintenance_specializations || []);

      // Assignments
      const propIds = assignmentsRes.property_ids || [];
      setAssignedProperties(propIds);
      setOriginalAssignments(propIds);

      // Available properties
      const props = propsRes.properties || propsRes.items || propsRes.data || [];
      setAvailableProperties(
        props.map((p: any) => ({ id: p.id || p.property_id, name: p.display_name || p.name || p.id }))
      );

      // Populate Tab 3
      setWhatsapp(record.comm_preference?.whatsapp || '');
      setTelegram(record.comm_preference?.telegram || '');
      setLine(record.comm_preference?.line || '');
      setSms(record.comm_preference?.sms || record.comm_preference?.phone || '');

    } catch (e) {
      setLoadError('Failed to load staff record.');
    } finally {
      setLoading(false);
    }
  }, [rawUserId]);

  useEffect(() => { load(); }, [load]);

  const toggleProperty = (id: string) =>
    setAssignedProperties(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );

  const handleSave = async () => {
    if (role === 'worker' && workerRoles.length === 0) {
      setError('Select at least one worker role.');
      setActiveTab(1);
      return;
    }
    setError(null);
    setSaving(true);
    try {
      // 1. PATCH profile fields (Phase 842 endpoint — partial update)
      await apiFetch(`/permissions/${encodeURIComponent(rawUserId)}`, {
        method: 'PATCH',
        body: JSON.stringify({
          role,
          display_name: displayName.trim() || undefined,
          phone: phoneNumber.trim() ? `${phoneCode}${phoneNumber.trim()}` : undefined,
          address: address.trim() || undefined,
          emergency_contact: emergencyName.trim() || emergencyNumber.trim() ? `${emergencyName.trim()} | ${emergencyCode}${emergencyNumber.trim()}` : undefined,
          photo_url: photoUrl.trim() || undefined,
          language,
          is_active: isActive,
          notes: notes.trim() || undefined,
          worker_roles: role === 'worker' ? workerRoles : [],
          maintenance_specializations: role === 'worker' && workerRoles.includes('maintenance') ? maintenanceSpecs : [],
          comm_preference: {
            whatsapp: whatsapp.trim() || undefined,
            telegram: telegram.trim() || undefined,
            line: line.trim() || undefined,
            sms: sms.trim() || undefined,
          },
        }),
      });

      // 2. Diff property assignments and apply changes
      const toAdd = assignedProperties.filter(id => !originalAssignments.includes(id));
      const toRemove = originalAssignments.filter(id => !assignedProperties.includes(id));

      await Promise.all([
        ...toAdd.map(propId =>
          apiFetch('/staff/assignments', {
            method: 'POST',
            body: JSON.stringify({ user_id: rawUserId, property_id: propId }),
          })
        ),
        ...toRemove.map(propId =>
          apiFetch(`/staff/assignments/${encodeURIComponent(rawUserId)}/${encodeURIComponent(propId)}`, {
            method: 'DELETE',
          })
        ),
      ]);

      setOriginalAssignments(assignedProperties);
      setLegacyRole(undefined); // successfully normalized
      setSuccess('Staff member updated.');
      setTimeout(() => setSuccess(null), 3000);
    } catch (e) {
      setError('Save failed. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleDeactivate = async () => {
    try {
      await apiFetch(`/permissions/${encodeURIComponent(rawUserId)}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: false }),
      });
      router.push('/admin/staff?deactivated=1');
    } catch {
      setError('Failed to deactivate staff member.');
      setConfirmDeactivate(false);
    }
  };

  const handlePhotoSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingPhoto(true);
    setError(null);
    try {
      const tok = getToken();
      if (!tok) throw new Error('Not authenticated');
      
      // Use the existing proxy. 'staff' acts as the folder in property-photos bucket.
      const { url } = await uploadPropertyPhoto(file, 'staff-avatars', 'reference', tok);
      setPhotoUrl(url);
      setSuccess('Photo uploaded successfully. Click Save Changes to keep.');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to upload photo');
    } finally {
      setUploadingPhoto(false);
      // Reset input so the same file can be selected again if needed
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const TABS = ['Profile', 'Role & Assignment', 'Access & Comms'];

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
        <div style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading staff record…</div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div style={{ padding: 'var(--space-6)' }}>
        <button onClick={() => router.back()} style={{ background: 'none', border: 'none', color: 'var(--color-text-dim)', cursor: 'pointer', fontSize: 'var(--text-sm)' }}>← Back</button>
        <div style={{ marginTop: 'var(--space-4)', color: '#f85149' }}>{loadError}</div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>

      {/* ── Page header ─────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 'var(--space-4)',
        padding: 'var(--space-4) var(--space-5)', borderBottom: '1px solid var(--color-border)',
        background: 'var(--color-surface)',
      }}>
        <button
          onClick={() => router.back()}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)',
            padding: '6px 10px', borderRadius: 'var(--radius-sm)',
          }}
        >
          ← Back
        </button>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
          <Avatar name={displayName || fullName} photoUrl={photoUrl} />
          
          <input
            type="file"
            accept={ACCEPTED_IMAGE_TYPES}
            ref={fileInputRef}
            style={{ display: 'none' }}
            onChange={handlePhotoSelect}
          />
          
          <button 
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadingPhoto}
            style={{
              background: 'none', border: 'none', color: 'var(--color-primary)',
              fontSize: '11px', fontWeight: 600, cursor: uploadingPhoto ? 'not-allowed' : 'pointer',
              opacity: uploadingPhoto ? 0.5 : 1, padding: 0, marginTop: -2,
            }}
          >
            {uploadingPhoto ? 'Uploading…' : 'Add photo'}
          </button>
        </div>
        <div style={{ flex: 1 }}>
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Staff Member
          </p>
          <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--color-text)', margin: 0 }}>
            {displayName || rawUserId}
          </h1>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
            {rawUserId}
          </div>
        </div>
        {/* Status dot */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 'var(--text-xs)' }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: isActive ? '#3fb950' : '#8b949e' }} />
          <span style={{ color: 'var(--color-text-dim)' }}>{isActive ? 'Active' : 'Inactive'}</span>
        </div>
      </div>

      {/* ── Legacy role warning banner ───────────────────────────────────── */}
      {legacyRole && (
        <div style={{
          background: 'rgba(210,153,34,0.1)', border: '1px solid rgba(210,153,34,0.4)',
          color: '#d29922', padding: '10px 20px', fontSize: 'var(--text-sm)',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <span>⚠</span>
          <span>
            Legacy role detected: <strong>{legacyRole}</strong> → normalized to{' '}
            <strong>role=worker, worker_roles=[{LEGACY_ROLE_MAP[legacyRole]?.worker_roles.join(', ')}]</strong>.
            Will be saved in canonical model on next save.
          </span>
        </div>
      )}

      {/* ── Tab bar ─────────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', gap: 0, borderBottom: '1px solid var(--color-border)',
        background: 'var(--color-surface)', padding: '0 var(--space-5)',
      }}>
        {TABS.map((t, i) => (
          <button key={t} onClick={() => setActiveTab(i as 0 | 1 | 2)} style={{
            padding: '12px 20px', background: 'none', border: 'none', cursor: 'pointer',
            fontSize: 'var(--text-sm)', fontWeight: activeTab === i ? 700 : 400,
            color: activeTab === i ? 'var(--color-primary)' : 'var(--color-text-dim)',
            borderBottom: activeTab === i ? '2px solid var(--color-primary)' : '2px solid transparent',
            marginBottom: -1, transition: 'all 0.15s',
          }}>{t}</button>
        ))}
      </div>

      {/* ── Error / success banners ──────────────────────────────────────── */}
      {error && (
        <div style={{ background: 'rgba(248,81,73,0.1)', border: '1px solid rgba(248,81,73,0.3)', color: '#f85149', padding: '10px 20px', fontSize: 'var(--text-sm)' }}>
          {error}
        </div>
      )}
      {success && (
        <div style={{ background: 'rgba(63,185,80,0.1)', border: '1px solid rgba(63,185,80,0.3)', color: '#3fb950', padding: '10px 20px', fontSize: 'var(--text-sm)' }}>
          ✓ {success}
        </div>
      )}

      {/* ── Content ─────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflow: 'auto', padding: 'var(--space-6) var(--space-5)', maxWidth: 720 }}>

        {/* ── Tab 1: Profile ────────────────────────────────────────────── */}
        {activeTab === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
              <Field label="Display Name">
                <input style={inputStyle} value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder="Name" />
              </Field>
              <Field label="Photo URL">
                <input style={inputStyle} value={photoUrl} onChange={e => setPhotoUrl(e.target.value)} placeholder="https://..." />
              </Field>
            </div>

            <div style={{ ...inputStyle, padding: '8px 12px', borderRadius: 'var(--radius-sm)', background: 'var(--color-surface-2)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)' }}>
              User ID: {rawUserId}
            </div>

            <div style={sectionHeadStyle}>Contact</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.5fr)', gap: 'var(--space-4)' }}>
              <Field label="Phone">
                <div style={{ display: 'flex', gap: '8px' }}>
                  <select 
                    style={{ ...inputStyle, width: '70px', cursor: 'pointer', padding: '9px 2px', textAlign: 'center' }} 
                    value={phoneCode} 
                    onChange={e => {
                      const code = e.target.value;
                      const oldFull = `${phoneCode}${phoneNumber}`.trim();
                      const newFull = `${code}${phoneNumber}`.trim();
                      setPhoneCode(code);
                      if (!whatsapp || whatsapp === oldFull) setWhatsapp(newFull);
                      if (!sms || sms === oldFull) setSms(newFull);
                    }}
                  >
                    {COUNTRY_CODES_OPTS.map(c => <option key={c.code} value={c.code}>{c.label}</option>)}
                  </select>
                  <input style={{ ...inputStyle, flex: 1 }} value={phoneNumber} 
                    onChange={e => {
                      const num = e.target.value;
                      const oldFull = `${phoneCode}${phoneNumber}`.trim();
                      const newFull = `${phoneCode}${num}`.trim();
                      setPhoneNumber(num);
                      if (!whatsapp || whatsapp === oldFull) setWhatsapp(newFull);
                      if (!sms || sms === oldFull) setSms(newFull);
                    }} 
                    placeholder="81 234 5678" 
                  />
                </div>
              </Field>
              <Field label="Emergency Contact">
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input style={{ ...inputStyle, flex: 1 }} value={emergencyName} onChange={e => setEmergencyName(e.target.value)} placeholder="Name" />
                  <select style={{ ...inputStyle, width: '70px', cursor: 'pointer', padding: '9px 2px', textAlign: 'center' }} value={emergencyCode} onChange={e => setEmergencyCode(e.target.value)}>
                    {COUNTRY_CODES_OPTS.map(c => <option key={c.code} value={c.code}>{c.label}</option>)}
                  </select>
                  <input style={{ ...inputStyle, flex: 1 }} value={emergencyNumber} onChange={e => setEmergencyNumber(e.target.value)} placeholder="Phone" />
                </div>
              </Field>
            </div>

            <Field label="Address">
              <textarea style={{ ...inputStyle, resize: 'vertical', minHeight: 72 }} value={address} onChange={e => setAddress(e.target.value)} />
            </Field>

            <div style={sectionHeadStyle}>Preferences</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
              <Field label="Language">
                <select style={{ ...inputStyle, cursor: 'pointer' }} value={language} onChange={e => setLanguage(e.target.value)}>
                  {LANGUAGES.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
                </select>
              </Field>
              <Field label="Status">
                <label style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4, cursor: 'pointer' }}>
                  <div onClick={() => setIsActive(!isActive)} style={{
                    width: 44, height: 24, borderRadius: 12,
                    background: isActive ? 'var(--color-primary)' : 'var(--color-border)',
                    position: 'relative', cursor: 'pointer', transition: 'background 0.2s', flexShrink: 0,
                  }}>
                    <div style={{ position: 'absolute', top: 2, left: isActive ? 22 : 2, width: 20, height: 20, borderRadius: '50%', background: '#fff', transition: 'left 0.2s' }} />
                  </div>
                  <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{isActive ? 'Active' : 'Inactive'}</span>
                </label>
              </Field>
            </div>

            <Field label="Internal Notes">
              <textarea style={{ ...inputStyle, resize: 'vertical', minHeight: 72 }} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Private notes visible to admin only" />
            </Field>

            {/* Meta */}
            {(createdAt || updatedAt) && (
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-3)' }}>
                {createdAt && <div>Created: {new Date(createdAt).toLocaleDateString()}</div>}
                {updatedAt && <div>Updated: {new Date(updatedAt).toLocaleDateString()}</div>}
              </div>
            )}

            {/* Danger zone */}
            <div style={{ marginTop: 'var(--space-6)', padding: 'var(--space-4)', border: '1px solid rgba(248,81,73,0.3)', borderRadius: 'var(--radius-md)', background: 'rgba(248,81,73,0.05)' }}>
              <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: '#f85149', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                Danger Zone
              </div>
              {!confirmDeactivate ? (
                <button onClick={() => setConfirmDeactivate(true)} style={{
                  padding: '8px 20px', background: 'transparent', border: '1px solid rgba(248,81,73,0.5)',
                  color: '#f85149', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 'var(--text-sm)', fontWeight: 600,
                }}>
                  Deactivate Staff Member
                </button>
              ) : (
                <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center' }}>
                  <span style={{ fontSize: 'var(--text-sm)', color: '#f85149' }}>Are you sure?</span>
                  <button onClick={handleDeactivate} style={{ padding: '8px 16px', background: '#f85149', border: 'none', color: '#fff', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontWeight: 700, fontSize: 'var(--text-sm)' }}>
                    Confirm Deactivate
                  </button>
                  <button onClick={() => setConfirmDeactivate(false)} style={{ padding: '8px 16px', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text-dim)', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 'var(--text-sm)' }}>
                    Cancel
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Tab 2: Role & Assignment ──────────────────────────────────── */}
        {activeTab === 1 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
            <Field label="Role *">
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 'var(--space-3)', marginTop: 4 }}>
                {CANONICAL_ROLES.map(r => (
                  <label key={r.value} style={{
                    display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px',
                    background: role === r.value ? 'rgba(var(--color-primary-rgb, 99,102,241), 0.12)' : 'var(--color-surface-2)',
                    border: `2px solid ${role === r.value ? 'var(--color-primary)' : 'var(--color-border)'}`,
                    borderRadius: 'var(--radius-md)', cursor: 'pointer', transition: 'all 0.15s',
                  }}>
                    <input type="radio" name="role" value={r.value} checked={role === r.value}
                      onChange={() => { setRole(r.value); setWorkerRoles([]); setMaintenanceSpecs([]); }}
                      style={{ accentColor: 'var(--color-primary)' }} />
                    <span style={{ fontWeight: role === r.value ? 700 : 400, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
                      {r.label}
                    </span>
                  </label>
                ))}
              </div>
            </Field>

            {role === 'worker' && (
              <div>
                <div style={sectionHeadStyle}>Worker Roles</div>
                {workerRoles.length === 0 && (
                  <div style={{ fontSize: 'var(--text-xs)', color: '#f85149', marginBottom: 'var(--space-2)' }}>
                    Select at least one worker role.
                  </div>
                )}
                <CheckGroup options={WORKER_ROLES} selected={workerRoles} onChange={setWorkerRoles} />

                {workerRoles.includes('maintenance') && (
                  <div style={{ marginTop: 'var(--space-4)' }}>
                    <div style={sectionHeadStyle}>Maintenance Specializations</div>
                    <CheckGroup options={MAINTENANCE_SPECS} selected={maintenanceSpecs} onChange={setMaintenanceSpecs} />
                  </div>
                )}
              </div>
            )}

            <div>
              <div style={sectionHeadStyle}>
                Assigned Properties
                {assignedProperties.length > 0 && (
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-primary)', marginLeft: 8, fontWeight: 400 }}>
                    {assignedProperties.length} assigned
                  </span>
                )}
              </div>
              {availableProperties.length === 0 ? (
                <div style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>No properties found.</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {availableProperties.map(p => (
                    <label key={p.id} style={{
                      display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
                      background: assignedProperties.includes(p.id) ? 'rgba(var(--color-primary-rgb, 99,102,241), 0.08)' : 'var(--color-surface-2)',
                      border: `1px solid ${assignedProperties.includes(p.id) ? 'var(--color-primary)' : 'var(--color-border)'}`,
                      borderRadius: 'var(--radius-sm)', cursor: 'pointer', transition: 'all 0.15s',
                    }}>
                      <input type="checkbox" checked={assignedProperties.includes(p.id)} onChange={() => toggleProperty(p.id)}
                        style={{ accentColor: 'var(--color-primary)' }} />
                      <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{p.name}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Tab 3: Access & Comms ────────────────────────────────────── */}
        {activeTab === 2 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div style={sectionHeadStyle}>Communication Channels</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
              <Field label="WhatsApp">
                <input style={inputStyle} value={whatsapp} onChange={e => setWhatsapp(e.target.value)} placeholder="+66 81 234 5678" />
              </Field>
              <Field label="Telegram">
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input style={{ ...inputStyle, flex: 1 }} value={telegram} onChange={e => setTelegram(e.target.value)} placeholder="Chat ID or @username" />
                  <button onClick={() => alert('Approval Request flow will dispatch an SMS deep-link via Twilio here in Phase 845.')} style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '0 12px', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', cursor: 'pointer', flexShrink: 0 }}>
                    Request ID
                  </button>
                </div>
              </Field>
              <Field label="LINE">
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input style={{ ...inputStyle, flex: 1 }} value={line} onChange={e => setLine(e.target.value)} placeholder="LINE ID" />
                  <button onClick={() => alert('Approval Request flow will dispatch an SMS deep-link via Twilio here in Phase 845.')} style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '0 12px', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', cursor: 'pointer', flexShrink: 0 }}>
                    Request ID
                  </button>
                </div>
              </Field>
              <Field label="SMS / Phone">
                <input style={inputStyle} value={sms} onChange={e => setSms(e.target.value)} placeholder="+66 81 234 5678" />
              </Field>
            </div>

            {role === 'owner' && (
              <div>
                <div style={sectionHeadStyle}>Owner Visibility Controls</div>
                <div style={{
                  padding: 'var(--space-4)', background: 'var(--color-surface-2)',
                  border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)',
                  color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)',
                }}>
                  Property visibility controls (financials, bookings, tasks) will be configured in a future update.
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Sticky footer ───────────────────────────────────────────────── */}
      <div style={{
        position: 'sticky', bottom: 0,
        background: 'var(--color-surface)', borderTop: '1px solid var(--color-border)',
        padding: 'var(--space-3) var(--space-5)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--space-3)',
      }}>
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          {activeTab > 0 && (
            <button onClick={() => setActiveTab((activeTab - 1) as 0 | 1 | 2)} style={{
              padding: '8px 18px', borderRadius: 'var(--radius-sm)',
              background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
              color: 'var(--color-text-dim)', cursor: 'pointer', fontSize: 'var(--text-sm)',
            }}>← Previous</button>
          )}
          {activeTab < 2 && (
            <button onClick={() => setActiveTab((activeTab + 1) as 0 | 1 | 2)} style={{
              padding: '8px 18px', borderRadius: 'var(--radius-sm)',
              background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
              color: 'var(--color-text)', cursor: 'pointer', fontSize: 'var(--text-sm)',
            }}>Next →</button>
          )}
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          style={{
            padding: '10px 28px', borderRadius: 'var(--radius-md)',
            background: saving ? 'var(--color-border)' : 'var(--color-primary)',
            color: '#fff', border: 'none', cursor: saving ? 'not-allowed' : 'pointer',
            fontWeight: 700, fontSize: 'var(--text-sm)',
            boxShadow: saving ? 'none' : '0 2px 12px rgba(99,102,241,0.4)',
            transition: 'all 0.15s',
          }}
        >
          {saving ? 'Saving…' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
}
