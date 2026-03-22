/**
 * POST /api/listing/fetch
 *
 * Lightweight proxy to the backend's listing preview extraction endpoint.
 * Used by the onboarding wizard to extract property data from a listing URL
 * before a property record exists.
 *
 * The backend does the actual OG/JSON-LD/embedded-data extraction — this
 * route simply proxies the request so the public wizard can use it without
 * auth (the backend preview endpoint is also unauthenticated).
 */

import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');

export async function POST(request: NextRequest) {
    try {
        const body = await request.json();
        const listingUrl = body.listing_url || body.url;

        if (!listingUrl) {
            return NextResponse.json(
                { success: false, error: 'listing_url is required' },
                { status: 400 },
            );
        }

        const backendRes = await fetch(`${API_BASE}/listing/preview-extract`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ listing_url: listingUrl }),
        });

        const data = await backendRes.json();

        // Transform backend response to wizard-compatible format
        const imported = data.imported || {};
        const extracted: Record<string, unknown> = {};

        if (imported.name) extracted.display_name = imported.name;
        if (imported.description) extracted.description = imported.description;
        if (imported.city) extracted.city = imported.city;
        if (imported.country) extracted.country = imported.country;
        if (imported.address) extracted.address = imported.address;
        if (imported.max_guests) extracted.max_guests = imported.max_guests;
        if (imported.bedrooms !== undefined) extracted.bedrooms = imported.bedrooms;
        if (imported.beds) extracted.beds = imported.beds;
        if (imported.bathrooms) extracted.bathrooms = imported.bathrooms;
        if (imported.photos) extracted.photos = imported.photos;

        // Detect platform from URL
        let sourcePlatform = '';
        if (/airbnb\./i.test(listingUrl)) sourcePlatform = 'airbnb';
        else if (/booking\.com/i.test(listingUrl)) sourcePlatform = 'booking';
        else if (/vrbo\.|abritel\.|stayz\./i.test(listingUrl)) sourcePlatform = 'vrbo';

        const hasData = Object.keys(extracted).length > 0;

        return NextResponse.json({
            success: hasData,
            extracted: hasData ? extracted : undefined,
            source_platform: sourcePlatform,
            warning: data.warning || null,
            could_not_import: data.could_not_import || [],
        });
    } catch (err) {
        console.error('[listing/fetch] Error:', err);
        return NextResponse.json(
            { success: false, error: 'Extraction failed. Please fill in details manually.' },
            { status: 500 },
        );
    }
}
