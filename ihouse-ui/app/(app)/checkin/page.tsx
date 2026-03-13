/**
 * Phase 554 — Redirect /checkin → /ops/checkin
 */
import { redirect } from 'next/navigation';

export default function CheckinRedirect() {
    redirect('/ops/checkin');
}
