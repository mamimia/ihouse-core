'use client';

/**
 * Phase 1033 — /manager/profile
 * Manager identity, assigned properties, notification prefs,
 * and read-only view of delegated capabilities.
 *
 * Uses:
 *   GET /permissions/me   — own permissions + comm_preference + capabilities
 *   GET /manager/team     — assigned properties from staff_assignments
 *   PATCH /permissions/{user_id}  — update notification prefs
 */

import { useState, useEffect, useCallback } from 'react';
import { api } from '../../../../lib/api';
import { getTabToken } from '../../../../lib/tokenStore';
import DraftGuard from '../../../../components/DraftGuard';

type PermissionsMe = {
  user_id: string;
  tenant_id?: string;
  role?: string;
  display_name?: string;
  is_active?: boolean;
  comm_preference?: Record<string, string | boolean | null>;
  permissions?: Record<string, boolean>;
  capabilities?: Record<string, boolean>;
};

type PropertyTeam = { property_id: string };

function getPayload(): { display_name?: string; email?: string; role?: string } {
  try {
    const token = getTabToken();
    if (!token) return {};
    return JSON.parse(atob(token.split('.')[1] || '{}'));
  } catch { return {}; }
}

const CAP_LABELS: Record<string, string> = {
  financial: 'Financial access',
  bookings: 'Booking management',
  staffing: 'Staff management',
  properties: 'Property management',
  reports: 'Reports access',
  can_manage_workers: 'Manage workers',
  can_approve_bookings: 'Approve bookings',
  can_view_financial: 'View financial',
  booking_flag_vip: 'Flag VIP bookings',
  booking_flag_dispute: 'Flag disputes',
  staff_manage_assignments: 'Manage assignments',
  staff_approve_availability: 'Approve availability',
  staff_create_worker: 'Create workers',
  staff_deactivate_worker: 'Deactivate workers',
  ops_view_cleaning_reports: 'View cleaning reports',
  ops_set_property_status: 'Set property status',
  settlement_view_deposits: 'View deposits',
  settlement_finalize: 'Finalize settlements',
  settlement_approve_deductions: 'Approve deductions',
  financial_view_revenue: 'View revenue',
  financial_export: 'Export financial data',
};

export default function ManagerProfilePage() {
  const [me, setMe] = useState<PermissionsMe | null>(null);
  const [properties, setProperties] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');
  const [lineId, setLineId] = useState('');
  const [phone, setPhone] = useState('');
  const jwtPayload = getPayload();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [meRes, teamRes] = await Promise.all([
        api.get<PermissionsMe>('/permissions/me').catch(() => null),
        api.get<{ properties: PropertyTeam[] }>('/manager/team').catch(() => null),
      ]);

      if (meRes) {
        setMe(meRes);
        const comm = meRes.comm_preference || {};
        setLineId(String(comm.line_id || comm.line || ''));
        setPhone(String(comm.phone || ''));
      }

      if (teamRes?.properties) {
        setProperties(teamRes.properties.map(p => p.property_id));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const savePrefs = async () => {
    if (!me?.user_id) return;
    setSaving(true);
    setSaveMsg('');
    try {
      await api.post(
        `/permissions/${me.user_id}`,
        {
          comm_preference: {
            ...(me.comm_preference || {}),
            line_id: lineId,
            phone,
          },
        }
      );
      setSaveMsg('Preferences saved');
      await load();
    } catch (e: unknown) {
      setSaveMsg(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
      setTimeout(() => setSaveMsg(''), 3000);
    }
  };

  const activeCaps = me?.permissions || me?.capabilities || {};
  const grantedCaps = Object.entries(activeCaps).filter(([, v]) => v === true);

  if (loading) return <DraftGuard><div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-dim)' }}>Loading profile…</div></DraftGuard>;

  return (
    <DraftGuard>
    <div style={{ maxWidth: 640, margin: '0 auto', padding: '24px 20px' }}>
      <h1 style={{ margin: '0 0 24px', fontSize: 'var(--text-xl)', fontWeight: 800, color: 'var(--color-text)', fontFamily: "'Manrope', sans-serif" }}>
        My Profile
      </h1>

      {/* Identity */}
      <Section title="Identity">
        <Field label="Display Name" value={me?.display_name || jwtPayload.display_name || '—'} />
        <Field label="Email" value={jwtPayload.email || '—'} />
        <Field label="Role" value="Operational Manager" />
        <Field label="Status" value={me?.is_active !== false ? 'Active' : 'Inactive'} />
        <Field label="User ID" value={me?.user_id || '—'} mono />
      </Section>

      {/* Assigned Properties */}
      <Section title="Supervised Properties">
        {properties.length === 0 ? (
          <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)', margin: 0 }}>
            No properties currently assigned.
          </p>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {properties.map(p => (
              <span key={p} style={{
                padding: '4px 12px', borderRadius: 20,
                background: 'var(--color-primary)18', color: 'var(--color-primary)',
                fontSize: 'var(--text-xs)', fontWeight: 600,
              }}>
                {p}
              </span>
            ))}
          </div>
        )}
      </Section>

      {/* Notification Preferences */}
      <Section title="Notification Preferences">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
              LINE ID
            </label>
            <input
              value={lineId}
              onChange={e => setLineId(e.target.value)}
              placeholder="Your LINE user ID"
              style={{
                width: '100%', padding: '9px 12px', borderRadius: 8,
                border: '1px solid var(--color-border)', background: 'var(--color-bg)',
                color: 'var(--color-text)', fontSize: 'var(--text-sm)', boxSizing: 'border-box',
              }}
            />
          </div>
          <div>
            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
              Phone
            </label>
            <input
              value={phone}
              onChange={e => setPhone(e.target.value)}
              placeholder="+66 xx xxx xxxx"
              style={{
                width: '100%', padding: '9px 12px', borderRadius: 8,
                border: '1px solid var(--color-border)', background: 'var(--color-bg)',
                color: 'var(--color-text)', fontSize: 'var(--text-sm)', boxSizing: 'border-box',
              }}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button
              onClick={savePrefs}
              disabled={saving}
              style={{
                padding: '9px 20px', borderRadius: 8, border: 'none',
                background: 'var(--color-primary)', color: '#fff', cursor: 'pointer',
                fontSize: 'var(--text-sm)', fontWeight: 700, opacity: saving ? 0.7 : 1,
              }}
            >
              {saving ? 'Saving…' : 'Save Preferences'}
            </button>
            {saveMsg && (
              <span style={{ fontSize: 'var(--text-xs)', color: saveMsg === 'Preferences saved' ? '#10b981' : '#ef4444' }}>
                {saveMsg}
              </span>
            )}
          </div>
        </div>
      </Section>

      {/* Delegated Capabilities (read-only) */}
      <Section title="Active Delegated Capabilities">
        {grantedCaps.length === 0 ? (
          <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)', margin: 0 }}>
            No additional capabilities delegated by admin.
          </p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {grantedCaps.map(([key]) => (
              <div key={key} style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '7px 12px', borderRadius: 8,
                background: '#10b98110', border: '1px solid #10b98130',
              }}>
                <span style={{ color: '#10b981', fontSize: '0.85em' }}>✓</span>
                <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
                  {CAP_LABELS[key] || key}
                </span>
              </div>
            ))}
          </div>
        )}
        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', margin: '12px 0 0' }}>
          Capabilities are managed by your admin. Contact admin to request changes.
        </p>
      </Section>
    </div>
    </DraftGuard>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{
      padding: '18px 20px', borderRadius: 12,
      border: '1px solid var(--color-border)', background: 'var(--color-surface)',
      marginBottom: 16,
    }}>
      <h2 style={{
        margin: '0 0 14px', fontSize: 'var(--text-sm)', fontWeight: 700,
        color: 'var(--color-text)', letterSpacing: '0.01em',
        fontFamily: "'Manrope', sans-serif",
      }}>
        {title}
      </h2>
      {children}
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '5px 0', borderBottom: '1px solid var(--color-border)' }}>
      <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{label}</span>
      <span style={{
        fontSize: 'var(--text-sm)', color: 'var(--color-text)',
        fontFamily: mono ? 'monospace' : 'inherit',
        maxWidth: '60%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {value}
      </span>
    </div>
  );
}
