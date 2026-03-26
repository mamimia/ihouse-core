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

// Temporary mailto email copy — language-aware (until Resend is wired)
const MAILTO_ACCESS: Record<string, { subject: string; body: (link: string) => string }> = {
  en: {
    subject: 'Welcome to Domaniqo \u2014 set up your access',
    body: (link) =>
      `Hello,\n\nWelcome to Domaniqo.\n\nYour staff profile has been approved.\nPlease use the link below to set your password and access your app:\n${link}\n\nThank you,\nDomaniqo Team`,
  },
  th: {
    subject: 'ยินดีต้อนรับสู่ Domaniqo \u2014 ตั้งค่าการเข้าใช้งานของคุณ',
    body: (link) =>
      `สวัสดี,\n\nยินดีต้อนรับสู่ Domaniqo\n\nโปรไฟล์พนักงานของคุณได้รับการอนุมัติแล้ว\nกรุณาใช้ลิงก์ด้านล่างเพื่อตั้งรหัสผ่านและเข้าใช้งานแอปของคุณ:\n${link}\n\nขอบคุณ,\nทีมงาน Domaniqo`,
  },
  he: {
    subject: 'ברוך הבא ל-Domaniqo \u2014 הגדרת הגישה שלך',
    body: (link) =>
      `\u200Fשלום,\n\n\u200Fברוך הבא ל-Domaniqo.\n\n\u200Fפרופיל העובד שלך אושר.\n\u200Fאפשר להשתמש בקישור הבא כדי להגדיר סיסמה ולהיכנס לאפליקציה שלך:\n${link}\n\n\u200Fתודה,\n\u200Fצוות Domaniqo`,
  },
};

function getAccessMailto(lang: string, toEmail: string, link: string): string {
  const tpl = MAILTO_ACCESS[lang] ?? MAILTO_ACCESS.en;
  return `mailto:${encodeURIComponent(toEmail)}?subject=${encodeURIComponent(tpl.subject)}&body=${encodeURIComponent(tpl.body(link))}`;
}


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
  cleaner: { role: 'worker', worker_roles: ['cleaner'] },
  checkin_staff: { role: 'worker', worker_roles: ['checkin'] },
  checkout_staff: { role: 'worker', worker_roles: ['checkout'] },
  maintenance: { role: 'worker', worker_roles: ['maintenance'] },
};

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
  if (daysLeft <= 60) return { label: `${daysLeft}d left`, color: 'var(--color-warn)' };
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
  comm_preference?: Record<string, any>;
  permissions?: Record<string, any>;
  created_at?: string;
  updated_at?: string;
  // Dedicated compliance columns (added in migration 20260323170000)
  date_of_birth?: string;
  id_photo_url?: string;
  id_number?: string;
  id_expiry_date?: string;
  work_permit_photo_url?: string;
  work_permit_number?: string;
  work_permit_expiry_date?: string;
};

type NormalizedRecord = RawRecord & {
  _legacyRole?: string;
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
  { value: 'admin', label: 'Admin' },
  { value: 'manager', label: 'Operational Manager' },
  { value: 'worker', label: 'Worker' },
  { value: 'owner', label: 'Owner' },
];
const WORKER_ROLES = [
  { value: 'cleaner', label: 'Cleaner' },
  { value: 'checkin', label: 'Check-in' },
  { value: 'checkout', label: 'Check-out' },
  { value: 'maintenance', label: 'Maintenance' },
];
const MAINTENANCE_SPECS = [
  { value: 'general', label: 'General' },
  { value: 'gardener', label: 'Gardener' },
  { value: 'pool', label: 'Pool' },
  { value: 'plumber', label: 'Plumber' },
  { value: 'painter', label: 'Painter' },
  { value: 'electrician', label: 'Electrician' },
  { value: 'ac', label: 'AC' },
  { value: 'other', label: 'Other' },
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
    }}>
      {photoUrl
        ? <img src={photoUrl} alt="avatar" style={{ width: '100%', height: '100%', objectFit: 'cover', imageOrientation: 'from-image' as any }} />
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
  const [activeTab, setActiveTab] = useState<0 | 1 | 2 | 3>(0);

  // Tab 1 — Profile
  const [fullName, setFullName] = useState('');
  const [displayName, setDisplayName] = useState('');  // legacy compat
  const [preferredName, setPreferredName] = useState('');  // nickname / display name
  const [email, setEmail] = useState('');
  const [dateOfBirth, setDateOfBirth] = useState('');
  const [photoUrl, setPhotoUrl] = useState('');
  const [idPhotoUrl, setIdPhotoUrl] = useState('');
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
  const [originalAssignments, setOriginalAssignments] = useState<string[]>([]);
  const [availableProperties, setAvailableProperties] = useState<{ id: string; name: string }[]>([]);

  // Tab 3 — Comms
  const [whatsapp, setWhatsapp] = useState('');
  const [telegram, setTelegram] = useState('');
  const [line, setLine] = useState('');
  const [preferredContact, setPreferredContact] = useState('');
  const [resendChannel, setResendChannel] = useState('email');
  const [resendSending, setResendSending] = useState(false);
  const [resendResult, setResendResult] = useState<{ status: string; message?: string; magic_link?: string } | null>(null);
  const [sms, setSms] = useState('');

  // Tab 4 — Documents & Compliance
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
  const [success, setSuccess] = useState<string | null>(null);
  const [confirmToggleActive, setConfirmToggleActive] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [createdAt, setCreatedAt] = useState<string | undefined>();
  const [updatedAt, setUpdatedAt] = useState<string | undefined>();
  
  // Phase 945: Activation Status
  const [authStatus, setAuthStatus] = useState<{ force_reset?: boolean; last_sign_in_at?: string | null; invited_at?: string | null } | null>(null);

  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [uploadingIdPhoto, setUploadingIdPhoto] = useState(false);
  const idFileInputRef = useRef<HTMLInputElement>(null);

  const [uploadingPermitPhoto, setUploadingPermitPhoto] = useState(false);
  const permitFileInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [raw, assignmentsRes, propsRes, authStatusRes] = await Promise.all([
        apiFetch<RawRecord>(`/permissions/${encodeURIComponent(rawUserId)}`),
        apiFetch<any>(`/staff/assignments/${encodeURIComponent(rawUserId)}`).catch(() => ({ property_ids: [] })),
        apiFetch<any>('/admin/properties?status=approved').catch(() => ({ properties: [] })),
        apiFetch<any>(`/admin/staff/${encodeURIComponent(rawUserId)}/status`).catch(() => null),
      ]);

      const record = normalizeLegacyRole(raw);
      setLegacyRole(record._legacyRole);
      
      if (authStatusRes && !authStatusRes.error) {
        setAuthStatus(authStatusRes);
      }

      // Populate Tab 1
      setFullName(record.display_name || '');
      setDisplayName('');  // legacy — unused for display; preferredName handles nickname
      setPhotoUrl(record.photo_url || '');
      setEmail(record.comm_preference?.email || '');
      // DOB: read from dedicated column first, fall back to comm_preference
      setDateOfBirth(
        record.date_of_birth ||
        record.comm_preference?.date_of_birth ||
        ''
      );
      // ID photo: read from dedicated column first
      setIdPhotoUrl(
        record.id_photo_url ||
        record.comm_preference?.id_photo_url ||
        ''
      );

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
      setStartDate(record.comm_preference?.start_date || '');
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

      // Phase 887d: Available properties — approved only.
      // The API call uses ?status=approved, but we also client-side filter as a
      // safety net in case the backend returns mixed results (cached, etc).
      const props = propsRes.properties || propsRes.items || propsRes.data || [];
      setAvailableProperties(
        props
          .filter((p: any) => !p.status || p.status === 'approved')
          .map((p: any) => ({ id: p.id || p.property_id, name: p.display_name || p.name || p.id }))
      );

      // Populate Tab 3
      setWhatsapp(record.comm_preference?.whatsapp || '');
      setTelegram(record.comm_preference?.telegram || '');
      setLine(record.comm_preference?.line || '');
      setSms(record.comm_preference?.sms || record.comm_preference?.phone || record.phone || '');
      setPreferredContact(record.comm_preference?.preferred_contact || record.comm_preference?.preferred_channel || '');
      setPreferredName(record.comm_preference?.preferred_name || record.comm_preference?.nickname || '');

      // Populate Tab 4 — Documents
      // Read from dedicated columns first, fall back to comm_preference variants
      setIdDocNumber(
        record.id_number ||
        record.comm_preference?.id_number ||
        record.comm_preference?.id_doc_number ||
        ''
      );
      setIdDocExpiry(
        record.id_expiry_date ||
        record.comm_preference?.id_expiry_date ||
        record.comm_preference?.id_doc_expiry ||
        ''
      );
      setIdDocStatus(record.comm_preference?.id_doc_status || 'valid');
      setWorkPermitPhotoUrl(
        record.work_permit_photo_url ||
        record.comm_preference?.work_permit_photo_url ||
        ''
      );
      setWorkPermitNumber(
        record.work_permit_number ||
        record.comm_preference?.work_permit_number ||
        ''
      );
      setWorkPermitExpiry(
        record.work_permit_expiry_date ||
        record.comm_preference?.work_permit_expiry_date ||
        record.comm_preference?.work_permit_expiry ||
        ''
      );
      setWorkPermitStatus(record.comm_preference?.work_permit_status || 'missing');

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
          display_name: fullName.trim() || undefined,  // primary: real full name
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
            email: email.trim() || undefined,
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

  const handleToggleActive = async () => {
    try {
      await apiFetch(`/permissions/${encodeURIComponent(rawUserId)}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: !isActive }),
      });
      router.push('/admin/staff?updated=1');
    } catch {
      setError(`Failed to ${isActive ? 'deactivate' : 'activate'} staff member.`);
      setConfirmToggleActive(false);
    }
  };

  const handleDelete = async () => {
    try {
      await apiFetch(`/permissions/${encodeURIComponent(rawUserId)}`, {
        method: 'DELETE',
      });
      router.push('/admin/staff?deleted=1');
    } catch {
      setError('Failed to delete staff member (usually because they are tied to existing tasks/bookings). Archiving is safer.');
      setConfirmDelete(false);
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
      setSuccess('ID Document uploaded successfully. Click Save Changes to keep.');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to upload document');
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
      setSuccess('Work permit uploaded. Click Save Changes to keep.');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to upload document');
    } finally {
      setUploadingPermitPhoto(false);
      if (permitFileInputRef.current) permitFileInputRef.current.value = '';
    }
  };

  const TABS = ['Profile', 'Role & Assignment', 'Access & Comms', 'Documents & Compliance'];

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
            {fullName || rawUserId}
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
          <button key={t} onClick={() => setActiveTab(i as 0 | 1 | 2 | 3)} style={{
            padding: '12px 20px', background: 'none', border: 'none', cursor: 'pointer',
            fontSize: 'var(--text-sm)', fontWeight: activeTab === i ? 700 : 400,
            color: activeTab === i ? 'var(--color-primary)' : 'var(--color-text-dim)',
            borderBottom: activeTab === i ? '2px solid var(--color-primary)' : '2px solid transparent',
            marginBottom: -1, transition: 'all 0.15s', whiteSpace: 'nowrap',
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
            {/* Full Name row */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
              <Field label="Full Name">
                <input style={inputStyle} value={fullName} onChange={e => setFullName(e.target.value)} placeholder="e.g. Somchai Jaidee" />
              </Field>
              <Field label="Display Name / Nickname">
                <input style={inputStyle} value={preferredName} onChange={e => setPreferredName(e.target.value)} placeholder="Optional — nickname at work" />
              </Field>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
              <Field label="Email">
                <input type="email" style={inputStyle} value={email} onChange={e => setEmail(e.target.value)} placeholder="worker@example.com" />
              </Field>
              <Field label="Date of Birth">
                <input type="date" style={inputStyle} value={dateOfBirth} onChange={e => setDateOfBirth(e.target.value)} />
              </Field>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
              <Field label="Photo URL / Avatar">
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
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                {/* Toggle Active / Archive */}
                <div>
                  <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginBottom: 8, marginTop: 0 }}>
                    {isActive ?
                      'Archiving (Deactivating) disables login access while keeping historical records.' :
                      'Activating restores login access for this worker.'}
                  </p>
                  {!confirmToggleActive ? (
                    <button onClick={() => setConfirmToggleActive(true)} style={{
                      padding: '8px 20px', background: 'transparent', border: '1px solid rgba(248,81,73,0.5)',
                      color: '#f85149', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 'var(--text-sm)', fontWeight: 600,
                    }}>
                      {isActive ? 'Deactivate (Archive) Staff Member' : 'Activate Staff Member'}
                    </button>
                  ) : (
                    <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center' }}>
                      <span style={{ fontSize: 'var(--text-sm)', color: '#f85149' }}>Are you sure?</span>
                      <button onClick={handleToggleActive} style={{ padding: '8px 16px', background: '#f85149', border: 'none', color: '#fff', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontWeight: 700, fontSize: 'var(--text-sm)' }}>
                        Confirm {isActive ? 'Archive' : 'Activate'}
                      </button>
                      <button onClick={() => setConfirmToggleActive(false)} style={{ padding: '8px 16px', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text-dim)', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 'var(--text-sm)' }}>
                        Cancel
                      </button>
                    </div>
                  )}
                </div>

                <hr style={{ border: 'none', borderTop: '1px solid rgba(248,81,73,0.2)', margin: '4px 0' }} />

                {/* Hard Delete */}
                <div>
                  <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginBottom: 8, marginTop: 0 }}>
                    Permanently delete this worker from your system. (Will fail if they have tasks assigned).
                  </p>
                  {!confirmDelete ? (
                    <button onClick={() => setConfirmDelete(true)} style={{
                      padding: '8px 20px', background: '#f85149', border: 'none',
                      color: '#fff', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 'var(--text-sm)', fontWeight: 600,
                    }}>
                      Delete Staff Member
                    </button>
                  ) : (
                    <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center' }}>
                      <span style={{ fontSize: 'var(--text-sm)', color: '#f85149', fontWeight: 600 }}>WARNING: This is permanent!</span>
                      <button onClick={handleDelete} style={{ padding: '8px 16px', background: '#f85149', border: '2px solid #b31d28', color: '#fff', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontWeight: 700, fontSize: 'var(--text-sm)' }}>
                        Yes, Hard Delete
                      </button>
                      <button onClick={() => setConfirmDelete(false)} style={{ padding: '8px 16px', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text-dim)', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 'var(--text-sm)' }}>
                        Cancel
                      </button>
                    </div>
                  )}
                </div>
              </div>
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

            {/* Send / Resend Access Link or Password Update */}
            {authStatus && (
              <div>
                <div style={sectionHeadStyle}>Activation Status</div>
                <div style={{
                  display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 'var(--space-3)',
                  background: 'var(--color-surface-2)', padding: 'var(--space-4)',
                  borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)',
                  marginBottom: 'var(--space-4)'
                }}>
                  <div>
                    <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 2 }}>Lifecycle Stage</div>
                    <div style={{ color: authStatus.force_reset ? 'var(--color-copper)' : 'var(--color-ok)', fontWeight: 600, fontSize: 'var(--text-sm)', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: authStatus.force_reset ? 'var(--color-copper)' : 'var(--color-ok)' }} />
                      {authStatus.force_reset ? 'Pending Activation' : 'Worker Activated'}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 2 }}>Invited / Updated</div>
                    <div style={{ color: 'var(--color-text)', fontSize: 'var(--text-sm)' }}>
                      {authStatus.invited_at ? new Date(authStatus.invited_at).toLocaleDateString() : 'N/A'}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 2 }}>Last Sign In</div>
                    <div style={{ color: 'var(--color-text)', fontSize: 'var(--text-sm)' }}>
                      {authStatus.last_sign_in_at ? new Date(authStatus.last_sign_in_at).toLocaleDateString() : 'Never'}
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div>
              <div style={sectionHeadStyle}>
                {authStatus?.force_reset === false ? 'Account Management' : 'Send Access Link'}
              </div>
              <div style={{
                background: 'var(--color-surface-2)', padding: 'var(--space-4)',
                borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)',
              }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', margin: '0 0 var(--space-3) 0' }}>
                  {authStatus?.force_reset === false
                    ? 'Generate a recovery password link or copy instructions to help the worker regain access to their account.'
                    : 'Send or re-send a first-access link to this staff member. They can use this to set their password and log into their role-specific app.'}
                </p>
                
                {authStatus?.force_reset === false ? (
                  // Post-Activation Controls
                  <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
                    <button
                      disabled={resendSending}
                      onClick={async () => {
                        setResendSending(true);
                        setResendResult(null);
                        try {
                          // Force channel as email since it's a reset
                          const resp = await apiFetch<any>(`/admin/staff/${rawUserId}/resend-access`, {
                            method: 'POST',
                            body: JSON.stringify({ channel: 'email', frontend_url: window.location.origin }),
                          });
                          setResendResult(resp);
                          alert('Password recovery process initiated via email magic link.');
                        } catch (err: any) {
                          setResendResult({ status: 'error', message: err.message || 'Failed to send' });
                        } finally {
                          setResendSending(false);
                        }
                      }}
                      style={{
                        padding: '10px 20px', borderRadius: 'var(--radius-sm)',
                        background: 'var(--color-primary, #4A7C59)', color: '#fff', border: 'none',
                        cursor: resendSending ? 'not-allowed' : 'pointer', fontWeight: 600,
                        fontSize: 'var(--text-sm)', opacity: resendSending ? 0.6 : 1,
                        whiteSpace: 'nowrap' as const,
                      }}
                    >
                      {resendSending ? 'Sending...' : 'Send Password Reset Link'}
                    </button>
                    <button
                      disabled={resendSending}
                      onClick={() => {
                        const loginUrl = `${window.location.origin}/login`;
                        const emailInput = email ? `Your login email is: ${email}` : `Use your registered email.`;
                        alert(`Login Instructions:\n1. Go to ${loginUrl}\n2. ${emailInput}\n3. Enter the password you created.\n\n(Tip: Save these instructions or copy them directly to clipboard in the future!)`);
                      }}
                      style={{
                        padding: '10px 20px', borderRadius: 'var(--radius-sm)',
                        background: 'transparent', color: 'var(--color-primary, #4A7C59)',
                        border: '1px solid var(--color-primary, #4A7C59)',
                        cursor: 'pointer', fontWeight: 600,
                        fontSize: 'var(--text-sm)', whiteSpace: 'nowrap' as const,
                      }}
                    >
                      Copy Login Instructions
                    </button>
                  </div>
                ) : (
                  // Pre-Activation Controls
                  <>
                    <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                      <div style={{ flex: 1, minWidth: 160 }}>
                        <label style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Delivery Channel</label>
                        <select
                          style={{ ...inputStyle, cursor: 'pointer', width: '100%' }}
                          value={resendChannel}
                          onChange={e => setResendChannel(e.target.value)}
                        >
                          <option value="email">Email</option>
                          {whatsapp && <option value="whatsapp">WhatsApp</option>}
                          {sms && <option value="sms">SMS / Phone</option>}
                          {telegram && <option value="telegram">Telegram</option>}
                          {line && <option value="line">LINE</option>}
                        </select>
                      </div>
                      <button
                        disabled={resendSending}
                        onClick={async () => {
                          setResendSending(true);
                          setResendResult(null);
                          try {
                            const resp = await apiFetch<any>(`/admin/staff/${rawUserId}/resend-access`, {
                              method: 'POST',
                              body: JSON.stringify({ channel: resendChannel, frontend_url: window.location.origin }),
                            });
                            setResendResult(resp);
                          } catch (err: any) {
                            setResendResult({ status: 'error', message: err.message || 'Failed to send' });
                          } finally {
                            setResendSending(false);
                          }
                        }}
                        style={{
                          padding: '10px 20px', borderRadius: 'var(--radius-sm)',
                          background: 'var(--color-primary, #4A7C59)', color: '#fff', border: 'none',
                          cursor: resendSending ? 'not-allowed' : 'pointer', fontWeight: 600,
                          fontSize: 'var(--text-sm)', opacity: resendSending ? 0.6 : 1,
                          minHeight: 40, whiteSpace: 'nowrap' as const,
                        }}
                      >
                        {resendSending ? 'Sending...' : 'Send Access Link'}
                      </button>
                    </div>

                    {/* mailto Send by Email — shown when email is known */}
                    {email && (
                      <div style={{ marginTop: 'var(--space-3)', padding: 'var(--space-3)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }}>
                        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', margin: '0 0 8px', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}>Quick Send by Email</p>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                          <span style={{ fontSize: 13, color: 'var(--color-text-dim)' }}>To: {email}</span>
                          <button
                            type="button"
                            disabled={resendSending}
                            onClick={async () => {
                              setResendSending(true);
                              setResendResult(null);
                              try {
                                const resp = await apiFetch<any>(`/admin/staff/${rawUserId}/resend-access`, {
                                  method: 'POST',
                                  body: JSON.stringify({ channel: 'email', frontend_url: window.location.origin }),
                                });
                                setResendResult(resp);
                                if (resp.magic_link) {
                                    window.location.href = getAccessMailto(language, email, resp.magic_link);
                                } else {
                                    alert('Could not generate the magic link. Check backend logs.');
                                }
                              } catch (err: any) {
                                setResendResult({ status: 'error', message: err.message || 'Failed to generate link' });
                              } finally {
                                setResendSending(false);
                              }
                            }}
                            style={{ display: 'inline-block', padding: '7px 14px', background: 'var(--color-primary)', borderRadius: 'var(--radius-sm)', color: '#fff', fontSize: 13, fontWeight: 600, border: 'none', cursor: resendSending ? 'not-allowed' : 'pointer', opacity: resendSending ? 0.6 : 1, whiteSpace: 'nowrap' }}
                          >
                            {resendSending ? 'Generating Link...' : '✉ Send by Email'}
                          </button>
                          <span style={{ fontSize: 11, color: 'var(--color-text-faint)' }}>Generates link and opens your mail client directly</span>
                        </div>
                        {resendResult?.magic_link && (
                          <div style={{ marginTop: 10 }}>
                            <p style={{ fontSize: 11, color: 'var(--color-text-faint)', margin: '0 0 6px' }}>Direct link (if your mail client didn't open):</p>
                            <div style={{ display: 'flex', gap: 8 }}>
                              <input readOnly value={resendResult.magic_link} style={{ ...inputStyle, fontFamily: 'monospace', fontSize: 12, flex: 1 }} onClick={(e: any) => e.target.select()} />
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </>
                )}

                {resendResult && (
                  <div style={{
                    marginTop: 'var(--space-3)', padding: 'var(--space-3)',
                    borderRadius: 'var(--radius-sm)',
                    background: resendResult.status === 'error' ? 'rgba(196,91,74,0.1)' : 'rgba(74,124,89,0.1)',
                    border: `1px solid ${resendResult.status === 'error' ? 'rgba(196,91,74,0.3)' : 'rgba(74,124,89,0.3)'}`,
                    fontSize: 'var(--text-sm)',
                    color: resendResult.status === 'error' ? 'var(--color-alert)' : 'var(--color-ok, #4A7C59)',
                  }}>
                    {resendResult.status === 'sent' && '✓ Access link sent via email.'}
                    {resendResult.status === 'link_generated' && (
                      <div>
                        <div style={{ marginBottom: 8 }}>✓ Magic link generated. Copy and send via {resendResult.message?.split('via ')[1] || resendChannel}:</div>
                        <input readOnly value={resendResult.magic_link || ''} style={{ ...inputStyle, fontFamily: 'monospace', fontSize: 12, width: '100%' }} onClick={(e: any) => e.target.select()} />
                      </div>
                    )}
                    {resendResult.status === 'error' && `✗ ${resendResult.message}`}
                  </div>
                )}
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
                  Property visibility controls (financials, bookings, tasks) will be configured in a future update.
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Tab 4: Documents & Compliance ─────────────────────────────── */}
        {activeTab === 3 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>

            {/* ── ID / Passport ─────────────────────────────── */}
            <div style={sectionHeadStyle}>ID / Passport</div>
            <div style={{ background: 'var(--color-surface-2)', padding: 'var(--space-4)', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                {/* Photo/file */}
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

            {/* ── Work Permit ──────────────────────────────── */}
            <div style={sectionHeadStyle}>Work Permit</div>
            <div style={{ background: 'var(--color-surface-2)', padding: 'var(--space-4)', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                {/* Photo/file */}
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

            {/* Compliance Summary */}
            <div style={{ background: 'var(--color-surface-2)', padding: 'var(--space-4)', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)', marginTop: 'var(--space-2)' }}>
              <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>Compliance Overview</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                {[{ label: 'ID / Passport', status: autoDocStatus(idDocStatus, idDocExpiry), expiry: idDocExpiry },
                  { label: 'Work Permit', status: autoDocStatus(workPermitStatus, workPermitExpiry), expiry: workPermitExpiry }].map(doc => {
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

      {/* ── Sticky footer ───────────────────────────────────────────────── */}
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
          {saving ? 'Saving…' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
}
