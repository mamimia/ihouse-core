'use client';

/**
 * Phase 260 — Language Context
 * Phase 838/839 — RTL guard
 * ==============================
 * Global language state. Stored in localStorage.
 *
 * RTL rule (Phase 839):
 *   isRTL is exposed on the context but NOT automatically applied to <html>.
 *   A surface must opt-in to RTL by wrapping its own container with:
 *     style={{ direction: isRTL ? 'rtl' : 'ltr' }}
 *   This must only be done AFTER the surface is fully localized.
 *   Applying dir=rtl to English text breaks the layout with zero benefit.
 *
 * Usage:
 *   const { lang, setLang, t, isRTL } = useLanguage();
 *   t('worker.my_tasks')  // → "งานของฉัน" if lang === 'th'
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { translations, SupportedLang, TranslationKey } from './translations';

export type { SupportedLang };

interface LangContextValue {
  lang: SupportedLang;
  setLang: (l: SupportedLang) => void;
  t: (key: TranslationKey) => string;
  isRTL: boolean;
}

const RTL_LANGS = new Set<SupportedLang>(['he']);
const STORAGE_KEY = 'domaniqo_lang';
const DEFAULT_LANG: SupportedLang = 'en';

const LangContext = createContext<LangContextValue>({
  lang: DEFAULT_LANG,
  setLang: () => { },
  t: (key) => key,
  isRTL: false,
});

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<SupportedLang>(DEFAULT_LANG);

  // Load saved language on mount
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const saved = localStorage.getItem(STORAGE_KEY) as SupportedLang | null;
    if (saved && saved in translations) {
      setLangState(saved);
    }
  }, []);

  // Only update the html lang attribute (for accessibility / screen readers).
  // dir="rtl" is NOT applied globally — see RTL rule in docblock above.
  useEffect(() => {
    if (typeof document === 'undefined') return;
    document.documentElement.setAttribute('lang', lang);
    // Explicitly reset to ltr to prevent any leftover state from old code.
    document.documentElement.setAttribute('dir', 'ltr');
  }, [lang]);

  const setLang = useCallback((l: SupportedLang) => {
    setLangState(l);
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, l);
    }
  }, []);

  const t = useCallback(
    (key: TranslationKey): string => {
      const pack = translations[lang];
      return (pack?.[key] ?? translations.en[key] ?? key) as string;
    },
    [lang],
  );

  const isRTL = RTL_LANGS.has(lang);

  return (
    <LangContext.Provider value={{ lang, setLang, t, isRTL }}>
      {children}
    </LangContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LangContext);
}
