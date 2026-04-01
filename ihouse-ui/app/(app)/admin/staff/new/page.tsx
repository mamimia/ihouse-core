'use client';
/**
 * Phase 843 / 887 — Staff Full-Page Create (aligned with edit model)
 * /admin/staff/new
 *
 * 4-tab full-page flow (matches [userId]/page.tsx):
 * Tab 1 — Profile (name, photo, phone, address, emergency, language, status, notes, start date)
 * Tab 2 — Role & Assignment (role, worker_roles, specializations, assigned properties)
 * Tab 3 — Access & Comms (WhatsApp, Telegram, LINE, SMS, preferred channel)
 * Tab 4 — Documents & Compliance (ID/Passport, Work Permit, compliance summary)
 *
 * Create-vs-edit differences preserved:
 * - userId (Supabase email) is required on create; read-only after creation
 * - No "Send Access Link" live call (no user_id until record exists); shows a post-creation reminder instead
 * - No "Danger Zone" (no record to delete yet)
 * - No legacy-role normalization banner (new records are always canonical)
 */

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
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
  if (!res.ok) {
    // Parse JSON error body so callers can access detail/message
    let errDetail: string | undefined;
    try {
      const body = await res.json();
      errDetail = body?.detail || body?.message || undefined;
    } catch { /* ignore parse errors */ }
    const err: any = new Error(errDetail || `${res.status}`);
    err.status = res.status;
    if (errDetail) err.detail = errDetail;
    throw err;
  }
  return res.json();
}

// ── Doc compliance helpers (mirrors edit page) ───────────────────────────────

const DOC_STATUSES = [
  { value: 'missing', label: 'Missing' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'verified', label: 'Verified' },
  { value: 'expiring_soon', label: 'Expiring Soon' },
  { value: 'expired', label: 'Expired' },
];

function docStatusColor(status: string): string {
  switch (status) {
    case 'verified': return 'var(--color-ok, #4A7C59)';
    case 'submitted': return 'var(--color-sage, #8FA39B)';
    case 'expiring_soon': return 'var(--color-warn, #B56E45)';
    case 'expired': return 'var(--color-alert, #C45B4A)';
    case 'missing': default: return 'var(--color-text-faint, #9A958E)';
  }
}

function expiryWarning(expiryDate: string): { label: string; color: string } | null {
  if (!expiryDate) return null;
  const now = new Date();
  const expiry = new Date(expiryDate);
  const daysLeft = Math.ceil((expiry.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  if (daysLeft < 0) return { label: 'Expired', color: 'var(--color-alert)' };
  if (daysLeft <= 30) return { label: `${daysLeft}d left`, color: 'var(--color-alert)' };
  if (daysLeft <= 90) return { label: `${daysLeft}d left`, color: 'var(--color-warn)' };
  return null;
}

function autoDocStatus(status: string, expiryDate: string): string {
  if (!expiryDate) return status;
  const now = new Date();
  const expiry = new Date(expiryDate);
  const daysLeft = Math.ceil((expiry.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  if (daysLeft < 0) return 'expired';
  if (daysLeft <= 90 && (status === 'verified' || status === 'submitted')) return 'expiring_soon';
  return status;
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
  { value: 'general',     label: 'General' },
  { value: 'gardener',    label: 'Gardener' },
  { value: 'pool',        label: 'Pool' },
  { value: 'plumber',     label: 'Plumber' },
  { value: 'painter',     label: 'Painter' },
  { value: 'electrician', label: 'Electrician' },
  { value: 'ac',          label: 'AC' },
  { value: 'other',       label: 'Other' },
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
  { code: '+1',  label: '🇺🇸 +1' },
  { code: '+44', label: '🇬🇧 +44' },
  { code: '+972',label: '🇮🇱 +972' },
  { code: '+95', label: '🇲🇲 +95' },
  { code: '+856',label: '🇱🇦 +856' },
  { code: '+855',label: '🇰🇭 +855' },
  { code: '+60', label: '🇲🇾 +60' },
  { code: '+65', label: '🇸🇬 +65' },
  { code: '+81', label: '🇯🇵 +81' },
  { code: '+7',  label: '🇷🇺 +7' },
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

function AvatarPreview({ name, photoUrl, uploading, onAddClick, fileRef, onFileChange }: {
  name: string; photoUrl: string; uploading: boolean;
  onAddClick: () => void;
  fileRef: React.RefObject<HTMLInputElement | null>;
  onFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  const initials = name.trim()
    ? name.trim().split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase()
    : '?';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 'var(--space-4)' }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
        <div style={{
          width: 72, height: 72, borderRadius: '50%',
          background: photoUrl ? 'transparent' : 'var(--color-primary)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 24, fontWeight: 700, color: '#fff', flexShrink: 0,
          overflow: 'hidden', border: '2px solid var(--color-border)',
        }}>
          {photoUrl
            ? <img src={photoUrl} alt="avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            : initials}
        </div>
        <input type="file" accept={ACCEPTED_IMAGE_TYPES} ref={fileRef} style={{ display: 'none' }} onChange={onFileChange} />
        <button type="button" onClick={onAddClick} disabled={uploading} style={{
          background: 'none', border: 'none', color: 'var(--color-primary)',
          fontSize: '11px', fontWeight: 600, cursor: uploading ? 'not-allowed' : 'pointer',
          opacity: uploading ? 0.5 : 1, padding: 0, marginTop: -2,
        }}>
          {uploading ? 'Uploading…' : 'Add photo'}
        </button>
      </div>
      <div style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-xs)' }}>
        Photo preview. Upload an image or leave blank for initials.
      </div>
    </div>
  );
}

// ── Main page ───────────────────────────────────────────────────────────────

export default function NewStaffPage() {
  const router = useRouter();

  // Tab state — 4 tabs matching the edit model
  const [activeTab, setActiveTab] = useState<0 | 1 | 2 | 3>(0);

  // Tab 1 — Profile
  const [fullName, setFullName] = useState('');
  const [preferredName, setPreferredName] = useState(''); // nickname / display name
  const [staffEmail, setStaffEmail] = useState(''); // primary email — becomes the user_id key
  const [personalEmail, setPersonalEmail] = useState('');  // optional secondary personal email
  const [dateOfBirth, setDateOfBirth] = useState('');
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
  const [startDate, setStartDate] = useState('');

  // Tab 2 — Role & Assignment
  const [role, setRole] = useState('worker');
  const [workerRoles, setWorkerRoles] = useState<string[]>([]);
  const [maintenanceSpecs, setMaintenanceSpecs] = useState<string[]>([]);
  const [assignedProperties, setAssignedProperties] = useState<string[]>([]);
  const [availableProperties, setAvailableProperties] = useState<{ id: string; name: string }[]>([]);

  // Tab 3 — Access & Comms
  const [whatsapp, setWhatsapp] = useState('');
  const [telegram, setTelegram] = useState('');
  const [line, setLine] = useState('');
  const [sms, setSms] = useState('');
  const [preferredContact, setPreferredContact] = useState('');

  // Tab 4 — Documents & Compliance
  const [idPhotoUrl, setIdPhotoUrl] = useState('');
  const [idDocNumber, setIdDocNumber] = useState('');
  const [idDocExpiry, setIdDocExpiry] = useState('');
  const [idDocStatus, setIdDocStatus] = useState('missing');
  const [workPermitPhotoUrl, setWorkPermitPhotoUrl] = useState('');
  const [workPermitNumber, setWorkPermitNumber] = useState('');
  const [workPermitExpiry, setWorkPermitExpiry] = useState('');
  const [workPermitStatus, setWorkPermitStatus] = useState('missing');

  // UI state
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Phase 947: email validation state
  const [emailError, setEmailError] = useState<string | null>(null);

  const validateEmail = (v: string) => {
    if (!v.trim()) { setEmailError(null); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim())) {
      setEmailError('Invalid email format — check for typos like missing .com or extra spaces.');
    } else {
      setEmailError(null);
    }
  };

  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [uploadingIdPhoto, setUploadingIdPhoto] = useState(false);
  const idFileInputRef = useRef<HTMLInputElement>(null);

  const [uploadingPermitPhoto, setUploadingPermitPhoto] = useState(false);
  const permitFileInputRef = useRef<HTMLInputElement>(null);

  // Load approved properties only — mirrors edit page filter
  useEffect(() => {
    apiFetch<any>('/admin/properties?status=approved')
      .then(res => {
        const props = res.properties || res.items || res.data || [];
        setAvailableProperties(
          props
            .filter((p: any) => !p.status || p.status === 'approved')
            .map((p: any) => ({ id: p.id || p.property_id, name: p.display_name || p.name || p.id }))
        );
      })
      .catch(() => {});
  }, []);

  const toggleProperty = (id: string) =>
    setAssignedProperties(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );

  // ── Upload handlers ────────────────────────────────────────────────────────

  const handlePhotoSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingPhoto(true);
    setError(null);
    try {
      const tok = getToken();
      if (!tok) throw new Error('Not authenticated');
      const { url } = await uploadPropertyPhoto(file, 'staff-avatars', 'reference', tok);
      setPhotoUrl(url);
    } catch (err: any) {
      setError(err.message || 'Failed to upload photo');
    } finally {
      setUploadingPhoto(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleIdPhotoSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingIdPhoto(true);
    setError(null);
    try {
      const tok = getToken();
      if (!tok) throw new Error('Not authenticated');
      const { url } = await uploadPropertyPhoto(file, 'staff-pii', 'reference', tok);
      setIdPhotoUrl(url);
      if (idDocStatus === 'missing') setIdDocStatus('submitted');
    } catch (err: any) {
      setError(err.message || 'Failed to upload ID photo');
    } finally {
      setUploadingIdPhoto(false);
      if (idFileInputRef.current) idFileInputRef.current.value = '';
    }
  };

  const handlePermitPhotoSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingPermitPhoto(true);
    setError(null);
    try {
      const tok = getToken();
      if (!tok) throw new Error('Not authenticated');
      const { url } = await uploadPropertyPhoto(file, 'staff-pii', 'reference', tok);
      setWorkPermitPhotoUrl(url);
      if (workPermitStatus === 'missing') setWorkPermitStatus('submitted');
    } catch (err: any) {
      setError(err.message || 'Failed to upload work permit');
    } finally {
      setUploadingPermitPhoto(false);
      if (permitFileInputRef.current) permitFileInputRef.current.value = '';
    }
  };

  // ── Save ──────────────────────────────────────────────────────────────────

  const [createdResult, setCreatedResult] = useState<{ user_id: string; email: string; magic_link?: string; delivery_method?: string } | null>(null);

  const handleSave = async () => {
    if (!staffEmail.trim()) { setError('Staff email is required.'); setActiveTab(0); return; }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(staffEmail.trim())) {
      setError('Invalid email address. The staff email is the auth identity — please double-check for typos.'); setActiveTab(0); return;
    }
    if (!role)          { setError('Role is required.'); setActiveTab(1); return; }
    if (role === 'worker' && workerRoles.length === 0) {
      setError('Select at least one worker role.'); setActiveTab(1); return;
    }
    if (role === 'manager' && assignedProperties.length === 0) {
      setError('Operational Manager must be assigned to at least one property. Select a property in the Role & Assignment tab before saving.');
      setActiveTab(1);
      return;
    }
    setError(null);
    setSaving(true);
    try {
      // Phase 1037: Call POST /admin/staff — creates a real Supabase auth user FIRST
      // (via invite_user_by_email), then provisions tenant_permissions with the real UUID.
      // This is identical in outcome to the approve-onboarding flow.
      const payload: Record<string, any> = {
        email: staffEmail.trim(),
        role,
        display_name: (preferredName || fullName).trim() || undefined,
        phone: phoneNumber.trim() ? `${phoneCode}${phoneNumber.trim()}` : undefined,
        address: address.trim() || undefined,
        emergency_contact: emergencyName.trim() || emergencyNumber.trim()
          ? `${emergencyName.trim()} | ${emergencyCode}${emergencyNumber.trim()}`
          : undefined,
        photo_url: photoUrl.trim() || undefined,
        language,
        is_active: isActive,
        notes: notes.trim() || undefined,
        worker_roles: role === 'worker' ? workerRoles : [],
        maintenance_specializations: role === 'worker' && workerRoles.includes('maintenance') ? maintenanceSpecs : [],
        property_ids: assignedProperties,
        frontend_url: typeof window !== 'undefined' ? window.location.origin : undefined,
        comm_preference: {
          whatsapp: whatsapp.trim() || undefined,
          telegram: telegram.trim() || undefined,
          line: line.trim() || undefined,
          sms: sms.trim() || undefined,
          email: staffEmail.trim(),   // Phase 947: must match auth email
          date_of_birth: dateOfBirth || undefined,
          start_date: startDate || undefined,
          preferred_contact: preferredContact || undefined,
          preferred_name: preferredName.trim() || undefined,
          id_photo_url: idPhotoUrl.trim() || undefined,
          id_doc_number: idDocNumber.trim() || undefined,
          id_doc_expiry: idDocExpiry || undefined,
          id_doc_status: autoDocStatus(idDocStatus, idDocExpiry),
          work_permit_photo_url: workPermitPhotoUrl.trim() || undefined,
          work_permit_number: workPermitNumber.trim() || undefined,
          work_permit_expiry: workPermitExpiry || undefined,
          work_permit_status: autoDocStatus(workPermitStatus, workPermitExpiry),
        },
      };

      const result = await apiFetch<{
        status: string;
        user_id: string;
        email: string;
        magic_link?: string;
        delivery_method?: string;
      }>('/admin/staff', { method: 'POST', body: JSON.stringify(payload) });

      // Show the result with magic link so admin can share it if the email didn't arrive
      setCreatedResult(result);
    } catch (e: any) {
      let msg = 'Save failed. Please check the details and try again.';
      if (e?.detail) {
        msg = e.detail;
      } else if (e?.message && e.message !== '400' && e.message !== '500') {
        msg = e.message;
      } else if (e?.message === '429') {
        msg = 'Email rate limit reached. Wait ~60 minutes or use a different email address.';
      } else if (e?.message === '400') {
        msg = 'Save failed: one or more fields are invalid. Check that all selected properties are approved and all required fields are filled.';
      }
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  const TABS = ['Profile', 'Role & Assignment', 'Access & Comms', 'Documents & Compliance'];

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>

      {/* ── Page header ───────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 'var(--space-4)',
        padding: 'var(--space-4) var(--space-5)', borderBottom: '1px solid var(--color-border)',
        background: 'var(--color-surface)',
      }}>
        <button onClick={() => router.back()} style={{
          display: 'flex', alignItems: 'center', gap: 6,
          background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)',
          padding: '6px 10px', borderRadius: 'var(--radius-sm)',
        }}>← Back</button>
        <div style={{ flex: 1 }}>
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Staff
          </p>
          <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--color-text)', margin: 0 }}>
            Add Staff Member
          </h1>
        </div>
      </div>

      {/* ── Tab bar ───────────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', gap: 0, borderBottom: '1px solid var(--color-border)',
        background: 'var(--color-surface)', padding: '0 var(--space-5)',
      }}>
        {TABS.map((t, i) => (
          <button key={t} onClick={() => setActiveTab(i as 0 | 1 | 2 | 3)} style={{
            padding: '12px 20px', background: 'none', border: 'none', cursor: 'pointer',
            fontSize: 'var(--text-sm)', fontWeight: activeTab === i ? 700 : 400,
            color: activeTab === i ? 'var(--color-primary)' : 'var(--color-text-dim)',
            borderBottom: activeTab === i ? '2px solid var(--color-primary)' : '2px solid transparent',
            marginBottom: -1, transition: 'all 0.15s', whiteSpace: 'nowrap',
          }}>{t}</button>
        ))}
      </div>

      {/* ── Error banner ──────────────────────────────────────────────────── */}
      {error && (
        <div style={{
          background: 'rgba(248,81,73,0.1)', border: '1px solid rgba(248,81,73,0.3)',
          color: '#f85149', padding: '10px 20px', fontSize: 'var(--text-sm)',
        }}>{error}</div>
      )}

      {/* ── Content ───────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflow: 'auto', padding: 'var(--space-6) var(--space-5)', maxWidth: 720 }}>

        {/* ── Tab 1: Profile ────────────────────────────────────────────── */}
        {activeTab === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <AvatarPreview
              name={preferredName || fullName}
              photoUrl={photoUrl}
              uploading={uploadingPhoto}
              onAddClick={() => fileInputRef.current?.click()}
              fileRef={fileInputRef}
              onFileChange={handlePhotoSelect}
            />

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
              <Field label="Full Name">
                <input style={inputStyle} value={fullName} onChange={e => setFullName(e.target.value)} placeholder="e.g. สมชาย ใจดี" />
              </Field>
              <Field label="Display Name / Nickname">
                <input style={inputStyle} value={preferredName} onChange={e => setPreferredName(e.target.value)} placeholder="Optional — nickname at work" />
              </Field>
            </div>

            {/* Staff email — required for create: becomes the user_id key */}
            <Field label="Staff Email *">
              <input
                style={{ ...inputStyle, borderColor: emailError ? '#f85149' : (!staffEmail.trim() && error ? '#f85149' : undefined) }}
                value={staffEmail}
                onChange={e => { setStaffEmail(e.target.value); validateEmail(e.target.value); }}
                onBlur={e => validateEmail(e.target.value)}
                placeholder="worker@company.com"
                type="email"
              />
              {emailError && (
                <span style={{ fontSize: 'var(--text-xs)', color: '#f85149', marginTop: 4, display: 'block' }}>
                  ⚠ {emailError}
                </span>
              )}
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 4, lineHeight: 1.5 }}>
                This email becomes the worker's Supabase Auth identity and login credential.
                It must exactly match the email they will use to log in. Typos here cannot be corrected without a database repair.
              </span>
            </Field>

            <Field label="Photo URL / Avatar">
              <input style={inputStyle} value={photoUrl} onChange={e => setPhotoUrl(e.target.value)} placeholder="https://..." />
            </Field>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
              <Field label="Personal Email (Optional)">
                <input style={inputStyle} value={personalEmail} onChange={e => setPersonalEmail(e.target.value)} placeholder="worker@gmail.com" type="email" />
              </Field>
              <Field label="Date of Birth">
                <input style={inputStyle} type="date" value={dateOfBirth} onChange={e => setDateOfBirth(e.target.value)} />
              </Field>
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
              <textarea style={{ ...inputStyle, resize: 'vertical', minHeight: 72 }} value={address} onChange={e => setAddress(e.target.value)} placeholder="Home or work address" />
            </Field>

            <div style={sectionHeadStyle}>Employment</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
              <Field label="Start Date / Hired Date">
                <input type="date" style={inputStyle} value={startDate} onChange={e => setStartDate(e.target.value)} />
              </Field>
              <div />
            </div>

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
          </div>
        )}

        {/* ── Tab 2: Role & Assignment ────────────────────────────────── */}
        {activeTab === 1 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
            <Field label="Role *">
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 'var(--space-3)', marginTop: 4 }}>
                {CANONICAL_ROLES.map(r => (
                  <label key={r.value} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '12px 16px',
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
                <div style={sectionHeadStyle}>Staff Roles</div>
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
              {/* Operational Manager must have at least one property — show persistent warning */}
              {role === 'manager' && assignedProperties.length === 0 && (
                <div style={{
                  background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.3)',
                  borderRadius: 'var(--radius-md)', padding: '10px 14px',
                  color: '#b45309', fontSize: 'var(--text-xs)', fontWeight: 600,
                  marginBottom: 'var(--space-3)', display: 'flex', alignItems: 'center', gap: 8,
                }}>
                  ⚠ Operational Manager requires at least one property assignment. This manager will have no operational scope until a property is assigned.
                </div>
              )}
              {availableProperties.length === 0 ? (
                <div style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>
                  No approved properties found. Add properties in Settings → Properties.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {availableProperties.map(p => (
                    <label key={p.id} style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      padding: '10px 14px',
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

            <div style={sectionHeadStyle}>Contact Preferences</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
              <Field label="Preferred Contact Channel">
                <select style={{ ...inputStyle, cursor: 'pointer' }} value={preferredContact} onChange={e => setPreferredContact(e.target.value)}>
                  <option value="">— Not set —</option>
                  <option value="whatsapp">WhatsApp</option>
                  <option value="telegram">Telegram</option>
                  <option value="line">LINE</option>
                  <option value="sms">SMS / Phone</option>
                  <option value="email">Email</option>
                </select>
              </Field>
            </div>

            {/* Access Link — create-flow note (no live resend until record exists) */}
            <div>
              <div style={sectionHeadStyle}>Send Access Link</div>
              <div style={{
                background: 'var(--color-surface-2)', padding: 'var(--space-4)',
                borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)',
              }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', margin: 0 }}>
                  After creating this staff member, open their profile and use the <strong>Send Access Link</strong> button in the Access & Comms tab to generate and send their first-login link via email, WhatsApp, SMS, Telegram, or LINE.
                </p>
              </div>
            </div>

            {role === 'owner' && (
              <div>
                <div style={sectionHeadStyle}>Owner Visibility Controls</div>
                <div style={{
                  padding: 'var(--space-4)', background: 'var(--color-surface-2)',
                  border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)',
                  color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)',
                }}>
                  Visibility controls (financials, bookings, tasks) are configured in Phase 847.
                  Assign this owner to properties in the Role &amp; Assignment tab first.
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Tab 4: Documents & Compliance ─────────────────────────── */}
        {activeTab === 3 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>

            {/* ID / Passport */}
            <div style={sectionHeadStyle}>ID / Passport</div>
            <div style={{ background: 'var(--color-surface-2)', padding: 'var(--space-4)', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                <Field label="Document Photo">
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                    {idPhotoUrl ? (
                      <div>
                        <a href={idPhotoUrl} target="_blank" rel="noopener noreferrer" style={{ display: 'inline-block' }}>
                          <img src={idPhotoUrl} alt="ID Document" style={{ maxWidth: 200, maxHeight: 120, objectFit: 'contain', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)' }} />
                        </a>
                        <div style={{ marginTop: 8 }}>
                          <button type="button" onClick={() => setIdPhotoUrl('')} style={{ fontSize: 'var(--text-xs)', color: 'var(--color-alert)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>Remove</button>
                        </div>
                      </div>
                    ) : (
                      <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>No ID uploaded.</div>
                    )}
                    <input type="file" accept={ACCEPTED_IMAGE_TYPES} ref={idFileInputRef} style={{ display: 'none' }} onChange={handleIdPhotoSelect} />
                    <button type="button" onClick={() => idFileInputRef.current?.click()} disabled={uploadingIdPhoto} style={{
                      padding: '8px 16px', borderRadius: 'var(--radius-sm)', background: 'var(--color-surface)',
                      border: '1px solid var(--color-border)', color: 'var(--color-text)', cursor: uploadingIdPhoto ? 'not-allowed' : 'pointer',
                      fontSize: 'var(--text-xs)', fontWeight: 600, width: 'fit-content',
                    }}>
                      {uploadingIdPhoto ? 'Uploading…' : 'Upload ID / Passport'}
                    </button>
                  </div>
                </Field>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
                  <Field label="Document Number">
                    <input style={inputStyle} value={idDocNumber} onChange={e => setIdDocNumber(e.target.value)} placeholder="Passport / ID number" />
                  </Field>
                  <Field label="Expiry Date">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                      <input type="date" style={{ ...inputStyle, flex: 1 }} value={idDocExpiry} onChange={e => setIdDocExpiry(e.target.value)} />
                      {(() => { const w = expiryWarning(idDocExpiry); return w ? <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: w.color, whiteSpace: 'nowrap' }}>{w.label}</span> : null; })()}
                    </div>
                  </Field>
                </div>

                <Field label="Status">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                    <select style={{ ...inputStyle, flex: 1, cursor: 'pointer' }} value={autoDocStatus(idDocStatus, idDocExpiry)} onChange={e => setIdDocStatus(e.target.value)}>
                      {DOC_STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                    </select>
                    <div style={{ width: 10, height: 10, borderRadius: '50%', background: docStatusColor(autoDocStatus(idDocStatus, idDocExpiry)), flexShrink: 0 }} />
                  </div>
                </Field>
              </div>
            </div>

            {/* Work Permit — shown for worker and manager; hidden for admin and owner */}
            {(role !== 'admin' && role !== 'owner') && (
              <>
            <div style={sectionHeadStyle}>Work Permit</div>
            <div style={{ background: 'var(--color-surface-2)', padding: 'var(--space-4)', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                <Field label="Document Photo">
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                    {workPermitPhotoUrl ? (
                      <div>
                        <a href={workPermitPhotoUrl} target="_blank" rel="noopener noreferrer" style={{ display: 'inline-block' }}>
                          <img src={workPermitPhotoUrl} alt="Work Permit" style={{ maxWidth: 200, maxHeight: 120, objectFit: 'contain', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)' }} />
                        </a>
                        <div style={{ marginTop: 8 }}>
                          <button type="button" onClick={() => setWorkPermitPhotoUrl('')} style={{ fontSize: 'var(--text-xs)', color: 'var(--color-alert)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>Remove</button>
                        </div>
                      </div>
                    ) : (
                      <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>No permit uploaded.</div>
                    )}
                    <input type="file" accept={ACCEPTED_IMAGE_TYPES} ref={permitFileInputRef} style={{ display: 'none' }} onChange={handlePermitPhotoSelect} />
                    <button type="button" onClick={() => permitFileInputRef.current?.click()} disabled={uploadingPermitPhoto} style={{
                      padding: '8px 16px', borderRadius: 'var(--radius-sm)', background: 'var(--color-surface)',
                      border: '1px solid var(--color-border)', color: 'var(--color-text)', cursor: uploadingPermitPhoto ? 'not-allowed' : 'pointer',
                      fontSize: 'var(--text-xs)', fontWeight: 600, width: 'fit-content',
                    }}>
                      {uploadingPermitPhoto ? 'Uploading…' : 'Upload Work Permit'}
                    </button>
                  </div>
                </Field>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
                  <Field label="Permit Number">
                    <input style={inputStyle} value={workPermitNumber} onChange={e => setWorkPermitNumber(e.target.value)} placeholder="Work permit number" />
                  </Field>
                  <Field label="Expiry Date">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                      <input type="date" style={{ ...inputStyle, flex: 1 }} value={workPermitExpiry} onChange={e => setWorkPermitExpiry(e.target.value)} />
                      {(() => { const w = expiryWarning(workPermitExpiry); return w ? <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: w.color, whiteSpace: 'nowrap' }}>{w.label}</span> : null; })()}
                    </div>
                  </Field>
                </div>

                <Field label="Status">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                    <select style={{ ...inputStyle, flex: 1, cursor: 'pointer' }} value={autoDocStatus(workPermitStatus, workPermitExpiry)} onChange={e => setWorkPermitStatus(e.target.value)}>
                      {DOC_STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                    </select>
                    <div style={{ width: 10, height: 10, borderRadius: '50%', background: docStatusColor(autoDocStatus(workPermitStatus, workPermitExpiry)), flexShrink: 0 }} />
                  </div>
                </Field>
              </div>
            </div>
            </>
            )}

            {/* Compliance Summary */}
            <div style={{ background: 'var(--color-surface-2)', padding: 'var(--space-4)', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)', marginTop: 'var(--space-2)' }}>
              <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>Compliance Overview</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                {[{ label: 'ID / Passport', status: autoDocStatus(idDocStatus, idDocExpiry), expiry: idDocExpiry },
                  ...(role !== 'admin' && role !== 'owner'
                    ? [{ label: 'Work Permit', status: autoDocStatus(workPermitStatus, workPermitExpiry), expiry: workPermitExpiry }]
                    : [])
                ].map(doc => {
                  const warning = expiryWarning(doc.expiry);
                  return (
                    <div key={doc.label} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', padding: 'var(--space-3)', background: 'var(--color-surface)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }}>
                      <div style={{ width: 10, height: 10, borderRadius: '50%', background: docStatusColor(doc.status), flexShrink: 0 }} />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>{doc.label}</div>
                        <div style={{ fontSize: 'var(--text-xs)', color: docStatusColor(doc.status), textTransform: 'capitalize' }}>
                          {doc.status.replace(/_/g, ' ')}
                          {warning && <span style={{ marginLeft: 8, fontWeight: 700 }}>· {warning.label}</span>}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Sticky footer ─────────────────────────────────────────────────── */}
      <div style={{
        position: 'sticky', bottom: 0,
        background: 'var(--color-surface)', borderTop: '1px solid var(--color-border)',
        padding: 'var(--space-3) var(--space-5)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--space-3)',
      }}>
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          {activeTab > 0 && (
            <button onClick={() => setActiveTab((activeTab - 1) as 0 | 1 | 2 | 3)} style={{
              padding: '8px 18px', borderRadius: 'var(--radius-sm)',
              background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
              color: 'var(--color-text-dim)', cursor: 'pointer', fontSize: 'var(--text-sm)',
            }}>← Previous</button>
          )}
          {activeTab < 3 && (
            <button onClick={() => setActiveTab((activeTab + 1) as 0 | 1 | 2 | 3)} style={{
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
          {saving ? 'Creating…' : '+ Create Staff Member'}
        </button>
    </div>

      {/* ── Success overlay — shown after staff member is created ─────────────── */}
      {createdResult && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 200,
          background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24,
        }}>
          <div style={{
            background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border)',
            padding: 32, maxWidth: 480, width: '100%',
            boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
          }}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>✅</div>
            <h2 style={{ margin: '0 0 8px', fontSize: 'var(--text-xl)', fontWeight: 700 }}>
              Staff member created
            </h2>
            <p style={{ margin: '0 0 20px', color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>
              <strong>{createdResult.email}</strong> has been added to your team.
              {createdResult.delivery_method === 'email_invite_sent'
                ? ' An invite email was sent — they can click the link to set their password.'
                : ' Copy the access link below to share it manually.'}
            </p>

            {createdResult.magic_link && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>
                  Access Link — copy to share manually
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input
                    readOnly
                    value={createdResult.magic_link}
                    style={{
                      flex: 1, background: 'var(--color-surface-2)',
                      border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)',
                      padding: '8px 10px', fontSize: 11, color: 'var(--color-text-dim)',
                      outline: 'none', overflow: 'hidden', textOverflow: 'ellipsis',
                    }}
                    onClick={(e) => (e.target as HTMLInputElement).select()}
                  />
                  <button
                    onClick={() => navigator.clipboard.writeText(createdResult.magic_link!)}
                    style={{
                      background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                      borderRadius: 'var(--radius-sm)', padding: '8px 14px',
                      fontSize: 11, fontWeight: 600, color: 'var(--color-text-dim)', cursor: 'pointer',
                      flexShrink: 0,
                    }}
                  >Copy</button>
                </div>
              </div>
            )}

            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={() => router.push(`/admin/staff/${createdResult.user_id}`)}
                style={{
                  flex: 1, padding: '10px 0', borderRadius: 'var(--radius-md)',
                  background: 'var(--color-primary)', color: '#fff', border: 'none',
                  fontWeight: 700, fontSize: 'var(--text-sm)', cursor: 'pointer',
                }}
              >View Staff Profile →</button>
              <button
                onClick={() => { setCreatedResult(null); router.push('/admin/staff/new'); }}
                style={{
                  flex: 1, padding: '10px 0', borderRadius: 'var(--radius-md)',
                  background: 'var(--color-surface-2)', color: 'var(--color-text)',
                  border: '1px solid var(--color-border)',
                  fontWeight: 600, fontSize: 'var(--text-sm)', cursor: 'pointer',
                }}
              >+ Add Another</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
