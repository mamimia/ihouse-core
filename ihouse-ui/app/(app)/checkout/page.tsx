/**
 * Phase 554 — Redirect /checkout → /ops/checkout
 */
import { redirect } from 'next/navigation';

export default function CheckoutRedirect() {
    redirect('/ops/checkout');
}
