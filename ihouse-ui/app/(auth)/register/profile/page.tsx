'use client';

/**
 * Phase 871 — /register/profile redirect
 * Legacy URL preserved — redirects to /register
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function RegisterProfileRedirect() {
    const router = useRouter();
    useEffect(() => { router.replace('/register'); }, [router]);
    return null;
}
