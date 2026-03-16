/**
 * Phase 179 — Next.js Route Guard Middleware
 * Phase 397 — JWT Role Enforcement
 *
 * Runs on every request (Edge Runtime).
 * 1. Public routes — no auth required.
 * 2. Protected routes — require ihouse_token cookie.
 * 3. Role enforcement — JWT role claim restricts route access.
 *
 * Role hierarchy:
 *   admin / manager → full access
 *   owner           → /owner, /dashboard
 *   worker          → /worker, /ops, /tasks, /maintenance, /checkin, /checkout
 *   ops             → /ops, /dashboard, /bookings, /tasks, /calendar
 *   checkin         → /checkin only
 *   checkout        → /checkout only
 *   maintenance     → /maintenance, /worker
 */

import { NextRequest, NextResponse } from 'next/server';

// Routes that do NOT require auth — prefix-matched
const PUBLIC_PREFIXES = [
    '/login',
    '/register',
    '/auth',
    '/favicon.ico',
    '/about',
    '/channels',
    '/early-access',
    '/inbox',
    '/platform',
    '/pricing',
    '/reviews',
    '/onboard',
    '/guest',
    '/invite',
];

function isPublicRoute(pathname: string): boolean {
    if (pathname === '/') return true;
    return PUBLIC_PREFIXES.some(p => pathname.startsWith(p));
}

// Phase 397: Role-to-allowed-route-prefix mapping
// admin/manager have full access (not listed — they bypass checks)
const ROLE_ALLOWED_PREFIXES: Record<string, string[]> = {
    owner:       ['/owner', '/dashboard'],
    worker:      ['/worker', '/ops', '/tasks', '/maintenance', '/checkin', '/checkout'],
    ops:         ['/ops', '/dashboard', '/bookings', '/tasks', '/calendar', '/guests'],
    checkin:     ['/checkin'],
    checkout:    ['/checkout'],
    maintenance: ['/maintenance', '/worker'],
};

// Roles that have unrestricted access
const FULL_ACCESS_ROLES = new Set(['admin', 'manager']);

/** Decode JWT payload without verification (Edge Runtime can't use node crypto). */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
    try {
        const parts = token.split('.');
        if (parts.length !== 3) return null;
        // Base64url → Base64
        const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
        const json = atob(base64);
        return JSON.parse(json);
    } catch {
        return null;
    }
}

export function middleware(request: NextRequest) {
    const { pathname } = request.nextUrl;

    // Always allow public paths and Next.js internals
    if (
        isPublicRoute(pathname) ||
        pathname.startsWith('/_next/') ||
        pathname.startsWith('/api/')
    ) {
        return NextResponse.next();
    }

    // Check for auth token in cookies
    const token = request.cookies.get('ihouse_token')?.value;

    if (!token) {
        const loginUrl = new URL('/login', request.url);
        loginUrl.searchParams.set('from', pathname);
        return NextResponse.redirect(loginUrl);
    }

    // Phase 397: Role enforcement
    const payload = decodeJwtPayload(token);
    const role = (typeof payload?.role === 'string' ? payload.role : '').toLowerCase();

    // If role is admin/manager or empty (legacy token), allow everything
    if (!role || FULL_ACCESS_ROLES.has(role)) {
        return NextResponse.next();
    }

    // Check if the role has access to this route
    const allowedPrefixes = ROLE_ALLOWED_PREFIXES[role];
    if (allowedPrefixes) {
        const hasAccess = allowedPrefixes.some(prefix => pathname.startsWith(prefix));
        if (!hasAccess) {
            // Redirect to role's default page instead of showing forbidden
            const defaultRoute = allowedPrefixes[0] || '/dashboard';
            return NextResponse.redirect(new URL(defaultRoute, request.url));
        }
    }

    return NextResponse.next();
}

export const config = {
    matcher: [
        /*
         * Match all request paths EXCEPT:
         * - _next/static (static files)
         * - _next/image (image optimization)
         * - favicon.ico
         */
        '/((?!_next/static|_next/image|favicon.ico).*)',
    ],
};
