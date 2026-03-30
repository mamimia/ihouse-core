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
        // Strip tracking query params — listing identity is in the URL path (e.g. /rooms/12345678).
        // This avoids PostgREST query-string breakage on URLs containing '&' and catches
        // re-submissions with different tracking suffixes (?s=76, ?unique_share_id=...).
        const sourceUrl = body.sourceUrl?.trim() || null;
        let canonicalSourceUrl: string | null = null;
        if (sourceUrl) {
            try {
                const parsed = new URL(sourceUrl);
                canonicalSourceUrl = `${parsed.origin}${parsed.pathname}`;
            } catch {
                canonicalSourceUrl = sourceUrl;
            }
        }
        if (canonicalSourceUrl) {
            // Match any existing record whose source_url starts with the canonical path
            // (covers both exact matches and records stored with different query params)
            const likePattern = encodeURIComponent(`${canonicalSourceUrl}%`);
            const checkRes = await supaFetch(
                `properties?tenant_id=eq.${PUBLIC_ONBOARD_TENANT}&source_url=like.${likePattern}&select=property_id,display_name,status,created_at,submitter_user_id&limit=1`,
            );
            if (checkRes.ok) {
                const existing = await checkRes.json();
                if (existing.length > 0) {
                    const ex = existing[0];
                    const isSameSubmitter = body.submitterUserId && ex.submitter_user_id === body.submitterUserId;
                    let message = '';
                    if (ex.status === 'draft') {
                        if (isSameSubmitter) {
                            message = `You already have a draft for this listing. View it in My Properties.`;
                        } else {
                            message = `This listing is already saved as a draft in the system. If you believe this is an error, please contact us.`;
                        }
                    } else if (ex.status === 'pending_review' || ex.status === 'pending') {
                        message = `This listing is already submitted and pending admin review.`;
                    } else if (ex.status === 'rejected') {
                        message = `This listing was previously submitted and rejected. Please contact us to resubmit.`;
                    } else if (ex.status === 'archived') {
                        message = `This listing was previously connected but is now archived. Contact us to restore it.`;
                    } else {
                        message = `This listing is already connected to property "${ex.display_name || ex.property_id}".`;
                    }
                    return NextResponse.json({
                        success: false,
                        conflict: true,
                        existing_property: { property_id: ex.property_id, display_name: ex.display_name, status: ex.status },
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
        // Submitter context — visible to admin in intake detail
        if (body.firstName) {
            propertyData.submitter_first_name = body.firstName;
        }
        if (body.lastName) {
            propertyData.submitter_last_name = body.lastName;
        }
        if (body.phone) {
            // Strip country-code-only values ("+ 66 ", "+66 ") — require at least 4 digits
            const phoneDigits = body.phone.replace(/\D/g, '');
            if (phoneDigits.length >= 4) {
                propertyData.submitter_phone = body.phone.trim();
            }
        }
        if (body.userType) {
            propertyData.submitter_user_type = body.userType;
        }
        if (body.portfolioSize) {
            propertyData.portfolio_size = body.portfolioSize;
        }

        const propertyRes = await supaFetch('properties', {
            method: 'POST',
            headers: { Prefer: 'return=representation' },
            body: JSON.stringify(propertyData),
        });

        if (!propertyRes.ok) {
            const errorText = await propertyRes.text();
            console.error('[onboard] Property insert failed:', propertyRes.status, errorText);
            // DB-level uniqueness violation (23505) — dedup check missed it (e.g. query param mismatch)
            // Surface as a conflict rather than a generic 500 so the UI shows a meaningful message.
            if (errorText.includes('23505') || errorText.includes('unique') || errorText.includes('duplicate')) {
                return NextResponse.json({
                    success: false,
                    conflict: true,
                    message: 'This listing URL is already registered in the system. If you believe this is an error, please contact us.',
                }, { status: 409 });
            }
            return NextResponse.json(
                { error: 'Failed to create property', detail: errorText },
                { status: 500 },
            );
        }

        const [createdProperty] = await propertyRes.json();

        // ── Insert photos into the new canonical table ──
        const photos = body.photos || [];
        for (let i = 0; i < photos.length; i++) {
            try {
                await supaFetch('property_marketing_photos', {
                    method: 'POST',
                    headers: { Prefer: 'return=minimal' },
                    body: JSON.stringify({
                        tenant_id: PUBLIC_ONBOARD_TENANT,
                        property_id: propertyId,
                        photo_url: photos[i],
                        display_order: i,
                        source: 'submitter',
                    }),
                });
            } catch (err) {
                console.warn('[onboard] Failed to save marketing photo:', err);
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
