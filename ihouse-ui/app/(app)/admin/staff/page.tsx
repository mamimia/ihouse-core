'use client';
/**
 * Phase 843 — Staff Management List
 * /admin/staff
 *
 * Changes from original:
 * - Removed InviteModal (replaced by full-page /admin/staff/new)
 * - Removed UserDetailPanel slide panel (replaced by /admin/staff/[userId])
 * - Added photo avatar column with initials fallback
 * - Added worker_roles[] sub-role tags
 * - "+ Add Staff" button → router.push('/admin/staff/new')
 * - Row click → router.push(`/admin/staff/${userId}`)
 * - Success/notice toasts from ?created=1 / ?deactivated=1 query params
 */

import { Suspense, useEffect, useState, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { getToken } from '@/lib/api';

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

// ── Types & Constants ─────────────────────────────────────────────────────

type UserRecord = {
  id?: string;
  user_id: string;
  role: string;
  permissions?: Record<string, any>;
  display_name?: string;
  phone?: string;
  emergency_contact?: string;
  worker_id?: string;
  worker_role?: string;
  worker_roles?: string[];
  photo_url?: string;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
};

// All valid canonical roles + legacy roles for display
const ROLE_LABELS: Record<string, string> = {
  admin: 'Admin',
  manager: 'Manager',
  worker: 'Worker',
  owner: 'Owner',
  // Legacy display-only labels
  cleaner: 'Cleaner ⚠',
  checkin_staff: 'Check-in ⚠',
  maintenance: 'Maintenance ⚠',
};

const ROLE_COLORS: Record<string, { bg: string; text: string }> = {
  admin:         { bg: 'rgba(130,80,223,0.15)',  text: '#a371f7' },
  manager:       { bg: 'rgba(56,158,214,0.15)',  text: '#58a6ff' },
  worker:        { bg: 'rgba(46,160,67,0.15)',   text: '#3fb950' },
  owner:         { bg: 'rgba(210,153,34,0.15)',  text: '#d29922' },
  // Legacy — amber warning colour
  cleaner:       { bg: 'rgba(210,153,34,0.15)',  text: '#d29922' },
  checkin_staff: { bg: 'rgba(210,153,34,0.15)',  text: '#d29922' },
  maintenance:   { bg: 'rgba(210,153,34,0.15)',  text: '#d29922' },
};

const CANONICAL_ROLES = ['admin', 'manager', 'worker', 'owner'];

const WORKER_ROLE_LABELS: Record<string, string> = {
  cleaner:     'Cleaner',
  checkin:     'Check-in',
  checkout:    'Check-out',
  maintenance: 'Maintenance',
};

// ── Components ───────────────────────────────────────────────────────────────

function RoleBadge({ role }: { role: string }) {
  const c = ROLE_COLORS[role] || { bg: 'rgba(110,118,129,0.15)', text: '#8b949e' };
  return (
    <span style={{
      display: 'inline-block', padding: '2px 10px', borderRadius: 12,
      background: c.bg, color: c.text, fontSize: 'var(--text-xs)', fontWeight: 600,
    }}>
      {ROLE_LABELS[role] || role}
    </span>
  );
}

function WorkerRoleTags({ roles }: { roles?: string[] }) {
  if (!roles?.length) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
      {roles.map(r => (
        <span key={r} style={{
          fontSize: 10, padding: '1px 7px', borderRadius: 8,
          background: 'rgba(46,160,67,0.1)', color: '#3fb950', fontWeight: 500,
        }}>
          {WORKER_ROLE_LABELS[r] || r}
        </span>
      ))}
    </div>
  );
}

function StatusDot({ active }: { active?: boolean }) {
  return (
    <span style={{
      display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
      background: active !== false ? '#3fb950' : '#8b949e', marginRight: 6,
    }} />
  );
}

function Avatar({ name, photoUrl, size = 36 }: { name?: string; photoUrl?: string; size?: number }) {
  const initials = (name || '?').trim().split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%', flexShrink: 0,
      background: photoUrl ? 'transparent' : 'var(--color-primary)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: size * 0.35, fontWeight: 700, color: '#fff',
      overflow: 'hidden', border: '1px solid var(--color-border)',
    }}>
      {photoUrl
        ? <img src={photoUrl} alt={name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        : initials}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

function ManageStaffContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [notice, setNotice] = useState<string | null>(null);

  const showNotice = (msg: string) => {
    setNotice(msg);
    setTimeout(() => setNotice(null), 3500);
  };

  // Show toast from redirect params
  useEffect(() => {
    if (searchParams?.get('created') === '1') showNotice('✓ Staff member created successfully.');
    if (searchParams?.get('deactivated') === '1') showNotice('Staff member deactivated.');
  }, [searchParams]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch<any>('/permissions');
      setUsers(res.permissions || []);
    } catch { /* graceful */ }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  // Summary counts for canonical roles only
  const roleCounts = CANONICAL_ROLES.reduce((acc, r) => {
    acc[r] = users.filter(u => u.role === r).length;
    return acc;
  }, {} as Record<string, number>);
  const legacyCount = users.filter(u => !CANONICAL_ROLES.includes(u.role)).length;

  const filtered = users.filter(u => {
    if (roleFilter === 'legacy') return !CANONICAL_ROLES.includes(u.role);
    if (roleFilter !== 'all' && u.role !== roleFilter) return false;
    if (search) {
      const s = search.toLowerCase();
      return (u.user_id || '').toLowerCase().includes(s) ||
             (u.display_name || '').toLowerCase().includes(s);
    }
    return true;
  });

  const cardStyle: React.CSSProperties = {
    background: 'var(--color-surface)',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-lg)',
    padding: 'var(--space-4)',
  };

  return (
    <div style={{ maxWidth: 1100 }}>

      {/* Notice toast */}
      {notice && (
        <div style={{
          position: 'fixed', top: 20, right: 20, zIndex: 999,
          background: 'var(--color-surface)', border: '1px solid var(--color-primary)',
          borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)',
          fontSize: 'var(--text-sm)', color: 'var(--color-primary)',
          boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
        }}>
          {notice}
        </div>
      )}

      {/* Header */}
      <div style={{ marginBottom: 'var(--space-4)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Settings
          </p>
          <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text)', letterSpacing: '-0.03em' }}>
            Manage Staff
          </h1>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
          <button
            onClick={() => router.push('/admin/staff/requests')}
            style={{
              padding: '10px 20px', borderRadius: 'var(--radius-md)',
              background: 'var(--color-surface-2)', color: 'var(--color-text)', border: '1px solid var(--color-border)',
              cursor: 'pointer', fontWeight: 600, fontSize: 'var(--text-sm)', transition: 'all 0.1s'
            }}
          >
            Pending Requests
          </button>
          {/* Phase 843: full-page create instead of modal */}
          <button
            onClick={() => router.push('/admin/staff/new')}
            style={{
              padding: '10px 20px', borderRadius: 'var(--radius-md)',
              background: 'var(--color-primary)', color: '#fff', border: 'none',
              cursor: 'pointer', fontWeight: 600, fontSize: 'var(--text-sm)',
            }}
          >
            + Add Staff
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: 'var(--space-3)', marginBottom: 'var(--space-5)' }}>
        <div style={cardStyle}>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Total</div>
          <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-primary)', marginTop: 4 }}>{users.length}</div>
        </div>
        {CANONICAL_ROLES.map(r => (
          <div key={r}
            style={{ ...cardStyle, cursor: 'pointer', borderColor: roleFilter === r ? (ROLE_COLORS[r]?.text || 'var(--color-border)') : 'var(--color-border)' }}
            onClick={() => setRoleFilter(roleFilter === r ? 'all' : r)}>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>{ROLE_LABELS[r]}</div>
            <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: ROLE_COLORS[r]?.text || 'var(--color-text)', marginTop: 4 }}>{roleCounts[r] || 0}</div>
          </div>
        ))}
        {legacyCount > 0 && (
          <div style={{ ...cardStyle, cursor: 'pointer', borderColor: roleFilter === 'legacy' ? '#d29922' : 'var(--color-border)' }}
            onClick={() => setRoleFilter(roleFilter === 'legacy' ? 'all' : 'legacy')}>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Legacy ⚠</div>
            <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: '#d29922', marginTop: 4 }}>{legacyCount}</div>
          </div>
        )}
      </div>

      {/* Legacy migration notice */}
      {legacyCount > 0 && (
        <div style={{
          background: 'rgba(210,153,34,0.08)', border: '1px solid rgba(210,153,34,0.3)',
          borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-4)',
          fontSize: 'var(--text-sm)', color: '#d29922', marginBottom: 'var(--space-4)',
          display: 'flex', gap: 8,
        }}>
          <span>⚠</span>
          <span>
            <strong>{legacyCount} staff member{legacyCount > 1 ? 's' : ''}</strong> still use legacy roles.
            Open each record and click <strong>Save Changes</strong> to migrate to the new role model.
          </span>
        </div>
      )}

      {/* Search */}
      <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
        <input
          value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search by name or email…"
          style={{
            flex: 1, background: 'var(--color-surface)', border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)', padding: '8px 14px', color: 'var(--color-text)',
            fontSize: 'var(--text-sm)', outline: 'none',
          }}
        />
        {roleFilter !== 'all' && (
          <button onClick={() => setRoleFilter('all')} style={{
            padding: '8px 14px', borderRadius: 'var(--radius-md)',
            background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
            color: 'var(--color-text-dim)', cursor: 'pointer', fontSize: 'var(--text-xs)',
          }}>
            Clear filter ✕
          </button>
        )}
      </div>

      {/* Table */}
      <div style={{ ...cardStyle, padding: 0, overflow: 'hidden' }}>
        {/* Header */}
        <div style={{
          display: 'grid', gridTemplateColumns: '48px 1fr 140px 80px',
          gap: 'var(--space-3)', padding: 'var(--space-3) var(--space-4)',
          borderBottom: '1px solid var(--color-border)',
          fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)',
          textTransform: 'uppercase', letterSpacing: '0.04em',
        }}>
          <div></div>
          <div>Staff Member</div>
          <div>Role</div>
          <div>Status</div>
        </div>

        {loading && (
          <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>
            Loading…
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>
            {search ? 'No staff match your search.' : 'No staff yet. Click "+ Add Staff" to get started.'}
          </div>
        )}

        {filtered.map(u => (
          <div
            key={u.user_id}
            onClick={() => router.push(`/admin/staff/${encodeURIComponent(u.user_id)}`)}
            style={{
              display: 'grid', gridTemplateColumns: '48px 1fr 140px 80px',
              gap: 'var(--space-3)', padding: 'var(--space-3) var(--space-4)',
              borderBottom: '1px solid var(--color-border)',
              cursor: 'pointer', transition: 'background 0.1s', alignItems: 'center',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-surface-2)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            {/* Avatar */}
            <Avatar name={u.display_name || u.user_id} photoUrl={u.photo_url} />

            {/* Name + user_id + worker sub-roles */}
            <div>
              <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
                {u.display_name || u.user_id}
              </div>
              {u.display_name && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)' }}>
                  {u.user_id}
                </div>
              )}
              <WorkerRoleTags roles={u.worker_roles} />
            </div>

            {/* Role badge */}
            <div><RoleBadge role={u.role} /></div>

            {/* Status */}
            <div style={{ fontSize: 'var(--text-sm)' }}>
              <StatusDot active={u.is_active} />
              {u.is_active !== false ? 'Active' : 'Off'}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ManageStaffPage() {
  return (
    <Suspense fallback={
      <div style={{ padding: 'var(--space-8)', textAlign: 'center', color: 'var(--color-text-dim)' }}>
        Loading staff…
      </div>
    }>
      <ManageStaffContent />
    </Suspense>
  );
}
