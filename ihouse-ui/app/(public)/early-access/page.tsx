'use client';

/**
 * Phase 858 — /early-access redirect
 * This page now redirects to /get-started (canonical intake).
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function EarlyAccessRedirect() {
    const router = useRouter();
    useEffect(() => { router.replace('/get-started'); }, [router]);
    return null;
}
