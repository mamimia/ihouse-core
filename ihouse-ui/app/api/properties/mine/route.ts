import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

/**
 * GET /api/properties/mine — Authenticated user's properties
 *
 * Reads the Supabase auth session from the Authorization header
 * and returns properties where submitter_user_id matches the user.
 */

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export async function GET(request: NextRequest) {
    try {
        // Get the access token from Authorization header or cookies
        let accessToken = request.headers.get('authorization')?.replace('Bearer ', '');

        if (!accessToken) {
            // Try to get from Supabase auth cookies
            const cookies = request.cookies;
            const sbAccessToken = cookies.get('sb-access-token')?.value
                || cookies.get(`sb-${new URL(SUPABASE_URL).hostname.split('.')[0]}-auth-token`)?.value;
            if (sbAccessToken) {
                try {
                    const parsed = JSON.parse(sbAccessToken);
                    accessToken = parsed?.access_token || parsed;
                } catch {
                    accessToken = sbAccessToken;
                }
            }
        }

        if (!accessToken) {
            return NextResponse.json(
                { error: 'Not authenticated', properties: [] },
                { status: 401 },
            );
        }

        // Verify the user from the access token
        const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
        const { data: { user }, error: userError } = await supabase.auth.getUser(accessToken);

        if (userError || !user) {
            return NextResponse.json(
                { error: 'Invalid session', properties: [] },
                { status: 401 },
            );
        }

        // Query properties by submitter_user_id
        const queryUrl = `${SUPABASE_URL}/rest/v1/properties?submitter_user_id=eq.${user.id}&select=property_id,display_name,property_type,city,country,status,created_at,max_guests,bedrooms,source_url&order=created_at.desc`;

        const res = await fetch(queryUrl, {
            headers: {
                apikey: SUPABASE_SERVICE_ROLE_KEY,
                Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
            },
        });

        if (!res.ok) {
            const detail = await res.text();
            console.error('[properties/mine] query failed:', res.status, detail);
            // If the column doesn't exist yet, return empty gracefully
            if (detail.includes('submitter_user_id') && detail.includes('does not exist')) {
                return NextResponse.json({ properties: [], migration_pending: true });
            }
            return NextResponse.json({ error: 'Query failed', properties: [] }, { status: 500 });
        }

        const rows = await res.json();

        // ── Lazy 90-day draft expiration ──
        // Drafts older than 90 days from creation are auto-expired.
        const NINETY_DAYS_MS = 90 * 24 * 60 * 60 * 1000;
        const now = Date.now();
        const expiredIds: string[] = [];
        for (const r of rows) {
            if (r.status === 'draft' && r.created_at) {
                const age = now - new Date(r.created_at).getTime();
                if (age > NINETY_DAYS_MS) {
                    expiredIds.push(r.property_id);
                    r.status = 'expired'; // Update local copy immediately
                }
            }
        }

        // Batch-expire old drafts in DB (fire-and-forget)
        if (expiredIds.length > 0) {
            for (const pid of expiredIds) {
                fetch(`${SUPABASE_URL}/rest/v1/properties?property_id=eq.${encodeURIComponent(pid)}&status=eq.draft`, {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json',
                        apikey: SUPABASE_SERVICE_ROLE_KEY,
                        Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
                    },
                    body: JSON.stringify({
                        status: 'expired',
                        archived_at: new Date().toISOString(),
                        archived_by: 'system:90-day-expiration',
                    }),
                }).catch(() => { /* non-critical */ });
            }
        }

        // Map to frontend shape
        const properties = rows.map((r: Record<string, unknown>) => ({
            id: r.property_id,
            name: r.display_name,
            property_type: r.property_type,
            city: r.city,
            country: r.country,
            status: r.status,
            created_at: r.created_at,
            max_guests: r.max_guests,
            bedrooms: r.bedrooms,
            source_url: r.source_url,
        }));

        return NextResponse.json({ properties, user_id: user.id, email: user.email });
    } catch (err) {
        console.error('[properties/mine] error:', err);
        return NextResponse.json(
            { error: 'Internal server error', properties: [] },
            { status: 500 },
        );
    }
}

