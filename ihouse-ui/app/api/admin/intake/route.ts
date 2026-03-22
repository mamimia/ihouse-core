import { NextRequest, NextResponse } from 'next/server';
import * as jose from 'jose';

/**
 * Admin Intake Queue API
 *
 * GET  /api/admin/intake — List all properties awaiting review (draft + pending_review)
 * POST /api/admin/intake — Approve or reject a property
 *
 * Authorization: uses the canonical ihouse_token JWT (same source as the sidebar).
 * The JWT contains role from tenant_permissions — no email-based shortcuts.
 *
 * Admin-only: requires role === 'admin' or role === 'manager' in ihouse_token.
 */

export const dynamic = 'force-dynamic';

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

/** IHOUSE_JWT_SECRET — must match the backend that issues ihouse_token */
const JWT_SECRET = process.env.IHOUSE_JWT_SECRET || '';

/** Roles that are allowed to access Admin Intake Queue */
const ADMIN_ROLES = new Set(['admin', 'manager']);

/**
 * Verify admin access using the canonical ihouse_token JWT.
 *
 * The ihouse_token is issued by /auth/login and /auth/google-callback on the
 * FastAPI backend. It contains:
 *   - sub: Supabase Auth UUID
 *   - role: from tenant_permissions table
 *   - email: user email
 *   - tenant_id: resolved tenant
 *
 * This is the SAME token the sidebar uses to decide what nav items to show.
 * By verifying this token here, the admin intake API and sidebar agree on
 * exactly the same role source of truth: tenant_permissions.
 */
async function verifyAdmin(request: NextRequest): Promise<{ userId: string; email: string; role: string } | null> {
    // 1. Try ihouse_token from cookie first (set during login)
    let token = request.cookies.get('ihouse_token')?.value;

    // 2. Fall back to Authorization header
    if (!token) {
        const authHeader = request.headers.get('authorization');
        if (authHeader?.startsWith('Bearer ')) {
            token = authHeader.slice(7);
        }
    }

    if (!token) return null;
    if (!JWT_SECRET) {
        console.error('[admin/intake] IHOUSE_JWT_SECRET not configured');
        return null;
    }

    try {
        const secret = new TextEncoder().encode(JWT_SECRET);
        const { payload } = await jose.jwtVerify(token, secret, { algorithms: ['HS256'] });

        const role = (payload.role as string) || '';
        const userId = (payload.sub as string) || '';
        const email = (payload.email as string) || '';

        if (!ADMIN_ROLES.has(role)) {
            console.warn(`[admin/intake] Access denied: user=${userId} email=${email} role=${role} (need admin|manager)`);
            return null;
        }

        return { userId, email, role };
    } catch (err) {
        console.warn('[admin/intake] JWT verification failed:', err);
        return null;
    }
}

function supaFetch(path: string, opts: RequestInit = {}) {
    return fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
        ...opts,
        headers: {
            'Content-Type': 'application/json',
            apikey: SUPABASE_SERVICE_ROLE_KEY,
            Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
            ...(opts.headers || {}),
        },
    });
}

export async function GET(request: NextRequest) {
    try {
        const admin = await verifyAdmin(request);
        if (!admin) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
        }

        const { searchParams } = new URL(request.url);
        const filter = searchParams.get('status') || 'pending_review,draft';
        const statuses = filter.split(',').map(s => `status.eq.${s.trim()}`).join(',');

        const queryUrl = `properties?or=(${statuses})&select=property_id,display_name,property_type,city,country,status,created_at,submitted_at,submitter_email,submitter_user_id,max_guests,bedrooms,source_url,source_platform,description&order=created_at.desc`;

        const res = await supaFetch(queryUrl);
        if (!res.ok) {
            const detail = await res.text();
            console.error('[admin/intake] query failed:', res.status, detail);
            return NextResponse.json({ error: 'Query failed', properties: [] }, { status: 500 });
        }

        const properties = await res.json();
        return NextResponse.json({ properties, count: properties.length });
    } catch (err) {
        console.error('[admin/intake] error:', err);
        return NextResponse.json({ error: 'Internal server error', properties: [] }, { status: 500 });
    }
}

export async function POST(request: NextRequest) {
    try {
        const admin = await verifyAdmin(request);
        if (!admin) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
        }

        const body = await request.json();
        const { propertyId, action, rejectionReason } = body;

        if (!propertyId || !['approve', 'reject'].includes(action)) {
            return NextResponse.json(
                { error: 'propertyId and action (approve|reject) required' },
                { status: 400 },
            );
        }

        const updateData: Record<string, unknown> = action === 'approve'
            ? {
                status: 'active',
                approved_at: new Date().toISOString(),
                approved_by: admin.email,
            }
            : {
                status: 'rejected',
                rejected_at: new Date().toISOString(),
                rejected_by: admin.email,
                rejection_reason: rejectionReason || null,
            };

        const updateUrl = `properties?property_id=eq.${encodeURIComponent(propertyId)}`;
        const res = await supaFetch(updateUrl, {
            method: 'PATCH',
            headers: { Prefer: 'return=representation' },
            body: JSON.stringify(updateData),
        });

        if (!res.ok) {
            const detail = await res.text();
            console.error('[admin/intake] update failed:', res.status, detail);
            return NextResponse.json({ error: 'Update failed', detail }, { status: 500 });
        }

        const [updated] = await res.json();
        return NextResponse.json({
            success: true,
            property_id: propertyId,
            action,
            new_status: updated?.status,
        });
    } catch (err) {
        console.error('[admin/intake] error:', err);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
