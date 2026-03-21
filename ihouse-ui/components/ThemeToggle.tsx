'use client';

import { useEffect, useState } from 'react';
import { useTheme } from './ThemeProvider';

export default function ThemeToggle() {
    const { resolvedTheme, setTheme } = useTheme();
    const [mounted, setMounted] = useState(false);

    useEffect(() => setMounted(true), []);

    if (!mounted) {
        return <div style={{ width: 36, height: 20, borderRadius: 10, background: 'var(--color-surface-2)', flexShrink: 0 }} />;
    }

    const isDark = resolvedTheme === 'dark';

    return (
        <div 
            onClick={() => setTheme(isDark ? 'light' : 'dark')}
            title={`Switch to ${isDark ? 'Light' : 'Dark'} mode`}
            style={{
                width: 36, 
                height: 20, 
                borderRadius: 10, 
                background: isDark ? 'rgba(234, 229, 222, 0.07)' : 'rgba(23, 26, 31, 0.07)', 
                position: 'relative', 
                cursor: 'pointer', 
                flexShrink: 0,
                border: isDark ? '1px solid rgba(234,229,222,0.1)' : '1px solid rgba(23,26,31,0.1)',
                transition: 'background 0.3s'
            }}
        >
            <div style={{
                position: 'absolute',
                top: 2,
                left: 2,
                width: 14,
                height: 14,
                borderRadius: '50%',
                background: isDark ? 'var(--color-stone)' : 'var(--color-midnight)',
                transition: 'transform 0.3s ease',
                transform: isDark ? 'translateX(16px)' : 'translateX(0)',
                boxShadow: '0 1px 2px rgba(0,0,0,0.2)'
            }} />
        </div>
    );
}
