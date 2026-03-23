/**
 * Shared identity-linking utilities — used by ALL profile pages.
 *
 * Canonical source for Google linking, unlock, password add flows.
 * Ensures the same redirectTo URL, session checks, and error handling
 * are used system-wide (admin, public, worker, etc.).
 */

import { supabase } from './supabaseClient';

/** Build the correct OAuth redirect URL for identity linking */
function getRedirectUrl(): string {
    if (typeof window !== 'undefined') {
        return `${window.location.origin}/auth/callback`;
    }
    return '/auth/callback';
}

/**
 * Link a Google identity to the current Supabase user.
 * Returns { success: true } on redirect, or { success: false, error: string } on failure.
 */
export async function linkGoogleAccount(): Promise<{ success: boolean; error?: string }> {
    if (!supabase) {
        return { success: false, error: 'Supabase client not configured.' };
    }

    // Check for active Supabase session
    const { data: sessionData } = await supabase.auth.getSession();
    if (!sessionData.session) {
        return {
            success: false,
            error: 'No active browser session. Please sign out and sign in again, then try linking.',
        };
    }

    try {
        sessionStorage.setItem('ihouse_linking_provider', 'google');
        const { error } = await supabase.auth.linkIdentity({
            provider: 'google',
            options: { redirectTo: getRedirectUrl() },
        });
        if (error) {
            sessionStorage.removeItem('ihouse_linking_provider');
            return { success: false, error: error.message };
        }
        // Supabase will redirect the browser — we won't reach here normally
        return { success: true };
    } catch (e) {
        sessionStorage.removeItem('ihouse_linking_provider');
        return { success: false, error: e instanceof Error ? e.message : 'Unknown error' };
    }
}

/**
 * Unlink a provider identity from the current Supabase user.
 */
export async function unlinkProvider(provider: string): Promise<{ success: boolean; error?: string }> {
    if (!supabase) {
        return { success: false, error: 'Supabase client not configured.' };
    }

    const { data: sessionData } = await supabase.auth.getSession();
    if (!sessionData.session) {
        return { success: false, error: 'No active browser session.' };
    }

    try {
        const { data: { user } } = await supabase.auth.getUser();
        const identity = user?.identities?.find(i => i.provider === provider);
        if (!identity) {
            return { success: false, error: `Provider "${provider}" not found.` };
        }
        const { error } = await supabase.auth.unlinkIdentity(identity);
        if (error) return { success: false, error: error.message };
        return { success: true };
    } catch (e) {
        return { success: false, error: e instanceof Error ? e.message : 'Unknown error' };
    }
}

/**
 * Add a password to the current Supabase user (for Google-only accounts).
 */
export async function addPassword(password: string): Promise<{ success: boolean; error?: string }> {
    if (!supabase) {
        return { success: false, error: 'Supabase client not configured.' };
    }

    const { data: sessionData } = await supabase.auth.getSession();
    if (!sessionData.session) {
        return {
            success: false,
            error: 'No active browser session. Sign in via Google first, then add email/password.',
        };
    }

    try {
        const { error } = await supabase.auth.updateUser({ password });
        if (error) return { success: false, error: error.message };
        return { success: true };
    } catch (e) {
        return { success: false, error: e instanceof Error ? e.message : 'Unknown error' };
    }
}

/** Google "G" SVG icon for consistent branding */
export const GoogleIcon = () => (
    <svg width="18" height="18" viewBox="0 0 48 48" style={{ flexShrink: 0 }}>
        <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
        <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
        <path fill="#FBBC05" d="M10.53 28.59a14.5 14.5 0 0 1 0-9.18l-7.98-6.19a24.09 24.09 0 0 0 0 21.56l7.98-6.19z"/>
        <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
    </svg>
);
