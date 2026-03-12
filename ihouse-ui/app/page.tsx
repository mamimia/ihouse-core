/**
 * Phase 287 — Frontend Foundation: Root Entry Point
 *
 * The app root redirects unauthenticated users to /login
 * and authenticated users to /dashboard.
 *
 * Middleware handles the actual auth check — this page
 * acts as a client-side redirect fallback for the root path.
 */
import { redirect } from 'next/navigation';

export default function RootPage() {
    // Middleware will intercept requests without a token and redirect to /login.
    // For authenticated users hitting '/', redirect to the main dashboard.
    redirect('/dashboard');
}
