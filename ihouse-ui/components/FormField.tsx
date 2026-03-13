'use client';

/**
 * Phase 575 — FormField Component
 *
 * Reusable form field with:
 *   - Label + required indicator
 *   - Error message display
 *   - Validation rules (required, minLength, maxLength, pattern, custom)
 *   - Consistent styling
 *   - Accessible aria attributes
 *
 * Usage:
 *   <FormField label="Guest Name" name="guest_name" required error={errors.guest_name}>
 *     <input ... />
 *   </FormField>
 *
 *   const { validate, errors, clearErrors } = useFormValidation(rules);
 */

import React, { useState, useCallback, ReactNode } from 'react';

// ---------------------------------------------------------------------------
// FormField — label wrapper with error display
// ---------------------------------------------------------------------------

interface FormFieldProps {
    label: string;
    name: string;
    error?: string;
    required?: boolean;
    hint?: string;
    children: ReactNode;
}

export function FormField({ label, name, error, required, hint, children }: FormFieldProps) {
    return (
        <div style={{ marginBottom: 'var(--space-4)' }}>
            <label
                htmlFor={name}
                style={{
                    display: 'block',
                    fontSize: 'var(--text-xs)',
                    fontWeight: 600,
                    color: error ? 'var(--color-danger)' : 'var(--color-text-dim)',
                    marginBottom: 'var(--space-1)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                }}
            >
                {label}
                {required && <span style={{ color: 'var(--color-danger)', marginLeft: 2 }}>*</span>}
            </label>
            {children}
            {hint && !error && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-1)' }}>
                    {hint}
                </div>
            )}
            {error && (
                <div
                    role="alert"
                    style={{
                        fontSize: 'var(--text-xs)',
                        color: 'var(--color-danger)',
                        marginTop: 'var(--space-1)',
                        fontWeight: 500,
                    }}
                >
                    {error}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Validation rules + hook
// ---------------------------------------------------------------------------

interface ValidationRule {
    required?: boolean | string;
    minLength?: number | { value: number; message: string };
    maxLength?: number | { value: number; message: string };
    pattern?: RegExp | { value: RegExp; message: string };
    validate?: (value: string) => true | string;
}

type ValidationRules = Record<string, ValidationRule>;
type ValidationErrors = Record<string, string>;

export function useFormValidation(rules: ValidationRules) {
    const [errors, setErrors] = useState<ValidationErrors>({});

    const validate = useCallback((data: Record<string, string>): boolean => {
        const newErrors: ValidationErrors = {};

        for (const [field, rule] of Object.entries(rules)) {
            const value = (data[field] || '').trim();

            // Required
            if (rule.required) {
                if (!value) {
                    const msg = typeof rule.required === 'string' ? rule.required : `${field} is required`;
                    newErrors[field] = msg;
                    continue;
                }
            }

            if (!value) continue;  // Skip other validations if empty and not required

            // Min length
            if (rule.minLength) {
                const min = typeof rule.minLength === 'number' ? rule.minLength : rule.minLength.value;
                const msg = typeof rule.minLength === 'number'
                    ? `Must be at least ${min} characters`
                    : rule.minLength.message;
                if (value.length < min) {
                    newErrors[field] = msg;
                    continue;
                }
            }

            // Max length
            if (rule.maxLength) {
                const max = typeof rule.maxLength === 'number' ? rule.maxLength : rule.maxLength.value;
                const msg = typeof rule.maxLength === 'number'
                    ? `Must be at most ${max} characters`
                    : rule.maxLength.message;
                if (value.length > max) {
                    newErrors[field] = msg;
                    continue;
                }
            }

            // Pattern
            if (rule.pattern) {
                const re = rule.pattern instanceof RegExp ? rule.pattern : rule.pattern.value;
                const msg = rule.pattern instanceof RegExp
                    ? `Invalid format`
                    : rule.pattern.message;
                if (!re.test(value)) {
                    newErrors[field] = msg;
                    continue;
                }
            }

            // Custom validate
            if (rule.validate) {
                const result = rule.validate(value);
                if (result !== true) {
                    newErrors[field] = result;
                }
            }
        }

        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    }, [rules]);

    const clearErrors = useCallback(() => setErrors({}), []);
    const clearField = useCallback((field: string) => {
        setErrors(prev => {
            const next = { ...prev };
            delete next[field];
            return next;
        });
    }, []);

    return { errors, validate, clearErrors, clearField };
}

// ---------------------------------------------------------------------------
// Standard input styles
// ---------------------------------------------------------------------------

export const inputStyle: React.CSSProperties = {
    width: '100%',
    background: 'var(--color-surface-2)',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-md)',
    color: 'var(--color-text)',
    fontSize: 'var(--text-sm)',
    padding: 'var(--space-2) var(--space-3)',
    transition: 'border-color 0.15s ease',
};

export const inputErrorStyle: React.CSSProperties = {
    ...inputStyle,
    borderColor: 'var(--color-danger)',
};
