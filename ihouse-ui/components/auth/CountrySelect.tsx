'use client';

/**
 * CountrySelect — Searchable country dropdown with auto-detection.
 *
 * Features:
 * - Auto-detects country from browser timezone on mount
 * - Searchable input with filtered dropdown
 * - Shows country name + phone prefix in options
 * - Returns full Country object on selection
 * - Click-outside closes dropdown
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { COUNTRIES, detectCountryCode, searchCountries, type Country } from '@/lib/countryData';

interface CountrySelectProps {
  value: string;           // ISO country code
  onChange: (country: Country) => void;
  disabled?: boolean;
  autoDetect?: boolean;    // attempt timezone-based detection on mount
  placeholder?: string;
}

export default function CountrySelect({
  value,
  onChange,
  disabled = false,
  autoDetect = true,
  placeholder = 'Select country',
}: CountrySelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [highlightIdx, setHighlightIdx] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Auto-detect on mount if no value is set
  useEffect(() => {
    if (autoDetect && !value) {
      const detected = detectCountryCode();
      if (detected) {
        const country = COUNTRIES.find(c => c.code === detected);
        if (country) onChange(country);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Click outside to close
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setSearch('');
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const selectedCountry = COUNTRIES.find(c => c.code === value);
  const filtered = searchCountries(search);

  const handleSelect = useCallback((country: Country) => {
    onChange(country);
    setOpen(false);
    setSearch('');
    setHighlightIdx(-1);
  }, [onChange]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        setOpen(true);
        e.preventDefault();
      }
      return;
    }
    if (e.key === 'Escape') {
      setOpen(false);
      setSearch('');
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightIdx(prev => Math.min(prev + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightIdx(prev => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter' && highlightIdx >= 0 && highlightIdx < filtered.length) {
      e.preventDefault();
      handleSelect(filtered[highlightIdx]);
    }
  };

  // Scroll highlighted item into view
  useEffect(() => {
    if (listRef.current && highlightIdx >= 0) {
      const el = listRef.current.children[highlightIdx] as HTMLElement;
      if (el) el.scrollIntoView({ block: 'nearest' });
    }
  }, [highlightIdx]);

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '12px 14px',
    paddingRight: '36px',
    background: 'var(--color-midnight, #171A1F)',
    border: `1px solid ${open ? 'var(--color-copper, #B56E45)' : 'rgba(234,229,222,0.1)'}`,
    borderRadius: 'var(--radius-md, 12px)',
    color: 'var(--color-stone, #EAE5DE)',
    fontSize: 'var(--text-sm, 14px)',
    transition: 'border-color 0.2s, box-shadow 0.2s',
    fontFamily: 'var(--font-sans, inherit)',
    boxSizing: 'border-box',
    cursor: disabled ? 'not-allowed' : 'pointer',
    boxShadow: open ? '0 0 0 3px rgba(181,110,69,0.15)' : 'none',
  };

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      {/* Input / display */}
      <div
        onClick={() => { if (!disabled) { setOpen(!open); setTimeout(() => inputRef.current?.focus(), 0); } }}
        style={{ position: 'relative' }}
      >
        {open ? (
          <input
            ref={inputRef}
            type="text"
            value={search}
            onChange={e => { setSearch(e.target.value); setHighlightIdx(0); }}
            onKeyDown={handleKeyDown}
            placeholder="Search country..."
            disabled={disabled}
            autoFocus
            style={inputStyle}
          />
        ) : (
          <div style={inputStyle}>
            {selectedCountry ? (
              <span>{selectedCountry.name}</span>
            ) : (
              <span style={{ color: 'rgba(234,229,222,0.3)' }}>{placeholder}</span>
            )}
          </div>
        )}
        {/* Chevron */}
        <div style={{
          position: 'absolute',
          right: 14,
          top: '50%',
          transform: `translateY(-50%) rotate(${open ? 180 : 0}deg)`,
          transition: 'transform 0.2s',
          color: 'rgba(234,229,222,0.3)',
          fontSize: 12,
          pointerEvents: 'none',
        }}>
          ▼
        </div>
      </div>

      {/* Dropdown */}
      {open && (
        <div
          ref={listRef}
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            marginTop: 4,
            maxHeight: 240,
            overflowY: 'auto',
            background: 'var(--color-elevated, #1E2127)',
            border: '1px solid rgba(234,229,222,0.1)',
            borderRadius: 'var(--radius-md, 12px)',
            boxShadow: '0 12px 40px rgba(0,0,0,0.4)',
            zIndex: 100,
          }}
        >
          {filtered.length === 0 ? (
            <div style={{
              padding: '12px 14px',
              color: 'rgba(234,229,222,0.3)',
              fontSize: 'var(--text-sm, 14px)',
            }}>
              No countries found
            </div>
          ) : (
            filtered.map((country, i) => (
              <div
                key={country.code}
                onClick={() => handleSelect(country)}
                style={{
                  padding: '10px 14px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  cursor: 'pointer',
                  background: i === highlightIdx
                    ? 'rgba(181,110,69,0.1)'
                    : value === country.code
                      ? 'rgba(74,124,89,0.08)'
                      : 'transparent',
                  transition: 'background 0.1s',
                  borderBottom: i < filtered.length - 1 ? '1px solid rgba(234,229,222,0.03)' : 'none',
                }}
                onMouseEnter={() => setHighlightIdx(i)}
              >
                <span style={{
                  fontSize: 'var(--text-sm, 14px)',
                  color: 'var(--color-stone, #EAE5DE)',
                  fontWeight: value === country.code ? 600 : 400,
                }}>
                  {country.name}
                </span>
                <span style={{
                  fontSize: 'var(--text-xs, 12px)',
                  color: 'rgba(234,229,222,0.3)',
                  flexShrink: 0,
                  marginLeft: 8,
                }}>
                  {country.phonePrefix}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
