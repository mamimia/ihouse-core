/**
 * Supabase Browser Client — Auth Operations
 *
 * Client-side Supabase client for:
 *   - signInWithPassword (email + pw)
 *   - signInWithOAuth (Google)
 *   - signUp (registration)
 *   - resetPasswordForEmail (forgot pw)
 *
 * Uses NEXT_PUBLIC_ env vars (safe for browser).
 * NOT used for data queries — those go through the Python backend via apiFetch.
 *
 * Gracefully handles missing env vars (returns null client).
 * Pages that import this must handle the null case.
 */
import { createClient, SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

/** Supabase client — null if env vars are missing. */
export const supabase: SupabaseClient | null =
    supabaseUrl && supabaseAnonKey
        ? createClient(supabaseUrl, supabaseAnonKey)
        : null;

/** Returns true if the Supabase client is configured and available. */
export function isSupabaseConfigured(): boolean {
    return supabase !== null;
}
