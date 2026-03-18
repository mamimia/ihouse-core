'use client';

/**
 * CompactLangSwitcher — Phase 838/839 (Revised)
 * ================================================
 * Ultra-minimal language control.
 *
 * Design rules:
 * - Collapsed: shows current short native code (EN / ไทย / עב)
 * - Expanded: short native code only per option — no duplicate names, no flags
 * - Min tap target: 44×44px
 * - Closes on outside tap, Escape key
 * - Dark/light/auto theme
 *
 * Usage:
 *   <CompactLangSwitcher />
 *   <CompactLangSwitcher theme="dark" />
 */

import { useState, useEffect, useRef } from 'react';
import { useLanguage, SupportedLang } from '../lib/LanguageContext';

const LANGS: { code: SupportedLang; short: string }[] = [
  { code: 'en', short: 'EN'   },
  { code: 'th', short: 'ไทย' },
  { code: 'he', short: 'עב'  },
];

interface Props {
  theme?: 'dark' | 'light' | 'auto';
  position?: 'inline' | 'fixed-top-right';
}

export default function CompactLangSwitcher({ theme = 'auto', position = 'inline' }: Props) {
  const { lang, setLang } = useLanguage();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click/tap
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent | TouchEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', h);
    document.addEventListener('touchstart', h);
    return () => { document.removeEventListener('mousedown', h); document.removeEventListener('touchstart', h); };
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('keydown', h);
    return () => document.removeEventListener('keydown', h);
  }, [open]);

  const isDark =
    theme === 'dark' ||
    (theme === 'auto' &&
      typeof document !== 'undefined' &&
      document.documentElement.getAttribute('data-theme') === 'dark');

  const pill = isDark
    ? { bg: 'rgba(255,255,255,0.07)', border: 'rgba(255,255,255,0.10)', color: 'rgba(255,255,255,0.65)' }
    : { bg: 'rgba(0,0,0,0.05)',       border: 'rgba(0,0,0,0.08)',        color: 'rgba(0,0,0,0.55)'       };

  const drop = isDark
    ? { bg: '#1a1f2e', border: 'rgba(255,255,255,0.09)', shadow: '0 6px 20px rgba(0,0,0,0.45)' }
    : { bg: '#ffffff', border: 'rgba(0,0,0,0.07)',        shadow: '0 6px 20px rgba(0,0,0,0.10)' };

  const rowActive = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)';
  const textActive = isDark ? '#93c5fd' : '#2563eb';
  const textNormal = isDark ? 'rgba(255,255,255,0.6)' : 'rgba(0,0,0,0.55)';

  const current = LANGS.find(l => l.code === lang) ?? LANGS[0];

  const posStyle: React.CSSProperties = position === 'fixed-top-right'
    ? { position: 'fixed', top: 12, right: 14, zIndex: 999 }
    : { position: 'relative' };

  return (
    <div ref={ref} id="compact-lang-switcher" style={posStyle}>
      {/* Trigger */}
      <button
        id="lang-switcher-trigger"
        onClick={() => setOpen(o => !o)}
        aria-label={`Language: ${current.short}. Tap to change.`}
        aria-expanded={open}
        aria-haspopup="listbox"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 3,
          padding: '5px 9px',
          minHeight: 30,
          minWidth: 44,
          borderRadius: 20,
          border: `1px solid ${pill.border}`,
          background: pill.bg,
          color: pill.color,
          cursor: 'pointer',
          fontSize: 12,
          fontWeight: 600,
          fontFamily: "'Inter', sans-serif",
          letterSpacing: '0.02em',
          transition: 'opacity 0.15s',
          backdropFilter: 'blur(6px)',
          WebkitBackdropFilter: 'blur(6px)',
        }}
      >
        {current.short}
        <span style={{ fontSize: 8, opacity: 0.5 }}>{open ? '▲' : '▼'}</span>
      </button>

      {/* Dropdown */}
      {open && (
        <div
          role="listbox"
          aria-label="Select language"
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            right: 0,
            minWidth: 62,
            background: drop.bg,
            border: `1px solid ${drop.border}`,
            borderRadius: 10,
            boxShadow: drop.shadow,
            overflow: 'hidden',
            zIndex: 1000,
            animation: 'langDropIn 100ms cubic-bezier(0.32,0.72,0,1)',
          }}
        >
          <style>{`
            @keyframes langDropIn {
              from { opacity:0; transform:translateY(-4px) scale(0.97); }
              to   { opacity:1; transform:translateY(0)   scale(1); }
            }
          `}</style>
          {LANGS.map(l => {
            const active = l.code === lang;
            return (
              <button
                key={l.code}
                id={`lang-option-${l.code}`}
                role="option"
                aria-selected={active}
                onClick={() => { setLang(l.code); setOpen(false); }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '100%',
                  padding: '9px 14px',
                  background: active ? rowActive : 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: 12,
                  fontWeight: active ? 700 : 500,
                  fontFamily: "'Inter', sans-serif",
                  color: active ? textActive : textNormal,
                  transition: 'background 0.1s',
                  letterSpacing: '0.01em',
                }}
                onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.background = rowActive; }}
                onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
              >
                {l.short}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
