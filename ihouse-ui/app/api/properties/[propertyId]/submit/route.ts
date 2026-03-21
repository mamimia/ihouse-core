import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

/**
 * PATCH /api/properties/[propertyId]/submit — Submit draft for review
 *
 * Sets status from 'draft' → 'pending_review'.
 * Requires authenticated user who owns the property.
 */

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export async function PATCH(
    request: NextRequest,
    { params }: { params: Promise<{ propertyId: string }> },
) {
    try {
        const { propertyId } = await params;
        const accessToken = request.headers.get('authorization')?.replace('Bearer ', '');
        if (!accessToken) {
            return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
        }

        const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
        const { data: { user }, error: userError } = await supabase.auth.getUser(accessToken);
        if (userError || !user) {
            return NextResponse.json({ error: 'Invalid session' }, { status: 401 });
        }

        // Verify ownership
        const queryUrl = `${SUPABASE_URL}/rest/v1/properties?property_id=eq.${encodeURIComponent(propertyId)}&submitter_user_id=eq.${user.id}&select=property_id,status&limit=1`;
        const checkRes = await fetch(queryUrl, {
            headers: {
                apikey: SUPABASE_SERVICE_ROLE_KEY,
                Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
            },
        });

        if (!checkRes.ok) {
            return NextResponse.json({ error: 'Query failed' }, { status: 500 });
        }

        const [property] = await checkRes.json();
        if (!property) {
            return NextResponse.json({ error: 'Property not found or not owned by you' }, { status: 404 });
        }
        if (property.status !== 'draft') {
            return NextResponse.json({ error: `Cannot submit: status is '${property.status}'` }, { status: 409 });
        }

        // Update status
        const updateUrl = `${SUPABASE_URL}/rest/v1/properties?property_id=eq.${encodeURIComponent(propertyId)}`;
        const updateRes = await fetch(updateUrl, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                apikey: SUPABASE_SERVICE_ROLE_KEY,
                Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
                Prefer: 'return=representation',
            },
            body: JSON.stringify({
                status: 'pending_review',
                submitted_at: new Date().toISOString(),
            }),
        });

        if (!updateRes.ok) {
            const detail = await updateRes.text();
            console.error('[submit] Update failed:', updateRes.status, detail);
            return NextResponse.json({ error: 'Update failed' }, { status: 500 });
        }

        return NextResponse.json({ success: true, status: 'pending_review' });
    } catch (err) {
        console.error('[submit] error:', err);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
