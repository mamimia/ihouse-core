'use client';
/**
 * Phase 845 — Staff Onboarding Requests (Admin)
 * /admin/staff/requests
 *
 * Lists all pending worker onboarding requests.
 * Allows admin to generate new invite links and approve or reject submissions.
 */

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { apiFetch } from '@/lib/api';

const BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

// Temporary mailto email copy — language-aware (until Resend is wired)
const MAILTO_ONBOARDING: Record<string, { subject: string; body: (link: string) => string }> = {
  en: {
    subject: 'Complete your Domaniqo staff onboarding',
    body: (link) =>
      `Hello,\n\nWe would like to continue your staff onboarding with Domaniqo.\n\nPlease complete your onboarding form here:\n${link}\n\nThis link was prepared for your role and language selection.\n\nThank you,\nDomaniqo Team`,
  },
  th: {
    subject: 'กรอกแบบฟอร์มเริ่มต้นการทำงานกับ Domaniqo ให้เสร็จสมบูรณ์',
    body: (link) =>
      `สวัสดี,\n\nเราต้องการดำเนินการเริ่มต้นการทำงานกับ Domaniqo ของคุณต่อให้เรียบร้อย\n\nกรุณากรอกแบบฟอร์มที่นี่:\n${link}\n\nลิงก์นี้ถูกเตรียมไว้ตามบทบาทและภาษาที่เลือกให้คุณ\n\nขอบคุณ,\nทีมงาน Domaniqo`,
  },
  he: {
    subject: 'השלמת קליטת העובד שלך ב-Domaniqo',
    // RTL: prepend RLM mark so mail clients render the body RTL
    body: (link) =>
      `\u200Fשלום,\n\n\u200Fנשמח להמשיך את תהליך קליטת העובד שלך ב-Domaniqo.\n\n\u200Fאפשר להשלים את טופס הקליטה כאן:\n${link}\n\n\u200Fהקישור הוכן בהתאם לתפקיד ולשפה שנבחרו עבורך.\n\n\u200Fתודה,\n\u200Fצוות Domaniqo`,
  },
};

function getOnboardingMailto(lang: string, toEmail: string, link: string): string {
  const tpl = MAILTO_ONBOARDING[lang] ?? MAILTO_ONBOARDING.en;
  return `mailto:${encodeURIComponent(toEmail)}?subject=${encodeURIComponent(tpl.subject)}&body=${encodeURIComponent(tpl.body(link))}`;
}


type PendingRequest = {
  id: string;
  email: string;
  created_at: string;
  metadata?: {
    status?: string;
    intended_role?: string;
    display_name?: string;
    worker_data?: {
      full_name?: string;
      display_name?: string;
      phone?: string;
      emergency_contact?: string;
      photo_url?: string;
      worker_roles?: string[];
      language?: string;
      comm_preference?: Record<string, string>;
    }
  }
};

export default function PendingRequestsPage() {
  const router = useRouter();
  const [requests, setRequests] = useState<PendingRequest[]>([]);
  const [genLanguage, setGenLanguage] = useState('th');
  const [genAccountRole, setGenAccountRole] = useState('worker');
  const [genRoles, setGenRoles] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteGenerated, setInviteGenerated] = useState('');
  const [showQR, setShowQR] = useState(false);
  const [approvedLink, setApprovedLink] = useState<{ workerName: string; link: string; deliveryMethod?: string } | null>(null);
  const [generatedForEmail, setGeneratedForEmail] = useState(''); // email used when generating the invite
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [confirmingRejectId, setConfirmingRejectId] = useState<string | null>(null);
  const [approvalError, setApprovalError] = useState<{ id: string; message: string } | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiFetch<{ requests: PendingRequest[] }>('/admin/staff-onboarding');
      setRequests(data.requests || []);
    } catch { } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleGenerate = async (withQR: boolean = false) => {
    setShowQR(withQR);
    try {
      const data = await apiFetch<{ invite_url: string }>('/admin/staff-onboarding/invite', {
        method: 'POST',
        body: JSON.stringify({
          email: inviteEmail,
          intended_role: genAccountRole,
          intended_language: genLanguage,
          preselected_roles: genRoles
        })
      });
      const fullLink = `${window.location.host}${data.invite_url}`;
      const generated = `${window.location.protocol}//${fullLink}`;
      setInviteGenerated(generated);
      setGeneratedForEmail(inviteEmail.trim()); // remember email for Send by Email
      setInviteEmail(''); // clear input for next use
    } catch {
      alert('Network error or token expired. Try logging in again.');
    }
  };

  const handleApprove = async (id: string, metadata: any) => {
    const role = metadata?.intended_role || 'worker';
    // Phase 1026 Fix H3: manager intended_role must not carry over worker sub-roles.
    // The backend normalizes as well, but be explicit here to avoid any payload pollution.
    const workerRoles = (role === 'manager')
      ? []
      : (metadata?.worker_data?.worker_roles || []);
    const displayName = metadata?.worker_data?.full_name || metadata?.display_name || 'Staff Member';

    try {
      const resp = await apiFetch<{ magic_link?: string }>(`/admin/staff-onboarding/${id}/approve`, {
        method: 'POST',
        body: JSON.stringify({ role, worker_roles: workerRoles, frontend_url: window.location.origin })
      });
      setConfirmingId(null);
      // Remove from list
      setRequests(r => r.filter(x => x.id !== id));
      
      if (resp.magic_link) {
        setApprovedLink({ workerName: displayName, link: resp.magic_link, deliveryMethod: (resp as any).delivery_method });
        window.scrollTo({ top: 0, behavior: 'smooth' });
      } else {
        alert('Worker approved successfully.');
      }
    } catch (err: any) {
      setConfirmingId(null);
      // Phase 1025 Fix D: Show specific human-readable messages per error code.
      // err.code is the machine code (from Fix A). err.message is the human text.
      const code: string = err?.code || '';
      if (code === 'INVALID_STATUS') {
        setApprovalError({ id, message: 'This request has already been approved. The worker is already on your staff list.' });
      } else if (code === 'RATE_LIMIT') {
        setApprovalError({ id, message: 'Email rate limit exceeded. Please wait ~60 minutes, or use the Resend Access button on the staff member\u2019s profile.' });
      } else if (code === 'IDENTITY_MISMATCH_AT_APPROVAL') {
        setApprovalError({ id, message: 'Identity mismatch: submitted email does not match existing account. Please contact support.' });
      } else if (code === 'VALIDATION_ERROR') {
        setApprovalError({ id, message: `Approval failed: ${err.message || 'Missing required data (check email).'}` });
      } else {
        setApprovalError({ id, message: `Approval failed: ${err.message || 'Unknown error. Please try again.'}` });
      }
    }
  };


  const handleReject = async (id: string) => {
    try {
      await apiFetch(`/admin/staff-onboarding/${id}/reject`, {
        method: 'POST'
      });
      setConfirmingRejectId(null);
      setRequests(r => r.filter(x => x.id !== id));
    } catch { setConfirmingRejectId(null); }
  };

  const cardStyle: React.CSSProperties = {
    background: 'var(--color-surface)',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-lg)',
    padding: 'var(--space-4)',
    marginBottom: 'var(--space-4)',
  };

  const inputStyle = {
    padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)',
    background: 'var(--color-surface-2)', color: 'var(--color-text)', outline: 'none',
  };

  const selectStyle: React.CSSProperties = {
    ...inputStyle,
    appearance: 'none', // Remove default arrow
    paddingRight: '24px', // Make space for custom arrow
    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20' fill='currentColor'%3E%3Cpath fill-rule='evenodd' d='M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z' clip-rule='evenodd'%3E%3C/path%3E%3C/svg%3E")`,
    backgroundRepeat: 'no-repeat',
    backgroundPosition: 'right 8px center',
    backgroundSize: '16px',
  };

  const messageTemplate = inviteGenerated ? (
    genAccountRole === 'owner'
      ? (genLanguage === 'th'
          ? `สวัสดี, ยินดีต้อนรับสู่ Domaniqo โปรดกรอกรายละเอียดเจ้าของของคุณที่นี่เพื่อตั้งค่าบัญชีของคุณ:\n\n${inviteGenerated}`
          : genLanguage === 'he'
          ? `שלום, זה מ-Domaniqo. נשמח לצרף אותך כבעל דירה (Owner). אנא מלא/י את הפרטים שלך כאן להקמת המשתמש:\n\n${inviteGenerated}`
          : `Hello! Welcome to Domaniqo. Please complete your Owner profile here to set up your account:\n\n${inviteGenerated}`)
      : (genLanguage === 'th'
          ? `สวัสดี, นี่คือข้อความจาก Domaniqo เราสนใจที่จะจ้างคุณ โปรดกรอกรายละเอียดของคุณที่นี่:\n\n${inviteGenerated}`
          : genLanguage === 'he'
          ? `שלום, זה מ-Domaniqo. נשמח לצרף אותך לצוות. אנא מלא/י את הפרטים שלך כאן:\n\n${inviteGenerated}`
          : `Hello, this is from Domaniqo. We'd love to have you on our team. Please complete your registration using this secure link:\n\n${inviteGenerated}`)
  ) : '';

  return (
    <div style={{ maxWidth: 900 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)', marginBottom: 'var(--space-5)' }}>
        <button
          onClick={() => router.back()}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)',
          }}
        >
          ← Back
        </button>
        <div>
          <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, margin: 0 }}>Pending Onboarding Requests</h1>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-faint)', marginTop: 4 }}>
            Generate public invitation links for new staff members, and approve their submitted details here.
          </p>
        </div>
      </div>

      {approvedLink && (
        <div style={{
          background: 'var(--color-ok-bg, rgba(46,160,67,0.1))',
          border: '1px solid var(--color-ok, #2ea043)',
          borderRadius: 'var(--radius-lg)',
          padding: 'var(--space-5)',
          marginBottom: 'var(--space-5)',
        }}>
          <h3 style={{ margin: '0 0 var(--space-2) 0', color: 'var(--color-ok, #2ea043)' }}>
            ✓ {approvedLink.workerName} Approved
          </h3>
          <p style={{ margin: '0 0 var(--space-3) 0', fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
            {approvedLink.deliveryMethod === 'email_invite_sent'
              ? '✉ Invite email sent automatically to the worker.'
              : '⚠ Email could not be auto-sent (existing user or rate limit). Use the link below.'}
          </p>

          {/* Copy link row */}
          <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-3)' }}>
            <input
              readOnly
              value={approvedLink.link}
              style={{ ...inputStyle, flex: 1, fontFamily: 'monospace', fontSize: 12 }}
            />
            <button
              onClick={() => { navigator.clipboard.writeText(approvedLink.link); alert('Copied!'); }}
              style={{ padding: '8px 14px', borderRadius: 'var(--radius-sm)', background: 'var(--color-primary)', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: 'var(--text-sm)', whiteSpace: 'nowrap' }}
            >
              Copy Link
            </button>
          </div>

          {/* Direct send shortcuts */}
          <p style={{ margin: '0 0 var(--space-2) 0', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
            Send directly:
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <a
              href={`https://wa.me/?text=${encodeURIComponent('Your access link: ' + approvedLink.link)}`}
              target="_blank" rel="noreferrer"
              style={{ padding: '7px 14px', borderRadius: 'var(--radius-sm)', background: '#25D366', color: '#fff', fontSize: 13, fontWeight: 600, textDecoration: 'none' }}
            >
              WhatsApp
            </a>
            <a
              href={`https://t.me/share/url?url=${encodeURIComponent(approvedLink.link)}&text=${encodeURIComponent('Your access link')}`}
              target="_blank" rel="noreferrer"
              style={{ padding: '7px 14px', borderRadius: 'var(--radius-sm)', background: '#2AABEE', color: '#fff', fontSize: 13, fontWeight: 600, textDecoration: 'none' }}
            >
              Telegram
            </a>
            <a
              href={`mailto:?subject=Your+Access+Link&body=${encodeURIComponent('Your access link: ' + approvedLink.link)}`}
              style={{ padding: '7px 14px', borderRadius: 'var(--radius-sm)', background: 'var(--color-surface-3, #444)', color: '#fff', fontSize: 13, fontWeight: 600, textDecoration: 'none' }}
            >
              Email
            </a>
            <a
              href={`sms:?body=${encodeURIComponent('Your access link: ' + approvedLink.link)}`}
              style={{ padding: '7px 14px', borderRadius: 'var(--radius-sm)', background: 'var(--color-surface-3, #444)', color: '#fff', fontSize: 13, fontWeight: 600, textDecoration: 'none' }}
            >
              SMS
            </a>
          </div>
          <button onClick={() => setApprovedLink(null)} style={{ marginTop: 'var(--space-3)', background: 'none', border: 'none', color: 'var(--color-text-faint)', cursor: 'pointer', fontSize: 12 }}>
            Dismiss
          </button>
        </div>
      )}


      {/* Generate Link Card */}
      <div style={{ ...cardStyle, background: 'var(--color-surface-2)' }}>
        <h3 style={{ fontSize: 'var(--text-md)', fontWeight: 600, marginBottom: 'var(--space-3)' }}>Generate Public Invite</h3>
        <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-3)' }}>
          <input
            value={inviteEmail}
            onChange={e => setInviteEmail(e.target.value)}
            placeholder="Optional: worker email"
            style={{ ...inputStyle, flex: 1 }}
          />
          <select
            value={genAccountRole}
            onChange={e => {
              setGenAccountRole(e.target.value);
              // Clear worker sub-roles if switching away from worker
              setGenRoles([]);
            }}
            style={{ ...selectStyle, width: '150px' }}
          >
            <option value="worker">Staff Member</option>
            <option value="manager">Operational Manager</option>
            <option value="owner">Owner</option>
          </select>
          <select
            value={genLanguage}
            onChange={e => setGenLanguage(e.target.value)}
            style={{ ...selectStyle, width: '100px' }}
          >
            <option value="en">English</option>
            <option value="th">Thai</option>
            <option value="he">Hebrew</option>
          </select>
        </div>
        {/* Phase 1026: Worker sub-role checkboxes only shown for Staff Member account type.
            Combined check-in & check-out stores both 'checkin' and 'checkout' as separate values.
            Operational Manager goes through the manager account role — no sub-role needed. */}
        {genAccountRole === 'worker' && (
          <div style={{ marginBottom: 'var(--space-3)' }}>
            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 6, display: 'block' }}>Pre-select Role (Optional)</label>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
              {/* Single roles */}
              {['cleaner', 'checkin', 'checkout', 'maintenance'].map(r => (
                <label key={r} style={{ fontSize: 13, display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', background: 'var(--color-surface)', padding: '4px 8px', borderRadius: 4, border: `1px solid ${genRoles.includes(r) ? 'var(--color-primary)' : 'var(--color-border)'}` }}>
                  <input
                    type="checkbox"
                    checked={genRoles.includes(r)}
                    onChange={(e) => {
                      if (e.target.checked) setGenRoles([...genRoles, r]);
                      else setGenRoles(genRoles.filter(x => x !== r));
                    }}
                  />
                  {r.charAt(0).toUpperCase() + r.slice(1)}
                </label>
              ))}
              {/* Combined check-in & check-out — stores as two separate values */}
              <label style={{ fontSize: 13, display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', background: 'var(--color-surface)', padding: '4px 8px', borderRadius: 4, border: `1px solid ${(genRoles.includes('checkin') && genRoles.includes('checkout')) ? 'var(--color-primary)' : 'var(--color-border)'}` }}>
                <input
                  type="checkbox"
                  checked={genRoles.includes('checkin') && genRoles.includes('checkout')}
                  onChange={(e) => {
                    if (e.target.checked) {
                      // Add both — deduplicated
                      const next = [...genRoles.filter(x => x !== 'checkin' && x !== 'checkout'), 'checkin', 'checkout'];
                      setGenRoles(next);
                    } else {
                      setGenRoles(genRoles.filter(x => x !== 'checkin' && x !== 'checkout'));
                    }
                  }}
                />
                Check-in &amp; Check-out
              </label>
            </div>
          </div>
        )}
        {/* Phase 1026: Manager account role context note */}
        {genAccountRole === 'manager' && (
          <div style={{ marginBottom: 'var(--space-3)', padding: '8px 12px', background: 'rgba(99,102,241,0.08)', borderRadius: 6, border: '1px solid var(--color-primary)', fontSize: 13, color: 'var(--color-text-dim)' }}>
            Operational Manager will be provisioned with <strong>role = Manager</strong>. No worker sub-roles are needed.
          </div>
        )}
        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
          <button
            onClick={() => handleGenerate(false)}
            style={{
              padding: '10px 16px', borderRadius: 'var(--radius-sm)',
              background: 'var(--color-primary)', color: '#fff', border: 'none',
              cursor: 'pointer', fontWeight: 600, fontSize: 'var(--text-sm)', flex: 1
            }}
          >
            Generate Link
          </button>
          <button
            onClick={() => handleGenerate(true)}
            style={{
              padding: '10px 16px', borderRadius: 'var(--radius-sm)',
              background: 'var(--color-surface)', color: 'var(--color-text)', border: '1px solid var(--color-border)',
              cursor: 'pointer', fontWeight: 600, fontSize: 'var(--text-sm)', flex: 1
            }}
          >
            Generate QR
          </button>
        </div>

          {inviteGenerated && (
            <div style={{ marginTop: 'var(--space-4)', padding: 'var(--space-3)', background: 'rgba(99,102,241,0.1)', border: '1px solid var(--color-primary)', borderRadius: 'var(--radius-sm)' }}>
              <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginBottom: 6 }}>Copy and send this link to the {genAccountRole}:</p>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <textarea
                  readOnly
                  value={messageTemplate}
                  style={{ ...inputStyle, flex: 1, fontFamily: 'monospace', fontSize: 13, minHeight: '80px', resize: 'vertical' }}
                />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <button
                    onClick={async () => {
                      try {
                        await navigator.clipboard.writeText(messageTemplate);
                        alert('Copied to clipboard!');
                      } catch (err) {
                        alert('Could not auto-copy (browser blocked). Please select the text manually and copy.');
                      }
                    }}
                    style={{ padding: '8px 12px', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13, color: 'var(--color-text)', whiteSpace: 'nowrap' }}
                  >
                    Copy
                  </button>
                  {generatedForEmail && (
                    <a
                      href={getOnboardingMailto(genLanguage, generatedForEmail, inviteGenerated)}
                      style={{ padding: '8px 12px', background: 'var(--color-primary)', border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13, color: '#fff', fontWeight: 600, textDecoration: 'none', textAlign: 'center', whiteSpace: 'nowrap' }}
                    >
                      Send by Email
                    </a>
                  )}
                </div>
              </div>
              {generatedForEmail && (
                <p style={{ margin: '8px 0 0', fontSize: 11, color: 'var(--color-text-faint)' }}>✉ Will open your mail client addressed to {generatedForEmail}</p>
              )}

              {showQR && (
                <div style={{ marginTop: 24, padding: 16, background: 'var(--color-surface)', borderRadius: 'var(--radius-md)', textAlign: 'center', border: '1px solid var(--color-border)' }}>
                  <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)', fontWeight: 600, marginBottom: 12 }}>Scan to Open Form</p>
                  <img
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(inviteGenerated)}`}
                    alt="QR Code"
                    style={{ width: 180, height: 180, borderRadius: 8, background: '#fff', padding: 8, margin: '0 auto', display: 'block' }}
                  />
                  {generatedForEmail && (
                    <div style={{ marginTop: 16 }}>
                      <a
                        href={getOnboardingMailto(genLanguage, generatedForEmail, inviteGenerated)}
                        style={{ display: 'inline-block', padding: '8px 18px', background: 'var(--color-primary)', borderRadius: 'var(--radius-sm)', color: '#fff', fontSize: 13, fontWeight: 600, textDecoration: 'none' }}
                      >
                        Send by Email
                      </a>
                      <p style={{ margin: '6px 0 0', fontSize: 11, color: 'var(--color-text-faint)' }}>✉ Send to {generatedForEmail}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
      </div>

      {/* Requests List */}
      <div>
        <h2 style={{ fontSize: 'var(--text-md)', fontWeight: 600, marginBottom: 'var(--space-4)' }}>Waiting for Approval ({requests.length})</h2>
        {loading && <div style={{ color: 'var(--color-text-dim)' }}>Loading...</div>}

        {!loading && requests.length === 0 && (
          <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--color-text-faint)', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)' }}>
            No pending submissions found.
          </div>
        )}

        {requests.map(req => {
          const wdata = req.metadata?.worker_data || {};
          const comm = wdata.comm_preference || {};
          return (
            <div key={req.id} style={{ ...cardStyle, position: 'relative' }}>
              <div style={{ display: 'flex', gap: 'var(--space-4)', alignItems: 'flex-start' }}>
                <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', overflow: 'hidden', flexShrink: 0 }}>
                  {wdata.photo_url ? (
                    <img src={wdata.photo_url} alt="photo" style={{ width: '100%', height: '100%', objectFit: 'cover', imageOrientation: 'from-image' as any }} />
                  ) : (
                    <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-text-dim)', fontSize: 24 }}>?</div>
                  )}
                </div>

                <div style={{ flex: 1 }}>
                  <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, margin: '0 0 4px 0', color: 'var(--color-text)' }}>
                    {wdata.full_name || req.email}
                  </h3>
                  {wdata.display_name && wdata.display_name !== wdata.full_name && (
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginBottom: 4 }}>Display: {wdata.display_name}</div>
                  )}
                  <div style={{ display: 'flex', gap: 16, fontSize: 'var(--text-sm)', color: 'var(--color-text-faint)', marginBottom: 12 }}>
                    <span>✉️ {req.email}</span>
                    {wdata.phone && <span>📞 {wdata.phone}</span>}
                    {wdata.language && <span>🌐 {wdata.language.toUpperCase()}</span>}
                  </div>

                  <div style={{ background: 'var(--color-surface-2)', padding: 'var(--space-3)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-sm)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                    <div>
                      <strong style={{ color: 'var(--color-text-dim)', fontSize: '11px', textTransform: 'uppercase' }}>Staff Roles</strong>
                      <div style={{ color: '#58a6ff', fontWeight: 600, marginTop: 2 }}>{wdata.worker_roles?.join(', ') || 'Staff Member'}</div>
                    </div>
                    <div>
                      <strong style={{ color: 'var(--color-text-dim)', fontSize: '11px', textTransform: 'uppercase' }}>Emergency</strong>
                      <div style={{ color: 'var(--color-text)', marginTop: 2 }}>{wdata.emergency_contact || '-'}</div>
                    </div>
                    {comm?.date_of_birth && (
                      <div>
                        <strong style={{ color: 'var(--color-text-dim)', fontSize: '11px', textTransform: 'uppercase' }}>Date of Birth</strong>
                        <div style={{ color: 'var(--color-text)', marginTop: 2 }}>{comm.date_of_birth}</div>
                      </div>
                    )}
                    {comm?.id_number && (
                      <div>
                        <strong style={{ color: 'var(--color-text-dim)', fontSize: '11px', textTransform: 'uppercase' }}>ID / Passport #</strong>
                        <div style={{ color: 'var(--color-text)', marginTop: 2 }}>{comm.id_number}{comm.id_expiry_date ? ` (exp: ${comm.id_expiry_date})` : ''}</div>
                      </div>
                    )}
                    {comm?.work_permit_number && (
                      <div>
                        <strong style={{ color: 'var(--color-text-dim)', fontSize: '11px', textTransform: 'uppercase' }}>Work Permit #</strong>
                        <div style={{ color: 'var(--color-text)', marginTop: 2 }}>{comm.work_permit_number}{comm.work_permit_expiry_date ? ` (exp: ${comm.work_permit_expiry_date})` : ''}</div>
                      </div>
                    )}
                  </div>

                  {/* Document thumbnails */}
                  {(comm?.id_photo_url || comm?.work_permit_photo_url) && (
                    <div style={{ display: 'flex', gap: 12, marginTop: 'var(--space-3)' }}>
                      {comm?.id_photo_url && (
                        <div style={{ textAlign: 'center' }}>
                          <img src={comm.id_photo_url} alt="ID" style={{ width: 80, height: 56, objectFit: 'cover', borderRadius: 4, border: '1px solid var(--color-border)' }} />
                          <div style={{ fontSize: 10, color: 'var(--color-text-faint)', marginTop: 2 }}>ID/Passport</div>
                        </div>
                      )}
                      {comm?.work_permit_photo_url && (
                        <div style={{ textAlign: 'center' }}>
                          <img src={comm.work_permit_photo_url} alt="WP" style={{ width: 80, height: 56, objectFit: 'cover', borderRadius: 4, border: '1px solid var(--color-border)' }} />
                          <div style={{ fontSize: 10, color: 'var(--color-text-faint)', marginTop: 2 }}>Work Permit</div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Communication channels */}
                  {(comm?.telegram || comm?.line || comm?.whatsapp) && (
                    <div style={{ display: 'flex', gap: 12, marginTop: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>
                      {comm?.telegram && <span>TG: {comm.telegram}</span>}
                      {comm?.line && <span>LINE: {comm.line}</span>}
                      {comm?.whatsapp && <span>WA: {comm.whatsapp}</span>}
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingLeft: 'var(--space-4)', minWidth: 120 }}>
                  {approvalError?.id === req.id && (
                    <div id={`approval-error-${req.id}`} style={{ padding: '8px 12px', background: 'rgba(248,81,73,0.1)', border: '1px solid rgba(248,81,73,0.3)', borderRadius: 'var(--radius-sm)', fontSize: 12, color: '#f85149', marginBottom: 4 }}>
                      {approvalError.message}
                      <button onClick={() => setApprovalError(null)} style={{ display: 'block', marginTop: 4, background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 11, textDecoration: 'underline' }}>Dismiss</button>
                    </div>
                  )}
                  {confirmingId === req.id ? (
                    <>
                      <span style={{ fontSize: 12, color: 'var(--color-text-faint)', marginBottom: 2 }}>Confirm approval?</span>
                      <button id={`confirm-approve-${req.id}`} onClick={() => handleApprove(req.id, req.metadata)} style={{ padding: '8px 16px', background: '#3fb950', color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontWeight: 700, fontSize: 'var(--text-sm)' }}>
                        ✓ Yes, Approve
                      </button>
                      <button onClick={() => setConfirmingId(null)} style={{ padding: '6px 16px', background: 'transparent', color: 'var(--color-text-faint)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 'var(--text-sm)' }}>
                        Cancel
                      </button>
                    </>
                  ) : confirmingRejectId === req.id ? (
                    <>
                      <span style={{ fontSize: 12, color: '#f85149', marginBottom: 2 }}>Reject and delete?</span>
                      <button id={`confirm-reject-${req.id}`} onClick={() => handleReject(req.id)} style={{ padding: '8px 16px', background: '#f85149', color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontWeight: 700, fontSize: 'var(--text-sm)' }}>
                        ✓ Yes, Reject
                      </button>
                      <button onClick={() => setConfirmingRejectId(null)} style={{ padding: '6px 16px', background: 'transparent', color: 'var(--color-text-faint)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 'var(--text-sm)' }}>
                        Cancel
                      </button>
                    </>
                  ) : (
                    <>
                      <button id={`approve-btn-${req.id}`} onClick={() => { setApprovalError(null); setConfirmingId(req.id); }} style={{ padding: '8px 20px', background: '#3fb950', color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontWeight: 600, fontSize: 'var(--text-sm)' }}>
                        Approve
                      </button>
                      <button id={`reject-btn-${req.id}`} onClick={() => setConfirmingRejectId(req.id)} style={{ padding: '8px 20px', background: 'transparent', color: '#f85149', border: '1px solid rgba(248,81,73,0.3)', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontWeight: 600, fontSize: 'var(--text-sm)' }}>
                        Reject
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
