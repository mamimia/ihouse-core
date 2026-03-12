/**
 * Phase 380 — Robots.txt
 *
 * Disallow crawling of (app) authenticated routes.
 */

import type { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
    return {
        rules: [
            {
                userAgent: '*',
                allow: '/',
                disallow: [
                    '/dashboard',
                    '/bookings',
                    '/calendar',
                    '/financial',
                    '/admin',
                    '/owner',
                    '/worker',
                    '/tasks',
                    '/guests',
                    '/manager',
                ],
            },
        ],
        sitemap: 'https://domaniqo.com/sitemap.xml',
    };
}
