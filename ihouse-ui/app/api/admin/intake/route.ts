import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

/**
 * Admin Intake Queue API
 *
 * GET  /api/admin/intake — List all properties awaiting review (draft + pending_review)
 * POST /api/admin/intake — Approve or reject a property
 *
 * Admin-only: requires authenticated user with admin role.
 */

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

async function verifyAdmin(request: NextRequest) {
    const accessToken = request.headers.get('authorization')?.replace('Bearer ', '');
    if (!accessToken) return null;

    const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
    const { data: { user }, error } = await supabase.auth.getUser(accessToken);
    if (error || !user) return null;

    // Check admin role in user metadata or permissions
    const meta = user.user_metadata || {};
    const appMeta = user.app_metadata || {};
    const isAdmin = meta.role === 'admin' || appMeta.role === 'admin'
        || user.email === 'admin@domaniqo.com'
        || user.email === 'amir@domaniqo.com';

    return isAdmin ? user : null;
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
