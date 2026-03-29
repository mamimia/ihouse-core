'use client';

/**
 * Phase 1015 — SelfCheckinPanel
 *
 * Admin/Manager control surface for Self Check-in on the Booking Detail page.
 * Mode-aware: renders differently for Default vs Late mode bookings.
 *
 * Default mode booking (no approval needed):
 *   - Shows portal link if active, last sent time
 *   - Resend action
 *   - Staffed override action (VIP, operational concern, etc.)
 *   - Step progress (what guest has / hasn't done)
 *
 * Late mode booking (explicit approval required):
 *   - Request → Approve → (in_progress) → access_released
 *   - Revoke action before access_released
 *   - Resend portal link after approval
 *   - Step progress
 *
 * Disabled mode:
 *   - Not rendered (caller responsibility to gate on property mode)
 *
 * Status badge colours mirror the booking status system for visual consistency.
 */

import { useState, useEffect, useCallback } from 'react';
import { api, ApiError } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SelfCheckinStatus {
  self_checkin_status: string | null;
  self_checkin_approved: boolean;
  self_checkin_approved_by: string | null;
  self_checkin_approved_at: string | null;
  self_checkin_reason: string | null;
  self_checkin_portal_url: string | null;
  self_checkin_portal_sent_at: string | null;
  self_checkin_access_released_at: string | null;
  self_checkin_steps_completed: Record<string, any> | null;
  self_checkin_config: Record<string, any> | null;
  self_checkin_staff_override: boolean;
  self_checkin_override_reason: string | null;
}

interface SelfCheckinPanelProps {
  bookingId: string;
  booking: any;
  propertyMode: 'default' | 'late_only' | 'disabled';
  onActionComplete?: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const OPS_TZ = 'Asia/Bangkok';

function fmtDt(d: string | null): string {
  if (!d) return '—';
  try {
    return new Date(d).toLocaleString('en-US', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
      timeZone: OPS_TZ,
    });
  } catch { return d; }
}

function StatusBadge({ status }: { status: string | null }) {
  const cfg: Record<string, { label: string; bg: string; color: string }> = {
    none:              { label: 'Not Started',      bg: 'rgba(148,163,184,0.12)', color: '#64748b' },
    requested:         { label: 'Requested',         bg: 'rgba(251,191,36,0.12)', color: '#b45309' },
    approved:          { label: 'Approved',          bg: 'rgba(59,130,246,0.12)', color: '#1d4ed8' },
    in_progress:       { label: 'In Progress',       bg: 'rgba(99,102,241,0.12)', color: '#4338ca' },
    access_released:   { label: 'Access Released',   bg: 'rgba(16,185,129,0.12)', color: '#059669' },
    completed:         { label: 'Completed',         bg: 'rgba(16,185,129,0.18)', color: '#065f46' },
    followup_required: { label: 'Follow-up Needed',  bg: 'rgba(239,68,68,0.12)',  color: '#b91c1c' },
  };
  const s = status || 'none';
  const { label, bg, color } = cfg[s] ?? { label: s, bg: 'rgba(148,163,184,0.12)', color: '#64748b' };
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 10px', borderRadius: 999, fontSize: 11,
      fontWeight: 600, letterSpacing: '0.04em', background: bg, color,
    }}>
      {label}
    </span>
  );
}

function StepIndicator({ steps, completed }: {
  steps: string[];
  completed: Record<string, any>;
}) {
  const LABELS: Record<string, string> = {
    id_photo: 'ID Photo',
    selfie: 'Selfie',
    agreement: 'House Rules Accepted',
    deposit: 'Deposit Acknowledged',
    electricity_meter: 'Electricity Meter',
    arrival_photos: 'Arrival Photos',
  };
  if (steps.length === 0) return null;
  const done = steps.filter(s => completed?.[s]);
  const pct = Math.round((done.length / steps.length) * 100);
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 11, color: 'var(--color-text-dim)' }}>
        <span>Steps ({done.length}/{steps.length})</span>
        <span>{pct}%</span>
      </div>
      <div style={{
        height: 4, borderRadius: 2, background: 'var(--color-border)',
        overflow: 'hidden', marginBottom: 8,
      }}>
        <div style={{
          height: '100%', width: `${pct}%`,
          background: pct === 100 ? '#059669' : 'var(--color-primary)',
          borderRadius: 2, transition: 'width 0.3s ease',
        }} />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {steps.map(s => {
          const isDone = !!completed?.[s];
          return (
            <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
              <span style={{ color: isDone ? '#059669' : 'var(--color-text-faint)', fontSize: 13 }}>
                {isDone ? '✓' : '○'}
              </span>
              <span style={{ color: isDone ? 'var(--color-text)' : 'var(--color-text-dim)' }}>
                {LABELS[s] ?? s}
              </span>
              {isDone && completed[s]?.completed_at && (
                <span style={{ color: 'var(--color-text-faint)', fontSize: 10, marginLeft: 'auto' }}>
                  {fmtDt(completed[s].completed_at)}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function SelfCheckinPanel({
  bookingId, booking, propertyMode, onActionComplete,
}: SelfCheckinPanelProps) {
  const sc: SelfCheckinStatus = booking;
  const scStatus = sc.self_checkin_status || 'none';
  const config = sc.self_checkin_config || {};
  const stepsCompleted = sc.self_checkin_steps_completed || {};
  const preAccessSteps: string[] = config.pre_access_steps || [];
  const postEntrySteps: string[] = config.post_entry_steps || [];

  // Form state
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [reason, setReason] = useState('');
  const [overrideReason, setOverrideReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  };

  const act = async (fn: () => Promise<any>, successMsg: string) => {
    setSubmitting(true);
    setError(null);
    try {
      await fn();
      showToast(successMsg);
      onActionComplete?.();
    } catch (err: unknown) {
      const msg = err instanceof ApiError
        ? ((err.body as any)?.detail || `API ${err.status}: ${err.code}`)
        : (err instanceof Error ? err.message : 'Action failed');
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Late mode: request
  // ---------------------------------------------------------------------------
  const handleRequest = () => act(
    () => api.requestSelfCheckin(bookingId, { reason: reason.trim() || 'Late arrival — no staff available' }),
    'Self check-in requested.',
  );

  // ---------------------------------------------------------------------------
  // Approve
  // ---------------------------------------------------------------------------
  const handleApprove = () => act(
    () => api.approveSelfCheckin(bookingId, {
      guest_phone: phone.trim() || undefined,
      guest_email: email.trim() || undefined,
      reason: reason.trim() || undefined,
    }),
    'Approved! Portal link sent to guest.',
  );

  // ---------------------------------------------------------------------------
  // Revoke
  // ---------------------------------------------------------------------------
  const handleRevoke = () => act(
    () => api.revokeSelfCheckin(bookingId),
    'Approval revoked. Guest link invalidated.',
  );

  // ---------------------------------------------------------------------------
  // Resend
  // ---------------------------------------------------------------------------
  const handleResend = () => act(
    () => api.resendSelfCheckinLink(bookingId, {
      guest_phone: phone.trim() || undefined,
      guest_email: email.trim() || undefined,
    }),
    'Portal link resent to guest.',
  );

  // ---------------------------------------------------------------------------
  // Staffed override
  // ---------------------------------------------------------------------------
  const [confirmingOverride, setConfirmingOverride] = useState(false);
  const handleOverride = () => act(
    () => api.staffedSelfCheckinOverride(bookingId, { reason: overrideReason.trim() }),
    'Staffed override applied. Auto-portal suppressed for this booking.',
  );

  // Section title
  const modeLabel = propertyMode === 'default' ? 'Default Self Check-in' : 'Late Self Check-in';

  // Surface control
  const canRevoke = ['approved', 'in_progress'].includes(scStatus);
  const canResend = ['approved', 'in_progress'].includes(scStatus);
  const canApprove = propertyMode === 'late_only' && ['none', 'requested'].includes(scStatus);
  const canRequest = propertyMode === 'late_only' && scStatus === 'none';
  const isReleased = ['access_released', 'completed', 'followup_required'].includes(scStatus);
  const canOverride = propertyMode === 'default' && !isReleased && !sc.self_checkin_staff_override;
  const isOverridden = sc.self_checkin_staff_override;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const panelBorderColor = isReleased
    ? 'rgba(16,185,129,0.3)'
    : scStatus === 'followup_required'
    ? 'rgba(239,68,68,0.3)'
    : 'var(--color-border)';

  return (
    <div style={{
      marginTop: 'var(--space-8)',
      background: 'var(--color-surface)',
      border: `1px solid ${panelBorderColor}`,
      borderRadius: 'var(--radius-lg)',
      padding: 'var(--space-5)',
      position: 'relative',
    }}>
      {/* Toast */}
      {toast && (
        <div style={{
          position: 'absolute', top: 12, right: 12,
          background: '#065f46', color: '#d1fae5',
          borderRadius: 8, padding: '6px 14px',
          fontSize: 12, fontWeight: 600, zIndex: 10,
        }}>
          {toast}
        </div>
      )}

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-4)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: '1rem' }}>🔑</span>
          <h2 style={{
            fontSize: 'var(--text-sm)', fontWeight: 600,
            color: 'var(--color-text-dim)', textTransform: 'uppercase',
            margin: 0, letterSpacing: '0.04em',
          }}>
            {modeLabel}
          </h2>
        </div>
        <StatusBadge status={isOverridden ? 'staffed_override' : scStatus} />
      </div>

      {/* Staffed override notice */}
      {isOverridden && (
        <div style={{
          background: 'rgba(245,158,11,0.07)', border: '1px solid rgba(245,158,11,0.25)',
          borderRadius: 8, padding: '8px 12px', marginBottom: 12, fontSize: 12,
          color: '#92400e',
        }}>
          ⚠️ <strong>Staffed override active.</strong> This booking is proceeding with physical check-in.
          {sc.self_checkin_override_reason && (
            <span style={{ display: 'block', marginTop: 2, color: '#b45309' }}>
              Reason: {sc.self_checkin_override_reason}
            </span>
          )}
        </div>
      )}

      {/* Meta grid */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px',
        fontSize: 12, color: 'var(--color-text-dim)', marginBottom: 12,
      }}>
        {sc.self_checkin_approved_by && (
          <>
            <span>Approved by</span>
            <span style={{ color: 'var(--color-text)' }}>
              {sc.self_checkin_approved_by === 'system:pre_arrival' ? 'System (auto)' : sc.self_checkin_approved_by}
            </span>
          </>
        )}
        {sc.self_checkin_approved_at && (
          <>
            <span>Approved at</span>
            <span style={{ color: 'var(--color-text)' }}>{fmtDt(sc.self_checkin_approved_at)}</span>
          </>
        )}
        {sc.self_checkin_portal_sent_at && (
          <>
            <span>Link sent</span>
            <span style={{ color: 'var(--color-text)' }}>{fmtDt(sc.self_checkin_portal_sent_at)}</span>
          </>
        )}
        {sc.self_checkin_access_released_at && (
          <>
            <span>Access released</span>
            <span style={{ color: '#059669', fontWeight: 600 }}>{fmtDt(sc.self_checkin_access_released_at)}</span>
          </>
        )}
        {sc.self_checkin_reason && (
          <>
            <span>Reason</span>
            <span style={{ color: 'var(--color-text)' }}>{sc.self_checkin_reason}</span>
          </>
        )}
      </div>

      {/* Portal URL (admin read-only — no access code) */}
      {sc.self_checkin_portal_url && !isReleased && (
        <div style={{
          background: 'rgba(99,102,241,0.05)', border: '1px solid rgba(99,102,241,0.15)',
          borderRadius: 8, padding: '8px 12px', marginBottom: 12, fontSize: 11,
          color: 'var(--color-text-dim)', wordBreak: 'break-all',
        }}>
          <span style={{ fontWeight: 600, color: 'var(--color-text)' }}>Portal link: </span>
          {sc.self_checkin_portal_url}
        </div>
      )}

      {/* Step progress — pre-access */}
      {preAccessSteps.length > 0 && (
        <div style={{
          background: 'var(--color-background)', border: '1px solid var(--color-border)',
          borderRadius: 8, padding: 10, marginBottom: 10,
        }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
            Pre-Access Steps
          </div>
          <StepIndicator steps={preAccessSteps} completed={stepsCompleted} />
        </div>
      )}

      {/* Step progress — post-entry */}
      {postEntrySteps.length > 0 && isReleased && (
        <div style={{
          background: 'var(--color-background)', border: '1px solid var(--color-border)',
          borderRadius: 8, padding: 10, marginBottom: 10,
        }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
            Post-Entry Steps
          </div>
          <StepIndicator steps={postEntrySteps} completed={stepsCompleted} />
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)',
          borderRadius: 8, padding: '8px 12px', fontSize: 12, color: '#b91c1c', marginBottom: 10,
        }}>
          {error}
        </div>
      )}

      {/* Contact fields (shown for request/approve/resend actions) */}
      {(canRequest || canApprove || canResend) && !isOverridden && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
          <input
            id="sc-phone"
            type="tel"
            placeholder="Guest phone (E.164)"
            value={phone}
            onChange={e => setPhone(e.target.value)}
            disabled={submitting}
            style={{
              padding: '7px 10px', borderRadius: 6, fontSize: 12,
              border: '1px solid var(--color-border)', background: 'var(--color-background)',
              color: 'var(--color-text)', outline: 'none',
            }}
          />
          <input
            id="sc-email"
            type="email"
            placeholder="Guest email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            disabled={submitting}
            style={{
              padding: '7px 10px', borderRadius: 6, fontSize: 12,
              border: '1px solid var(--color-border)', background: 'var(--color-background)',
              color: 'var(--color-text)', outline: 'none',
            }}
          />
        </div>
      )}

      {/* Reason field (Late mode request/approve) */}
      {(canRequest || canApprove) && propertyMode === 'late_only' && (
        <input
          id="sc-reason"
          type="text"
          placeholder="Reason (e.g. guest arrives at midnight, no staff available)"
          value={reason}
          onChange={e => setReason(e.target.value)}
          disabled={submitting}
          style={{
            width: '100%', padding: '7px 10px', borderRadius: 6, fontSize: 12,
            border: '1px solid var(--color-border)', background: 'var(--color-background)',
            color: 'var(--color-text)', outline: 'none', marginBottom: 10,
            boxSizing: 'border-box',
          }}
        />
      )}

      {/* Action buttons */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>

        {/* Late mode: request */}
        {canRequest && (
          <button
            id="btn-sc-request"
            onClick={handleRequest}
            disabled={submitting}
            style={actionBtn({color: '#b45309', bg: 'rgba(245,158,11,0.1)', border: 'rgba(245,158,11,0.4)'})}
          >
            {submitting ? '…' : 'Record Request'}
          </button>
        )}

        {/* Approve (Late: moves requested→approved, Default: manual approve override) */}
        {(canApprove || (propertyMode === 'default' && scStatus === 'none' && !isOverridden)) && (
          <button
            id="btn-sc-approve"
            onClick={handleApprove}
            disabled={submitting}
            style={actionBtn({color: '#1d4ed8', bg: 'rgba(59,130,246,0.1)', border: 'rgba(59,130,246,0.4)'})}
          >
            {submitting ? '…' : propertyMode === 'late_only' ? 'Approve & Send Link' : 'Send Portal Link'}
          </button>
        )}

        {/* Resend */}
        {canResend && (
          <button
            id="btn-sc-resend"
            onClick={handleResend}
            disabled={submitting}
            style={actionBtn({color: '#4338ca', bg: 'rgba(99,102,241,0.09)', border: 'rgba(99,102,241,0.35)'})}
          >
            {submitting ? '…' : 'Resend Link'}
          </button>
        )}

        {/* Revoke */}
        {canRevoke && (
          <button
            id="btn-sc-revoke"
            onClick={handleRevoke}
            disabled={submitting}
            style={actionBtn({color: '#b91c1c', bg: 'rgba(239,68,68,0.07)', border: 'rgba(239,68,68,0.3)'})}
          >
            {submitting ? '…' : 'Revoke Approval'}
          </button>
        )}

        {/* Staffed override (Default mode only) */}
        {canOverride && !confirmingOverride && (
          <button
            id="btn-sc-override"
            onClick={() => setConfirmingOverride(true)}
            disabled={submitting}
            style={actionBtn({color: '#92400e', bg: 'rgba(245,158,11,0.07)', border: 'rgba(245,158,11,0.3)'})}
          >
            Convert to Staffed
          </button>
        )}
      </div>

      {/* Staffed override confirmation */}
      {confirmingOverride && (
        <div style={{
          marginTop: 12, background: 'rgba(245,158,11,0.06)',
          border: '1px solid rgba(245,158,11,0.3)', borderRadius: 8, padding: 12,
        }}>
          <p style={{ margin: '0 0 8px', fontSize: 12, color: '#92400e', fontWeight: 600 }}>
            Override to staffed check-in?
          </p>
          <p style={{ margin: '0 0 8px', fontSize: 11, color: 'var(--color-text-dim)' }}>
            The auto-portal link will be suppressed. A worker will need to be assigned for physical check-in.
          </p>
          <input
            id="sc-override-reason"
            type="text"
            placeholder="Required: reason for staffed override"
            value={overrideReason}
            onChange={e => setOverrideReason(e.target.value)}
            disabled={submitting}
            style={{
              width: '100%', padding: '7px 10px', borderRadius: 6, fontSize: 12,
              border: '1px solid rgba(245,158,11,0.4)', background: 'var(--color-background)',
              color: 'var(--color-text)', outline: 'none', marginBottom: 8, boxSizing: 'border-box',
            }}
          />
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              id="btn-sc-override-confirm"
              onClick={handleOverride}
              disabled={submitting || !overrideReason.trim()}
              style={actionBtn({color: '#92400e', bg: 'rgba(245,158,11,0.14)', border: 'rgba(245,158,11,0.5)'})}
            >
              {submitting ? '…' : 'Confirm Override'}
            </button>
            <button
              onClick={() => setConfirmingOverride(false)}
              disabled={submitting}
              style={actionBtn({color: 'var(--color-text-dim)', bg: 'var(--color-background)', border: 'var(--color-border)'})}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function actionBtn({ color, bg, border }: { color: string; bg: string; border: string }) {
  return {
    padding: '6px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600,
    cursor: 'pointer', border: `1px solid ${border}`, background: bg, color,
    transition: 'opacity 0.15s ease',
  } as React.CSSProperties;
}
