/**
 * POST /api/listing/extract
 *
 * Accepts { url: string } and attempts to extract property fields from
 * the public Airbnb listing page using Playwright (headless Chromium).
 *
 * Returns extracted fields + per-field confidence.  If extraction fails
 * or the URL is unsupported the endpoint returns { success: false } so
 * the wizard can fall back to manual entry.
 *
 * V1 scope: Airbnb only.
 */

import { NextRequest, NextResponse } from 'next/server';

/* ──────── helpers ──────── */

function detectPlatform(url: string): string | null {
    if (/airbnb\./i.test(url)) return 'airbnb';
    if (/booking\.com/i.test(url)) return 'booking';
    if (/vrbo\.|abritel\.|fewo-direkt\.|stayz\./i.test(url)) return 'vrbo';
    return null;
}

/** Map Airbnb "Entire home", "Private room", etc. → our property_type values */
function mapPropertyType(raw: string): string {
    const lower = raw.toLowerCase();
    if (lower.includes('villa')) return 'villa';
    if (lower.includes('apartment') || lower.includes('condo') || lower.includes('flat')) return 'apartment';
    if (lower.includes('house') || lower.includes('home') || lower.includes('cottage')) return 'house';
    if (lower.includes('room')) return 'room';
    if (lower.includes('loft')) return 'loft';
    if (lower.includes('cabin')) return 'cabin';
    if (lower.includes('bungalow')) return 'bungalow';
    return 'house'; // default
}

/** Parse "4 guests · 2 bedrooms · 2 beds · 2.5 baths" style text */
function parseCapacity(text: string): {
    guests?: number;
    bedrooms?: number;
    beds?: number;
    bathrooms?: number;
} {
    const result: Record<string, number> = {};
    const normalized = text.toLowerCase().replace(/\s+/g, ' ');

    const guestMatch = normalized.match(/(\d+)\s*guest/);
    if (guestMatch) result.guests = parseInt(guestMatch[1], 10);

    const bedroomMatch = normalized.match(/(\d+)\s*bedroom/);
    if (bedroomMatch) result.bedrooms = parseInt(bedroomMatch[1], 10);

    // "Studio" counts as 0 bedrooms
    if (/studio/i.test(normalized) && !result.bedrooms) result.bedrooms = 0;

    const bedMatch = normalized.match(/(\d+)\s*bed(?!room)/);
    if (bedMatch) result.beds = parseInt(bedMatch[1], 10);

    const bathMatch = normalized.match(/([\d.]+)\s*bath/);
    if (bathMatch) result.bathrooms = parseFloat(bathMatch[1]);

    return result;
}

/** Extract city / country from Airbnb title pattern:
 *  "Property Name - Type for Rent in City, Region, Country"  */
function parseLocation(title: string): { city?: string; country?: string; region?: string } {
    // Pattern: "... in City, Region, Country - Airbnb"
    const inMatch = title.match(/\bin\s+(.+?)(?:\s*-\s*Airbnb)?$/i);
    if (!inMatch) return {};

    const parts = inMatch[1].split(',').map(p => p.trim());
    if (parts.length >= 3) {
        return { city: parts[0], region: parts[1], country: parts[2] };
    } else if (parts.length === 2) {
        return { city: parts[0], country: parts[1] };
    } else if (parts.length === 1) {
        return { city: parts[0] };
    }
    return {};
}

/* ──────── main handler ──────── */

export async function POST(request: NextRequest) {
    try {
        const body = await request.json();
        const url = body.url?.trim();

        if (!url) {
            return NextResponse.json({ success: false, error: 'URL is required' }, { status: 400 });
        }

        const platform = detectPlatform(url);
        if (platform !== 'airbnb') {
            return NextResponse.json({
                success: false,
                error: platform
                    ? `${platform} parsing is not yet supported. Only Airbnb is available in V1.`
                    : 'Unsupported URL. Please provide an Airbnb listing URL.',
            }, { status: 400 });
        }

        // Dynamic import of playwright to avoid bundling issues
        let chromium;
        try {
            const pw = await import('playwright');
            chromium = pw.chromium;
        } catch {
            console.error('[extract] Playwright not available');
            return NextResponse.json({
                success: false,
                error: 'Parser engine not available. Please fill in property details manually.',
            }, { status: 503 });
        }

        // Launch headless browser
        const browser = await chromium.launch({ headless: true });
        const context = await browser.newContext({
            userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport: { width: 1280, height: 900 },
            locale: 'en-US',
        });
        const page = await context.newPage();

        try {
            // Navigate to listing
            await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 });

            // Wait for content to render (Airbnb is a React SPA)
            await page.waitForTimeout(4000);

            // Dismiss any modals (translation, cookie, etc.)
            try {
                const closeButtons = page.locator('button[aria-label="Close"], button:has-text("OK"), button:has-text("Got it")');
                const count = await closeButtons.count();
                for (let i = 0; i < Math.min(count, 3); i++) {
                    await closeButtons.nth(i).click({ timeout: 1000 }).catch(() => {});
                }
            } catch { /* no modals — fine */ }

            await page.waitForTimeout(1000);

            // ──── Extract fields ────

            // 1. Title from <title> tag
            const pageTitle = await page.title();

            // 2. og:title (often cleaner)
            const ogTitle = await page.getAttribute('meta[property="og:title"]', 'content').catch(() => null);

            // 3. Display name: clean up "... - Airbnb" suffix
            const rawName = ogTitle || pageTitle || '';
            const displayName = rawName
                .replace(/\s*[-–—]\s*Airbnb.*$/i, '')
                .replace(/\s*[-–—]\s*(Houses|Apartments|Villas|Homes|Condos|Rooms)\s+for\s+Rent.*/i, '')
                .trim();

            // 4. Property type from heading
            const typeText = await page.locator('h2:has-text("Entire"), h2:has-text("Private room"), h2:has-text("Shared room"), h2:has-text("Hotel room")')
                .first()
                .textContent()
                .catch(() => null);

            // Also check in the title for type hints
            const propertyType = mapPropertyType(typeText || rawName || '');

            // 5. Capacity: "4 guests · 2 bedrooms · 2 beds · 2.5 baths"
            const capacityText = await page.locator('ol:has(li)').first().textContent().catch(() => null)
                || await page.locator('div:has-text("guest")').first().textContent().catch(() => null)
                || '';

            const capacity = parseCapacity(capacityText);

            // 6. Location from page title
            const location = parseLocation(pageTitle);

            // 7. Description
            let description = '';
            try {
                // Try multiple selectors for the description
                const descSection = page.locator('[data-section-id="DESCRIPTION_DEFAULT"] span, [data-section-id="DESCRIPTION_DEFAULT"] div');
                const descCount = await descSection.count();
                if (descCount > 0) {
                    description = (await descSection.first().textContent()) || '';
                }

                // Fallback: look for description in a broader selector
                if (!description) {
                    const descAlt = page.locator('div[data-testid="listing-description"] span, section:has(h2:has-text("About")) span');
                    const altCount = await descAlt.count();
                    if (altCount > 0) {
                        description = (await descAlt.first().textContent()) || '';
                    }
                }
            } catch { /* description extraction failed — ok */ }

            // Truncate description at 1000 chars
            if (description.length > 1000) {
                description = description.substring(0, 1000) + '...';
            }

            // Build address from location parts
            const addressParts = [location.city, location.region, location.country].filter(Boolean);
            const address = addressParts.join(', ') || null;

            // Build response
            const extracted: Record<string, unknown> = {};
            const confidence: Record<string, string> = {};

            if (displayName) {
                extracted.display_name = displayName;
                confidence.display_name = 'reliable';
            }
            if (propertyType) {
                extracted.property_type = propertyType;
                confidence.property_type = 'estimated'; // heuristic mapping
            }
            if (location.city) {
                extracted.city = location.city;
                confidence.city = 'reliable';
            }
            if (location.country) {
                extracted.country = location.country;
                confidence.country = 'reliable';
            }
            if (capacity.guests) {
                extracted.max_guests = capacity.guests;
                confidence.max_guests = 'reliable';
            }
            if (capacity.bedrooms !== undefined) {
                extracted.bedrooms = capacity.bedrooms;
                confidence.bedrooms = 'reliable';
            }
            if (capacity.beds) {
                extracted.beds = capacity.beds;
                confidence.beds = 'reliable';
            }
            if (capacity.bathrooms) {
                extracted.bathrooms = capacity.bathrooms;
                confidence.bathrooms = 'reliable';
            }
            if (description) {
                extracted.description = description;
                confidence.description = 'reliable';
            }
            if (address) {
                extracted.address = address;
                confidence.address = 'estimated'; // region-level only
            }

            return NextResponse.json({
                success: true,
                source_url: url,
                source_platform: 'airbnb',
                extracted,
                confidence,
                fields_count: Object.keys(extracted).length,
            });
        } finally {
            await browser.close();
        }
    } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Unknown error';
        console.error('[extract] Parser error:', message);
        return NextResponse.json({
            success: false,
            error: `Parser failed: ${message}. Please fill in property details manually.`,
        }, { status: 500 });
    }
}
