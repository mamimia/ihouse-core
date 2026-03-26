'use client';

import { useLanguage } from '@/lib/LanguageContext';

export default function WorkerHeader({ title, subtitle }: { title: string; subtitle?: string }) {
    const { lang, t } = useLanguage();
    
    // Map internal language state to standard BCP 47 locale strings
    const localeStr = lang === 'he' ? 'he-IL' : lang === 'th' ? 'th-TH' : 'en-US';

    const today = new Date();
    
    const todayStr = t('worker.stat_today');
    const weekday = today.toLocaleDateString(localeStr, { weekday: 'long' });
    const monthName = today.toLocaleDateString(localeStr, { month: 'long' });
    
    // Use en-US to ensure western digits for the numeric components (e.g. 27, 03)
    // to keep it looking clean and standardized across locales as requested.
    const day = today.toLocaleDateString('en-US', { day: 'numeric' });
    const numericMonth = today.toLocaleDateString('en-US', { month: '2-digit' });

    return (
        <div style={{ marginBottom: 'var(--space-5)' }}>
            {/* ROW 1: [localized Today] • [localized Weekday] */}
            <div style={{ 
                fontSize: 'var(--text-sm)', 
                fontWeight: 600, 
                color: 'var(--color-text-dim)', 
                textTransform: 'uppercase', 
                letterSpacing: '0.05em'
            }}>
                {todayStr} • {weekday}
            </div>

            {/* ROW 2: [prominent day-of-month] */}
            <div style={{ 
                fontSize: '2.4rem', 
                fontWeight: 800, 
                color: 'var(--color-text)', 
                lineHeight: 1.1,
                marginTop: 6,
                marginBottom: 2
            }}>
                {day}
            </div>

            {/* ROW 3: [localized Month] • [numeric month] */}
            <div style={{ 
                fontSize: 'var(--text-sm)', 
                fontWeight: 600, 
                color: 'var(--color-text-dim)', 
                textTransform: 'uppercase', 
                letterSpacing: '0.05em',
                marginBottom: 16
            }}>
                {monthName} • {numericMonth}
            </div>

            {/* Surface Title & Subtitle */}
            <h1 style={{ 
                fontSize: '2rem', 
                fontWeight: 800, 
                color: 'var(--color-text)', 
                letterSpacing: '-0.03em', 
                marginTop: 4 
            }}>
                {title}
            </h1>
            {subtitle && (
                <p style={{ 
                    fontSize: 'var(--text-xs)', 
                    color: 'var(--color-text-dim)', 
                    marginTop: 2 
                }}>
                    {subtitle}
                </p>
            )}
        </div>
    );
}
