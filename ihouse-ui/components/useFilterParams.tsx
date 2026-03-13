'use client';

/**
 * Phase 579 — useSearchParams Persistence Hook
 *
 * Syncs filter/search state to URL search params (query string).
 * Filters survive page reload and can be shared via URL.
 *
 * Usage:
 *   const { params, setParam, removeParam, setParams } = useFilterParams({
 *     status: '',
 *     q: '',
 *     sort: 'updated_at',
 *   });
 */

import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import { useCallback, useMemo } from 'react';

interface UseFilterParamsOptions {
    /** Default values for params — used when URL param is missing */
    defaults?: Record<string, string>;
    /** Replace vs push navigation (default: replace) */
    push?: boolean;
}

export function useFilterParams(defaults: Record<string, string> = {}, options: UseFilterParamsOptions = {}) {
    const searchParams = useSearchParams();
    const router = useRouter();
    const pathname = usePathname();

    // Current params: URL overrides defaults
    const params = useMemo(() => {
        const result: Record<string, string> = { ...defaults };
        searchParams.forEach((value, key) => {
            result[key] = value;
        });
        return result;
    }, [searchParams, defaults]);

    const _navigate = useCallback((newParams: URLSearchParams) => {
        const qs = newParams.toString();
        const url = qs ? `${pathname}?${qs}` : pathname;
        if (options.push) {
            router.push(url);
        } else {
            router.replace(url);
        }
    }, [pathname, router, options.push]);

    const setParam = useCallback((key: string, value: string) => {
        const newParams = new URLSearchParams(searchParams.toString());
        if (value === '' || value === defaults[key]) {
            newParams.delete(key);
        } else {
            newParams.set(key, value);
        }
        _navigate(newParams);
    }, [searchParams, defaults, _navigate]);

    const removeParam = useCallback((key: string) => {
        const newParams = new URLSearchParams(searchParams.toString());
        newParams.delete(key);
        _navigate(newParams);
    }, [searchParams, _navigate]);

    const setParams = useCallback((updates: Record<string, string>) => {
        const newParams = new URLSearchParams(searchParams.toString());
        for (const [key, value] of Object.entries(updates)) {
            if (value === '' || value === defaults[key]) {
                newParams.delete(key);
            } else {
                newParams.set(key, value);
            }
        }
        _navigate(newParams);
    }, [searchParams, defaults, _navigate]);

    const clearAll = useCallback(() => {
        _navigate(new URLSearchParams());
    }, [_navigate]);

    return { params, setParam, removeParam, setParams, clearAll };
}
