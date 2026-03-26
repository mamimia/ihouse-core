'use client';

/**
 * PasswordInput — Phase 839
 * =========================
 * Accessible password field with show/hide toggle.
 * Shared by: /login/password, /register, /reset
 */

import { useState } from 'react';
import { useLanguage } from '../../lib/LanguageContext';

interface PasswordInputProps {
  id: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onFocus?: () => void;
  onBlur?: () => void;
  placeholder?: string;
  autoFocus?: boolean;
  disabled?: boolean;
  autoComplete?: string;
  className?: string;
  style?: React.CSSProperties;
}

export default function PasswordInput({
  id,
  value,
  onChange,
  onFocus,
  onBlur,
  placeholder = '••••••••',
  autoFocus,
  disabled,
  autoComplete = 'current-password',
  className = 'auth-input',
  style,
}: PasswordInputProps) {
  const { isRTL } = useLanguage();
  const [show, setShow] = useState(false);

  const baseStyle: React.CSSProperties = {
    width: '100%',
    padding: isRTL ? '12px 14px 12px 44px' : '12px 44px 12px 14px', // extra padding for toggle button

    background: 'var(--color-midnight, #171A1F)',
    border: '1px solid rgba(234,229,222,0.1)',
    borderRadius: 'var(--radius-md, 12px)',
    color: 'var(--color-stone, #EAE5DE)',
    fontSize: 'var(--text-sm, 14px)',
    transition: 'border-color 0.2s, box-shadow 0.2s',
    fontFamily: 'var(--font-sans, inherit)',
    boxSizing: 'border-box',
    ...style,
  };

  return (
    <div style={{ position: 'relative' }}>
      <input
        id={id}
        className={className}
        type={show ? 'text' : 'password'}
        value={value}
        onChange={onChange}
        onFocus={onFocus}
        onBlur={onBlur}
        placeholder={placeholder}
        autoComplete={autoComplete}
        autoFocus={autoFocus}
        disabled={disabled}
        style={baseStyle}
      />
      <button
        type="button"
        tabIndex={-1}
        aria-label={show ? 'Hide password' : 'Show password'}
        onClick={() => setShow(s => !s)}
        style={{
          position: 'absolute',
          ...(isRTL ? { left: 12 } : { right: 12 }),
          top: '50%',
          transform: 'translateY(-50%)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: 4,
          color: 'var(--color-copper, #B56E45)',
          opacity: 0.6,
          transition: 'opacity 0.15s',
          display: 'flex',
          alignItems: 'center',
          lineHeight: 1,
        }}
        onMouseEnter={e => (e.currentTarget.style.opacity = '1')}
        onMouseLeave={e => (e.currentTarget.style.opacity = '0.6')}
      >
        {show ? (
          // Eye-off icon
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
            <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
            <line x1="1" y1="1" x2="23" y2="23"/>
          </svg>
        ) : (
          // Eye icon
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
        )}
      </button>
    </div>
  );
}
