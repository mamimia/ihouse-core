'use client';

/**
 * Phase 858 — /register/profile redirect
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function RegisterProfileRedirect() {
    const router = useRouter();
    useEffect(() => { router.replace('/get-started'); }, [router]);
    return null;
}
