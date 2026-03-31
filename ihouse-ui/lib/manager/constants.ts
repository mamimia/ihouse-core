/**
 * Phase 1033 — Operational Manager Baseline v1
 * lib/manager/constants.ts
 *
 * Route constants, API endpoint paths, and display label maps for the
 * Operational Manager cockpit module.
 *
 * Rules:
 * - All API paths are relative (no leading domain — used with lib/api helpers)
 * - Route paths are absolute app-router paths
 * - No runtime logic here — constants and maps only
 *
 * SCAFFOLD — not yet wired into live surfaces.
 */

// ---------------------------------------------------------------------------
// Baseline routes
// ---------------------------------------------------------------------------

export const OM_ROUTES = {
  hub:      '/manager',
  alerts:   '/manager/alerts',
  streams:  '/manager/streams',
  team:     '/manager/team',
  tasks:    '/manager/tasks',
  bookings: '/manager/bookings',
  calendar: '/manager/calendar',
  profile:  '/manager/profile',
} as const;

// ---------------------------------------------------------------------------
// API endpoint paths
// ---------------------------------------------------------------------------

export const OM_API = {
  // Hub summary (to build — does not exist yet)
  hubSummary:    '/manager/summary',

  // Alerts (to build — does not exist yet)
  alerts:        '/manager/alerts',
  alertById:     (id: string) => `/manager/alerts/${id}`,
  alertAck:      (id: string) => `/manager/alerts/${id}/acknowledge`,

  // Stream (to build — does not exist yet)
  stream:        '/manager/stream',

  // Team (exists — Phase 1033 draft endpoint)
  team:          '/manager/team',

  // Tasks (manager-scoped, exists — Phase 1033 draft endpoint)
  tasks:         '/manager/tasks',
  taskNotes:     (id: string) => `/tasks/${id}/notes`,
  taskReassign:  (id: string) => `/tasks/${id}/reassign`,
  taskAdhoc:     '/tasks/adhoc',

  // Bookings coordination (existing endpoint)
  bookings:          '/bookings',
  bookingOpNotes:    (id: string) => `/bookings/${id}/operational-notes`,
  bookingEarlyCo:    (id: string) => `/bookings/${id}/approve-early-checkout`,

  // Permissions / profile
  permissionsMe:     '/permissions/me',
  patchPermissions:  (userId: string) => `/permissions/${userId}`,
} as const;

// ---------------------------------------------------------------------------
// Alert severity display
// ---------------------------------------------------------------------------

export const ALERT_SEVERITY_STYLE: Record<string, { color: string; bg: string; label: string }> = {
  CRITICAL: { color: '#ef4444', bg: '#ef444418', label: 'Critical' },
  HIGH:     { color: '#f97316', bg: '#f9731618', label: 'High' },
  NORMAL:   { color: '#3b82f6', bg: '#3b82f618', label: 'Normal' },
  LOW:      { color: '#6b7280', bg: '#6b728018', label: 'Low' },
};

// ---------------------------------------------------------------------------
// Task kind display
// ---------------------------------------------------------------------------

export const TASK_KIND_LABEL: Record<string, string> = {
  CLEANING:        'Cleaning',
  CHECKIN_PREP:    'Check-in',
  GUEST_WELCOME:   'Welcome',
  CHECKOUT_VERIFY: 'Check-out',
  MAINTENANCE:     'Maintenance',
  GENERAL:         'General',
};

export const TASK_KIND_COLOR: Record<string, string> = {
  CLEANING:        '#10b981',
  CHECKIN_PREP:    '#3b82f6',
  GUEST_WELCOME:   '#8b5cf6',
  CHECKOUT_VERIFY: '#f97316',
  MAINTENANCE:     '#ef4444',
  GENERAL:         '#6b7280',
};

export const TASK_STATUS_STYLE: Record<string, { color: string; bg: string }> = {
  PENDING:           { color: '#f59e0b', bg: '#f59e0b18' },
  ACKNOWLEDGED:      { color: '#3b82f6', bg: '#3b82f618' },
  IN_PROGRESS:       { color: '#10b981', bg: '#10b98118' },
  MANAGER_EXECUTING: { color: '#8b5cf6', bg: '#8b5cf618' },
  COMPLETED:         { color: '#6b7280', bg: '#6b728018' },
  CANCELED:          { color: '#ef4444', bg: '#ef444418' },
};

export const TASK_PRIORITY_DOT: Record<string, string> = {
  CRITICAL: '#ef4444',
  HIGH:     '#f97316',
  NORMAL:   '#6b7280',
  LOW:      '#9ca3af',
};

// ---------------------------------------------------------------------------
// Operational lane display (used in Team view and task filters)
// ---------------------------------------------------------------------------

export const LANE_LABELS: Record<string, string> = {
  CLEANING:        'Cleaning',
  MAINTENANCE:     'Maintenance',
  CHECKIN_CHECKOUT: 'Check-in/out',
  CHECKIN_PREP:    'Check-in',
  GUEST_WELCOME:   'Welcome',
  CHECKOUT_VERIFY: 'Check-out',
  GENERAL:         'General',
};

// ---------------------------------------------------------------------------
// Stream / activity display
// ---------------------------------------------------------------------------

export const STREAM_KIND_STYLE: Record<string, { icon: string; color: string; bg: string }> = {
  TASK_ACKNOWLEDGED:          { icon: '👁',  color: '#60a5fa', bg: 'rgba(59,130,246,0.12)'  },
  TASK_COMPLETED:             { icon: '✓',  color: '#34d399', bg: 'rgba(16,185,129,0.12)'  },
  TASK_IN_PROGRESS:           { icon: '▶',  color: '#60a5fa', bg: 'rgba(59,130,246,0.08)'  },
  TASK_CREATED:               { icon: '+',  color: '#a78bfa', bg: 'rgba(139,92,246,0.10)'  },
  TASK_CANCELED:              { icon: '✕',  color: '#f87171', bg: 'rgba(239,68,68,0.10)'   },
  BOOKING_FLAGS_UPDATED:      { icon: '⚑',  color: '#fbbf24', bg: 'rgba(245,158,11,0.12)'  },
  MANAGER_TAKEOVER_INITIATED: { icon: '⚡', color: '#f87171', bg: 'rgba(239,68,68,0.12)'   },
  MANAGER_TASK_COMPLETED:     { icon: '✓',  color: '#34d399', bg: 'rgba(16,185,129,0.12)'  },
  BOOKING_CREATED:            { icon: '📋', color: '#8b5cf6', bg: 'rgba(139,92,246,0.08)'  },
  BOOKING_CANCELED:           { icon: '✕',  color: '#6b7280', bg: 'rgba(107,114,128,0.10)' },
  WORKER_ASSIGNED:            { icon: '👤', color: '#10b981', bg: 'rgba(16,185,129,0.10)'  },
  BATON_TRANSFER:             { icon: '⇄',  color: '#f59e0b', bg: 'rgba(245,158,11,0.10)'  },
};

export const STREAM_KIND_DEFAULT_STYLE = { icon: '·', color: '#6b7280', bg: 'rgba(107,114,128,0.08)' };
