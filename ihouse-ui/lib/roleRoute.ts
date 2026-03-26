/**
 * Phase 392 — Role-Based Route Mapping
 * Phase 948a — Worker sub-role routing fix
 *
 * Determines the landing page after login based on user role.
 * Called after auth to redirect users to their role-appropriate surface.
 *
 * For `role=worker`, reads `worker_role` (or `worker_roles[0]`) from the JWT
 * to determine the correct role-specific surface. Without this, all workers
 * landed on /worker which rendered the combined check-in/check-out view.
 */

interface RolePayload {
    role?: string;
    user_role?: string;
    worker_role?: string;
    worker_roles?: string[];
}

/** Attempts to decode the JWT payload and extract role claims. */
function getPayloadFromToken(token: string): RolePayload | null {
    try {
        const parts = token.split('.');
        if (parts.length !== 3) return null;
        return JSON.parse(atob(parts[1])) as RolePayload;
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
    cleaner: '/ops/cleaner',           // Phase 836: cleaner lands on dedicated cleaning surface
    maintenance: '/ops/maintenance',
    checkin: '/ops/checkin',
    checkout: '/ops/checkout',
    checkin_checkout: '/ops/checkin-checkout',
    owner: '/owner',
    identity_only: '/welcome',         // Phase 862 P28: identity-only users land on welcome page
};

/** Returns the best landing route for the authenticated user. */
export function getRoleRoute(token?: string): string {
    if (!token) return '/dashboard';
    const p = getPayloadFromToken(token);
    if (!p) return '/dashboard';

    const outerRole = (p.role ?? p.user_role ?? '').toLowerCase();

    // Phase 948a: For `role=worker`, fall through to the worker's actual sub-role.
    // This ensures cleaners land on /ops/cleaner, not the generic /worker+combined view.
    if (outerRole === 'worker') {
        const subRole = (p.worker_role || (p.worker_roles ?? [])[0] || '').toLowerCase();
        if (subRole && ROLE_ROUTES[subRole]) {
            return ROLE_ROUTES[subRole];
        }
        return ROLE_ROUTES['worker'];  // fallback: generic worker home
    }

    return ROLE_ROUTES[outerRole] ?? '/dashboard';
}

export default getRoleRoute;
