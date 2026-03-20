'use client';

/**
 * Phase 858 — /register/email redirect
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function RegisterEmailRedirect() {
    const router = useRouter();
    useEffect(() => { router.replace('/get-started'); }, [router]);
    return null;
}
