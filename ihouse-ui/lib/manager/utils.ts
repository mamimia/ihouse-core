/**
 * Phase 1033 — Operational Manager Baseline v1
 * lib/manager/utils.ts
 *
 * Pure utility functions shared across the OM cockpit module.
 * No React. No side effects. No API calls.
 * Import freely from any OM page or component.
 *
 * SCAFFOLD — not yet wired into live surfaces.
 */

import type { AlertSeverity, TaskPriority } from './types';

// ---------------------------------------------------------------------------
// Time formatting
// ---------------------------------------------------------------------------

/** Returns a human-readable relative label: "just now", "5m ago", "2h ago", "Mar 31". */
export function fmtRelative(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    const d   = new Date(iso);
    const now = new Date();
    const ms  = now.getTime() - d.getTime();
    const min = Math.floor(ms / 60_000);
    if (min < 1)  return 'just now';
    if (min < 60) return `${min}m ago`;
    const h = Math.floor(min / 60);
    if (h < 24)   return `${h}h ago`;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return iso ?? '—';
  }
}

/** Returns a short formatted timestamp: "Mar 31, 14:05". */
export function fmtShort(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

/** Returns a date-only label: "Mar 31". */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch { return iso; }
}

// ---------------------------------------------------------------------------
// Severity / priority ordering
// ---------------------------------------------------------------------------

const SEVERITY_RANK: Record<AlertSeverity | string, number> = {
  CRITICAL: 0,
  HIGH:     1,
  NORMAL:   2,
  LOW:      3,
};

const PRIORITY_RANK: Record<TaskPriority | string, number> = {
  CRITICAL: 0,
  HIGH:     1,
  NORMAL:   2,
  LOW:      3,
};

/**
 * Comparator for sorting alerts by severity (CRITICAL first).
 * Usage: alerts.sort(bySeverity)
 */
export function bySeverity<T extends { severity: string }>(a: T, b: T): number {
  return (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9);
}

/**
 * Comparator for sorting tasks by priority (CRITICAL first).
 * Usage: tasks.sort(byPriority)
 */
export function byPriority<T extends { priority: string }>(a: T, b: T): number {
  return (PRIORITY_RANK[a.priority] ?? 9) - (PRIORITY_RANK[b.priority] ?? 9);
}

// ---------------------------------------------------------------------------
// Coverage gap helpers
// ---------------------------------------------------------------------------

/** Returns true if a lane has no primary worker assigned. */
export function hasGap(coverage: { has_primary: boolean } | undefined): boolean {
  return !coverage?.has_primary;
}

/** Counts total coverage gaps across all properties. */
export function countGaps(
  properties: ReadonlyArray<{ coverage_gaps: string[] }>
): number {
  return properties.reduce((acc, p) => acc + p.coverage_gaps.length, 0);
}

// ---------------------------------------------------------------------------
// String helpers
// ---------------------------------------------------------------------------

/** Truncates a UUID to a short display token: "a1b2c3d4…" */
export function shortId(id: string | null | undefined): string {
  if (!id) return '—';
  return id.length > 8 ? `${id.slice(0, 8)}…` : id;
}

/** Converts snake_case or SCREAMING_SNAKE_CASE to a display label. */
export function snakeToLabel(s: string): string {
  return s
    .toLowerCase()
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
}
