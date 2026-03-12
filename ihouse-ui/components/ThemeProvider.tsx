'use client';

/**
 * Phase 377 — ThemeProvider Component
 *
 * Applies data-theme attribute to <html> based on user preference.
 * Dark-preferred: defaults to "dark", respects OS preference, allows manual toggle.
 * Persists choice in localStorage.
 */

import { createContext, useContext, useEffect, useState, useCallback } from 'react';

type Theme = 'dark' | 'light' | 'system';

interface ThemeContextType {
    theme: Theme;
    resolvedTheme: 'dark' | 'light';
    setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType>({
    theme: 'system',
    resolvedTheme: 'dark',
    setTheme: () => {},
});

export function useTheme() {
    return useContext(ThemeContext);
}

function getSystemPreference(): 'dark' | 'light' {
    if (typeof window === 'undefined') return 'dark';
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

function resolveTheme(theme: Theme): 'dark' | 'light' {
    if (theme === 'system') return getSystemPreference();
    return theme;
}

const STORAGE_KEY = 'domaniqo-theme';

export default function ThemeProvider({ children }: { children: React.ReactNode }) {
    const [theme, setThemeState] = useState<Theme>('system');
    const [resolvedTheme, setResolvedTheme] = useState<'dark' | 'light'>('dark');

    // Initialize from localStorage on mount
    useEffect(() => {
        const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
        const initial = stored || 'system';
        setThemeState(initial);
        const resolved = resolveTheme(initial);
        setResolvedTheme(resolved);
        document.documentElement.setAttribute('data-theme', resolved);
    }, []);

    // Listen for OS preference changes when in system mode
    useEffect(() => {
        if (theme !== 'system') return;
        const mql = window.matchMedia('(prefers-color-scheme: light)');
        const handler = () => {
            const resolved = resolveTheme('system');
            setResolvedTheme(resolved);
            document.documentElement.setAttribute('data-theme', resolved);
        };
        mql.addEventListener('change', handler);
        return () => mql.removeEventListener('change', handler);
    }, [theme]);

    const setTheme = useCallback((newTheme: Theme) => {
        setThemeState(newTheme);
        const resolved = resolveTheme(newTheme);
        setResolvedTheme(resolved);
        document.documentElement.setAttribute('data-theme', resolved);
        localStorage.setItem(STORAGE_KEY, newTheme);
    }, []);

    return (
        <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme }}>
            {children}
        </ThemeContext.Provider>
    );
}
