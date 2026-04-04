'use client';

/**
 * Phase 1068 — OM Unread Badge Context + Popup Alert
 *
 * Provides:
 *   - totalUnread: number        — live unread count polled every 15s
 *   - newestAlert: NewestUnread  — newest unread message for popup
 *   - dismissAlert()             — clears the popup without marking read
 *   - refresh()                  — manual re-fetch
 *
 * Used by:
 *   - OMSidebar / OMBottomNav — nav badge
 *   - OMUnreadPopup           — floating alert component
 *   - ManagerInboxPage        — re-polls on reply/open
 *
 * Poll interval: 15 seconds.
 * Polling is only active when the OM manager context is present (role=manager).
 * The context is lightweight: single endpoint GET /manager/guest-messages/unread-count.
 */

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useRef,
    useState,
} from 'react';
import { apiFetch } from '@/lib/api';

export interface NewestUnread {
    booking_id:  string;
    guest_name:  string;
    preview:     string;
    created_at:  string;
    sender_type: string;  // 'guest' | 'system'
}

interface UnreadContextValue {
    totalUnread:  number;
    newestAlert:  NewestUnread | null;
    dismissAlert: () => void;
    refresh:      () => void;
}

const UnreadContext = createContext<UnreadContextValue>({
    totalUnread:  0,
    newestAlert:  null,
    dismissAlert: () => {},
    refresh:      () => {},
});

export function useUnread() {
    return useContext(UnreadContext);
}

// The most recently seen newest message id — so we only popup on NEW arrivals
let _seenNewestId: string | null = null;

const POLL_INTERVAL_MS = 15_000;

export function OMUnreadProvider({ children }: { children: React.ReactNode }) {
    const [totalUnread, setTotalUnread] = useState(0);
    const [newestAlert, setNewestAlert] = useState<NewestUnread | null>(null);
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const isOMContext = typeof window !== 'undefined' && (() => {
        try {
            const previewRole = sessionStorage.getItem('ihouse_preview_role');
            if (previewRole === 'manager') return true;
            const ssToken = sessionStorage.getItem('ihouse_token');
            const lsToken = localStorage.getItem('ihouse_token');
            const token = ssToken ?? lsToken;
            if (!token) return false;
            const payload = JSON.parse(atob(token.split('.')[1] || '{}'));
            return payload.role === 'manager';
        } catch { return false; }
    })();

    const fetchUnread = useCallback(async () => {
        if (!isOMContext) return;
        try {
            const res = await apiFetch<{
                total_unread: number;
                newest_unread: NewestUnread | null;
            }>('/manager/guest-messages/unread-count');

            setTotalUnread(res.total_unread ?? 0);

            // Only surface the popup if this is a genuinely new message
            const newest = res.newest_unread;
            if (newest) {
                // Distinguish by booking_id + created_at combination
                const newestKey = `${newest.booking_id}::${newest.created_at}`;
                if (_seenNewestId !== newestKey) {
                    _seenNewestId = newestKey;
                    // Only fire popup if there are actual unread messages
                    if ((res.total_unread ?? 0) > 0) {
                        setNewestAlert(newest);
                    }
                }
            } else {
                // No unread at all — if we had an alert, clear it silently
                if (res.total_unread === 0) {
                    setNewestAlert(null);
                }
            }
        } catch {
            // Non-blocking — silently ignore
        }
    }, [isOMContext]);

    const refresh = useCallback(() => {
        fetchUnread();
    }, [fetchUnread]);

    const dismissAlert = useCallback(() => {
        setNewestAlert(null);
    }, []);

    useEffect(() => {
        if (!isOMContext) return;
        fetchUnread();
        intervalRef.current = setInterval(fetchUnread, POLL_INTERVAL_MS);
        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return (
        <UnreadContext.Provider value={{ totalUnread, newestAlert, dismissAlert, refresh }}>
            {children}
        </UnreadContext.Provider>
    );
}
