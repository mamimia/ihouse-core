import { NextRequest, NextResponse } from 'next/server';

/**
 * POST /api/onboard — Public property onboarding endpoint
 * 
 * Creates a property with status='pending' (requires admin approval to activate).
 * Generates clean prefix-based IDs (e.g. DOM-001, KPG-002).
 * Checks for duplicate source_url before insert.
 */

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

const PUBLIC_ONBOARD_TENANT = 'public-onboard';

const supaFetch = (path: string, opts: RequestInit = {}) =>
    fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
        ...opts,
        headers: {
            'Content-Type': 'application/json',
            apikey: SUPABASE_ANON_KEY,
            Authorization: `Bearer ${SUPABASE_ANON_KEY}`,
            ...(opts.headers || {}),
        },
    });

/** Generate a clean prefix-based ID: DOM-001, KPG-002, etc. */
async function generateCleanId(): Promise<string> {
    // 1. Read current config
    const cfgRes = await supaFetch(
        `tenant_property_config?tenant_id=eq.${PUBLIC_ONBOARD_TENANT}&select=id_prefix,next_seq&limit=1`,
    );
    if (!cfgRes.ok) return `DOM-${Date.now().toString(36).slice(-4)}`;
    const [cfg] = await cfgRes.json();
    if (!cfg) return `DOM-${Date.now().toString(36).slice(-4)}`;

    const prefix = cfg.id_prefix || 'DOM';
    const seq = cfg.next_seq || 1;
    const paddedSeq = String(seq).padStart(3, '0');

    // 2. Atomically increment sequence
    await supaFetch(
        `tenant_property_config?tenant_id=eq.${PUBLIC_ONBOARD_TENANT}`,
        {
            method: 'PATCH',
            body: JSON.stringify({ next_seq: seq + 1 }),
        },
    );

    return `${prefix}-${paddedSeq}`;
}

export async function POST(request: NextRequest) {
    try {
        const body = await request.json();

        const propertyName = body.propertyName?.trim();
        if (!propertyName) {
            return NextResponse.json(
                { error: 'Property name is required' },
                { status: 400 },
            );
        }

        // ── Deduplication check ──
        const sourceUrl = body.sourceUrl?.trim() || null;
        if (sourceUrl) {
            const checkRes = await supaFetch(
                `properties?tenant_id=eq.${PUBLIC_ONBOARD_TENANT}&source_url=eq.${encodeURIComponent(sourceUrl)}&select=property_id,display_name,status,created_at&limit=1`,
            );
            if (checkRes.ok) {
                const existing = await checkRes.json();
                if (existing.length > 0) {
                    const ex = existing[0];
                    let message = '';
                    if (ex.status === 'archived') {
                        message = `This listing was previously connected but is now archived. Contact us to restore it.`;
                    } else if (ex.status === 'pending') {
                        message = `This listing is already submitted and pending review.`;
                    } else if (ex.status === 'rejected') {
                        message = `This listing was previously submitted. Contact us for more information.`;
                    } else {
                        message = `This listing is already connected to property "${ex.display_name}".`;
                    }
                    return NextResponse.json({
                        success: false,
                        conflict: true,
                        existing_property: ex,
                        message,
                    }, { status: 409 });
                }
            }
        }

        // ── Generate clean ID ──
        const propertyId = await generateCleanId();

        // ── Insert property as DRAFT (bound to user) ──
        const propertyData: Record<string, unknown> = {
            tenant_id: PUBLIC_ONBOARD_TENANT,
            property_id: propertyId,
            display_name: propertyName,
            status: 'draft',
            property_type: body.propertyType || null,
            city: body.city || null,
            country: body.country || null,
            max_guests: body.maxGuests ? parseInt(body.maxGuests, 10) : null,
            bedrooms: body.bedrooms ? parseInt(body.bedrooms, 10) : null,
            beds: body.beds ? parseInt(body.beds, 10) : null,
            bathrooms: body.bathrooms ? parseFloat(body.bathrooms) : null,
            address: body.address || null,
            description: body.description || null,
            source_url: sourceUrl,
            source_platform: body.sourcePlatform || null,
        };

        // Bind property to authenticated user if provided
        if (body.submitterUserId) {
            propertyData.submitter_user_id = body.submitterUserId;
        }
        if (body.submitterEmail) {
            propertyData.submitter_email = body.submitterEmail;
        }

        const propertyRes = await supaFetch('properties', {
            method: 'POST',
            headers: { Prefer: 'return=representation' },
            body: JSON.stringify(propertyData),
        });

        if (!propertyRes.ok) {
            const errorText = await propertyRes.text();
            console.error('[onboard] Property insert failed:', propertyRes.status, errorText);
            return NextResponse.json(
                { error: 'Failed to create property', detail: errorText },
                { status: 500 },
            );
        }

        const [createdProperty] = await propertyRes.json();

        // ── Insert photos ──
        const photos = body.photos || [];
        for (let i = 0; i < photos.length; i++) {
            try {
                await supaFetch('property_photos', {
                    method: 'POST',
                    headers: { Prefer: 'return=minimal' },
                    body: JSON.stringify({
                        tenant_id: PUBLIC_ONBOARD_TENANT,
                        property_id: propertyId,
                        photo_url: photos[i],
                        room_type: 'general',
                        sort_order: i,
                        is_hero: i === 0
                    }),
                });
            } catch (err) {
                console.warn('[onboard] Failed to save photo:', err);
            }
        }

        // ── Insert channel mappings ──
        const channels = body.channels || [];
        const channelResults = [];

        for (const ch of channels) {
            if (!ch.provider || !ch.url) continue;
            try {
                const chRes = await supaFetch('channel_map', {
                    method: 'POST',
                    headers: { Prefer: 'return=representation' },
                    body: JSON.stringify({
                        tenant_id: PUBLIC_ONBOARD_TENANT,
                        property_id: propertyId,
                        provider: ch.provider,
                        external_channel_id: ch.url,
                        active: true,
                    }),
                });
                if (chRes.ok) {
                    const [mapping] = await chRes.json();
                    channelResults.push({ provider: ch.provider, status: 'registered', id: mapping?.id });
                } else {
                    channelResults.push({ provider: ch.provider, status: 'error', detail: await chRes.text() });
                }
            } catch (chErr) {
                channelResults.push({ provider: ch.provider, status: 'error', detail: String(chErr) });
            }
        }

        // ── Formspree notification ──
        try {
            await fetch('https://formspree.io/f/mqaprpwn', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
                body: JSON.stringify({
                    _subject: `[Pending Review] New Property: ${propertyName} (${propertyId})`,
                    property_id: propertyId,
                    property_name: propertyName,
                    source_url: sourceUrl,
                    submitted_at: new Date().toISOString(),
                }),
            });
        } catch { /* non-critical */ }

        return NextResponse.json({
            success: true,
            persisted: true,
            property_id: propertyId,
            status: 'draft',
            property: createdProperty,
            channels: channelResults,
            message: `Property "${propertyName}" saved as draft.`,
        });

    } catch (err) {
        console.error('[onboard] Unexpected error:', err);
        return NextResponse.json(
            { error: 'Internal server error', detail: String(err) },
            { status: 500 },
        );
    }
}
