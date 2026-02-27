import { db } from "../db"
import { applyEvent } from "../router"

/**
 * Phase 4 – Deterministic Rebuild Engine
 * 
 * Guarantees:
 * - No direct state mutation outside event application
 * - Rebuild derives state ONLY from event log
 * - Deterministic replay order (created_at ASC)
 */

export async function resetProjections() {
  // ⚠ DO NOT delete events table
  await db.exec(`
    DELETE FROM bookings;
    DELETE FROM conflict_tasks;
    DELETE FROM booking_overrides;
    DELETE FROM notifications;
  `)
}

export async function replayAllEvents() {
  const events = await db.all(`
    SELECT * FROM events
    ORDER BY created_at ASC
  `)

  for (const event of events) {
    await applyEvent(event, { replay: true })
  }
}

export async function rebuildFromScratch() {
  console.log("Rebuild started...")

  await resetProjections()
  await replayAllEvents()

  console.log("Rebuild completed.")
}
