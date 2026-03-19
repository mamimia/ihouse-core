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

type PendingRequest = {
  id: string;
  email: string;
  created_at: string;
  metadata?: {
    status?: string;
    intended_role?: string;
    worker_data?: {
      full_name?: string;
      phone?: string;
      emergency_contact?: string;
      photo_url?: string;
      worker_roles?: string[];
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
  const [approvedLink, setApprovedLink] = useState<{ workerName: string; link: string } | null>(null);

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
      setInviteGenerated(`${window.location.protocol}//${fullLink}`);
      setInviteEmail('');
    } catch {
      alert('Network error or token expired. Try logging in again.');
    }
  };

  const handleApprove = async (id: string, metadata: any) => {
    if (!confirm('Approve this worker and provision their access?')) return;
    const role = metadata?.intended_role || 'worker';
    const workerRoles = metadata?.worker_data?.worker_roles || [];
    const displayName = metadata?.display_name || 'Worker';

    try {
      const resp = await apiFetch<{ magic_link?: string }>(`/admin/staff-onboarding/${id}/approve`, {
        method: 'POST',
        body: JSON.stringify({ role, worker_roles: workerRoles })
      });
      // Remove from list
      setRequests(r => r.filter(x => x.id !== id));
      
      if (resp.magic_link) {
        setApprovedLink({ workerName: displayName, link: resp.magic_link });
        window.scrollTo({ top: 0, behavior: 'smooth' });
      } else {
        alert('Worker Approved successfully.');
      }
    } catch (err: any) {
      alert(err.message || 'Network error during approval');
    }
  };

  const handleReject = async (id: string) => {
    if (!confirm('Reject and delete this request?')) return;
    try {
      await apiFetch(`/admin/staff-onboarding/${id}/reject`, {
        method: 'POST'
      });
      setRequests(r => r.filter(x => x.id !== id));
    } catch { }
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
            Generate public invitation links for new workers, and approve their submitted details here.
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
          <h3 style={{ margin: '0 0 var(--space-3) 0', color: 'var(--color-ok, #2ea043)' }}>
            ✓ {approvedLink.workerName} Approved Successfully!
          </h3>
          <p style={{ margin: '0 0 var(--space-4) 0', fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
            Here is their personalized single-use login link. Please copy it and send it to them right away.
          </p>
          <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
            <input 
              readOnly 
              value={approvedLink.link} 
              style={{ ...inputStyle, flex: 1, fontFamily: 'monospace', fontSize: 13 }}
            />
            <button 
              onClick={() => {
                navigator.clipboard.writeText(approvedLink.link);
                alert('Copied to clipboard!');
              }}
              style={{
                padding: '10px 16px', borderRadius: 'var(--radius-sm)',
                background: 'var(--color-primary)', color: '#fff', border: 'none',
                cursor: 'pointer', fontWeight: 600, fontSize: 'var(--text-sm)'
              }}
            >
              Copy Link
            </button>
          </div>
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
            onChange={e => setGenAccountRole(e.target.value)}
            style={{ ...selectStyle, width: '150px' }}
          >
            <option value="worker">Worker</option>
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
        {genAccountRole === 'worker' && (
          <div style={{ marginBottom: 'var(--space-3)' }}>
            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 6, display: 'block' }}>Pre-select Roles (Optional)</label>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
              {['cleaner', 'checkin', 'checkout', 'checkin/checkout', 'maintenance', 'op_manager'].map(r => (
                <label key={r} style={{ fontSize: 13, display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', background: 'var(--color-surface)', padding: '4px 8px', borderRadius: 4, border: '1px solid var(--color-border)' }}>
                  <input 
                    type="checkbox" 
                    checked={genRoles.includes(r)} 
                    onChange={(e) => {
                      if (e.target.checked) setGenRoles([...genRoles, r]);
                      else setGenRoles(genRoles.filter(x => x !== r));
                    }} 
                  />
                  {r === 'op_manager' ? 'Op Manager' : r === 'checkin/checkout' ? 'Check-in & Check-out' : r.charAt(0).toUpperCase() + r.slice(1)}
                </label>
              ))}
            </div>
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
              <button
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(messageTemplate);
                    alert('Copied to clipboard!');
                  } catch (err) {
                    alert('Could not auto-copy (browser blocked). Please select the text manually and copy.');
                  }
                }}
                style={{ padding: '8px 12px', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13, color: 'var(--color-text)' }}
              >
                Copy
              </button>
            </div>
            
            {showQR && (
              <div style={{ marginTop: 24, padding: 16, background: 'var(--color-surface)', borderRadius: 'var(--radius-md)', textAlign: 'center', border: '1px solid var(--color-border)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)', fontWeight: 600, marginBottom: 12 }}>Scan to Open Form</p>
                <img 
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(inviteGenerated)}`} 
                  alt="QR Code" 
                  style={{ width: 180, height: 180, borderRadius: 8, background: '#fff', padding: 8, margin: '0 auto', display: 'block' }} 
                />
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
                  <div style={{ display: 'flex', gap: 16, fontSize: 'var(--text-sm)', color: 'var(--color-text-faint)', marginBottom: 12 }}>
                    <span>✉️ {req.email}</span>
                    {wdata.phone && <span>📞 {wdata.phone}</span>}
                  </div>

                  <div style={{ background: 'var(--color-surface-2)', padding: 'var(--space-3)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-sm)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                    <div>
                      <strong style={{ color: 'var(--color-text-dim)', fontSize: '11px', textTransform: 'uppercase' }}>Worker Roles</strong>
                      <div style={{ color: '#58a6ff', fontWeight: 600, marginTop: 2 }}>{wdata.worker_roles?.join(', ') || 'Worker'}</div>
                    </div>
                    <div>
                      <strong style={{ color: 'var(--color-text-dim)', fontSize: '11px', textTransform: 'uppercase' }}>Emergency</strong>
                      <div style={{ color: 'var(--color-text)', marginTop: 2 }}>{wdata.emergency_contact || '-'}</div>
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingLeft: 'var(--space-4)' }}>
                  <button onClick={() => handleApprove(req.id, req.metadata)} style={{ padding: '8px 20px', background: '#3fb950', color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontWeight: 600, fontSize: 'var(--text-sm)' }}>
                    Approve
                  </button>
                  <button onClick={() => handleReject(req.id)} style={{ padding: '8px 20px', background: 'transparent', color: '#f85149', border: '1px solid rgba(248,81,73,0.3)', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontWeight: 600, fontSize: 'var(--text-sm)' }}>
                    Reject
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
