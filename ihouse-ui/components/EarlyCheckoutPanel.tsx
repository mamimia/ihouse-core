'use client';

/**
 * Phase 999 — Early Checkout Admin Panel
 * =======================================
 *
 * Self-contained component that manages the full early checkout lifecycle
 * for a given booking on the admin side:
 *
 *   State: none      → shows "Record Request" form
 *   State: requested → shows request intake summary + "Approve" form
 *   State: approved  → shows approval summary + "Revoke" option
 *   State: completed → shows read-only completed record
 *
 * Permission rendering:
 *   caller_can_approve = true  → approval form is shown
 *   caller_can_approve = false → approval form is hidden (info-only for ops)
 *
 * This component makes direct API calls to:
 *   GET    /admin/bookings/{id}/early-checkout
 *   POST   /admin/bookings/{id}/early-checkout/request
 *   POST   /admin/bookings/{id}/early-checkout/approve
 *   DELETE /admin/bookings/{id}/early-checkout/approve
 */

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type EarlyCheckoutStatus = 'none' | 'requested' | 'approved' | 'completed';

interface EarlyCheckoutState {
  booking_id: string;
  original_checkout_date: string;
  booking_status: string;
  early_checkout_status: EarlyCheckoutStatus;
  request: {
    recorded: boolean;
    source: string | null;
    note: string | null;
    at: string;
    proposed_date: string | null;
  };
  approval: {
    approved: boolean;
    approved_by: string | null;
    approved_at: string;
    effective_at: string;
    effective_date: string;
    reason: string | null;
    approval_note: string | null;
  };
  task: {
    task_id: string;
    due_date: string;
    original_due_date: string | null;
    is_early_checkout: boolean;
    status: string;
    priority: string;
  } | null;
  caller_can_approve: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtDate(d: string | null | undefined): string {
  if (!d) return '—';
  try {
    return new Date(d).toLocaleDateString('en-US', {
      weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
    });
  } catch { return d; }
}

function fmtDateTime(d: string | null | undefined): string {
  if (!d) return '—';
  try {
    return new Date(d).toLocaleString('en-US', {
      weekday: 'short', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return d || '—'; }
}

const SOURCE_LABELS: Record<string, string> = {
  phone: '📞 Phone call',
  message: '💬 Message',
  guest_portal: '🌐 Guest portal',
  ops_escalation: '⚡ Ops escalation',
  other: 'Other',
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: EarlyCheckoutStatus }) {
  const config = {
    none: { label: 'No early checkout', color: 'var(--color-text-dim)', bg: 'var(--color-surface-2)' },
    requested: { label: '⏳ Request Received', color: '#d97706', bg: '#fef3c7' },
    approved: { label: '✅ Approved', color: '#15803d', bg: '#dcfce7' },
    completed: { label: '🏁 Completed', color: '#1d4ed8', bg: '#dbeafe' },
  }[status] || { label: status, color: 'var(--color-text)', bg: 'var(--color-surface-2)' };

  return (
    <span style={{
      fontSize: 'var(--text-xs)', fontWeight: 700, padding: '3px 10px',
      borderRadius: 99, background: config.bg, color: config.color,
      display: 'inline-block',
    }}>
      {config.label}
    </span>
  );
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-4)', fontSize: 'var(--text-sm)', padding: '6px 0', borderBottom: '1px solid var(--color-border)' }}>
      <span style={{ color: 'var(--color-text-dim)', whiteSpace: 'nowrap' }}>{label}</span>
      <span style={{ fontWeight: 500, color: 'var(--color-text)', textAlign: 'right', maxWidth: '60%' }}>{value || '—'}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Early Checkout Panel — main export
// ---------------------------------------------------------------------------

interface EarlyCheckoutPanelProps {
  bookingId: string;
  /** If true, renders inline inside another page. If false, renders standalone. */
  embedded?: boolean;
}

export function EarlyCheckoutPanel({ bookingId, embedded = false }: EarlyCheckoutPanelProps) {
  const [state, setState] = useState<EarlyCheckoutState | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Request form state
  const [reqSource, setReqSource] = useState<string>('phone');
  const [reqNote, setReqNote] = useState<string>('');
  const [reqProposedDate, setReqProposedDate] = useState<string>('');
  const [reqProposedTime, setReqProposedTime] = useState<string>('11:00');

  // Approval form state
  const [appDate, setAppDate] = useState<string>('');
  const [appTime, setAppTime] = useState<string>('11:00');
  const [appReason, setAppReason] = useState<string>('');
  const [appNote, setAppNote] = useState<string>('');

  // Revoke confirmation
  const [revokeConfirm, setRevokeConfirm] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await (api as any).getEarlyCheckoutState?.(bookingId);
      if (res) {
        setState(res);
        // Pre-fill approval date from request proposed_date if available
        if (res.request?.proposed_date && !appDate) {
          setAppDate(res.request.proposed_date);
        }
        if (res.approval?.effective_date && !appDate) {
          setAppDate(res.approval.effective_date);
        }
      } else {
        setError('Could not load early checkout state.');
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to load.');
    }
    setLoading(false);
  }, [bookingId]);

  useEffect(() => { load(); }, [load]);

  const showMsg = (type: 'ok' | 'err', msg: string) => {
    if (type === 'ok') { setSuccess(msg); setError(null); }
    else { setError(msg); setSuccess(null); }
    setTimeout(() => { setSuccess(null); setError(null); }, 4000);
  };

  // ── Request intake ────────────────────────────────────────────────────────

  const handleRequest = async () => {
    if (!reqSource) return;
    setSubmitting(true);
    try {
      const res = await (api as any).recordEarlyCheckoutRequest?.(bookingId, {
        request_source: reqSource,
        request_note: reqNote || undefined,
        proposed_date: reqProposedDate || undefined,
        proposed_time: reqProposedTime || undefined,
      });
      if (res?.status === 'request_recorded') {
        showMsg('ok', 'Request recorded. Pending approval.');
        await load();
      } else {
        showMsg('err', res?.detail || 'Request failed.');
      }
    } catch (e: any) {
      showMsg('err', e?.message || 'Request failed.');
    }
    setSubmitting(false);
  };

  // ── Approval ──────────────────────────────────────────────────────────────

  const handleApprove = async () => {
    if (!appDate) { showMsg('err', 'Effective checkout date is required.'); return; }
    setSubmitting(true);
    try {
      const res = await (api as any).approveEarlyCheckout?.(bookingId, {
        early_checkout_date: appDate,
        early_checkout_time: appTime || '11:00',
        reason: appReason || undefined,
        approval_note: appNote || undefined,
      });
      if (res?.status === 'approved') {
        showMsg('ok', `Approved. Checkout task rescheduled to ${appDate}.`);
        await load();
      } else {
        showMsg('err', res?.detail || 'Approval failed.');
      }
    } catch (e: any) {
      showMsg('err', e?.detail || e?.message || 'Approval failed.');
    }
    setSubmitting(false);
  };

  // ── Revoke ────────────────────────────────────────────────────────────────

  const handleRevoke = async () => {
    setSubmitting(true);
    try {
      const res = await (api as any).revokeEarlyCheckout?.(bookingId);
      if (res?.status === 'revoked') {
        showMsg('ok', 'Approval revoked. Task restored to original schedule.');
        setRevokeConfirm(false);
        await load();
      } else {
        showMsg('err', res?.detail || 'Revocation failed.');
      }
    } catch (e: any) {
      showMsg('err', e?.message || 'Revocation failed.');
    }
    setSubmitting(false);
  };

  // ── Render ────────────────────────────────────────────────────────────────

  const panelStyle = embedded ? {} : {
    maxWidth: 640,
    margin: '0 auto',
  };

  if (loading) {
    return (
      <div style={panelStyle}>
        <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading early checkout state…</p>
      </div>
    );
  }

  if (!state) {
    return (
      <div style={panelStyle}>
        <p style={{ color: 'var(--color-text-faint)', fontSize: 'var(--text-sm)' }}>No early checkout data available.</p>
      </div>
    );
  }

  const ecStatus = state.early_checkout_status;
  const canApprove = state.caller_can_approve;
  const isCheckedIn = ['checked_in', 'active'].includes((state.booking_status || '').toLowerCase());

  return (
    <div style={{ ...panelStyle, display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
        <div>
          <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)', margin: 0 }}>
            🔴 Early Check-out
          </h2>
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', margin: '4px 0 0' }}>
            Exception flow — requires Admin or authorized Operational Manager approval.
          </p>
        </div>
        <StatusBadge status={ecStatus} />
      </div>

      {/* ── Booking Context ──────────────────────────────────────────────── */}
      <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
          <div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 4 }}>Original Checkout Date</div>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 700, color: 'var(--color-text)' }}>
              {fmtDate(state.original_checkout_date)}
            </div>
          </div>
          {ecStatus === 'approved' || ecStatus === 'completed' ? (
            <div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 4 }}>Approved Early Checkout</div>
              <div style={{ fontSize: 'var(--text-md)', fontWeight: 700, color: '#d97706' }}>
                {fmtDateTime(state.approval.effective_at)}
              </div>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 4 }}>Booking Status</div>
              <div style={{ fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--color-text)' }}>
                {state.booking_status}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Feedback messages ────────────────────────────────────────────── */}
      {success && (
        <div style={{ background: '#dcfce7', border: '1px solid #86efac', borderRadius: 'var(--radius-md)', padding: 'var(--space-3)', fontSize: 'var(--text-sm)', color: '#15803d', fontWeight: 500 }}>
          ✅ {success}
        </div>
      )}
      {error && (
        <div style={{ background: '#fee2e2', border: '1px solid #fca5a5', borderRadius: 'var(--radius-md)', padding: 'var(--space-3)', fontSize: 'var(--text-sm)', color: '#dc2626', fontWeight: 500 }}>
          ❌ {error}
        </div>
      )}

      {/* ── APPROVED state: summary ──────────────────────────────────────── */}
      {(ecStatus === 'approved' || ecStatus === 'completed') && (
        <div style={{ background: 'var(--color-surface)', border: '2px solid #86efac', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)' }}>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: '#15803d', marginBottom: 'var(--space-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Approval Details
          </div>
          <InfoRow label="Effective checkout" value={fmtDateTime(state.approval.effective_at)} />
          <InfoRow label="Original checkout" value={fmtDate(state.original_checkout_date)} />
          <InfoRow label="Approved by" value={state.approval.approved_by} />
          <InfoRow label="Approved at" value={fmtDateTime(state.approval.approved_at)} />
          {state.approval.reason && <InfoRow label="Reason" value={state.approval.reason} />}
          {state.approval.approval_note && <InfoRow label="Operations note" value={state.approval.approval_note} />}
          {state.task && (
            <InfoRow
              label="Checkout task"
              value={
                <span>
                  {state.task.is_early_checkout
                    ? <span style={{ color: '#d97706', fontWeight: 700 }}>🔴 Early — due {fmtDate(state.task.due_date)}</span>
                    : <span>Due {fmtDate(state.task.due_date)}</span>}
                  {state.task.original_due_date && (
                    <span style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-xs)', display: 'block' }}>
                      Originally: {fmtDate(state.task.original_due_date)}
                    </span>
                  )}
                </span>
              }
            />
          )}

          {/* Revoke — only if not completed and caller can approve */}
          {ecStatus === 'approved' && canApprove && (
            <div style={{ marginTop: 'var(--space-4)' }}>
              {!revokeConfirm ? (
                <button
                  id="ec-revoke-btn"
                  onClick={() => setRevokeConfirm(true)}
                  style={ghostBtnStyle}
                >
                  Revoke Approval
                </button>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 'var(--text-sm)', color: '#dc2626' }}>Revoke this early checkout approval?</span>
                  <button
                    id="ec-revoke-confirm-btn"
                    onClick={handleRevoke}
                    disabled={submitting}
                    style={{ ...dangerBtnStyle, opacity: submitting ? 0.6 : 1 }}
                  >
                    {submitting ? 'Revoking…' : 'Yes, Revoke'}
                  </button>
                  <button onClick={() => setRevokeConfirm(false)} style={ghostBtnStyle}>
                    Cancel
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── REQUESTED state: request summary ────────────────────────────── */}
      {(ecStatus === 'requested' || ecStatus === 'approved') && state.request.recorded && (
        <div style={{ background: 'var(--color-surface)', border: '1px solid #fde68a', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)' }}>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: '#d97706', marginBottom: 'var(--space-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Request Intake
          </div>
          <InfoRow label="Source" value={SOURCE_LABELS[state.request.source || ''] || state.request.source} />
          <InfoRow label="Recorded at" value={fmtDateTime(state.request.at)} />
          {state.request.note && <InfoRow label="Staff note" value={state.request.note} />}
          {state.request.proposed_date && ecStatus === 'requested' && (
            <InfoRow label="Proposed date" value={fmtDate(state.request.proposed_date)} />
          )}
        </div>
      )}

      {/* ── INTAKE FORM: record request (shown when status=none and guest is checked in) ──── */}
      {ecStatus === 'none' && isCheckedIn && (
        <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
          <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--color-text)', marginBottom: 'var(--space-4)' }}>
            Record Guest Early Departure Request
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            <div>
              <label style={labelStyle}>Request source *</label>
              <select
                id="ec-request-source"
                value={reqSource}
                onChange={e => setReqSource(e.target.value)}
                style={selectStyle}
              >
                {Object.entries(SOURCE_LABELS).map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
              <div>
                <label style={labelStyle}>Proposed date (optional)</label>
                <input
                  id="ec-proposed-date"
                  type="date"
                  value={reqProposedDate}
                  onChange={e => setReqProposedDate(e.target.value)}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Proposed time</label>
                <input
                  id="ec-proposed-time"
                  type="time"
                  value={reqProposedTime}
                  onChange={e => setReqProposedTime(e.target.value)}
                  style={inputStyle}
                />
              </div>
            </div>

            <div>
              <label style={labelStyle}>Staff note (optional)</label>
              <textarea
                id="ec-request-note"
                value={reqNote}
                onChange={e => setReqNote(e.target.value)}
                placeholder="e.g. Guest called, emergency flight change..."
                rows={3}
                style={{ ...inputStyle, resize: 'vertical' }}
              />
            </div>

            <button
              id="ec-record-request-btn"
              onClick={handleRequest}
              disabled={submitting || !reqSource}
              style={{ ...primaryBtnStyle, opacity: submitting ? 0.6 : 1 }}
            >
              {submitting ? 'Recording…' : 'Record Request →'}
            </button>
          </div>
        </div>
      )}

      {/* ── APPROVAL FORM: shown when caller_can_approve and status=requested ──── */}
      {ecStatus === 'requested' && canApprove && (
        <div style={{ background: 'var(--color-surface)', border: '2px solid #fde68a', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
          <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--color-text)', marginBottom: 'var(--space-1)' }}>
            Grant Early Checkout Approval
          </div>
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-4)', margin: '0 0 var(--space-4)' }}>
            This will reschedule the checkout task and unlock early checkout for the worker.
            The original checkout date ({fmtDate(state.original_checkout_date)}) will be preserved.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
              <div>
                <label style={labelStyle}>Effective checkout date *</label>
                <input
                  id="ec-approve-date"
                  type="date"
                  value={appDate}
                  onChange={e => setAppDate(e.target.value)}
                  max={state.original_checkout_date}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Effective time</label>
                <input
                  id="ec-approve-time"
                  type="time"
                  value={appTime}
                  onChange={e => setAppTime(e.target.value)}
                  style={inputStyle}
                />
              </div>
            </div>

            <div>
              <label style={labelStyle}>Reason / guest explanation *</label>
              <input
                id="ec-approve-reason"
                type="text"
                value={appReason}
                onChange={e => setAppReason(e.target.value)}
                placeholder="e.g. Flight change, family emergency..."
                style={inputStyle}
              />
            </div>

            <div>
              <label style={labelStyle}>Operations note (internal, optional)</label>
              <textarea
                id="ec-approve-note"
                value={appNote}
                onChange={e => setAppNote(e.target.value)}
                placeholder="e.g. Notify cleaning team same-day. Confirm with property owner."
                rows={3}
                style={{ ...inputStyle, resize: 'vertical' }}
              />
            </div>

            <div style={{ background: '#fef3c7', border: '1px solid #fde68a', borderRadius: 'var(--radius-md)', padding: 'var(--space-3)', fontSize: 'var(--text-xs)', color: '#92400e' }}>
              <strong>Important:</strong> This system handles operational + internal settlement only.
              Any booking-price or unused-night adjustments must be handled separately through the original booking channel (Airbnb, Booking.com, etc.).
            </div>

            <button
              id="ec-approve-btn"
              onClick={handleApprove}
              disabled={submitting || !appDate}
              style={{
                ...primaryBtnStyle,
                background: '#d97706',
                opacity: submitting || !appDate ? 0.6 : 1,
              }}
            >
              {submitting ? 'Approving…' : '✅ Approve Early Check-out'}
            </button>
          </div>
        </div>
      )}

      {/* ── APPROVAL PENDING: viewer without approve right ──────────────── */}
      {ecStatus === 'requested' && !canApprove && (
        <div style={{ background: '#fef3c7', border: '1px solid #fde68a', borderRadius: 'var(--radius-md)', padding: 'var(--space-3)', fontSize: 'var(--text-sm)', color: '#92400e' }}>
          Request recorded. Awaiting approval from Admin or an authorized Operational Manager.
        </div>
      )}

      {/* ── COMPLETED STATE ──────────────────────────────────────────────── */}
      {ecStatus === 'completed' && (
        <div style={{ background: '#dbeafe', border: '1px solid #93c5fd', borderRadius: 'var(--radius-md)', padding: 'var(--space-3)', fontSize: 'var(--text-sm)', color: '#1d4ed8' }}>
          🏁 Early checkout completed. See the guest dossier for the full record including settlement and photos.
        </div>
      )}

    </div>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 'var(--text-xs)',
  color: 'var(--color-text-dim)',
  marginBottom: 4,
  fontWeight: 500,
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  fontSize: 'var(--text-sm)',
  border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius-md)',
  background: 'var(--color-bg)',
  color: 'var(--color-text)',
  boxSizing: 'border-box',
};

const selectStyle: React.CSSProperties = {
  ...inputStyle,
};

const primaryBtnStyle: React.CSSProperties = {
  background: 'var(--color-primary)',
  color: '#fff',
  border: 'none',
  borderRadius: 'var(--radius-md)',
  padding: '10px 20px',
  fontSize: 'var(--text-sm)',
  fontWeight: 600,
  cursor: 'pointer',
  width: '100%',
  transition: 'opacity 0.15s',
};

const ghostBtnStyle: React.CSSProperties = {
  background: 'transparent',
  color: 'var(--color-text-dim)',
  border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius-md)',
  padding: '6px 14px',
  fontSize: 'var(--text-sm)',
  cursor: 'pointer',
};

const dangerBtnStyle: React.CSSProperties = {
  background: '#dc2626',
  color: '#fff',
  border: 'none',
  borderRadius: 'var(--radius-md)',
  padding: '6px 16px',
  fontSize: 'var(--text-sm)',
  fontWeight: 600,
  cursor: 'pointer',
};
