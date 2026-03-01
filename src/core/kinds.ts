/**
 * Phase 11 – Single Source of Truth
 *
 * This file is the canonical list of event kinds recognized by iHouse Core.
 * Python adapters must consume a generated registry derived from this list.
 */

export const EVENT_KINDS = [
  "STATE_TRANSITION",
  "BOOKING_CONFLICT",
  "TASK_COMPLETION",
  "SLA_ESCALATION",
] as const;

export type EventKind = (typeof EVENT_KINDS)[number];

/**
 * Runtime guard: ensures a value is one of the known kinds.
 * Deterministic, no IO.
 */
export function isEventKind(v: unknown): v is EventKind {
  return typeof v === "string" && (EVENT_KINDS as readonly string[]).includes(v);
}
