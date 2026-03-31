'use client';

/**
 * Phase 1033 — /manager/bookings
 * Booking coordination surface for Operational Manager.
 *
 * Manager-safe: shows only operational context, NO financial/PII columns.
 * Adds operational overlay columns (ETA, coordination_status, operational_notes).
 * Approve early checkout action available at baseline.
 */

import { useState, useEffect, useCallback } from 'react';
import { api } from '../../../../lib/api';
import DraftGuard from '../../../../components/DraftGuard';

type Booking = {
  id: string;
  booking_id?: string;
  property_id?: string;
  reservation_ref?: string;
  source?: string;
  check_in?: string;
  check_out?: string;
  status?: string;
  guest_first_name?: string;
  // operational overlay (may not exist yet — graceful fallback)
  expected_arrival_eta?: string | null;
  coordination_status?: string | null;
  operational_notes?: string | null;
  priority_flags?: string[] | null;
  last_operational_update?: string | null;
};

function fmtDate(d?: string | null) {
  if (!d) return '—';
  try { return new Date(d).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }); }
  catch { return d; }
}

const STATUS_PILL: Record<string, { bg: string; color: string }> = {
  active:    { bg: '#10b98118', color: '#10b981' },
  canceled:  { bg: '#ef444418', color: '#ef4444' },
  completed: { bg: '#6b728018', color: '#6b7280' },
};

// ── Booking Note Modal ────────────────────────────────────────────────────────

function BookingNoteModal({ bookingId, onClose }: { bookingId: string; onClose: () => void }) {
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    if (!note.trim()) return;
    setSaving(true);
    try {
      // POST to booking operational overlay — if endpoint doesn't exist yet, fails gracefully
      await api.post<{ status: string }>(`/bookings/${bookingId}/operational-notes`, { note });
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save note');
      setSaving(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60,
    }}>
      <div style={{
        background: 'var(--color-surface)', borderRadius: 12, padding: 28,
        width: '100%', maxWidth: 440, boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
      }}>
        <h3 style={{ margin: '0 0 14px', fontWeight: 700, fontSize: 'var(--text-base)', color: 'var(--color-text)' }}>
          Add Coordination Note
        </h3>
        <p style={{ margin: '0 0 12px', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
          Note is stored on the operational overlay, not on the booking core.
        </p>
        <textarea autoFocus value={note} onChange={e => setNote(e.target.value)} rows={4}
          placeholder="e.g. Guest arriving late, confirm with check-in team"
          style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', resize: 'vertical', boxSizing: 'border-box' }} />
        {error && <p style={{ color: '#ef4444', fontSize: 'var(--text-xs)', margin: '8px 0 0' }}>{error}</p>}
        <div style={{ display: 'flex', gap: 10, marginTop: 16, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid var(--color-border)', background: 'transparent', cursor: 'pointer', color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Cancel</button>
          <button onClick={submit} disabled={saving || !note.trim()} style={{ padding: '8px 18px', borderRadius: 8, border: 'none', background: 'var(--color-primary)', color: '#fff', cursor: 'pointer', fontSize: 'var(--text-sm)', fontWeight: 600, opacity: saving ? 0.7 : 1 }}>
            {saving ? 'Saving…' : 'Save Note'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Early Checkout Modal ──────────────────────────────────────────────────────

function EarlyCheckoutModal({ booking, onClose, onDone }: { booking: Booking; onClose: () => void; onDone: () => void }) {
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    setSaving(true);
    try {
      await api.post<{ status: string }>(`/bookings/${booking.id}/approve-early-checkout`, { reason });
      onDone();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to approve early checkout');
      setSaving(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60,
    }}>
      <div style={{
        background: 'var(--color-surface)', borderRadius: 12, padding: 28,
        width: '100%', maxWidth: 440, boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
      }}>
        <h3 style={{ margin: '0 0 6px', fontWeight: 700, fontSize: 'var(--text-base)', color: 'var(--color-text)' }}>
          Approve Early Check-out
        </h3>
        <p style={{ margin: '0 0 16px', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
          Booking {booking.reservation_ref || booking.id} · {booking.property_id}<br />
          This does not issue a refund. Financial adjustments remain an admin action.
        </p>
        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
          Reason (optional)
        </label>
        <input autoFocus value={reason} onChange={e => setReason(e.target.value)}
          placeholder="e.g. Guest requested, confirmed by email"
          style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', boxSizing: 'border-box' }} />
        {error && <p style={{ color: '#ef4444', fontSize: 'var(--text-xs)', margin: '8px 0 0' }}>{error}</p>}
        <div style={{ display: 'flex', gap: 10, marginTop: 16, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid var(--color-border)', background: 'transparent', cursor: 'pointer', color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Cancel</button>
          <button onClick={submit} disabled={saving} style={{ padding: '8px 18px', borderRadius: 8, border: 'none', background: '#10b981', color: '#fff', cursor: 'pointer', fontSize: 'var(--text-sm)', fontWeight: 600, opacity: saving ? 0.7 : 1 }}>
            {saving ? 'Approving…' : 'Approve Early C/O'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function ManagerBookingsPage() {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [noteBooking, setNoteBooking] = useState<Booking | null>(null);
  const [earlyCoBooking, setEarlyCoBooking] = useState<Booking | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<{ bookings?: Booking[]; data?: Booking[] }>('/bookings');
      setBookings(res.bookings || res.data || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load bookings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = search
    ? bookings.filter(b =>
        (b.reservation_ref || '').toLowerCase().includes(search.toLowerCase()) ||
        (b.property_id || '').toLowerCase().includes(search.toLowerCase()) ||
        (b.guest_first_name || '').toLowerCase().includes(search.toLowerCase())
      )
    : bookings;

  if (loading) return <DraftGuard><div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-dim)' }}>Loading bookings…</div></DraftGuard>;

  return (
    <DraftGuard>
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '24px 20px' }}>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ margin: 0, fontSize: 'var(--text-xl)', fontWeight: 800, color: 'var(--color-text)', fontFamily: "'Manrope', sans-serif" }}>
          Bookings
        </h1>
        <p style={{ margin: '4px 0 0', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
          Coordination view — operational overlay only. No financial data. No full guest PII.
        </p>
      </div>

      {/* Search */}
      <input
        value={search}
        onChange={e => setSearch(e.target.value)}
        placeholder="Search by ref, property, or guest name…"
        style={{
          width: '100%', padding: '10px 14px', borderRadius: 10,
          border: '1px solid var(--color-border)', background: 'var(--color-bg)',
          color: 'var(--color-text)', fontSize: 'var(--text-sm)',
          boxSizing: 'border-box', marginBottom: 16,
        }}
      />

      {error && (
        <div style={{ padding: 14, borderRadius: 8, background: '#ef444414', color: '#ef4444', marginBottom: 16, fontSize: 'var(--text-sm)' }}>
          {error}
        </div>
      )}

      {filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--color-text-faint)' }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>📋</div>
          <div>No bookings found</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {filtered.map(b => (
            <BookingCard
              key={b.id}
              booking={b}
              expanded={expandedId === b.id}
              onToggle={() => setExpandedId(p => p === b.id ? null : b.id)}
              onNote={() => setNoteBooking(b)}
              onEarlyCo={() => setEarlyCoBooking(b)}
            />
          ))}
        </div>
      )}

      {noteBooking && (
        <BookingNoteModal bookingId={noteBooking.id} onClose={() => setNoteBooking(null)} />
      )}
      {earlyCoBooking && (
        <EarlyCheckoutModal
          booking={earlyCoBooking}
          onClose={() => setEarlyCoBooking(null)}
          onDone={() => { setEarlyCoBooking(null); load(); }}
        />
      )}
    </div>
    </DraftGuard>
  );
}

function BookingCard({
  booking: b, expanded, onToggle, onNote, onEarlyCo,
}: {
  booking: Booking;
  expanded: boolean;
  onToggle: () => void;
  onNote: () => void;
  onEarlyCo: () => void;
}) {
  const statusStyle = STATUS_PILL[b.status || 'active'] || STATUS_PILL.active;
  const hasVip = b.priority_flags?.includes('vip');

  return (
    <div style={{
      borderRadius: 10, border: '1px solid var(--color-border)',
      background: 'var(--color-surface)', overflow: 'hidden',
    }}>
      <button onClick={onToggle} style={{
        width: '100%', padding: '12px 16px', display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', background: 'transparent', border: 'none',
        cursor: 'pointer', textAlign: 'left', gap: 10,
      }}>
        <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'auto 1fr auto', gap: 12, alignItems: 'center' }}>
          {/* Status */}
          <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4, ...statusStyle, flexShrink: 0 }}>
            {(b.status || 'active').toUpperCase()}
          </span>
          {/* Core */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
                {b.reservation_ref || b.id.slice(0, 8)}
              </span>
              {hasVip && <span style={{ fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 3, background: '#f59e0b18', color: '#f59e0b' }}>VIP</span>}
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{b.property_id}</span>
            </div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
              {b.guest_first_name ? `${b.guest_first_name} · ` : ''}{fmtDate(b.check_in)} → {fmtDate(b.check_out)}
            </div>
          </div>
          {/* ETA / coordination status */}
          {b.coordination_status && (
            <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 4, background: '#3b82f618', color: '#3b82f6', flexShrink: 0 }}>
              {b.coordination_status}
            </span>
          )}
        </div>
        <span style={{ color: 'var(--color-text-faint)', fontSize: '0.8em', flexShrink: 0, marginLeft: 8 }}>
          {expanded ? '▲' : '▼'}
        </span>
      </button>

      {/* Expanded operational detail */}
      {expanded && (
        <div style={{ borderTop: '1px solid var(--color-border)', padding: '14px 16px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, marginBottom: 14 }}>
            <OverlayField label="Expected ETA" value={b.expected_arrival_eta || '—'} />
            <OverlayField label="Coordination Status" value={b.coordination_status || '—'} />
            <OverlayField label="Last Op. Update" value={b.last_operational_update ? new Date(b.last_operational_update).toLocaleString() : '—'} />
            <OverlayField label="Source" value={b.source || '—'} />
          </div>
          {b.operational_notes && (
            <div style={{
              padding: '10px 12px', borderRadius: 8, background: 'var(--color-bg)',
              border: '1px solid var(--color-border)', marginBottom: 14,
            }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-text-dim)', marginBottom: 4, letterSpacing: '0.04em' }}>OPERATIONAL NOTE</div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{b.operational_notes}</div>
            </div>
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={onNote} style={{
              padding: '7px 14px', borderRadius: 8, border: '1px solid var(--color-border)',
              background: 'transparent', cursor: 'pointer', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)',
            }}>📝 Add Note</button>
            {b.status === 'active' && (
              <button onClick={onEarlyCo} style={{
                padding: '7px 14px', borderRadius: 8, border: 'none',
                background: '#10b98118', color: '#10b981', cursor: 'pointer',
                fontSize: 'var(--text-xs)', fontWeight: 600,
              }}>✓ Approve Early C/O</button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function OverlayField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-text-dim)', marginBottom: 2, letterSpacing: '0.04em' }}>{label}</div>
      <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{value}</div>
    </div>
  );
}
