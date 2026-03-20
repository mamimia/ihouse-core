'use client';

/**
 * Phase 858 — /register redirect
 * Self-registration is replaced by the /get-started intake flow.
 * Users who bookmarked /register are redirected cleanly.
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function RegisterRedirect() {
    const router = useRouter();
    useEffect(() => { router.replace('/get-started'); }, [router]);
    return null;
}
