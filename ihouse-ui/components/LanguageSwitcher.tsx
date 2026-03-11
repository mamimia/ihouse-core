'use client';

/**
 * Phase 260 — Language Switcher Component
 * Compact selector with flag emoji. Renders in sidebar at bottom.
 * Uses the Domaniqo warm palette (light mode — matches tokens.css).
 */

import { useLanguage, SupportedLang } from '../lib/LanguageContext';

const LANGS: { code: SupportedLang; flag: string; label: string }[] = [
  { code: 'en', flag: '🇬🇧', label: 'EN' },
  { code: 'th', flag: '🇹🇭', label: 'TH' },
  { code: 'he', flag: '🇮🇱', label: 'HE' },
];

export default function LanguageSwitcher() {
  const { lang, setLang } = useLanguage();

  return (
    <div
      style={{
        padding: '0 12px',
        marginBottom: 8,
      }}
    >
      <div
        style={{
          fontSize: 10,
          color: '#9A958E',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          marginBottom: 6,
          paddingLeft: 4,
          fontFamily: "'Inter', sans-serif",
        }}
      >
        Language
      </div>
      <div style={{ display: 'flex', gap: 4 }}>
        {LANGS.map(({ code, flag, label }) => {
          const active = lang === code;
          return (
            <button
              key={code}
              id={`lang-btn-${code}`}
              onClick={() => setLang(code)}
              title={code === 'en' ? 'English' : code === 'th' ? 'ภาษาไทย' : 'עברית'}
              style={{
                flex: 1,
                padding: '6px 4px',
                borderRadius: 8,
                border: active ? '1.5px solid #334036' : '1px solid #DDD8D0',
                background: active ? '#334036' : 'transparent',
                color: active ? '#F8F6F2' : '#9A958E',
                fontSize: 11,
                fontWeight: active ? 700 : 400,
                cursor: 'pointer',
                transition: 'all 0.15s',
                fontFamily: "'Inter', sans-serif",
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 1,
              }}
            >
              <span style={{ fontSize: 14 }}>{flag}</span>
              <span>{label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
