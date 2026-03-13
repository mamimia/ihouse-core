/**
 * Phase 179 — Next.js Route Guard Middleware
 *
 * Runs on every request (Edge Runtime).
 * Checks for 'ihouse_token' in the request cookies.
 * If not present on a protected route → redirect to /login.
 *
 * Public routes (no auth required):
 *   /login
 *   /_next/* (Next.js internals)
 *   /favicon.ico, /public assets
 *
 * Note: localStorage is not accessible in Edge Runtime.
 * The login page writes the token to a cookie as well as localStorage
 * so middleware can read it. The api.ts file reads from localStorage
 * for API calls (client-side only).
 */

import { NextRequest, NextResponse } from 'next/server';

// Routes that do NOT require auth — prefix-matched
const PUBLIC_PREFIXES = [
    '/login',
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
    // Exact match for root
    if (pathname === '/') return true;
    // Prefix match for all others
    return PUBLIC_PREFIXES.some(p => pathname.startsWith(p));
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
