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
import { useLanguage } from '@/lib/LanguageContext';

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
  if (!res.ok) {
    // Phase 1038: Read body before throwing so the real backend reason is surfaced.
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body?.detail || body?.message || body?.error || detail;
    } catch { /* ignore JSON parse failure */ }
    throw new Error(detail);
  }
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

// ── Gregorian Date Input ─────────────────────────────────────────────────────
// Day + Month selects (fixed small sets) + Year number input.
// Completely locale-independent — never shows Buddhist Era.
// mode controls the year range:
//   'birth'      → 1940 – this year  (wide historical range for DOB)
//   'employment' → 2000 – this year+2 (past + modest future for hire dates)
//   'expiry'     → this year – this year+20 (future-biased for documents)
const MONTHS_EN = [
  'January','February','March','April','May','June',
  'July','August','September','October','November','December',
];

type DateFieldMode = 'birth' | 'employment' | 'expiry';

function GregorianDateInput({
  value, onChange, style, mode = 'birth',
}: {
  value: string;        // ISO YYYY-MM-DD or empty string
  onChange: (v: string) => void;
  style?: React.CSSProperties;
  mode?: DateFieldMode;
}) {
  const thisYear = new Date().getFullYear();

  // Field-specific year boundaries
  const yearMin = mode === 'birth'      ? 1940
                : mode === 'employment' ? 2000
                : /* expiry */            thisYear;          // current year onwards
  const yearMax = mode === 'birth'      ? thisYear
                : mode === 'employment' ? thisYear + 2
                : /* expiry */            thisYear + 20;     // 20 years forward for docs

  // Parse current value
  const parts = (value || '').split('-');
  const curYear  = parts[0] || '';
  const curMonth = parts[1] || '';
  const curDay   = parts[2] || '';

  const update = (y: string, m: string, d: string) => {
    if (y && m && d) onChange(`${y}-${m.padStart(2,'0')}-${d.padStart(2,'0')}`);
    else onChange('');
  };

  // Days adjusts to selected month
  const daysInMonth = curYear && curMonth
    ? new Date(parseInt(curYear), parseInt(curMonth), 0).getDate()
    : 31;
  const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);

  const sel: React.CSSProperties = {
    ...style, flex: 1, cursor: 'pointer', appearance: 'auto' as any,
  };

  return (
    <div style={{ display: 'flex', gap: 6 }}>
      {/* Day — select (1-31) */}
      <select
        style={{ ...sel, flex: '0 0 68px' }}
        value={curDay}
        onChange={e => update(curYear, curMonth, e.target.value)}
        aria-label="Day"
      >
        <option value="">Day</option>
        {days.map(d => <option key={d} value={String(d).padStart(2,'0')}>{d}</option>)}
      </select>

      {/* Month — select (January-December) */}
      <select
        style={{ ...sel, flex: '0 0 120px' }}
        value={curMonth}
        onChange={e => update(curYear, e.target.value, curDay)}
        aria-label="Month"
      >
        <option value="">Month</option>
        {MONTHS_EN.map((m, i) => (
          <option key={i+1} value={String(i+1).padStart(2,'0')}>{m}</option>
        ))}
      </select>

      {/* Year — number input: type directly or arrow-key, no long dropdown */}
      <input
        type="number"
        aria-label="Year"
        min={yearMin}
        max={yearMax}
        placeholder="Year"
        value={curYear}
        onChange={e => {
          const y = e.target.value;
          // Accept partial input while typing; only commit full 4-digit year within range
          if (!y) { update('', curMonth, curDay); return; }
          update(y, curMonth, curDay);
        }}
        style={{
          ...style,
          flex: '0 0 82px',
          cursor: 'text',
          MozAppearance: 'textfield' as any,
        }}
      />
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
  const { t } = useLanguage();
  const rawUserId = decodeURIComponent(params.userId as string);

  // Loading state
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [legacyRole, setLegacyRole] = useState<string | undefined>(undefined);

  // Tab state
  const [activeTab, setActiveTab] = useState<0 | 1 | 2 | 3 | 4>(0);

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
  // Role summary/edit mode: collapsed by default (shows saved summary), opens only on [Edit]
  const [roleEditMode, setRoleEditMode] = useState(false);

  // Phase 1030: Priority/Primary/Backup state for each assigned property
  // propertyLaneData[property_id] → { is_primary, priority, lane_count }
  const [propertyLaneData, setPropertyLaneData] = useState<Record<string, { is_primary: boolean; priority: number; lane_count: number; lanes: Record<string, any[]>; supervisors?: { user_id: string; display_name: string; role: string; photo_url?: string; is_active?: boolean; assigned_at?: string }[] }>>({});
  // Baton-transfer confirmation modal
  const [batonPreview, setBatonPreview] = useState<{
    user_id: string; property_id: string; property_name: string;
    removed_name: string; is_primary: boolean; new_primary_name?: string;
    pending_tasks_count: number; acknowledged_tasks_count: number;
  } | null>(null);
  const [batonLoading, setBatonLoading] = useState(false);
  // Primary/Backup help panel
  const [showPBHelp, setShowPBHelp] = useState(false);

  // Tab 3 — Comms
  const [whatsapp, setWhatsapp] = useState('');
  const [telegram, setTelegram] = useState('');
  const [line, setLine] = useState('');
  const [preferredContact, setPreferredContact] = useState('');
  const [resendChannel, setResendChannel] = useState('email');
  const [resendSending, setResendSending] = useState(false);
  // delivery_method and email are returned by resend-access and needed to show correct success message
  const [resendResult, setResendResult] = useState<{ status: string; message?: string; magic_link?: string; delivery_method?: string; email?: string } | null>(null);
  const [sms, setSms] = useState('');

  // Tab 4 — Documents & Compliance
  const [idDocNumber, setIdDocNumber] = useState('');
  const [idDocExpiry, setIdDocExpiry] = useState('');
  const [idDocStatus, setIdDocStatus] = useState('missing');
  const [workPermitPhotoUrl, setWorkPermitPhotoUrl] = useState('');
  const [workPermitNumber, setWorkPermitNumber] = useState('');
  const [workPermitExpiry, setWorkPermitExpiry] = useState('');
  const [workPermitStatus, setWorkPermitStatus] = useState('missing');

  // Phase 1021-C: Linked owner profile state
  const [linkedOwner, setLinkedOwner] = useState<{ id: string; name: string; email?: string; property_ids?: string[] } | null | 'loading'>('loading');

  // Phase 1023-C: Delegated Authority state
  type CapEntry = { key: string; label: string; description: string; power_type: string; granted: boolean };
  type CapGroup = { group: string; label: string; capabilities: CapEntry[] };
  const [capGroups, setCapGroups] = useState<CapGroup[]>([]);
  const [capLoading, setCapLoading] = useState(false);
  const [capDirty, setCapDirty] = useState<Record<string, Record<string, boolean>>>({});  // group → { key: localBool }
  const [capPending, setCapPending] = useState<string | null>(null);  // group currently in confirm step
  const [capApplying, setCapApplying] = useState<string | null>(null);  // group currently being saved
  const [capError, setCapError] = useState<string | null>(null);
  const [capHistory, setCapHistory] = useState<any[]>([]);
  const [capInfoOpen, setCapInfoOpen] = useState<string | null>(null); // capability key with open info popover

  // UI state
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [confirmToggleActive, setConfirmToggleActive] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [createdAt, setCreatedAt] = useState<string | undefined>();
  const [updatedAt, setUpdatedAt] = useState<string | undefined>();

  // Phase 1061b — Deactivation modal state
  const [showDeactivateModal, setShowDeactivateModal] = useState(false);
  const [deactivateLoading, setDeactivateLoading] = useState(false);
  // Warning data loaded when modal opens
  const [deactivateWarning, setDeactivateWarning] = useState<{
    assigned_properties: number;
    pending_tasks: number;
    active_tasks: number;
    loaded: boolean;
  }>({ assigned_properties: 0, pending_tasks: 0, active_tasks: 0, loaded: false });
  
  // Phase 945+947: Activation Status + Identity Chain
  const [authStatus, setAuthStatus] = useState<{ 
    force_reset?: boolean; 
    last_sign_in_at?: string | null; 
    invited_at?: string | null;
    access_link_sent_at?: string | null;
    access_link_opened_at?: string | null;
    // Phase 947: identity chain
    auth_email?: string | null;
    comm_email?: string | null;
    identity_mismatch?: boolean;
  } | null>(null);
  // Phase 947d: explicit status load failure — prevents silent grey-pill degradation
  const [statusLoadFailed, setStatusLoadFailed] = useState(false);
  // Phase 947d: repair UI state
  const [repairLoading, setRepairLoading] = useState(false);
  const [repairResult, setRepairResult] = useState<{ ok: boolean; message: string } | null>(null);

  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [uploadingIdPhoto, setUploadingIdPhoto] = useState(false);
  const idFileInputRef = useRef<HTMLInputElement>(null);

  const [uploadingPermitPhoto, setUploadingPermitPhoto] = useState(false);
  const permitFileInputRef = useRef<HTMLInputElement>(null);

  const fetchAuthStatus = useCallback(async () => {
    try {
      const authStatusRes = await apiFetch<any>(`/admin/staff/${encodeURIComponent(rawUserId)}/status`);
      if (authStatusRes && !authStatusRes.error) {
        setAuthStatus(authStatusRes);
        setStatusLoadFailed(false); // clear any previous failure
      } else {
        // Backend returned an error shape — explicit failure, not neutral grey
        setStatusLoadFailed(true);
      }
    } catch (e) {
      // Network or 5xx — must show error, NOT silent grey pills
      setStatusLoadFailed(true);
      console.error('[lifecycle] status fetch failed:', e);
    }
  }, [rawUserId]);

  // Phase 947c: Poll the status block every 30s so lifecycle pills reflect reality
  // without requiring a full page reload. Scoped only to fetchAuthStatus — does
  // not re-fetch trade data, tabs, or form state.
  useEffect(() => {
    fetchAuthStatus(); // immediate call on mount
    const interval = setInterval(fetchAuthStatus, 30_000);
    return () => clearInterval(interval);
  }, [fetchAuthStatus]);

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

      // Phase 1038: Fetch lane/priority data for ALL available properties (not just assigned).
      // This lets us show existing supervisors on every row — even unassigned ones.
      if (propsRes) {
        const allPropIds = (
          propsRes.properties || propsRes.items || propsRes.data || []
        )
          .filter((p: any) => !p.status || p.status === 'approved')
          .map((p: any) => p.id || p.property_id)
          .filter(Boolean);

        const laneDataMap: Record<string, any> = {};
        await Promise.all(
          allPropIds.map(async (pid: string) => {
            try {
              const laneRes = await apiFetch<any>(`/staff/property-lane/${encodeURIComponent(pid)}`);
              laneDataMap[pid] = laneRes;
            } catch { /* best effort */ }
          })
        );
        setPropertyLaneData(laneDataMap);
      }

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

  // Phase 1021-C: Fetch linked owner profile whenever userId or role changes
  const fetchLinkedOwner = useCallback(async () => {
    setLinkedOwner('loading');
    try {
      const res = await apiFetch<any>(`/admin/owners/by-user/${encodeURIComponent(rawUserId)}`);
      setLinkedOwner(res.linked ? res.owner : null);
    } catch {
      setLinkedOwner(null);
    }
  }, [rawUserId]);

  useEffect(() => {
    if (role === 'owner') fetchLinkedOwner();
    else setLinkedOwner(null);
  }, [role, fetchLinkedOwner]);

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
    } catch (e: any) {
      setError(e?.message || 'Save failed. Please try again.');
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
      // Update in place — no redirect
      setIsActive(prev => !prev);
      setShowDeactivateModal(false);
      setConfirmToggleActive(false);
      setSuccess(isActive ? 'Staff member deactivated. They will lose access on their next request.' : 'Staff member reactivated. They can now log in again.');
      setTimeout(() => setSuccess(null), 5000);
    } catch {
      setError(`Failed to ${isActive ? 'deactivate' : 'reactivate'} staff member.`);
      setShowDeactivateModal(false);
      setConfirmToggleActive(false);
    }
  };

  // Fetch warning info when deactivation modal opens
  const openDeactivateModal = async () => {
    setShowDeactivateModal(true);
    setDeactivateWarning({ assigned_properties: 0, pending_tasks: 0, active_tasks: 0, loaded: false });
    try {
      const [assignRes, tasksRes] = await Promise.all([
        apiFetch<any>(`/staff/assignments/${encodeURIComponent(rawUserId)}`).catch(() => ({ property_ids: [] })),
        apiFetch<any>(`/worker/tasks?limit=100`).catch(() => ({ tasks: [] })),
      ]);
      const propCount = (assignRes.property_ids || []).length;
      const allTasks: any[] = tasksRes.tasks || [];
      const workerTasks = allTasks.filter((t: any) => t.assigned_to === rawUserId || t.worker_id === rawUserId);
      const pendingTasks = workerTasks.filter((t: any) => ['PENDING', 'ACKNOWLEDGED'].includes(t.status)).length;
      const activeTasks = workerTasks.filter((t: any) => t.status === 'IN_PROGRESS').length;
      setDeactivateWarning({ assigned_properties: propCount, pending_tasks: pendingTasks, active_tasks: activeTasks, loaded: true });
    } catch {
      setDeactivateWarning(prev => ({ ...prev, loaded: true }));
    }
  };

  const handleDelete = async () => {
    try {
      // Phase 1037: Hard delete = remove from tenant_permissions + Supabase Auth.
      // DELETE /admin/staff/{userId} handles both atomically.
      // Falls back to permissions-only delete if auth deletion fails gracefully.
      await apiFetch(`/admin/staff/${encodeURIComponent(rawUserId)}`, {
        method: 'DELETE',
      });
      router.push('/admin/staff?deleted=1');
    } catch {
      setError('Failed to delete staff member (usually because they are tied to existing tasks/bookings). Try archiving instead.');
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

  const TABS = [
    'Profile',
    'Role & Assignment',
    'Access & Comms',
    'Documents & Compliance',
    // Tab 4 only appears for managers, added dynamically below
  ];
  const visibleTabs = role === 'manager'
    ? [...TABS, 'Delegated Authority']
    : TABS;
  const maxTab = visibleTabs.length - 1;

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
        {visibleTabs.map((t, i) => (
          <button key={t} onClick={() => {
            setActiveTab(i as 0 | 1 | 2 | 3 | 4);
            // Lazy-load capabilities when tab 4 is opened
            if (i === 4 && capGroups.length === 0 && !capLoading) {
              setCapLoading(true);
              Promise.all([
                apiFetch(`/admin/managers/${rawUserId}/capabilities`),
                apiFetch(`/admin/managers/${rawUserId}/capabilities/history?limit=5`),
              ]).then(([capRes, histRes]) => {
                if (capRes?.data?.grouped_capabilities) setCapGroups(capRes.data.grouped_capabilities);
                if (histRes?.data?.events) setCapHistory(histRes.data.events);
              }).catch(() => setCapError('Failed to load delegated capabilities.')).finally(() => setCapLoading(false));
            }
          }} style={{
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
                <GregorianDateInput value={dateOfBirth} onChange={setDateOfBirth} style={inputStyle} mode="birth" />
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
                <GregorianDateInput value={startDate} onChange={setStartDate} style={inputStyle} mode="employment" />
              </Field>
              <div />
            </div>

            <div style={sectionHeadStyle}>Preferences</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
              <Field label="Preferred Language">
                <select style={{ ...inputStyle, cursor: 'pointer' }} value={language} onChange={e => setLanguage(e.target.value)}>
                  {LANGUAGES.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
                </select>
              </Field>
            </div>

            <Field label="Internal Notes">
              <textarea style={{ ...inputStyle, resize: 'vertical', minHeight: 72 }} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Private notes visible to admin only" />
            </Field>

            {/* Meta */}
            {(createdAt || updatedAt) && (
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-3)' }}>
                {createdAt && <div>Created: {new Date(createdAt).toLocaleDateString('en-GB')}</div>}
                {updatedAt && <div>Updated: {new Date(updatedAt).toLocaleDateString('en-GB')}</div>}
              </div>
            )}

            {/* ── Danger Zone — Phase 1061b ─────────────────────────────── */}
            <div style={{ marginTop: 'var(--space-6)', padding: 'var(--space-4)', border: '1px solid rgba(248,81,73,0.3)', borderRadius: 'var(--radius-md)', background: 'rgba(248,81,73,0.05)' }}>
              <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: '#f85149', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                Danger Zone
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>

                {/* ── Primary control: Deactivate / Reactivate ── */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--space-4)' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)', marginBottom: 4 }}>
                      {isActive ? 'Deactivate Staff Member' : 'Reactivate Staff Member'}
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', lineHeight: 1.5 }}>
                      {isActive
                        ? 'Removes login and app access immediately. Historical records, tasks, and assignments are preserved. This action is reversible.'
                        : 'Restores full login and app access for this staff member. They will be able to sign in on their next attempt.'}
                    </div>
                  </div>
                  {isActive ? (
                    <button
                      id="btn-deactivate-staff"
                      onClick={openDeactivateModal}
                      style={{
                        flexShrink: 0, padding: '9px 20px',
                        background: 'transparent',
                        border: '1.5px solid #f85149',
                        color: '#f85149',
                        borderRadius: 'var(--radius-sm)',
                        cursor: 'pointer', fontSize: 'var(--text-sm)', fontWeight: 700,
                        whiteSpace: 'nowrap',
                        transition: 'background 0.15s, color 0.15s',
                      }}
                      onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(248,81,73,0.1)'; }}
                      onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent'; }}
                    >
                      Deactivate Staff Member
                    </button>
                  ) : (
                    <button
                      id="btn-reactivate-staff"
                      onClick={handleToggleActive}
                      style={{
                        flexShrink: 0, padding: '9px 20px',
                        background: '#1a7f37',
                        border: 'none',
                        color: '#fff',
                        borderRadius: 'var(--radius-sm)',
                        cursor: 'pointer', fontSize: 'var(--text-sm)', fontWeight: 700,
                        whiteSpace: 'nowrap',
                        transition: 'background 0.15s',
                      }}
                      onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = '#2da44e'; }}
                      onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = '#1a7f37'; }}
                    >
                      ✓ Reactivate Staff Member
                    </button>
                  )}
                </div>

                <hr style={{ border: 'none', borderTop: '1px solid rgba(248,81,73,0.15)', margin: '0' }} />

                {/* ── Secondary control: Permanent Delete ── */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--space-4)' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)', marginBottom: 4 }}>
                      Permanently Delete
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', lineHeight: 1.5 }}>
                      Removes all records permanently. Will fail if this staff member has assigned tasks. Use Deactivate instead unless permanent removal is required.
                    </div>
                  </div>
                  {!confirmDelete ? (
                    <button
                      id="btn-delete-staff"
                      onClick={() => setConfirmDelete(true)}
                      style={{
                        flexShrink: 0, padding: '9px 20px',
                        background: '#f85149', border: 'none',
                        color: '#fff', borderRadius: 'var(--radius-sm)',
                        cursor: 'pointer', fontSize: 'var(--text-sm)', fontWeight: 700,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      Delete Permanently
                    </button>
                  ) : (
                    <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center', flexShrink: 0 }}>
                      <button onClick={handleDelete} style={{ padding: '8px 14px', background: '#b31d28', border: '2px solid #b31d28', color: '#fff', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontWeight: 700, fontSize: 'var(--text-sm)' }}>
                        Yes, Delete
                      </button>
                      <button onClick={() => setConfirmDelete(false)} style={{ padding: '8px 14px', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text-dim)', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 'var(--text-sm)' }}>
                        Cancel
                      </button>
                    </div>
                  )}
                </div>

              </div>
            </div>

            {/* ── Deactivation Confirmation Modal — Phase 1061b ── */}
            {showDeactivateModal && (
              <div
                style={{
                  position: 'fixed', inset: 0, zIndex: 9999,
                  background: 'rgba(0,0,0,0.65)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  padding: 'var(--space-4)',
                }}
                onClick={e => { if (e.target === e.currentTarget) setShowDeactivateModal(false); }}
              >
                <div style={{
                  background: 'var(--color-surface)',
                  border: '1px solid rgba(248,81,73,0.4)',
                  borderRadius: 'var(--radius-lg)',
                  padding: 'var(--space-5)',
                  maxWidth: 480, width: '100%',
                  boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
                }}>
                  {/* Modal header */}
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
                    <div style={{ fontSize: 28, lineHeight: 1 }}>⚠️</div>
                    <div>
                      <div style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--color-text)', marginBottom: 4 }}>
                        Deactivate {fullName || 'this staff member'}?
                      </div>
                      <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', lineHeight: 1.5 }}>
                        This will deactivate them immediately. Any current session will be blocked on the next request.
                      </div>
                    </div>
                  </div>

                  {/* What will happen */}
                  <div style={{ background: 'var(--color-surface-2)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-3)', marginBottom: 'var(--space-4)', fontSize: 'var(--text-sm)', lineHeight: 1.7 }}>
                    <div style={{ fontWeight: 600, color: 'var(--color-text)', marginBottom: 6 }}>What happens when you deactivate:</div>
                    <div style={{ color: 'var(--color-text-dim)' }}>✗ &nbsp;They lose all login and app access immediately</div>
                    <div style={{ color: 'var(--color-text-dim)' }}>✗ &nbsp;Any active session will be blocked on the next request</div>
                    <div style={{ color: 'var(--color-ok, #4A7C59)' }}>✓ &nbsp;Historical records and task history are preserved</div>
                    <div style={{ color: 'var(--color-ok, #4A7C59)' }}>✓ &nbsp;This action is reversible — you can reactivate them later</div>
                  </div>

                  {/* Live warning data */}
                  {!deactivateWarning.loaded ? (
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginBottom: 'var(--space-3)' }}>Checking assignments and tasks…</div>
                  ) : (deactivateWarning.assigned_properties > 0 || deactivateWarning.pending_tasks > 0 || deactivateWarning.active_tasks > 0) ? (
                    <div style={{ background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.25)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-3)', marginBottom: 'var(--space-4)', fontSize: 'var(--text-sm)' }}>
                      <div style={{ fontWeight: 600, color: '#f85149', marginBottom: 6 }}>Active work to be aware of:</div>
                      {deactivateWarning.assigned_properties > 0 && (
                        <div style={{ color: 'var(--color-text-dim)' }}>• Assigned to {deactivateWarning.assigned_properties} propert{deactivateWarning.assigned_properties === 1 ? 'y' : 'ies'} — assignments remain but they cannot work them</div>
                      )}
                      {deactivateWarning.active_tasks > 0 && (
                        <div style={{ color: '#f85149', fontWeight: 600 }}>• {deactivateWarning.active_tasks} task{deactivateWarning.active_tasks === 1 ? '' : 's'} currently IN PROGRESS — reassign before deactivating</div>
                      )}
                      {deactivateWarning.pending_tasks > 0 && (
                        <div style={{ color: 'var(--color-text-dim)' }}>• {deactivateWarning.pending_tasks} pending/acknowledged task{deactivateWarning.pending_tasks === 1 ? '' : 's'} — will remain unworked until reassigned</div>
                      )}
                    </div>
                  ) : (
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginBottom: 'var(--space-3)' }}>No active tasks or in-progress work detected.</div>
                  )}

                  {/* Actions */}
                  <div style={{ display: 'flex', gap: 'var(--space-3)', justifyContent: 'flex-end' }}>
                    <button
                      onClick={() => setShowDeactivateModal(false)}
                      style={{ padding: '9px 20px', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text-dim)', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 'var(--text-sm)', fontWeight: 500 }}
                    >
                      Cancel
                    </button>
                    <button
                      id="btn-confirm-deactivate"
                      onClick={handleToggleActive}
                      disabled={deactivateLoading}
                      style={{
                        padding: '9px 20px', background: '#f85149', border: 'none',
                        color: '#fff', borderRadius: 'var(--radius-sm)',
                        cursor: deactivateLoading ? 'not-allowed' : 'pointer',
                        fontSize: 'var(--text-sm)', fontWeight: 700,
                        opacity: deactivateLoading ? 0.7 : 1,
                      }}
                    >
                      {deactivateLoading ? 'Deactivating…' : 'Yes, Deactivate Staff Member'}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
        {/* ── Tab 2: Role & Assignment ──────────────────────────────────── */}
        {activeTab === 1 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>

            {/* ── Role summary / edit-mode toggle ── */}
            {roleEditMode ? (
              // ── Edit Mode: full selection grid ──────────────────────────
              <>
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
              <button
                type="button"
                onClick={() => setRoleEditMode(false)}
                style={{
                  alignSelf: 'flex-start', padding: '6px 14px', borderRadius: 'var(--radius-sm)',
                  background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                  color: 'var(--color-text-dim)', cursor: 'pointer', fontSize: 'var(--text-xs)', fontWeight: 600,
                }}
              >
                ✓ Collapse Role
              </button>
              </>
            ) : (
              // ── Summary Mode: collapsed one-liner ───────────────────────
              <div style={{
                display: 'flex', alignItems: 'center', gap: 'var(--space-3)',
                padding: 'var(--space-3) var(--space-4)',
                background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-md)',
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>Role</div>
                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>
                    {role === 'worker' ? (
                      workerRoles.length > 0 ? (
                        <>
                          {workerRoles.map(r => r.charAt(0).toUpperCase() + r.slice(1)).join(' & ')}
                          {maintenanceSpecs.length > 0 && (
                            <span style={{ color: 'var(--color-text-dim)', fontWeight: 400 }}>
                              {' · '}{maintenanceSpecs.join(', ')}
                            </span>
                          )}
                        </>
                      ) : (
                        <span style={{ color: '#f85149' }}>No roles selected</span>
                      )
                    ) : (
                      CANONICAL_ROLES.find(r => r.value === role)?.label || role
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setRoleEditMode(true)}
                  style={{
                    padding: '6px 14px', borderRadius: 'var(--radius-sm)',
                    background: 'none', border: '1px solid var(--color-border)',
                    color: 'var(--color-primary)', cursor: 'pointer', fontSize: 'var(--text-xs)', fontWeight: 700,
                  }}
                >
                  Edit
                </button>
              </div>
            )}

            {/* ── Phase 1039: Supervisory Role Info Block (OM) ──────────────────
                 Shown when role = manager. Explains the scope model directly
                 in the UI so the operator doesn't need to check docs. */}
            {role === 'manager' && (
              <div style={{
                background: 'rgba(99,102,241,0.05)',
                border: '1px solid rgba(99,102,241,0.18)',
                borderRadius: 'var(--radius-md)',
                padding: '14px 16px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                  <span style={{ fontSize: 16 }}>🏢</span>
                  <span style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--color-primary)' }}>
                    Operational Manager — Supervisory Scope Role
                  </span>
                </div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', lineHeight: 1.75, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <div>📋 <strong style={{ color: 'var(--color-text)' }}>What this role does:</strong> An Operational Manager oversees property operations at a managerial level — monitoring tasks, taking over stuck tasks, reassigning, and adding intervention notes. This is a supervisory scope role, not a worker lane.</div>
                  <div>🏠 <strong style={{ color: 'var(--color-text)' }}>One OM can supervise multiple villas.</strong> Assign this person to as many properties as needed — each assignment grants them managerial oversight of that villa.</div>
                  <div>👥 <strong style={{ color: 'var(--color-text)' }}>Multiple OMs can be assigned to the same villa.</strong> There is no single-OM limit per property. All assigned OMs have the same scope.</div>
                  <div>🚫 <strong style={{ color: 'var(--color-text)' }}>Primary / Backup does not apply to OM.</strong> That model is for worker lanes (cleaning, maintenance, check-in/out) only. OMs are not in a worker lane and are never ranked as Primary or Backup.</div>
                  <div>👤 <strong style={{ color: 'var(--color-text)' }}>The name chips on each villa row</strong> show the Operational Managers already assigned to supervise that property. Checking the box below assigns this person as an additional supervisor.</div>
                </div>
              </div>
            )}

            {/* Phase 1021-C: Linked Owner Profile — read-only summary (editable on Owners side) */}
            {role === 'owner' && (
              <div>
                <div style={sectionHeadStyle}>Linked Owner Profile</div>
                <div style={{
                  padding: 'var(--space-4)',
                  background: 'var(--color-surface-2)',
                  border: `1px solid ${
                    linkedOwner === 'loading' ? 'var(--color-border)'
                    : linkedOwner ? 'rgba(74,124,89,0.35)'
                    : 'rgba(181,110,69,0.35)'
                  }`,
                  borderRadius: 'var(--radius-md)',
                }}>
                  {linkedOwner === 'loading' && (
                    <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Loading…</div>
                  )}
                  {linkedOwner === null && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 14 }}>⚠️</span>
                        <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'rgba(181,110,69,1)' }}>
                          No owner profile linked yet
                        </span>
                      </div>
                      <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', lineHeight: 1.6 }}>
                        This user has the Owner role but is not yet linked to a business owner profile.
                        Property ownership, financial records, and portal access are managed through the owner profile.
                      </div>
                      <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                        {/* Phase 1021-C fix: carry full user context so Owners page opens create/link flow immediately */}
                        <a
                          href={`/admin/owners?${new URLSearchParams({
                            linkUserId: rawUserId,
                            linkName: fullName || displayName || '',
                            linkEmail: email || '',
                            linkPhone: phoneNumber ? `${phoneCode}${phoneNumber}`.trim() : '',
                            linkPropertyIds: assignedProperties.join(','),
                          }).toString()}`}
                          style={{
                            display: 'inline-block', padding: '7px 14px',
                            background: 'var(--color-primary)', color: '#fff',
                            borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)',
                            fontWeight: 600, textDecoration: 'none',
                          }}
                        >
                          Create or Link Owner Profile →
                        </a>
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--color-text-faint)', fontStyle: 'italic' }}>
                        The Owners section will open with this user's details pre-filled. Portal access and property ownership are managed from there.
                      </div>
                    </div>
                  )}
                  {linkedOwner && linkedOwner !== 'loading' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 14 }}>✓</span>
                        <span style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--color-ok, #4A7C59)' }}>
                          {linkedOwner.name}
                        </span>
                        {linkedOwner.email && (
                          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                            · {linkedOwner.email}
                          </span>
                        )}
                      </div>
                      {linkedOwner.property_ids && linkedOwner.property_ids.length > 0 && (
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                          Owns {linkedOwner.property_ids.length} propert{linkedOwner.property_ids.length === 1 ? 'y' : 'ies'}
                        </div>
                      )}
                      <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center', flexWrap: 'wrap' }}>
                        <a
                          href="/admin/owners"
                          style={{
                            display: 'inline-block', padding: '5px 12px',
                            background: 'var(--color-surface)', color: 'var(--color-primary)',
                            border: '1px solid var(--color-primary)',
                            borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)',
                            fontWeight: 600, textDecoration: 'none',
                          }}
                        >
                          Open in Owners →
                        </a>
                        <span style={{ fontSize: 11, color: 'var(--color-text-faint)', fontStyle: 'italic' }}>
                          Portal access and property ownership are managed from the Owners section.
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            <div>
              {/* ── Assigned Properties section head with help button ── */}
              <div style={{ ...sectionHeadStyle, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>Assigned Properties</span>
                {assignedProperties.length > 0 && (
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-primary)', fontWeight: 400 }}>
                    {assignedProperties.length} assigned
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => setShowPBHelp(v => !v)}
                  title="What is Primary / Backup?"
                  style={{
                    marginLeft: 'auto', width: 20, height: 20, borderRadius: '50%',
                    background: showPBHelp ? 'var(--color-primary)' : 'var(--color-surface-2)',
                    border: '1px solid var(--color-border)', color: showPBHelp ? '#fff' : 'var(--color-text-dim)',
                    cursor: 'pointer', fontSize: 11, fontWeight: 700, display: 'flex',
                    alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                  }}
                >?
                </button>
              </div>

              {/* Phase 1039: Context note for supervisory property rows */}
              {(role === 'manager' || role === 'admin') && (
                <div style={{
                  fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)',
                  padding: '8px 12px', marginBottom: 4,
                  background: 'rgba(99,102,241,0.04)',
                  border: '1px solid rgba(99,102,241,0.1)',
                  borderRadius: 'var(--radius-sm)', lineHeight: 1.6,
                }}>
                  <strong style={{ color: 'var(--color-text)' }}>Supervisory assignment:</strong> Checking a villa grants this person managerial scope over that property. The chips on each row show other supervisors already assigned. Multiple supervisors per villa is normal and expected.
                </div>
              )}

              {/* ── Primary/Backup Help Panel ── */}
              {showPBHelp && (
                <div style={{
                  background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.2)',
                  borderRadius: 'var(--radius-md)', padding: '14px 16px', marginBottom: 'var(--space-4)',
                  fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', lineHeight: 1.7,
                }}>
                  <div style={{ fontWeight: 700, color: 'var(--color-text)', marginBottom: 8, fontSize: 'var(--text-sm)' }}>
                    Primary &amp; Backup — How it works
                  </div>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <tbody>
                      {[
                        ['⭐ Primary', 'The main person responsible for this type of work at this property. Receives all auto-generated tasks from bookings.'],
                        ['🔵 Backup', 'A standby person. Does not receive tasks automatically. Enters the flow only if the Primary is removed.'],
                        ['🔄 When Backup becomes Primary', 'If the Primary is removed, the first Backup is automatically promoted. Their PENDING tasks transfer. ACKNOWLEDGED tasks stay with the original worker.'],
                        ['🚫 What does NOT happen automatically', 'ACKNOWLEDGED and IN_PROGRESS tasks never move automatically. They stay with the original worker until an admin decides.'],
                        ['📋 What admin should expect', 'A confirmation screen appears before any primary removal. Acknowledged tasks that need action will be listed clearly.'],
                      ].map(([title, desc]) => (
                        <tr key={title} style={{ verticalAlign: 'top' }}>
                          <td style={{ fontWeight: 700, paddingRight: 12, paddingBottom: 8, whiteSpace: 'nowrap', color: 'var(--color-text)', width: 220 }}>{title}</td>
                          <td style={{ paddingBottom: 8 }}>{desc}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {availableProperties.length === 0 ? (
                <div style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>No properties found.</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {availableProperties.map(p => {
                    const assigned = assignedProperties.includes(p.id);
                    const laneInfo = propertyLaneData[p.id];
                    const isSupervisory = role === 'manager' || role === 'admin' || role === 'owner';

                    // ── Supervisory-scope property rows ─────────────────────────
                    // For manager / admin / owner: show ALL assigned supervisors
                    // as name chips. Show first 2, then "+N more" overflow chip.
                    if (isSupervisory) {
                      // ALL supervisors for this property (backend already deduplicates)
                      const allSupervisors: { user_id: string; display_name: string; role: string }[] =
                        laneInfo?.supervisors || [];
                      const CHIP_LIMIT = 2;
                      const visibleSupervisors = allSupervisors.slice(0, CHIP_LIMIT);
                      const overflowCount = allSupervisors.length - CHIP_LIMIT;

                      return (
                        <div key={p.id} style={{
                          display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
                          background: assigned ? 'rgba(99,102,241,0.06)' : 'var(--color-surface-2)',
                          border: `1px solid ${assigned ? 'var(--color-primary)' : 'var(--color-border)'}`,
                          borderRadius: 'var(--radius-sm)', transition: 'all 0.15s',
                        }}>
                          <input
                            type="checkbox"
                            checked={assigned}
                            onChange={() =>
                              setAssignedProperties(prev =>
                                prev.includes(p.id) ? prev.filter(x => x !== p.id) : [...prev, p.id]
                              )
                            }
                            style={{ accentColor: 'var(--color-primary)', flexShrink: 0 }}
                          />

                          <span style={{ flex: 1, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{p.name}</span>

                          {/* All supervisors chip strip — max 2 visible + overflow */}
                          <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'nowrap' }}>
                            {visibleSupervisors.map((s: any) => (
                              <span key={s.user_id} title={`${s.role}: ${s.display_name}`} style={{
                                fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 99,
                                background: s.user_id === rawUserId
                                  ? 'rgba(99,102,241,0.15)' : 'rgba(180,130,60,0.12)',
                                color: s.user_id === rawUserId ? 'var(--color-primary)' : '#c8954a',
                                border: `1px solid ${s.user_id === rawUserId ? 'rgba(99,102,241,0.3)' : 'rgba(180,130,60,0.25)'}`,
                                whiteSpace: 'nowrap',
                              }}>
                                👤 {s.display_name}
                              </span>
                            ))}
                            {overflowCount > 0 && (
                              <span title={allSupervisors.slice(CHIP_LIMIT).map((s: any) => s.display_name).join(', ')} style={{
                                fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 99,
                                background: 'rgba(100,100,100,0.1)', color: 'var(--color-text-dim)',
                                border: '1px solid var(--color-border)', whiteSpace: 'nowrap',
                                cursor: 'help',
                              }}>
                                +{overflowCount}
                              </span>
                            )}
                            {allSupervisors.length === 0 && !assigned && (
                              <span style={{
                                fontSize: 10, fontWeight: 500, padding: '2px 8px', borderRadius: 99,
                                background: 'rgba(63,185,80,0.08)', color: '#3fb950',
                                border: '1px solid rgba(63,185,80,0.2)', whiteSpace: 'nowrap',
                              }}>No supervisor yet</span>
                            )}
                          </div>
                        </div>
                      );
                    }

                    // ── Worker lane property rows ────────────────────────────────
                    // For workers: show Primary / Backup / Will be Primary as before.
                    let thisPriority = 1;
                    let laneCount = 0;
                    if (laneInfo?.lanes) {
                      for (const workers of Object.values(laneInfo.lanes) as any[][]) {
                        laneCount += workers.length;
                        const found = workers.find((w: any) => w.user_id === rawUserId);
                        if (found) thisPriority = found.priority;
                      }
                    }
                    const isCurrentPrimary = assigned && thisPriority === 1;
                    const backupNum = assigned && thisPriority > 1 ? thisPriority - 1 : null;
                    const wouldBePrimary = !assigned && laneCount === 0;
                    const wouldBeBackup = !assigned && laneCount > 0;

                    return (
                      <div key={p.id} style={{
                        display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
                        background: assigned ? 'rgba(99,102,241,0.06)' : 'var(--color-surface-2)',
                        border: `1px solid ${assigned ? 'var(--color-primary)' : 'var(--color-border)'}`,
                        borderRadius: 'var(--radius-sm)', transition: 'all 0.15s',
                      }}>
                        <input
                          type="checkbox"
                          checked={assigned}
                          onChange={async () => {
                            if (assigned && isCurrentPrimary) {
                              // Phase 1030: Show baton-transfer preview before removing primary
                              setBatonLoading(true);
                              try {
                                const preview = await apiFetch<any>(`/staff/assignments/${encodeURIComponent(rawUserId)}/${encodeURIComponent(p.id)}/removal-preview`);
                                setBatonPreview({ ...preview, property_name: p.name });
                              } catch {
                                // Fallback: just proceed with toggle
                                setAssignedProperties(prev => prev.filter(x => x !== p.id));
                              } finally {
                                setBatonLoading(false);
                              }
                            } else {
                              setAssignedProperties(prev =>
                                prev.includes(p.id) ? prev.filter(x => x !== p.id) : [...prev, p.id]
                              );
                            }
                          }}
                          disabled={batonLoading}
                          style={{ accentColor: 'var(--color-primary)', flexShrink: 0 }}
                        />

                        <span style={{ flex: 1, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{p.name}</span>

                        {/* Primary/Backup badge for assigned worker properties */}
                        {assigned && (
                          <span style={{
                            fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 99,
                            background: isCurrentPrimary ? 'rgba(99,102,241,0.15)' : 'rgba(88,166,255,0.12)',
                            color: isCurrentPrimary ? 'var(--color-primary)' : '#58a6ff',
                            border: `1px solid ${isCurrentPrimary ? 'rgba(99,102,241,0.3)' : 'rgba(88,166,255,0.25)'}`,
                            whiteSpace: 'nowrap',
                          }}>
                            {isCurrentPrimary ? '⭐ Primary' : `🔵 Backup ${backupNum}`}
                          </span>
                        )}

                        {/* Preview badge for unassigned properties */}
                        {!assigned && wouldBePrimary && (
                          <span style={{
                            fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 99,
                            background: 'rgba(63,185,80,0.1)', color: '#3fb950',
                            border: '1px solid rgba(63,185,80,0.25)', whiteSpace: 'nowrap',
                          }}>→ Will be Primary</span>
                        )}
                        {!assigned && wouldBeBackup && (
                          <span style={{
                            fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 99,
                            background: 'rgba(88,166,255,0.08)', color: '#58a6ff',
                            border: '1px solid rgba(88,166,255,0.2)', whiteSpace: 'nowrap',
                          }}>→ Will be Backup</span>
                        )}
                      </div>
                    );
                  })}
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

            {/* Unified Access & Onboarding Card */}
            <div style={sectionHeadStyle}>{t('admin.worker_onboarding_access')}</div>
            
            <div style={{
              background: 'var(--color-surface-2)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border)',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              marginBottom: 'var(--space-4)'
            }}>
              {/* TOP HALF: Actions */}
              <div style={{ padding: 'var(--space-4)' }}>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {authStatus?.force_reset === false ? t('admin.account_management') : t('admin.send_access_link_title')}
                </div>
                
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', margin: '0 0 var(--space-4) 0', lineHeight: 1.4 }}>
                  {authStatus?.force_reset === false
                    ? t('admin.account_management_desc')
                    : t('admin.send_access_link_desc')}
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
                          const resp = await apiFetch<any>(`/admin/staff/${rawUserId}/resend-access`, {
                            method: 'POST',
                            body: JSON.stringify({ channel: 'email', frontend_url: window.location.origin }),
                          });
                          setResendResult(resp);
                          await fetchAuthStatus();
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
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                    <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                      <div style={{ flex: 1, minWidth: 160, maxWidth: 300 }}>
                        <label style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Delivery Channel</label>
                        <select
                          style={{ ...inputStyle, cursor: 'pointer', width: '100%' }}
                          value={resendChannel}
                          onChange={e => setResendChannel(e.target.value)}
                        >
                          <option value="email">Email {email ? `(${email})` : ''}</option>
                          {whatsapp && <option value="whatsapp">WhatsApp ({whatsapp})</option>}
                          {sms && <option value="sms">SMS / Phone ({sms})</option>}
                          {telegram && <option value="telegram">Telegram ({telegram})</option>}
                          {line && <option value="line">LINE ({line})</option>}
                        </select>
                      </div>
                      
                      <button
                        disabled={resendSending || !!authStatus?.identity_mismatch}
                        onClick={async () => {
                          setResendSending(true);
                          setResendResult(null);
                          try {
                            const resp = await apiFetch<any>(`/admin/staff/${rawUserId}/resend-access`, {
                              method: 'POST',
                              body: JSON.stringify({ channel: resendChannel, frontend_url: window.location.origin }),
                            });
                            setResendResult(resp);
                            await fetchAuthStatus();
                          } catch (err: any) {
                            setResendResult({ status: 'error', message: err.message || 'Failed to send' });
                          } finally {
                            setResendSending(false);
                          }
                        }}
                        style={{
                          padding: '10px 20px', borderRadius: 'var(--radius-sm)',
                          background: 'var(--color-surface)', color: 'var(--color-text)', border: '1px solid var(--color-border)',
                          cursor: resendSending ? 'not-allowed' : 'pointer', fontWeight: 600,
                          fontSize: 'var(--text-sm)', opacity: resendSending ? 0.6 : 1,
                          minHeight: 40, whiteSpace: 'nowrap' as const,
                        }}
                      >
                        {resendSending ? 'Sending...' : 'Generate Link'}
                      </button>

                      {email && (
                        <button
                          type="button"
                          disabled={resendSending || !!authStatus?.identity_mismatch}
                          onClick={async () => {
                            setResendSending(true);
                            setResendResult(null);
                            try {
                              const resp = await apiFetch<any>(`/admin/staff/${rawUserId}/resend-access`, {
                                method: 'POST',
                                body: JSON.stringify({ channel: 'email', frontend_url: window.location.origin }),
                              });
                              setResendResult(resp);
                              if (resp.status === 'sent' && resp.delivery_method === 'email_invite') {
                                // Supabase sent the invite email directly to the worker.
                                // No action_link is returned or needed — the worker gets it in their inbox.
                              } else if (resp.status === 'sent' && resp.magic_link) {
                                // Fallback: magic link resent via email — open mailto draft
                                window.location.href = getAccessMailto(language, email, resp.magic_link);
                              } else if (resp.status === 'link_generated' && resp.magic_link) {
                                window.location.href = getAccessMailto(language, email, resp.magic_link);
                              } else if (!resp.error && resp.status !== 'error') {
                                console.warn('[Quick Send] unexpected response shape:', resp);
                              }
                              await fetchAuthStatus(); // refresh lifecycle pills
                            } catch (err: any) {
                              setResendResult({ status: 'error', message: err.message || 'Failed to generate link' });
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
                          {resendSending ? 'Generating Link...' : '✉ Quick Send by Email'}
                        </button>
                      )}
                    </div>
                    {email && <div style={{ fontSize: 11, color: 'var(--color-text-faint)' }}>Quick Send generates the link and directly opens your native mail client draft.</div>}
                  </div>
                )}

                {/* Phase 947d: Identity Mismatch Banner — full repair UX */}
                {authStatus?.identity_mismatch && (() => {
                  // Classify the mismatch for frontend messaging only.
                  // The backend has the authoritative edit-distance guard (> 3 = deep mismatch).
                  // For UX: if local parts are same or very similar → show repair button.
                  // If obviously different names → show manual investigation message only.
                  const authLocal = (authStatus.auth_email || '').split('@')[0].toLowerCase().trim();
                  const commLocal = (authStatus.comm_email || '').split('@')[0].toLowerCase().trim();
                  // Simple edit-distance heuristic for UI classification
                  const lenDiff = Math.abs(authLocal.length - commLocal.length);
                  const isRepairableCase = authLocal === commLocal || lenDiff <= 4;

                  const handleRepair = async () => {
                    if (!isRepairableCase) return;
                    setRepairLoading(true);
                    setRepairResult(null);
                    try {
                      const res = await apiFetch<any>(`/admin/staff/${encodeURIComponent(rawUserId)}/repair-email`, {
                        method: 'POST',
                        body: JSON.stringify({ confirmed: true }),
                      });
                      if (res.status === 'repaired') {
                        setRepairResult({ ok: true, message: `✓ Fixed: auth email updated to ${res.auth_email_after}. Refreshing status…` });
                        setTimeout(() => { fetchAuthStatus(); setRepairResult(null); }, 2000);
                      } else if (res.status === 'already_correct') {
                        setRepairResult({ ok: true, message: '✓ Already correct — no repair needed.' });
                        fetchAuthStatus();
                      } else {
                        setRepairResult({ ok: false, message: res.detail || 'Repair failed.' });
                      }
                    } catch {
                      setRepairResult({ ok: false, message: 'Request failed. Please try again.' });
                    } finally {
                      setRepairLoading(false);
                    }
                  };

                  return (
                    <div style={{
                      marginBottom: 'var(--space-3)',
                      padding: '10px 14px',
                      borderRadius: 'var(--radius-sm)',
                      background: 'rgba(196,91,74,0.07)',
                      border: '2px solid var(--color-alert, #C45B4A)',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                        <span style={{ fontSize: 14 }}>⚠️</span>
                        <span style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--color-alert, #C45B4A)' }}>
                          Identity Mismatch — Access Link Blocked
                        </span>
                      </div>

                      <div style={{ fontSize: 12, color: 'var(--color-text-dim)', lineHeight: 1.6 }}>
                        <div style={{ marginBottom: 4 }}>
                          {isRepairableCase
                            ? '⚠ The auth account email does not match the worker\'s contact email. This can be fixed automatically.'
                            : '🚫 The auth account appears to belong to a different person. This requires manual investigation.'}
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, fontFamily: 'monospace', fontSize: 11, marginBottom: 8 }}>
                          <span><span style={{ color: 'var(--color-alert)' }}>Auth account email:</span> {authStatus.auth_email}</span>
                          <span><span style={{ color: 'var(--color-ok, #4A7C59)' }}>Comm email (correct):</span> {authStatus.comm_email}</span>
                        </div>

                        {isRepairableCase ? (
                          <div>
                            <div style={{ marginBottom: 6, fontSize: 11 }}>
                              <strong>What to do:</strong> Click "Fix Auth Email" to update the Supabase auth account email from
                              <code style={{ margin: '0 4px', background: 'rgba(0,0,0,0.08)', padding: '1px 4px', borderRadius: 3 }}>{authStatus.auth_email}</code>
                              to
                              <code style={{ margin: '0 4px', background: 'rgba(0,0,0,0.08)', padding: '1px 4px', borderRadius: 3 }}>{authStatus.comm_email}</code>.
                              The worker\'s account ID and permissions stay unchanged.
                            </div>
                            {repairResult && (
                              <div style={{ marginBottom: 8, padding: '6px 10px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                                background: repairResult.ok ? 'rgba(74,124,89,0.1)' : 'rgba(196,91,74,0.1)',
                                color: repairResult.ok ? 'var(--color-ok)' : 'var(--color-alert)',
                              }}>
                                {repairResult.message}
                              </div>
                            )}
                            <button
                              onClick={handleRepair}
                              disabled={repairLoading}
                              style={{
                                padding: '6px 14px', borderRadius: 'var(--radius-sm)',
                                background: repairLoading ? 'var(--color-surface-3)' : 'var(--color-ok, #4A7C59)',
                                border: 'none', color: '#fff', fontWeight: 700, fontSize: 12,
                                cursor: repairLoading ? 'not-allowed' : 'pointer', opacity: repairLoading ? 0.6 : 1,
                              }}
                            >
                              {repairLoading ? 'Fixing…' : '🔧 Fix Auth Email'}
                            </button>
                          </div>
                        ) : (
                          <div style={{ fontSize: 11, opacity: 0.8 }}>
                            <strong>What to do:</strong> This is a deep identity mismatch (different person linked).
                            A system administrator must manually inspect and re-point the <code>tenant_permissions.user_id</code> FK to the correct auth account.
                            The automatic repair tool cannot safely resolve this case.
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })()}

                {resendResult && (
                  <div style={{
                    marginTop: 'var(--space-3)', padding: 'var(--space-3)',
                    borderRadius: 'var(--radius-sm)',
                    background: resendResult.status === 'error' ? 'rgba(196,91,74,0.1)' : 'rgba(74,124,89,0.1)',
                    border: `1px solid ${resendResult.status === 'error' ? 'var(--color-alert)' : 'var(--color-ok, #4A7C59)'}`,
                    fontSize: 'var(--text-sm)',
                    color: resendResult.status === 'error' ? 'var(--color-alert)' : 'var(--color-ok, #4A7C59)',
                  }}>
                    {resendResult.status === 'sent' && resendResult.delivery_method === 'email_invite' && (
                      <span>✓ Invite email sent by Supabase directly to <strong>{resendResult.email || email}</strong>. The worker will receive it in their inbox.</span>
                    )}
                    {resendResult.status === 'sent' && resendResult.delivery_method === 'magic_link_resent' && (
                      <span>✓ Access link resent. Mail client draft opened.</span>
                    )}
                    {resendResult.status === 'sent' && !resendResult.delivery_method && '✓ Access link sent via email.'}
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

              {/* BOTTOM HALF: Lifecycle Tracker */}
              {(() => {
                // Phase 947d: If status load explicitly failed, show error — never silent grey
                if (statusLoadFailed) {
                  return (
                    <div style={{ padding: '12px 16px', borderTop: '1px solid var(--color-border)', background: 'var(--color-surface-1)' }}>
                      <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--color-text-faint)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        {t('admin.activation_lifecycle')}
                      </div>
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: 8,
                        padding: '8px 12px', borderRadius: 'var(--radius-sm)',
                        background: 'rgba(181,110,69,0.08)', border: '1px solid rgba(181,110,69,0.3)',
                      }}>
                        <span style={{ fontSize: 13 }}>⚠</span>
                        <span style={{ fontSize: 11, color: 'var(--color-warn, #B56E45)', fontWeight: 600 }}>
                          Lifecycle status unavailable — backend returned an error.
                          Pills are hidden to avoid showing misleading data.
                        </span>
                        <button
                          onClick={fetchAuthStatus}
                          style={{ marginLeft: 'auto', padding: '3px 10px', fontSize: 11, background: 'none',
                            border: '1px solid var(--color-warn, #B56E45)', borderRadius: 4,
                            color: 'var(--color-warn, #B56E45)', cursor: 'pointer', fontWeight: 600, flexShrink: 0 }}
                        >
                          Retry
                        </button>
                      </div>
                    </div>
                  );
                }

                // Normal path — authStatus loaded successfully
                const isActivated = authStatus?.force_reset === false;
                const isOpened = !!authStatus?.access_link_opened_at || !!authStatus?.last_sign_in_at || isActivated;
                const isSent = !!authStatus?.access_link_sent_at || !!authStatus?.invited_at || isOpened;
                const isLastActive = isActivated && !!authStatus?.last_sign_in_at;
                
                return (
                  <div style={{ padding: '12px 16px', borderTop: '1px solid var(--color-border)', background: 'var(--color-surface-1)' }}>
                    <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--color-text-faint)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                      {t('admin.activation_lifecycle')}
                    </div>
                    
                    <div style={{ display: 'flex', width: '100%', gap: 'var(--space-2)' }}>
                      {/* Sent Pill */}
                      <div style={{ display: 'flex', flex: 1, flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: isSent ? 'rgba(74,124,89,0.1)' : 'var(--color-surface-3)', padding: '4px 10px', borderRadius: 100, border: `1px solid ${isSent ? 'rgba(74,124,89,0.3)' : 'var(--color-border)'}` }}>
                          <div style={{ width: 6, height: 6, borderRadius: '50%', background: isSent ? 'var(--color-ok)' : 'var(--color-text-faint)' }} />
                          <span style={{ fontSize: 11, fontWeight: 600, color: isSent ? 'var(--color-ok)' : 'var(--color-text-dim)', whiteSpace: 'nowrap' }}>
                            {t('admin.access_link_sent')}
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--color-text-dim)', textAlign: 'center', minHeight: 16 }}>
                          {authStatus?.access_link_sent_at ? (
                            <>{new Date(authStatus.access_link_sent_at).toLocaleDateString('en-GB', { month: 'short', day: 'numeric'})} <span style={{ opacity: 0.8 }}>{new Date(authStatus.access_link_sent_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit'})}</span></>
                          ) : '—'}
                        </div>
                      </div>

                      {/* Opened Pill */}
                      <div style={{ display: 'flex', flex: 1, flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: isOpened ? 'rgba(74,124,89,0.1)' : 'var(--color-surface-3)', padding: '4px 10px', borderRadius: 100, border: `1px solid ${isOpened ? 'rgba(74,124,89,0.3)' : 'var(--color-border)'}` }}>
                          <div style={{ width: 6, height: 6, borderRadius: '50%', background: isOpened ? 'var(--color-ok)' : 'var(--color-text-faint)' }} />
                          <span style={{ fontSize: 11, fontWeight: 600, color: isOpened ? 'var(--color-ok)' : 'var(--color-text-dim)', whiteSpace: 'nowrap' }}>
                            {t('admin.link_opened')}
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--color-text-dim)', textAlign: 'center', minHeight: 16 }}>
                          {authStatus?.access_link_opened_at ? (
                            <>{new Date(authStatus.access_link_opened_at).toLocaleDateString('en-GB', { month: 'short', day: 'numeric'})} <span style={{ opacity: 0.8 }}>{new Date(authStatus.access_link_opened_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit'})}</span></>
                          ) : '—'}
                        </div>
                      </div>

                      {/* Activated Pill */}
                      <div style={{ display: 'flex', flex: 1, flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: isActivated ? 'rgba(74,124,89,0.1)' : 'var(--color-surface-3)', padding: '4px 10px', borderRadius: 100, border: `1px solid ${isActivated ? 'rgba(74,124,89,0.3)' : 'var(--color-border)'}` }}>
                          <div style={{ width: 6, height: 6, borderRadius: '50%', background: isActivated ? 'var(--color-ok)' : 'var(--color-text-faint)' }} />
                          <span style={{ fontSize: 11, fontWeight: 600, color: isActivated ? 'var(--color-ok)' : 'var(--color-text-dim)', whiteSpace: 'nowrap' }}>
                            {t('admin.worker_activated')}
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--color-text-dim)', textAlign: 'center', minHeight: 16 }}>
                          {/* Activated typically does not have a timestamp */}
                          {isActivated ? '—' : '—'}
                        </div>
                      </div>

                      {/* Last Active Pill */}
                      <div style={{ display: 'flex', flex: 1, flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: isLastActive ? 'rgba(74,124,89,0.1)' : 'var(--color-surface-3)', padding: '4px 10px', borderRadius: 100, border: `1px solid ${isLastActive ? 'rgba(74,124,89,0.3)' : 'var(--color-border)'}` }}>
                          <div style={{ width: 6, height: 6, borderRadius: '50%', background: isLastActive ? 'var(--color-ok)' : 'var(--color-text-faint)' }} />
                          <span style={{ fontSize: 11, fontWeight: 600, color: isLastActive ? 'var(--color-ok)' : 'var(--color-text-dim)', whiteSpace: 'nowrap' }}>
                            {t('admin.active_session')}
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--color-text-dim)', textAlign: 'center', minHeight: 16 }}>
                          {authStatus?.last_sign_in_at ? (
                            <>{new Date(authStatus.last_sign_in_at).toLocaleDateString('en-GB', { month: 'short', day: 'numeric'})} <span style={{ opacity: 0.8 }}>{new Date(authStatus.last_sign_in_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit'})}</span></>
                          ) : '—'}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })()}
            </div>


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
                      <GregorianDateInput
                        value={idDocExpiry}
                        onChange={setIdDocExpiry}
                        style={{ ...inputStyle, flex: 1 }}
                        mode="expiry"
                      />
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
                      <GregorianDateInput
                        value={workPermitExpiry}
                        onChange={setWorkPermitExpiry}
                        style={{ ...inputStyle, flex: 1 }}
                        mode="expiry"
                      />
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

        {/* ── Tab 5: Delegated Authority (manager only) ──────────────────── */}
        {activeTab === 4 && role === 'manager' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>

            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--space-4)' }}>
              <div>
                <div style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--color-text)', marginBottom: 4 }}>
                  Delegated Authority
                </div>
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', lineHeight: 1.5 }}>
                  Manage what operational capabilities this manager can exercise on your behalf.
                  Only what you explicitly grant is active. Admin always retains full authority.
                </div>
              </div>
              <span style={{
                padding: '4px 12px', borderRadius: 9999,
                background: 'rgba(99,102,241,0.12)', color: 'var(--color-primary)',
                fontSize: 'var(--text-xs)', fontWeight: 700,
              }}>manager</span>
            </div>

            {capError && (
              <div style={{ background: 'rgba(248,81,73,0.1)', border: '1px solid rgba(248,81,73,0.3)', color: '#f85149', padding: '10px 16px', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-sm)' }}>
                {capError}
              </div>
            )}

            {capLoading ? (
              <div style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)', padding: 'var(--space-4)' }}>Loading capabilities…</div>
            ) : capGroups.length === 0 ? (
              <div style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)', padding: 'var(--space-4)' }}>
                No capabilities data available. Ensure this user has a manager record.
              </div>
            ) : (
              capGroups.map((group) => {
                const dirty = capDirty[group.group] ?? {};
                const isDirty = Object.keys(dirty).length > 0;
                const isPending = capPending === group.group;
                const isApplying = capApplying === group.group;

                // For each capability: use dirty value if present, else server-side granted
                const effectiveCaps = group.capabilities.map((cap) => ({
                  ...cap,
                  granted: group.group in capDirty && cap.key in dirty ? dirty[cap.key] : cap.granted,
                }));

                // Compute diff for confirm step
                const changedCaps = isPending
                  ? effectiveCaps.filter((cap) => {
                      const original = group.capabilities.find(c => c.key === cap.key)?.granted ?? false;
                      return cap.granted !== original;
                    })
                  : [];

                return (
                  <div key={group.group} style={{
                    border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)',
                    overflow: 'hidden',
                  }}>
                    {/* Section header */}
                    <div style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '12px 16px',
                      background: 'var(--color-surface-2)',
                      borderBottom: '1px solid var(--color-border)',
                    }}>
                      <span style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--color-text)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                        {group.label}
                      </span>
                      <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
                        {isDirty && !isPending && (
                          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-warn, #B56E45)', fontWeight: 600 }}>unsaved changes</span>
                        )}
                        {!isPending && (
                          <button
                            disabled={!isDirty || isApplying}
                            onClick={() => setCapPending(group.group)}
                            style={{
                              padding: '5px 14px', borderRadius: 'var(--radius-sm)',
                              background: isDirty ? 'var(--color-primary)' : 'var(--color-surface)',
                              color: isDirty ? '#fff' : 'var(--color-text-faint)',
                              border: `1px solid ${isDirty ? 'var(--color-primary)' : 'var(--color-border)'}`,
                              fontSize: 'var(--text-xs)', fontWeight: 700,
                              cursor: isDirty ? 'pointer' : 'not-allowed',
                              transition: 'all 0.15s',
                            }}
                          >
                            Apply
                          </button>
                        )}
                        {isPending && (
                          <>
                            <button
                              onClick={() => setCapPending(null)}
                              style={{
                                padding: '5px 12px', borderRadius: 'var(--radius-sm)',
                                background: 'none', border: '1px solid var(--color-border)',
                                fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', cursor: 'pointer',
                              }}
                            >Cancel</button>
                            <button
                              disabled={isApplying}
                              onClick={async () => {
                                setCapApplying(group.group);
                                setCapPending(null);
                                setCapError(null);
                                // Build the full section payload from effective caps
                                const payload: Record<string, boolean> = {};
                                effectiveCaps.forEach(c => { payload[c.key] = c.granted; });
                                try {
                                  const res = await apiFetch(`/admin/managers/${rawUserId}/capabilities/section`, {
                                    method: 'PATCH',
                                    body: JSON.stringify({ section: group.group, capabilities: payload }),
                                  });
                                  if (res?.data) {
                                    // Refresh capability groups from server response
                                    const refreshed = await apiFetch(`/admin/managers/${rawUserId}/capabilities`);
                                    if (refreshed?.data?.grouped_capabilities) {
                                      setCapGroups(refreshed.data.grouped_capabilities);
                                    }
                                    // Refresh history
                                    const histRefresh = await apiFetch(`/admin/managers/${rawUserId}/capabilities/history?limit=5`);
                                    if (histRefresh?.data?.events) setCapHistory(histRefresh.data.events);
                                    // Clear dirty for this group
                                    setCapDirty(prev => { const n = { ...prev }; delete n[group.group]; return n; });
                                  }
                                } catch {
                                  setCapError(`Failed to save ${group.label} capabilities. Please try again.`);
                                } finally {
                                  setCapApplying(null);
                                }
                              }}
                              style={{
                                padding: '5px 14px', borderRadius: 'var(--radius-sm)',
                                background: isApplying ? 'var(--color-border)' : '#2da44e',
                                color: '#fff', border: 'none',
                                fontSize: 'var(--text-xs)', fontWeight: 700,
                                cursor: isApplying ? 'not-allowed' : 'pointer',
                                transition: 'all 0.15s',
                              }}
                            >
                              {isApplying ? 'Saving…' : 'Confirm'}
                            </button>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Confirm diff preview */}
                    {isPending && changedCaps.length > 0 && (
                      <div style={{
                        background: 'rgba(99,102,241,0.06)', borderBottom: '1px solid var(--color-border)',
                        padding: '10px 16px',
                      }}>
                        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-dim)', marginBottom: 6 }}>
                          Changes to apply:
                        </div>
                        {changedCaps.map(c => (
                          <div key={c.key} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 'var(--text-xs)', marginBottom: 2 }}>
                            <span style={{
                              padding: '2px 8px', borderRadius: 9999, fontWeight: 700,
                              background: c.granted ? 'rgba(46,160,67,0.15)' : 'rgba(248,81,73,0.12)',
                              color: c.granted ? '#2ea843' : '#f85149',
                            }}>
                              {c.granted ? '+ Grant' : '− Revoke'}
                            </span>
                            <span style={{ color: 'var(--color-text)' }}>{c.label}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Capability toggles */}
                    <div style={{ padding: 0 }}>
                      {effectiveCaps.map((cap, idx) => (
                        <div key={cap.key}>
                          <div
                            style={{
                              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                              padding: '12px 16px',
                              borderBottom: (idx < effectiveCaps.length - 1 || capInfoOpen === cap.key) ? '1px solid var(--color-border)' : 'none',
                            opacity: isPending ? 0.7 : 1,
                            transition: 'background 0.1s',
                            cursor: isPending ? 'default' : 'pointer',
                          }}
                          onClick={() => {
                            if (isPending || isApplying) return;
                            const currentVal = cap.granted;
                            setCapDirty(prev => ({
                              ...prev,
                              [group.group]: {
                                ...prev[group.group],
                                [cap.key]: !currentVal,
                              },
                            }));
                          }}
                        >
                          {/* Left: label + power_type badge */}
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1, minWidth: 0 }}>
                            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)', lineHeight: 1.4 }}>
                              {cap.label}
                            </span>
                            {cap.power_type && (
                              <span style={{
                                display: 'inline-block', fontSize: 10, fontWeight: 700,
                                padding: '1px 6px', borderRadius: 4, letterSpacing: '0.04em',
                                alignSelf: 'flex-start',
                                textTransform: 'uppercase',
                                ...(cap.power_type === 'view' ? {
                                  background: 'rgba(56,139,253,0.12)', color: '#388bfd',
                                } : cap.power_type === 'approve' ? {
                                  background: 'rgba(210,153,34,0.14)', color: '#d29922',
                                } : cap.power_type === 'edit' ? {
                                  background: 'rgba(99,102,241,0.12)', color: 'var(--color-primary)',
                                } : /* execute */ {
                                  background: 'rgba(248,81,73,0.1)', color: '#f85149',
                                }),
                              }}>
                                {cap.power_type}
                              </span>
                            )}
                          </div>

                          {/* Right: ⓘ info icon + toggle */}
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                            {/* Info button — stops toggle click from propagating */}
                            {cap.description && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setCapInfoOpen(prev => prev === cap.key ? null : cap.key);
                                }}
                                title="What does this permission mean?"
                                style={{
                                  background: 'none', border: 'none', cursor: 'pointer',
                                  color: capInfoOpen === cap.key ? 'var(--color-primary)' : 'var(--color-text-faint)',
                                  fontSize: 15, lineHeight: 1, padding: '2px 4px',
                                  borderRadius: 4,
                                  transition: 'color 0.15s',
                                }}
                              >ⓘ</button>
                            )}

                            {/* Toggle switch */}
                            <div style={{
                              width: 40, height: 22, borderRadius: 11,
                              background: cap.granted ? 'var(--color-primary)' : 'var(--color-border)',
                              position: 'relative', transition: 'background 0.2s', flexShrink: 0,
                            }}>
                              <div style={{
                                width: 16, height: 16, borderRadius: '50%', background: '#fff',
                                position: 'absolute', top: 3,
                                left: cap.granted ? 21 : 3,
                                transition: 'left 0.2s',
                                boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                              }} />
                            </div>
                          </div>
                        </div>

                        {/* Info popover — appears inline below the row when open */}
                        {capInfoOpen === cap.key && cap.description && (
                          <div style={{
                            background: 'var(--color-surface-2)',
                            border: '1px solid var(--color-border)',
                            borderTop: 'none',
                            padding: '12px 16px',
                            fontSize: 'var(--text-xs)',
                            color: 'var(--color-text-dim)',
                            lineHeight: 1.6,
                          }}>
                            {cap.description}
                          </div>
                        )}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })
            )}

            {/* Audit trail footer */}
            {capHistory.length > 0 && (
              <div style={{
                borderTop: '1px solid var(--color-border)',
                paddingTop: 'var(--space-4)',
              }}>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                  Recent Capability Changes
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                  {capHistory.map((ev, i) => {
                    const isGrant = ev.action === 'MANAGER_CAPABILITY_GRANTED';
                    
                    // Fallback map for rows written before capability_label was saved in audit payloads
                    const fallbackMap: Record<string, string> = {
                      'booking_flag_vip': 'Flag bookings as VIP',
                      'booking_flag_dispute': 'Flag bookings as disputed',
                      'booking_approve_early_co': 'Approve early checkout',
                      'booking_approve_self_ci': 'Approve self check-in',
                      'booking_create_manual': 'Create manual bookings',
                      'booking_exception_notes': 'Add operator notes to bookings',
                      'staff_view_roster': 'View staff roster & contact details',
                      'staff_manage_assignments': 'Assign / unassign staff to properties',
                      'staff_approve_availability': 'Approve / reject availability requests',
                      'staff_create_worker': 'Create new worker accounts (invite)',
                      'staff_deactivate_worker': 'Archive / deactivate worker accounts',
                      'ops_task_takeover': 'Take over worker tasks',
                      'ops_task_reassign': 'Reassign tasks between workers',
                      'ops_schedule_tasks': 'Create ad-hoc operational tasks',
                      'ops_view_cleaning_reports': 'View cleaning completion reports & photos',
                      'ops_set_property_status': 'Set property operational status',
                      'settlement_view_deposits': 'View deposit collection records',
                      'settlement_finalize': 'Finalize checkout settlements',
                      'settlement_approve_deductions': 'Approve damage deductions',
                      'settlement_void': 'Void a finalized settlement',
                      'financial_view_revenue': 'View revenue & occupancy metrics',
                      'financial_view_owner_stmt': 'View owner statements',
                      'financial_export': 'Export financial data',
                      // Phase 862 legacy coarse keys
                      'financial': 'Full Financial Suite (Legacy)',
                      'staffing': 'Full Staffing Suite (Legacy)',
                      'properties': 'Full Properties Suite (Legacy)',
                      'bookings': 'Full Bookings Suite (Legacy)',
                      'maintenance': 'Full Maintenance Suite (Legacy)',
                      'settings': 'Tenant Settings (Legacy)',
                      'intake': 'Property Intake (Legacy)',
                    };
                    
                    // Phase 1023-C: prefer human label stored in payload, fall back to stable map, then raw key
                    const rawKey = ev.payload?.capability ?? '';
                    const capLabel = ev.payload?.capability_label ?? fallbackMap[rawKey] ?? rawKey;
                    
                    const when = ev.occurred_at ? new Date(ev.occurred_at).toLocaleDateString('en-GB', { month: 'short', day: 'numeric', year: 'numeric' }) : '';
                    return (
                      <div key={ev.id ?? i} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                        <span style={{
                          padding: '2px 7px', borderRadius: 9999, fontWeight: 700, flexShrink: 0,
                          background: isGrant ? 'rgba(46,160,67,0.12)' : 'rgba(248,81,73,0.1)',
                          color: isGrant ? '#2ea843' : '#f85149',
                        }}>
                          {isGrant ? 'Granted' : 'Revoked'}
                        </span>
                        <span style={{ color: 'var(--color-text)' }}>{capLabel}</span>
                        <span style={{ marginLeft: 'auto', whiteSpace: 'nowrap' }}>{when}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>


      {/* ── Phase 1030: Baton-Transfer Confirmation Modal ─────────────────── */}
      {batonPreview && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 1050,
          background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24,
        }}>
          <div style={{
            background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border)', padding: '28px 32px',
            maxWidth: 520, width: '100%', boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
              <span style={{ fontSize: 22 }}>⚠️</span>
              <div>
                <div style={{ fontWeight: 700, fontSize: 'var(--text-base)', color: 'var(--color-text)' }}>
                  Remove Primary Worker
                </div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                  {batonPreview.property_name}
                </div>
              </div>
            </div>

            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', lineHeight: 1.7, marginBottom: 20 }}>
              <p style={{ margin: '0 0 12px 0' }}>
                <strong style={{ color: 'var(--color-text)' }}>{batonPreview.removed_name}</strong> is currently the{' '}
                <span style={{ color: 'var(--color-primary)', fontWeight: 700 }}>Primary</span> worker for this property.
              </p>

              {batonPreview.new_primary_name ? (
                <div style={{
                  background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)',
                  borderRadius: 'var(--radius-sm)', padding: '12px 14px', marginBottom: 12,
                }}>
                  <div style={{ fontWeight: 700, color: 'var(--color-text)', marginBottom: 6 }}>If you continue:</div>
                  <ul style={{ margin: 0, paddingLeft: 20, display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <li>
                      <strong>{batonPreview.new_primary_name}</strong> will become the new Primary.
                    </li>
                    {batonPreview.pending_tasks_count > 0 && (
                      <li>
                        <strong style={{ color: '#3fb950' }}>{batonPreview.pending_tasks_count} PENDING task{batonPreview.pending_tasks_count !== 1 ? 's' : ''}</strong>{' '}
                        will automatically transfer to {batonPreview.new_primary_name}.
                      </li>
                    )}
                    {batonPreview.acknowledged_tasks_count > 0 && (
                      <li>
                        <strong style={{ color: '#d29922' }}>{batonPreview.acknowledged_tasks_count} ACKNOWLEDGED task{batonPreview.acknowledged_tasks_count !== 1 ? 's' : ''}</strong>{' '}
                        will <strong>stay with {batonPreview.removed_name}</strong> and require manual reassignment.
                      </li>
                    )}
                    <li style={{ color: 'var(--color-text-faint)' }}>
                      IN_PROGRESS tasks are never moved automatically.
                    </li>
                  </ul>
                </div>
              ) : (
                <div style={{
                  background: 'rgba(210,153,34,0.08)', border: '1px solid rgba(210,153,34,0.3)',
                  borderRadius: 'var(--radius-sm)', padding: '12px 14px', marginBottom: 12, color: '#d29922',
                }}>
                  ⚠ No Backup exists for this property. After removal, future tasks will be <strong>unassigned</strong> and require manual assignment.
                </div>
              )}

              {batonPreview.acknowledged_tasks_count > 0 && (
                <div style={{
                  background: 'rgba(210,153,34,0.06)', border: '1px solid rgba(210,153,34,0.25)',
                  borderRadius: 'var(--radius-sm)', padding: '8px 12px',
                  fontSize: 'var(--text-xs)', color: '#d29922',
                }}>
                  <strong>Action required:</strong> After this transfer, visit the Tasks page and manually reassign the {batonPreview.acknowledged_tasks_count} acknowledged task(s) still assigned to {batonPreview.removed_name}.
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setBatonPreview(null)}
                style={{
                  padding: '9px 20px', borderRadius: 'var(--radius-sm)',
                  background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                  color: 'var(--color-text)', cursor: 'pointer', fontWeight: 600, fontSize: 'var(--text-sm)',
                }}
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  // Execute the removal by toggling the property off
                  setAssignedProperties(prev => prev.filter(x => x !== batonPreview.property_id));
                  setBatonPreview(null);
                }}
                style={{
                  padding: '9px 20px', borderRadius: 'var(--radius-sm)',
                  background: 'var(--color-alert, #C45B4A)', border: 'none',
                  color: '#fff', cursor: 'pointer', fontWeight: 700, fontSize: 'var(--text-sm)',
                  boxShadow: '0 2px 8px rgba(196,91,74,0.35)',
                }}
              >
                Confirm &amp; Transfer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Sticky footer ───────────────────────────────────────────────── */}
      <div style={{
        position: 'sticky', bottom: 0,
        background: 'var(--color-surface)', borderTop: '1px solid var(--color-border)',
        padding: 'var(--space-3) var(--space-5)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--space-3)',
      }}>
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          {activeTab > 0 && (
            <button onClick={() => setActiveTab((activeTab - 1) as 0 | 1 | 2 | 3 | 4)} style={{
              padding: '8px 18px', borderRadius: 'var(--radius-sm)',
              background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
              color: 'var(--color-text-dim)', cursor: 'pointer', fontSize: 'var(--text-sm)',
            }}>← Previous</button>
          )}
          {activeTab < maxTab && activeTab !== 4 && (
            <button onClick={() => setActiveTab((activeTab + 1) as 0 | 1 | 2 | 3 | 4)} style={{
              padding: '8px 18px', borderRadius: 'var(--radius-sm)',
              background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
              color: 'var(--color-text)', cursor: 'pointer', fontSize: 'var(--text-sm)',
            }}>Next →</button>
          )}
        </div>

        {/* Tab 4 (Delegated Authority) has its own section-level Apply/Confirm — no global save */}
        {activeTab !== 4 && (
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
        )}
      </div>
    </div>
  );
}
