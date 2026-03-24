'use client';

import { useState, useEffect } from 'react';

/**
 * Phase 883 — Worker Timing Truth
 *
 * Shared countdown hook used by all worker-facing home pages.
 * Replaces plain "Next date" treatment with live time-to-action / overdue language.
 *
 * @param targetIso  ISO 8601 datetime string (date or datetime).
 *                   If only a date (YYYY-MM-DD) is given, provide defaultTime
 *                   to anchor to a meaningful hour (e.g. "11:00" for checkout,
 *                   "14:00" for checkin, "10:00" for cleaning).
 * @param defaultTime  HH:MM local time to apply when targetIso is date-only.
 */
export function useCountdown(
  targetIso: string | null,
  defaultTime = '10:00'
): { label: string; isOverdue: boolean; isUrgent: boolean; diffMs: number } {

  const resolve = () => {
    if (!targetIso) return { label: '—', isOverdue: false, isUrgent: false, diffMs: 0 };

    // If targetIso looks like a date-only string (no T), attach defaultTime
    const normalized = targetIso.includes('T')
      ? targetIso
      : `${targetIso}T${defaultTime}:00`;

    const target = new Date(normalized).getTime();
    const now = Date.now();
    const diffMs = target - now;
    const absSec = Math.abs(diffMs) / 1000;

    const isOverdue = diffMs < 0;
    const isUrgent = !isOverdue && diffMs < 2 * 60 * 60 * 1000; // within 2h

    // ── Format label ──
    if (Math.abs(diffMs) < 30 * 60 * 1000) {
      // Within ±30 minutes = "NOW"
      return { label: isOverdue ? 'NOW (overdue)' : 'NOW', isOverdue, isUrgent: true, diffMs };
    }

    const totalMin = Math.floor(absSec / 60);
    const days = Math.floor(totalMin / (60 * 24));
    const hours = Math.floor((totalMin % (60 * 24)) / 60);
    const mins = totalMin % 60;

    let label: string;
    if (days >= 2) {
      label = isOverdue
        ? `Overdue ${days}d`
        : `in ${days}d`;
    } else if (days === 1) {
      label = isOverdue
        ? `Overdue 1d ${hours}h`
        : `in 1d ${hours}h`;
    } else if (hours >= 1) {
      label = isOverdue
        ? `Overdue ${hours}h ${mins}m`
        : `in ${hours}h ${mins}m`;
    } else {
      label = isOverdue
        ? `Overdue ${mins}m`
        : `in ${mins}m`;
    }

    return { label, isOverdue, isUrgent, diffMs };
  };

  const [state, setState] = useState(resolve);

  useEffect(() => {
    setState(resolve());
    const id = setInterval(() => setState(resolve()), 30_000);
    return () => clearInterval(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetIso, defaultTime]);

  return state;
}

/**
 * Compute "X ago" label for an elapsed timestamp.
 * Used by Maintenance for "Reported 3h ago" treatment.
 */
export function useElapsed(sinceIso: string | null): string {
  const resolve = () => {
    if (!sinceIso) return '—';
    const diffMs = Date.now() - new Date(sinceIso).getTime();
    const totalMin = Math.floor(diffMs / 60_000);
    if (totalMin < 1) return 'just now';
    if (totalMin < 60) return `${totalMin}m ago`;
    const h = Math.floor(totalMin / 60);
    const m = totalMin % 60;
    if (h < 24) return m > 0 ? `${h}h ${m}m ago` : `${h}h ago`;
    const d = Math.floor(h / 24);
    return `${d}d ago`;
  };

  const [label, setLabel] = useState(resolve);
  useEffect(() => {
    setLabel(resolve());
    const id = setInterval(() => setLabel(resolve()), 30_000);
    return () => clearInterval(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sinceIso]);

  return label;
}
