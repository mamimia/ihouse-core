'use client';

/**
 * Phase 576 — Booking Form Validation Rules
 * Phase 577 — Property Form Validation Rules
 * Phase 578 — Task Form Validation Rules
 *
 * Centralized validation rules for all CRUD forms.
 * Used with useFormValidation from FormField.tsx.
 */

// ---------------------------------------------------------------------------
// Phase 576 — Booking validation rules
// ---------------------------------------------------------------------------

export const bookingValidationRules = {
    property_id: {
        required: 'Property is required',
        minLength: 1,
    },
    guest_name: {
        required: 'Guest name is required',
        minLength: { value: 2, message: 'Name must be at least 2 characters' },
        maxLength: { value: 200, message: 'Name must be at most 200 characters' },
    },
    check_in: {
        required: 'Check-in date is required',
        pattern: {
            value: /^\d{4}-\d{2}-\d{2}$/,
            message: 'Must be YYYY-MM-DD format',
        },
    },
    check_out: {
        required: 'Check-out date is required',
        pattern: {
            value: /^\d{4}-\d{2}-\d{2}$/,
            message: 'Must be YYYY-MM-DD format',
        },
        validate: (value: string) => {
            // Will be compared with check_in at form submit time
            return true;
        },
    },
    source: {
        required: 'Booking source is required',
    },
};

/**
 * Cross-field validation: check_out must be after check_in.
 */
export function validateBookingDates(data: Record<string, string>): string | null {
    if (data.check_in && data.check_out) {
        if (data.check_out <= data.check_in) {
            return 'Check-out must be after check-in';
        }
    }
    return null;
}

// ---------------------------------------------------------------------------
// Phase 577 — Property validation rules
// ---------------------------------------------------------------------------

export const propertyValidationRules = {
    name: {
        required: 'Property name is required',
        minLength: { value: 2, message: 'Name must be at least 2 characters' },
        maxLength: { value: 200, message: 'Name must be at most 200 characters' },
    },
    property_type: {
        required: 'Property type is required',
    },
    address: {
        maxLength: { value: 500, message: 'Address must be at most 500 characters' },
    },
    city: {
        maxLength: { value: 100, message: 'City must be at most 100 characters' },
    },
    country: {
        maxLength: { value: 100, message: 'Country must be at most 100 characters' },
    },
    bedrooms: {
        validate: (value: string) => {
            const num = parseInt(value, 10);
            if (isNaN(num) || num < 0 || num > 50) return 'Bedrooms must be 0-50';
            return true;
        },
    },
    max_guests: {
        validate: (value: string) => {
            const num = parseInt(value, 10);
            if (isNaN(num) || num < 1 || num > 100) return 'Max guests must be 1-100';
            return true;
        },
    },
};

// ---------------------------------------------------------------------------
// Phase 578 — Task validation rules
// ---------------------------------------------------------------------------

export const taskValidationRules = {
    task_kind: {
        required: 'Task type is required',
    },
    property_id: {
        required: 'Property is required',
    },
    priority: {
        pattern: {
            value: /^(critical|high|normal|low)$/,
            message: 'Priority must be critical, high, normal, or low',
        },
    },
    notes: {
        maxLength: { value: 2000, message: 'Notes must be at most 2000 characters' },
    },
    deadline: {
        validate: (value: string) => {
            if (!value) return true;
            const d = new Date(value);
            if (isNaN(d.getTime())) return 'Invalid date';
            if (d < new Date()) return 'Deadline cannot be in the past';
            return true;
        },
    },
};

// ---------------------------------------------------------------------------
// Maintenance validation rules
// ---------------------------------------------------------------------------

export const maintenanceValidationRules = {
    property_id: {
        required: 'Property is required',
    },
    title: {
        required: 'Title is required',
        minLength: { value: 3, message: 'Title must be at least 3 characters' },
        maxLength: { value: 200, message: 'Title must be at most 200 characters' },
    },
    description: {
        maxLength: { value: 5000, message: 'Description must be at most 5000 characters' },
    },
    priority: {
        pattern: {
            value: /^(low|medium|high|urgent)$/,
            message: 'Priority must be low, medium, high, or urgent',
        },
    },
};
