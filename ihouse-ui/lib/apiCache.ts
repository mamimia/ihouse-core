'use client';

/**
 * Phase 580 — API Response Caching Layer
 *
 * Stale-while-revalidate cache for API responses.
 * Configurable TTL per endpoint pattern.
 *
 * Usage:
 *   import { cachedFetch } from './apiCache';
 *   const data = await cachedFetch('/bookings', () => api.getBookings(), 30_000);
 */

type CacheEntry = {
    data: unknown;
    timestamp: number;
    ttl: number;
};

const cache = new Map<string, CacheEntry>();

/** Default TTLs by endpoint pattern (ms) */
const DEFAULT_TTLS: [RegExp, number][] = [
    [/\/health/, 10_000],                    // 10s
    [/\/operations\/today/, 30_000],          // 30s
    [/\/bookings$/, 30_000],                  // 30s
    [/\/analytics/, 60_000],                  // 1 min
    [/\/properties/, 60_000],                 // 1 min
    [/\/currencies/, 300_000],                // 5 min
    [/\/export\/types/, 600_000],             // 10 min
];

function getTTL(key: string): number {
    for (const [pattern, ttl] of DEFAULT_TTLS) {
        if (pattern.test(key)) return ttl;
    }
    return 30_000; // default 30s
}

/**
 * Fetch with stale-while-revalidate caching.
 *
 * @param key     Cache key (usually API path)
 * @param fetcher Async function that performs the actual fetch
 * @param ttl     Optional TTL override in ms
 */
export async function cachedFetch<T>(
    key: string,
    fetcher: () => Promise<T>,
    ttl?: number,
): Promise<T> {
    const entry = cache.get(key);
    const effectiveTTL = ttl ?? getTTL(key);
    const now = Date.now();

    // Fresh cache hit
    if (entry && (now - entry.timestamp) < effectiveTTL) {
        return entry.data as T;
    }

    // Stale cache hit — return stale data but revalidate in background
    if (entry) {
        // Fire-and-forget revalidation
        fetcher().then(data => {
            cache.set(key, { data, timestamp: Date.now(), ttl: effectiveTTL });
        }).catch(() => {});
        return entry.data as T;
    }

    // No cache — fetch fresh
    const data = await fetcher();
    cache.set(key, { data, timestamp: now, ttl: effectiveTTL });
    return data;
}

/** Invalidate a specific cache entry */
export function invalidateCache(key: string): void {
    cache.delete(key);
}

/** Invalidate all entries matching a pattern */
export function invalidateCachePattern(pattern: RegExp): void {
    for (const key of cache.keys()) {
        if (pattern.test(key)) cache.delete(key);
    }
}

/** Clear entire cache */
export function clearCache(): void {
    cache.clear();
}

/** Get cache stats (for debugging) */
export function getCacheStats(): { size: number; keys: string[] } {
    return {
        size: cache.size,
        keys: Array.from(cache.keys()),
    };
}
