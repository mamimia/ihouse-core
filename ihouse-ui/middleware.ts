/**
 * Phase 179 — Next.js Route Guard Middleware
 * Phase 397 — JWT Role Enforcement
 * Phase 836 — Access Hardening (cleaner restriction + dev-login public)
 *
 * Runs on every request (Edge Runtime).
 * 1. Public routes — no auth required.
 * 2. Protected routes — require ihouse_token cookie.
 * 3. Role enforcement — JWT role claim restricts route access.
 *
 * Role hierarchy:
 *   admin / manager  → full access
 *   owner            → /owner, /dashboard
 *   worker           → /worker, /ops, /tasks, /maintenance, /checkin, /checkout
 *   cleaner          → /worker, /ops
 *   ops              → /ops, /dashboard, /bookings, /tasks, /calendar
 *   checkin          → /checkin only
 *   checkout         → /checkout only
 *   maintenance      → /maintenance, /worker
 *   identity_only    → /welcome, /profile, /get-started, /my-properties (Phase 862 P28)
 */

import { NextRequest, NextResponse } from 'next/server';

// Routes that do NOT require auth — prefix-matched
const PUBLIC_PREFIXES = [
    '/login',
    '/dev-login',     // Phase 831: worker-family roles need a production login path
    '/register',      // Phase 871: standalone sign-up (identity-only account creation)
    '/auth',
    '/favicon.ico',
    '/about',
    '/channels',
    '/early-access',  // Phase 858: redirects to /get-started (kept public for redirect to work)
    '/get-started',   // Phase 858: canonical public intake wizard
    '/no-access',     // Phase 856B: authenticated-but-unbound landing
    '/inbox',
    '/platform',
    '/pricing',
    '/privacy',       // Phase 860: public legal page
    '/terms',         // Phase 860: public legal page
    '/reviews',
    '/onboard',       // Phase 858: /onboard/connect property wizard (future: auth-gate inside)
    '/profile',        // Phase 862 P19: shared profile page for all authenticated users
    '/my-properties',  // Phase 858: post-auth draft management (client-side auth check)
    '/welcome',        // Phase 862 P28: identity-only user landing
    '/guest',
    '/invite',
    '/staff',
];

function isPublicRoute(pathname: string): boolean {
    if (pathname === '/') return true;
    return PUBLIC_PREFIXES.some(p => pathname.startsWith(p));
}

// Phase 397: Role-to-allowed-route-prefix mapping
// admin/manager have full access (not listed — they bypass checks)
const ROLE_ALLOWED_PREFIXES: Record<string, string[]> = {
    owner:         ['/owner', '/dashboard'],
    worker:        ['/worker', '/ops', '/maintenance', '/checkin', '/checkout'],
    cleaner:       ['/worker', '/ops'],  // Phase 831: restrict cleaner to worker + ops surfaces only
    ops:           ['/ops', '/dashboard', '/bookings', '/tasks', '/calendar', '/guests'],
    checkin:       ['/checkin', '/ops/checkin'],
    checkout:      ['/checkout', '/ops/checkout'],
    maintenance:   ['/maintenance', '/worker'],
    identity_only: ['/welcome', '/profile', '/get-started', '/my-properties'],  // Phase 862 P28
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
    
    // Check if the user is deactivated
    if (payload?.is_active === false) {
        if (pathname !== '/deactivated') {
            return NextResponse.redirect(new URL('/deactivated', request.url));
        }
        return NextResponse.next();
    }
    
    // If they are on deactivated but are active, redirect to dashboard
    if (pathname === '/deactivated' && payload?.is_active !== false) {
        return NextResponse.redirect(new URL('/dashboard', request.url));
    }

    // Check if they need a forced password reset
    if (payload?.force_reset === true) {
        if (pathname !== '/update-password') {
            return NextResponse.redirect(new URL('/update-password', request.url));
        }
        return NextResponse.next();
    }
    if (pathname === '/update-password' && payload?.force_reset !== true) {
        return NextResponse.redirect(new URL('/dashboard', request.url));
    }

    const role = (typeof payload?.role === 'string' ? payload.role : '').toLowerCase();

    // Phase 862 (Canonical Auth P4): empty/missing role → /no-access
    // Previously, legacy tokens with no role claim got unrestricted admin access.
    // Now, only explicit admin/manager roles get full access.
    if (!role) {
        if (pathname !== '/no-access') {
            return NextResponse.redirect(new URL('/no-access', request.url));
        }
        return NextResponse.next();
    }

    // If role is admin/manager, allow everything
    if (FULL_ACCESS_ROLES.has(role)) {
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

    // Phase 862 P23: Forward identity claims as headers for downstream pages
    const response = NextResponse.next();
    const tenantId = typeof payload?.tenant_id === 'string' ? payload.tenant_id : '';
    if (tenantId) {
        response.headers.set('x-tenant-id', tenantId);
    }
    response.headers.set('x-user-role', role);
    return response;
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
