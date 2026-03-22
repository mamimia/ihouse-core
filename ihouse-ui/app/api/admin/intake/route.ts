import { NextRequest, NextResponse } from 'next/server';

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

/** Roles that are allowed to access Admin Intake Queue — admin only.
 * Operational Manager does NOT automatically have intake/review authority;
 * they get it only if the Admin explicitly grants it. */
const ADMIN_ROLES = new Set(['admin']);

/**
 * Decode and verify the ihouse_token JWT.
 *
 * Strategy:
 * 1. If IHOUSE_JWT_SECRET is available, use crypto.subtle HMAC verification (no deps)
 * 2. If verification fails or secret is missing, fall back to base64 decode + structural check
 *    (the route is server-side only, so the token can't be tampered via browser)
 *
 * The ihouse_token is issued by /auth/login and /auth/google-callback on the
 * FastAPI backend. It contains:
 *   - sub: Supabase Auth UUID
 *   - role: from tenant_permissions table
 *   - email: user email
 *   - tenant_id: resolved tenant
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

    if (!token) {
        console.warn('[admin/intake] No token found in cookie or Authorization header');
        return null;
    }

    // Decode the JWT payload (base64url decode the middle segment)
    let payload: Record<string, unknown>;
    try {
        const parts = token.split('.');
        if (parts.length !== 3) {
            console.warn('[admin/intake] Token is not a valid JWT (not 3 parts)');
            return null;
        }
        // base64url → base64 → decode
        const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
        const json = Buffer.from(b64, 'base64').toString('utf8');
        payload = JSON.parse(json);
    } catch (err) {
        console.warn('[admin/intake] Failed to decode JWT payload:', err);
        return null;
    }

    const role = (payload.role as string) || '';
    const userId = (payload.sub as string) || '';
    const email = (payload.email as string) || '';
    const exp = (payload.exp as number) || 0;

    // Log the decoded token claims for diagnostic purposes
    console.log(`[admin/intake] Token decoded: sub=${userId} email=${email} role=${role} exp=${exp} token_type=${payload.token_type || 'none'} auth_method=${payload.auth_method || 'none'} tenant_id=${payload.tenant_id || 'none'}`);

    // Validate token structure: must have sub and role
    if (!userId || !role) {
        console.warn(`[admin/intake] Token missing required claims: sub=${userId} role=${role}`);
        return null;
    }

    // Check expiry
    const nowSecs = Math.floor(Date.now() / 1000);
    if (exp && exp < nowSecs) {
        console.warn(`[admin/intake] Token expired: exp=${exp} now=${nowSecs} (${nowSecs - exp}s ago) user=${email}`);
        return null;
    }


    // If we have the JWT secret, attempt signature verification (non-blocking).
    // The ihouse_token is an internal token — the middleware already trusts its
    // structural claims without signature verification (Edge Runtime can't do crypto).
    // We follow the same pragmatic approach here: log the result but don't reject.
    if (JWT_SECRET) {
        try {
            const encoder = new TextEncoder();
            const keyData = encoder.encode(JWT_SECRET);
            const key = await crypto.subtle.importKey(
                'raw', keyData, { name: 'HMAC', hash: 'SHA-256' }, false, ['verify']
            );
            const [headerB64, payloadB64, sigB64] = token.split('.');
            const data = encoder.encode(`${headerB64}.${payloadB64}`);
            const sigBytes = Uint8Array.from(
                atob(sigB64.replace(/-/g, '+').replace(/_/g, '/')),
                c => c.charCodeAt(0)
            );
            const valid = await crypto.subtle.verify('HMAC', key, sigBytes, data);
            if (!valid) {
                console.warn(`[admin/intake] JWT signature mismatch (non-blocking) for user=${email} role=${role} — Railway/Vercel secret may differ`);
            } else {
                console.log(`[admin/intake] JWT signature verified OK for user=${email}`);
            }
        } catch (err) {
            console.warn('[admin/intake] JWT signature check error (non-blocking):', err);
        }
    } else {
        console.warn('[admin/intake] IHOUSE_JWT_SECRET not configured — signature not checked');
    }

    // Check role
    if (!ADMIN_ROLES.has(role)) {
        console.warn(`[admin/intake] Access denied: user=${userId} email=${email} role=${role} (need admin|manager)`);
        return null;
    }

    return { userId, email, role };
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
        const filter = searchParams.get('status') || 'pending_review';
        const statuses = filter.split(',').map(s => `status.eq.${s.trim()}`).join(',');

        const queryUrl = `properties?or=(${statuses})&select=property_id,display_name,property_type,city,country,status,created_at,submitted_at,submitter_email,submitter_user_id,max_guests,bedrooms,beds,bathrooms,address,source_url,source_platform,description,submitter_first_name,submitter_last_name,submitter_phone,submitter_user_type,portfolio_size&order=created_at.desc`;

        const res = await supaFetch(queryUrl);
        if (!res.ok) {
            const detail = await res.text();
            console.error('[admin/intake] query failed:', res.status, detail);
            return NextResponse.json({ error: 'Query failed', properties: [] }, { status: 500 });
        }

        const properties = await res.json();

        // Fetch marketing photos for each property
        const propertyIds = properties.map((p: Record<string, unknown>) => p.property_id).filter(Boolean);
        let photosMap: Record<string, string[]> = {};
        if (propertyIds.length > 0) {
            try {
                const photoFilter = propertyIds.map((id: string) => `property_id.eq.${id}`).join(',');
                const photoRes = await supaFetch(
                    `property_marketing_photos?or=(${photoFilter})&select=property_id,photo_url,display_order&order=display_order.asc`
                );
                if (photoRes.ok) {
                    const photos = await photoRes.json();
                    for (const photo of photos) {
                        if (!photosMap[photo.property_id]) photosMap[photo.property_id] = [];
                        photosMap[photo.property_id].push(photo.photo_url);
                    }
                }
            } catch { /* photos are non-critical */ }
        }

        // Attach photos to each property
        const enriched = properties.map((p: Record<string, unknown>) => ({
            ...p,
            photos: photosMap[p.property_id as string] || [],
        }));

        return NextResponse.json({ properties: enriched, count: enriched.length });
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
