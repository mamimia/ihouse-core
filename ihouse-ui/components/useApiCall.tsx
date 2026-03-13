'use client';

/**
 * Phase 565 — useApiCall Hook
 *
 * Standardized hook for API calls with:
 *   - Loading state
 *   - Error state with message
 *   - Automatic toast.error on failure
 *   - Retry capability
 *   - Data typing
 *
 * Usage:
 *   const { data, loading, error, refetch } = useApiCall(() => api.getBookings());
 *   const { execute, loading } = useApiAction((id) => api.deleteBooking(id));
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { toast } from './Toast';

// ---------------------------------------------------------------------------
// useApiCall — for GET-style data fetching
// ---------------------------------------------------------------------------

interface UseApiCallOptions {
    /** Skip initial fetch (manual trigger only) */
    skip?: boolean;
    /** Auto-refresh interval in ms (0 = disabled) */
    pollInterval?: number;
    /** Show toast on error (default: true) */
    showToast?: boolean;
    /** Custom error message prefix */
    errorPrefix?: string;
}

interface UseApiCallResult<T> {
    data: T | null;
    loading: boolean;
    error: string | null;
    refetch: () => Promise<void>;
}

export function useApiCall<T>(
    fetcher: () => Promise<T>,
    deps: unknown[] = [],
    options: UseApiCallOptions = {},
): UseApiCallResult<T> {
    const { skip = false, pollInterval = 0, showToast = true, errorPrefix } = options;
    const [data, setData] = useState<T | null>(null);
    const [loading, setLoading] = useState(!skip);
    const [error, setError] = useState<string | null>(null);
    const mountedRef = useRef(true);

    const execute = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await fetcher();
            if (mountedRef.current) {
                setData(result);
                setError(null);
            }
        } catch (err) {
            if (mountedRef.current) {
                const msg = err instanceof Error ? err.message : 'Request failed';
                const fullMsg = errorPrefix ? `${errorPrefix}: ${msg}` : msg;
                setError(fullMsg);
                if (showToast) toast.error(fullMsg);
            }
        } finally {
            if (mountedRef.current) setLoading(false);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, deps);

    useEffect(() => {
        mountedRef.current = true;
        if (!skip) execute();
        return () => { mountedRef.current = false; };
    }, [execute, skip]);

    // Polling
    useEffect(() => {
        if (!pollInterval || skip) return;
        const timer = setInterval(execute, pollInterval);
        return () => clearInterval(timer);
    }, [execute, pollInterval, skip]);

    return { data, loading, error, refetch: execute };
}

// ---------------------------------------------------------------------------
// useApiAction — for POST/PUT/DELETE mutations
// ---------------------------------------------------------------------------

interface UseApiActionOptions {
    /** Show toast on success */
    successMessage?: string;
    /** Show toast on error (default: true) */
    showToast?: boolean;
    /** Custom error message prefix */
    errorPrefix?: string;
    /** Callback after success */
    onSuccess?: (result: unknown) => void;
}

interface UseApiActionResult<TArgs extends unknown[], TResult> {
    execute: (...args: TArgs) => Promise<TResult | null>;
    loading: boolean;
    error: string | null;
}

export function useApiAction<TArgs extends unknown[], TResult>(
    action: (...args: TArgs) => Promise<TResult>,
    options: UseApiActionOptions = {},
): UseApiActionResult<TArgs, TResult> {
    const { successMessage, showToast = true, errorPrefix, onSuccess } = options;
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const execute = useCallback(async (...args: TArgs): Promise<TResult | null> => {
        setLoading(true);
        setError(null);
        try {
            const result = await action(...args);
            if (successMessage) toast.success(successMessage);
            if (onSuccess) onSuccess(result);
            return result;
        } catch (err) {
            const msg = err instanceof Error ? err.message : 'Action failed';
            const fullMsg = errorPrefix ? `${errorPrefix}: ${msg}` : msg;
            setError(fullMsg);
            if (showToast) toast.error(fullMsg);
            return null;
        } finally {
            setLoading(false);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return { execute, loading, error };
}
