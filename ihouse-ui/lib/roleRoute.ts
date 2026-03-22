/**
 * Phase 392 — Role-Based Route Mapping
 *
 * Determines the landing page after login based on user role.
 * Called after auth to redirect users to their role-appropriate surface.
 *
 * Role is derived from JWT `role` claim. If absent, falls back to /dashboard (admin default).
 */

/** Attempts to decode the JWT payload and extract a role claim. */
function getRoleFromToken(token: string): string | null {
    try {
        const parts = token.split('.');
        if (parts.length !== 3) return null;
        const payload = JSON.parse(atob(parts[1]));
        return payload.role ?? payload.user_role ?? null;
    } catch {
        return null;
    }
}

/** Maps a role string to the landing route. */
const ROLE_ROUTES: Record<string, string> = {
    admin: '/dashboard',
    manager: '/dashboard',
    ops: '/ops',
    operations: '/ops',
    worker: '/worker',
    cleaner: '/ops/cleaner',   // Phase 836: cleaner lands on dedicated cleaning surface
    maintenance: '/maintenance',
    checkin: '/checkin',
    checkout: '/checkout',
    owner: '/owner',
    identity_only: '/welcome', // Phase 862 P28: identity-only users land on welcome page
};

/** Returns the best landing route for the authenticated user. */
export function getRoleRoute(token?: string): string {
    if (!token) return '/dashboard';
    const role = getRoleFromToken(token);
    if (!role) return '/dashboard';
    return ROLE_ROUTES[role.toLowerCase()] ?? '/dashboard';
}

export default getRoleRoute;
