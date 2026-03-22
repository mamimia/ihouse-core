/**
 * Phase 862 P46 — isCapabilityDenied helper
 *
 * Checks if an ApiError from apiFetch is a CAPABILITY_DENIED response.
 * Used in page-level error handling to show AccessDenied instead of
 * blank screens or redirect loops.
 *
 * Usage:
 *   try {
 *     const data = await api.getFinancialSummary(period);
 *   } catch (err) {
 *     if (isCapabilityDenied(err)) {
 *       setDeniedCapability('Financial');
 *       return;
 *     }
 *     // handle other errors
 *   }
 */

import { ApiError } from './api';

export function isCapabilityDenied(err: unknown): boolean {
  if (!(err instanceof ApiError)) return false;
  if (err.status !== 403) return false;
  const body = err.body as Record<string, unknown> | undefined;
  const detail = body?.detail;
  return typeof detail === 'string' && detail.startsWith('CAPABILITY_DENIED');
}

/**
 * Extract the capability name from a CAPABILITY_DENIED detail string.
 * Example: "CAPABILITY_DENIED:financial" → "Financial"
 */
export function extractDeniedCapability(err: unknown): string | null {
  if (!isCapabilityDenied(err)) return null;
  const body = (err as ApiError).body as Record<string, unknown> | undefined;
  const detail = body?.detail as string;
  const parts = detail.split(':');
  if (parts.length >= 2) {
    const cap = parts[1].trim();
    return cap.charAt(0).toUpperCase() + cap.slice(1);
  }
  return null;
}
