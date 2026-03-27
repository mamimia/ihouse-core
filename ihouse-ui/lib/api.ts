// Phase 153 — iHouse Core API client
// Phase 163 — Financial Dashboard API methods added
// Phase 169 — Admin Settings: getProviders, getPermissions, patchProvider
// Phase 179 — Auth: login()
// Phase 186 — Auth: logout(), apiFetch auto-logout on 401/403
// Typed fetch wrapper for all backend endpoints.
// Base URL: NEXT_PUBLIC_API_URL env var (or http://localhost:8000 for dev).

const BASE_URL =
    process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

let _token: string | null =
    typeof window !== "undefined" ? localStorage.getItem("ihouse_token") : null;

export function setToken(token: string) {
    _token = token;
    if (typeof window !== "undefined") {
        localStorage.setItem("ihouse_token", token);
    }
}

export function clearToken() {
    _token = null;
    if (typeof window !== "undefined") {
        localStorage.removeItem("ihouse_token");
    }
}

export function getToken(): string | null {
    return _token;
}

// ---------------------------------------------------------------------------
// Phase 186 — Client-side logout helper (also called by apiFetch on 401/403)
// ---------------------------------------------------------------------------

export function performClientLogout(redirectPath = '/login'): void {
    clearToken();
    // Clear cookie so middleware also evicts
    if (typeof document !== 'undefined') {
        document.cookie = 'ihouse_token=; path=/; max-age=0; SameSite=Lax';
    }
    if (typeof window !== 'undefined') {
        window.location.href = redirectPath;
    }
}

// ---------------------------------------------------------------------------
// Core fetch helper
// ---------------------------------------------------------------------------

export async function apiFetch<T>(path: string, init?: RequestInit, _retryCount = 0): Promise<T> {
    const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(init?.headers as Record<string, string>),
    };
    if (_token) headers["Authorization"] = `Bearer ${_token}`;
    
    // Phase 847 — JWT Simulation (Preview As)
    if (typeof window !== 'undefined') {
        const previewRole = sessionStorage.getItem('ihouse_preview_role');
        if (previewRole) {
            headers["X-Preview-Role"] = previewRole;
        }
    }

    let resp: Response;
    try {
        resp = await fetch(`${BASE_URL}${path}`, { ...init, headers });
    } catch (networkErr) {
        // Phase 568: offline / network failure
        if (typeof window !== 'undefined') {
            window.dispatchEvent(new CustomEvent('ihouse:offline'));
        }
        // Retry once on network error for GET requests
        if (_retryCount === 0 && (!init?.method || init.method === 'GET')) {
            await new Promise(r => setTimeout(r, 500));
            return apiFetch<T>(path, init, 1);
        }
        throw new ApiError(0, "NETWORK_ERROR", { message: "Network unavailable" });
    }

    // Phase 568: retry once on 5xx for GET requests
    if (resp.status >= 500 && _retryCount === 0 && (!init?.method || init.method === 'GET')) {
        await new Promise(r => setTimeout(r, 500));
        return apiFetch<T>(path, init, 1);
    }

    if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        const detail = body?.detail || '';

        // Phase 862 P44: Distinguish auth failures from capability denials.
        // CAPABILITY_DENIED means the user IS authenticated but lacks a specific
        // delegated capability — do NOT logout, just throw the error.
        // Phase 866: PREVIEW_READ_ONLY means preview mode blocked a mutation — same treatment.
        // Only auto-logout on true auth failures (missing/expired/invalid token).
        if (resp.status === 401 || resp.status === 403) {
            const isCapabilityDenial = typeof detail === 'string' && detail.startsWith('CAPABILITY_DENIED');
            const isPreviewBlock = body?.error?.code === 'PREVIEW_READ_ONLY' || body?.ok === false && body?.error?.code === 'PREVIEW_READ_ONLY';
            if (!isCapabilityDenial && !isPreviewBlock && _token) {
                performClientLogout('/login');
            }
        }
        throw new ApiError(resp.status, body?.error || "UNKNOWN_ERROR", body);
    }
    const body = await resp.json();
    // Phase 789: Unwrap canonical {ok, data} envelope from backend
    // Some routers (bookings, auth, checkin, session) use api.envelope.ok()
    // which wraps responses in {ok: true, data: {...}}. Transparently unwrap
    // so consumer code always sees the inner payload directly.
    if (body && typeof body === 'object' && body.ok === true && 'data' in body) {
        return body.data as T;
    }
    return body as T;
}

export class ApiError extends Error {
    constructor(
        public status: number,
        public code: string,
        public body: unknown
    ) {
        super(`API ${status}: ${code}`);
    }
}

// ---------------------------------------------------------------------------
// Endpoint types
// ---------------------------------------------------------------------------

export interface OperationsToday {
    tenant_id: string;
    generated_at: string;
    date: string;
    arrivals_today: number;
    departures_today: number;
    cleanings_due_today: number;
}

export interface Task {
    task_id: string;
    kind: string;
    status: string;
    priority: string;
    urgency: string;
    worker_role: string;
    ack_sla_minutes: number;
    booking_id: string;
    property_id: string;
    due_date: string;
    title: string;
    description?: string;
    created_at: string;
    updated_at: string;
}

export interface TaskListResponse {
    tenant_id: string;
    count: number;
    tasks: Task[];
}

export interface OutboundHealthProvider {
    provider: string;
    ok_count: number;
    failed_count: number;
    dry_run_count: number;
    skipped_count: number;
    last_sync_at: string | null;
    failure_rate_7d: number | null;
}

export interface OutboundHealthResponse {
    tenant_id: string;
    provider_count: number;
    checked_at: string;
    providers: OutboundHealthProvider[];
}

// Phase 157 — DLQ summary (used by admin and dashboard pages via /admin/dlq)
export interface DlqSummaryEntry {
    id: number;
    provider: string;
    event_type: string;
    rejection_code: string;
    received_at: string;
    status: string;
}

export interface DlqSummaryResponse {
    tenant_id: string;
    count: number;
    entries: DlqSummaryEntry[];
}

// ---------------------------------------------------------------------------
// Financial types (Phase 163)
// ---------------------------------------------------------------------------

export interface FinancialCurrencyBucket {
    gross: string;
    commission: string;
    net: string;
    booking_count: number;
}

export interface FinancialSummaryResponse {
    tenant_id: string;
    period: string;
    total_bookings: number;
    currencies: Record<string, FinancialCurrencyBucket>;
    base_currency?: string;
    conversion_warnings?: string[];
}

export interface FinancialByProviderResponse {
    tenant_id: string;
    period: string;
    providers: Record<string, Record<string, FinancialCurrencyBucket>>;
    base_currency?: string;
    conversion_warnings?: string[];
}

export interface FinancialByPropertyResponse {
    tenant_id: string;
    period: string;
    properties: Record<string, Record<string, FinancialCurrencyBucket>>;
    base_currency?: string;
    conversion_warnings?: string[];
}

export interface LifecycleDistributionResponse {
    tenant_id: string;
    period: string;
    total_bookings: number;
    distribution: Record<string, number>;
}

export interface ReconciliationResponse {
    tenant_id?: string;
    period?: string;
    exceptions?: Array<{ booking_id: string; issue?: string }>;
    count?: number;
}

export interface OwnerStatementLineItem {
    booking_id: string;
    provider: string;
    currency: string | null;
    check_in: string | null;
    check_out: string | null;
    gross: string | null;
    ota_commission: string | null;
    net_to_property: string | null;
    source_confidence: string;
    epistemic_tier: string;
    lifecycle_status: string | null;
    event_kind: string;
    recorded_at: string | null;
}

export interface OwnerStatementSummary {
    currency: string;
    gross_total: string | null;
    ota_commission_total: string | null;
    net_to_property_total: string | null;
    management_fee_pct: string;
    management_fee_amount: string | null;
    owner_net_total: string | null;
    booking_count: number;
    ota_collecting_excluded_from_net: number;
    overall_epistemic_tier: string;
}

export interface OwnerStatementResponse {
    tenant_id: string;
    property_id: string;
    month: string;
    total_bookings_checked: number;
    summary: OwnerStatementSummary;
    line_items: OwnerStatementLineItem[];
}

// ---------------------------------------------------------------------------
// Phase 169 — Admin Settings types
// ---------------------------------------------------------------------------

export interface Provider {
    provider: string;
    tier: string;
    supports_api_write: boolean;
    supports_ical_push: boolean;
    supports_ical_pull: boolean;
    rate_limit_per_min: number;
    auth_method: string;
    notes: string | null;
    updated_at: string | null;
}

export interface ProviderListResponse {
    total: number;
    providers: Provider[];
}

export interface Permission {
    user_id: string;
    role: string;
    permissions: Record<string, unknown>;
    created_at?: string;
}

export interface PermissionListResponse {
    tenant_id: string;
    permissions: Permission[];
}

// ---------------------------------------------------------------------------
// Phase 179 — Auth types
// ---------------------------------------------------------------------------

export interface LoginResponse {
    token: string;
    tenant_id: string;
    role: string;  // Phase 397
    expires_in: number;
    user_id?: string;       // Pre-801: Supabase Auth UUID
    email?: string;         // Pre-801: user email
    full_name?: string;     // Pre-801: user full name
    auth_method?: string;   // Pre-801: 'supabase' for production login
    language?: string;      // Phase 839: Localization preference
    supabase_access_token?: string;   // Supabase session — for linkIdentity/updateUser
    supabase_refresh_token?: string;  // Supabase session — for linkIdentity/updateUser
}

// Phase 191 — Multi-Currency Overview types
export interface CurrencyOverviewRow {
    currency: string;
    booking_count: number;
    gross_total: string;
    net_total: string;
    avg_commission_rate: string | null;
}

export interface MultiCurrencyOverviewResponse {
    tenant_id: string;
    period: string;
    total_bookings: number;
    currencies: CurrencyOverviewRow[];
}

// Phase 192/193 — Guest Profile types
export interface Guest {
    id: string;
    tenant_id?: string;
    full_name: string;
    email: string | null;
    phone: string | null;
    nationality: string | null;
    passport_no: string | null;
    notes: string | null;
    created_at: string;
    updated_at: string;
}

export interface GuestListResponse {
    count: number;
    guests: Guest[];
}

// Phase 190 — Audit Event types
export interface AuditEvent {
    id: number;
    actor_id: string;
    action: string;
    entity_type: string;
    entity_id: string;
    payload: Record<string, unknown>;
    occurred_at: string;
}

export interface AuditEventListResponse {
    tenant_id: string;
    count: number;
    events: AuditEvent[];
}

// Phase 200 — Booking Calendar
export interface Booking {
    booking_id: string;
    source: string | null;
    reservation_ref: string | null;
    property_id: string | null;
    status: string | null;
    check_in: string | null;
    check_out: string | null;
    version: number | null;
    created_at: string | null;
    updated_at: string | null;
}

export interface BookingListResponse {
    tenant_id: string;
    count: number;
    bookings: Booking[];
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export const api = {
    // Pre-801: Production login (email + password → Supabase Auth)
    loginWithEmail: (email: string, password: string): Promise<LoginResponse> =>
        apiFetch('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
        }),

    // Phase 179 — Dev login (backward compat, uses tenant_id + secret)
    login: (tenant_id: string, secret: string, role: string = 'manager'): Promise<LoginResponse> =>
        apiFetch('/auth/login-session', {
            method: 'POST',
            body: JSON.stringify({ tenant_id, secret, role }),
        }),

    // Phase 186 — Logout
    // Phase 870 P1-1: Also sign out from Supabase to invalidate the Supabase session
    logout: async (): Promise<void> => {
        try {
            // Best-effort: call server to clear cookie. Ignore errors.
            await fetch(`${BASE_URL}/auth/logout`, { method: 'POST' });
        } catch (_) {
            // swallow — client-side cleanup still runs
        }
        // Phase 870: Invalidate Supabase session so getSession() returns null
        try {
            const { supabase } = await import('./supabaseClient');
            if (supabase) {
                await supabase.auth.signOut();
            }
        } catch (_) {
            // swallow — client-side cleanup still runs
        }
        performClientLogout('/login');
    },

    getOperationsToday: (): Promise<OperationsToday> =>
        apiFetch("/operations/today"),

    getTasks: (params?: {
        status?: string;
        priority?: string;
        limit?: number;
    }): Promise<TaskListResponse> => {
        const q = new URLSearchParams();
        if (params?.status) q.set("status", params.status);
        if (params?.priority) q.set("priority", params.priority);
        if (params?.limit) q.set("limit", String(params.limit));
        return apiFetch(`/tasks${q.size ? "?" + q : ""}`);
    },

    getOutboundHealth: (): Promise<OutboundHealthResponse> =>
        apiFetch("/admin/outbound-health"),

    // Phase 372: Audit log
    getAuditLog: (limit?: number): Promise<{ entries: unknown[] }> =>
        apiFetch(`/admin/audit-log${limit ? `?limit=${limit}` : ""}`),

    getDlq: (params?: {
        status?: string;
        limit?: number;
    }): Promise<DlqSummaryResponse> => {
        const q = new URLSearchParams();
        if (params?.status) q.set("status", params.status);
        if (params?.limit) q.set("limit", String(params.limit));
        return apiFetch(`/admin/dlq${q.size ? "?" + q : ""}`);
    },

    // Phase 157 — Worker task actions
    // Phase 882c — Added worker_role param for preview role-scoped task filtering
    getWorkerTasks: (params?: {
        status?: string;
        priority?: string;
        limit?: number;
        worker_role?: string;
    }): Promise<WorkerTaskListResponse> => {
        const q = new URLSearchParams();
        if (params?.status) q.set("status", params.status);
        if (params?.priority) q.set("priority", params.priority);
        if (params?.limit) q.set("limit", String(params.limit));
        if (params?.worker_role) q.set("worker_role", params.worker_role);
        return apiFetch(`/worker/tasks${q.size ? "?" + q : ""}`);
    },

    acknowledgeTask: (id: string): Promise<WorkerTask> =>
        apiFetch(`/worker/tasks/${id}/acknowledge`, { method: "PATCH" }),

    startTask: (id: string): Promise<WorkerTask> =>
        apiFetch(`/worker/tasks/${id}/start`, { method: "PATCH" }),

    completeTask: (id: string, notes?: string): Promise<WorkerTask> =>
        apiFetch(`/worker/tasks/${id}/complete`, {
            method: "PATCH",
            body: JSON.stringify({ notes: notes ?? "" }),
        }),

    // Phase 163 — Financial Dashboard
    getFinancialSummary: (period: string, baseCurrency?: string): Promise<FinancialSummaryResponse> => {
        const q = new URLSearchParams({ period });
        if (baseCurrency) q.set("base_currency", baseCurrency);
        return apiFetch(`/financial/summary?${q}`);
    },

    getFinancialByProvider: (period: string, baseCurrency?: string): Promise<FinancialByProviderResponse> => {
        const q = new URLSearchParams({ period });
        if (baseCurrency) q.set("base_currency", baseCurrency);
        return apiFetch(`/financial/by-provider?${q}`);
    },

    getFinancialByProperty: (period: string, baseCurrency?: string): Promise<FinancialByPropertyResponse> => {
        const q = new URLSearchParams({ period });
        if (baseCurrency) q.set("base_currency", baseCurrency);
        return apiFetch(`/financial/by-property?${q}`);
    },

    getLifecycleDistribution: (period: string): Promise<LifecycleDistributionResponse> =>
        apiFetch(`/financial/lifecycle-distribution?period=${period}`),

    getReconciliation: (period: string): Promise<ReconciliationResponse> =>
        apiFetch(`/admin/reconciliation?period=${period}`),

    // Phase 164 — Owner Statement
    getOwnerStatement: (
        propertyId: string,
        month: string,
        managementFeePct?: string,
    ): Promise<OwnerStatementResponse> => {
        const q = new URLSearchParams({ month });
        if (managementFeePct) q.set("management_fee_pct", managementFeePct);
        return apiFetch(`/owner-statement/${encodeURIComponent(propertyId)}?${q}`);
    },

    // Phase 169 — Admin Settings
    getProviders: (): Promise<ProviderListResponse> =>
        apiFetch("/admin/registry/providers"),

    getPermissions: (): Promise<PermissionListResponse> =>
        apiFetch("/permissions"),

    patchProvider: (
        provider: string,
        updates: Record<string, unknown>,
    ): Promise<Provider> =>
        apiFetch(`/admin/registry/providers/${encodeURIComponent(provider)}`, {
            method: "PATCH",
            body: JSON.stringify(updates),
        }),

    // Phase 842 — Tenant Integrations
    getTenantIntegrations: (): Promise<{ integrations: any[] }> =>
        apiFetch("/admin/integrations"),

    updateTenantIntegration: (
        provider: string,
        updates: Record<string, unknown>
    ): Promise<any> =>
        apiFetch(`/admin/integrations/${encodeURIComponent(provider)}`, {
            method: "PUT",
            body: JSON.stringify(updates),
        }),

    testTenantIntegration: (
        provider: string,
        credentials: Record<string, unknown>
    ): Promise<{ success: boolean; message: string }> =>
        apiFetch(`/admin/integrations/${encodeURIComponent(provider)}/test`, {
            method: "POST",
            body: JSON.stringify({ credentials }),
        }),

    // Phase 190 — Audit Events (Manager UI)
    getAuditEvents: (params?: {
        entity_type?: string;
        entity_id?: string;
        actor_id?: string;
        limit?: number;
    }): Promise<AuditEventListResponse> => {
        const q = new URLSearchParams();
        if (params?.entity_type) q.set("entity_type", params.entity_type);
        if (params?.entity_id) q.set("entity_id", params.entity_id);
        if (params?.actor_id) q.set("actor_id", params.actor_id);
        if (params?.limit) q.set("limit", String(params.limit));
        return apiFetch(`/admin/audit${q.size ? "?" + q : ""}`);
    },

    // Phase 191 — Multi-Currency Financial Overview
    getMultiCurrencyOverview: (
        period: string,
        currency?: string,
    ): Promise<MultiCurrencyOverviewResponse> => {
        const q = new URLSearchParams({ period });
        if (currency) q.set("currency", currency);
        return apiFetch(`/financial/multi-currency-overview?${q}`);
    },

    // Phase 193 — Guest Profile
    listGuests: (search?: string, limit?: number): Promise<GuestListResponse> => {
        const q = new URLSearchParams();
        if (search) q.set("search", search);
        if (limit) q.set("limit", String(limit));
        return apiFetch(`/guests${q.size ? "?" + q : ""}`);
    },
    getGuest: (id: string): Promise<Guest> =>
        apiFetch(`/guests/${id}`),
    createGuest: (body: { full_name: string; email?: string; phone?: string; nationality?: string; passport_no?: string; notes?: string }): Promise<Guest> =>
        apiFetch("/guests", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
    patchGuest: (id: string, body: Partial<Omit<Guest, "id" | "tenant_id" | "created_at" | "updated_at">>): Promise<Guest> =>
        apiFetch(`/guests/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),

    // Phase 200 — Booking Calendar
    getBookings: (params?: {
        property_id?: string;
        status?: string;
        source?: string;
        check_in_from?: string;
        check_in_to?: string;
        limit?: number;
    }): Promise<BookingListResponse> => {
        const q = new URLSearchParams();
        if (params?.property_id) q.set('property_id', params.property_id);
        if (params?.status) q.set('status', params.status);
        if (params?.source) q.set('source', params.source);
        if (params?.check_in_from) q.set('check_in_from', params.check_in_from);
        if (params?.check_in_to) q.set('check_in_to', params.check_in_to);
        if (params?.limit) q.set('limit', String(params.limit));
        return apiFetch(`/bookings${q.size ? '?' + q : ''}`);
    },

    // Strategic pivot — Manual Booking (main path)
    createManualBooking: (body: {
        property_id: string;
        check_in: string;
        check_out: string;
        guest_name: string;
        booking_source?: string;
        notes?: string;
        number_of_guests?: number;
        tasks_opt_out?: string[];
    }): Promise<{ booking_id: string; status: string; tasks_created: string[]; ota_blocked: string | null }> =>
        apiFetch('/bookings/manual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        }),

    // Strategic pivot — iCal Feed (main path)
    connectIcalFeed: (body: {
        property_id: string;
        ical_url: string;
    }): Promise<{ connection_id: string; bookings_created: number; status: string }> =>
        apiFetch('/integrations/ical/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        }),

    // Properties list (for dropdowns)
    listProperties: (): Promise<{ properties: Array<{ property_id: string; display_name: string; status: string }> }> =>
        apiFetch('/properties'),

    createProperty: (body: {
        property_id: string;
        display_name?: string;
        timezone?: string;
        base_currency?: string;
    }): Promise<{ property_id: string; display_name: string; timezone: string; base_currency: string }> =>
        apiFetch('/properties', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        }),

    // Phase 201 — Worker Channel Preferences
    getWorkerPreferences: (): Promise<WorkerPreferencesResponse> =>
        apiFetch('/worker/preferences'),

    setWorkerPreference: (channel_type: string, channel_id: string): Promise<{ status: string; channel_type: string; channel_id: string }> =>
        apiFetch('/worker/preferences', {
            method: 'PUT',
            body: JSON.stringify({ channel_type, channel_id }),
        }),

    deleteWorkerPreference: (channel_type: string): Promise<{ status: string; channel_type: string }> =>
        apiFetch(`/worker/preferences/${encodeURIComponent(channel_type)}`, {
            method: 'DELETE',
        }),

    // Phase 202 — Notification History
    getWorkerNotifications: (params?: { limit?: number; status?: string }): Promise<NotificationHistoryResponse> => {
        const q = new URLSearchParams();
        if (params?.limit) q.set('limit', String(params.limit));
        if (params?.status) q.set('status', params.status);
        return apiFetch(`/worker/notifications${q.size ? '?' + q : ''}`);
    },

    // Phase 205 — DLQ Inspector + Replay
    getDlqEntries: (params?: {
        source?: string;
        status?: 'all' | 'pending' | 'applied' | 'error';
        limit?: number;
    }): Promise<DlqListResponse> => {
        const q = new URLSearchParams();
        if (params?.source) q.set('source', params.source);
        if (params?.status) q.set('status', params.status);
        if (params?.limit) q.set('limit', String(params.limit));
        const qs = q.toString() ? `?${q}` : '';
        return apiFetch(`/admin/dlq${qs}`);
    },

    replayDlqEntry: (envelope_id: string): Promise<ReplayResult> =>
        apiFetch(`/admin/dlq/${encodeURIComponent(envelope_id)}/replay`, {
            method: 'POST',
        }),

    // Phase 216 — Portfolio Dashboard (added Phase 288)
    getPortfolioDashboard: (params?: {
        as_of?: string;
        month?: string;
    }): Promise<PortfolioDashboardResponse> => {
        const q = new URLSearchParams();
        if (params?.as_of) q.set('as_of', params.as_of);
        if (params?.month) q.set('month', params.month);
        return apiFetch(`/portfolio/dashboard${q.size ? '?' + q : ''}`);
    },

    // Phase 289 — Booking detail helpers
    getBookingHistory: (booking_id: string): Promise<{ booking_id: string; events: BookingHistoryEntry[]; count: number }> =>
        apiFetch(`/booking-history/${encodeURIComponent(booking_id)}`),

    getBookingAmendments: (booking_id: string): Promise<{ amendments: BookingAmendment[]; count: number }> =>
        apiFetch(`/bookings/${encodeURIComponent(booking_id)}/amendments`),

    getBookingFinancial: (booking_id: string): Promise<BookingFinancialDetail> =>
        apiFetch(`/financial/${encodeURIComponent(booking_id)}`),

    // Phase 291 — Cashflow Projection
    getCashflowProjection: (period: string, baseCurrency?: string): Promise<CashflowProjectionResponse> => {
        const q = new URLSearchParams({ period });
        if (baseCurrency) q.set('base_currency', baseCurrency);
        return apiFetch(`/cashflow/projection?${q}`);
    },

    // Phase 311 — Admin notification log
    getNotificationLog: (opts?: { limit?: number; reference_id?: string }): Promise<NotificationLogResponse> => {
        const q = new URLSearchParams();
        if (opts?.limit) q.set('limit', String(opts.limit));
        if (opts?.reference_id) q.set('reference_id', opts.reference_id);
        const qs = q.toString();
        return apiFetch(`/notifications/log${qs ? '?' + qs : ''}`);
    },

    // Phase 312 — Manager Copilot
    getMorningBriefing: (language = 'en'): Promise<MorningBriefingResponse> =>
        apiFetch('/ai/copilot/morning-briefing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ language }),
        }),

    // Phase 398 — Booking Check-in / Check-out
    checkinBooking: (bookingId: string): Promise<{ status: string; booking_id: string; checked_in_at: string; noop: boolean }> =>
        apiFetch(`/bookings/${bookingId}/checkin`, { method: 'POST' }),

    checkoutBooking: (bookingId: string): Promise<{ status: string; booking_id: string; checked_out_at: string; cleaning_tasks_created: number; noop: boolean }> =>
        apiFetch(`/bookings/${bookingId}/checkout`, { method: 'POST' }),

    // Phase 510 — Guest Feedback
    getGuestFeedback: (params?: { property_id?: string; limit?: number }): Promise<{ total: number; entries: unknown[] }> => {
        const q = new URLSearchParams();
        if (params?.property_id) q.set('property_id', params.property_id);
        if (params?.limit) q.set('limit', String(params.limit));
        return apiFetch(`/admin/guest-feedback${q.size ? '?' + q : ''}`);
    },

    // Phase 511 — Staff Performance
    getStaffPerformance: (): Promise<{ workers: unknown[] }> =>
        apiFetch('/admin/staff/performance'),

    // Phase 512 — Task Templates
    getTaskTemplates: (): Promise<{ templates: unknown[] }> =>
        apiFetch('/admin/task-templates'),
    createTaskTemplate: (body: { name: string; kind: string; description?: string }): Promise<unknown> =>
        apiFetch('/admin/task-templates', { method: 'POST', body: JSON.stringify(body) }),
    deleteTaskTemplate: (id: string): Promise<unknown> =>
        apiFetch(`/admin/task-templates/${id}`, { method: 'DELETE' }),

    // Phase 513 — Integrations
    getIntegrations: (): Promise<{ properties: unknown[] }> =>
        apiFetch('/admin/integrations'),
    getIntegrationsSummary: (): Promise<{ enabled: number; disabled: number; stale: number; failed: number }> =>
        apiFetch('/admin/integrations/summary'),

    // Phase 514 — Rate Cards
    getRateCards: (propertyId: string): Promise<{ rate_cards: unknown[] }> =>
        apiFetch(`/properties/${propertyId}/rate-cards`),
    getPricingSuggestion: (propertyId: string): Promise<{ suggestions: unknown[] }> =>
        apiFetch(`/pricing/suggestion/${propertyId}`),

    // Phase 545 — Export & Health
    getHealthDetailed: (): Promise<{
        uptime_seconds: number; process_start_utc: string;
        request_counts: Record<string, number>;
        error_counts: Record<string, { '4xx': number; '5xx': number }>;
        latency: Record<string, { count: number; min_ms: number | null; max_ms: number | null; avg_ms: number | null; p95_ms: number | null }>;
    }> => apiFetch('/health/detailed'),

    getExportTypes: (): Promise<{ types: { id: string; label: string; description: string }[] }> =>
        apiFetch('/export/types'),

    exportCSV: (exportType: string, params?: { property_id?: string; date_from?: string; date_to?: string }): Promise<Blob> => {
        const q = new URLSearchParams();
        if (params?.property_id) q.set('property_id', params.property_id);
        if (params?.date_from) q.set('date_from', params.date_from);
        if (params?.date_to) q.set('date_to', params.date_to);
        const headers: Record<string, string> = {};
        if (_token) headers['Authorization'] = `Bearer ${_token}`;
        return fetch(`${BASE_URL}/export/csv/${exportType}${q.size ? '?' + q : ''}`, { headers })
            .then(r => r.blob());
    },

    // Phase 546 — Ops & Messaging
    getTodaysArrivals: (): Promise<{ arrivals: unknown[] }> =>
        apiFetch('/operations/arrivals'),

    getTodaysDepartures: (): Promise<{ departures: unknown[] }> =>
        apiFetch('/operations/departures'),

    getOperationsTodayFull: (): Promise<{
        arrivals_count: number; departures_count: number;
        active_tasks_count: number; sla_breaches_count: number;
        critical_pending_count: number;
    }> => apiFetch('/operations/today'),

    getGuestConversations: (): Promise<{ conversations: unknown[] }> =>
        apiFetch('/guest-messages/conversations'),

    getGuestMessages: (bookingRef: string): Promise<{ messages: unknown[] }> =>
        apiFetch(`/guest-messages/${encodeURIComponent(bookingRef)}`),

    getGuestReplySuggestion: (bookingRef: string): Promise<{ suggestion: string }> =>
        apiFetch(`/guest-messages/${encodeURIComponent(bookingRef)}/suggest`, { method: 'POST' }),

    getNotificationHistory: (params?: { limit?: number }): Promise<{ notifications: unknown[] }> => {
        const q = new URLSearchParams();
        if (params?.limit) q.set('limit', String(params.limit));
        return apiFetch(`/notifications/history${q.size ? '?' + q : ''}`);
    },

    // Phase 547 — Settings & Session
    getSessionInfo: (): Promise<{ tenant_id: string; role: string; email?: string }> =>
        apiFetch('/auth/session'),

    updatePassword: (currentPassword: string, newPassword: string): Promise<{ status: string }> =>
        apiFetch('/auth/password', {
            method: 'PUT',
            body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
        }),

    getSchedulerStatus: (): Promise<{ total_jobs: number; jobs: Record<string, { description: string; interval_hours: number }> }> =>
        apiFetch('/admin/scheduler/status'),

    triggerJob: (jobName: string): Promise<{ status: string; job: string }> =>
        apiFetch(`/admin/scheduler/trigger/${encodeURIComponent(jobName)}`, { method: 'POST' }),

    // Phase 547 — Analytics
    getAnalyticsSummary: (period?: string): Promise<unknown> => {
        const q = period ? `?period=${period}` : '';
        return apiFetch(`/analytics/summary${q}`);
    },
};

// Phase 157 — Worker task types
// Phase 201 — Worker channel preference types
export interface WorkerChannel {
    channel_type: string;  // 'line' | 'whatsapp' | 'telegram'
    channel_id: string;
    active: boolean;
    created_at: string | null;
    updated_at: string | null;
}

export interface WorkerPreferencesResponse {
    user_id: string;
    channels: WorkerChannel[];
}

// Phase 202 — Notification delivery types
export interface NotificationDelivery {
    notification_delivery_id: string;
    channel_type: string;
    channel_id: string;
    status: 'sent' | 'failed';
    error_message: string | null;
    trigger_reason: string | null;
    task_id: string | null;
    dispatched_at: string;
}

export interface NotificationHistoryResponse {
    user_id: string;
    notifications: NotificationDelivery[];
    count: number;
}

export interface WorkerTask {
    task_id: string;
    kind: string;         // CLEANING | CHECKIN_PREP | CHECKOUT_PREP | MAINTENANCE
    status: string;       // pending | acknowledged | in_progress | completed
    priority: string;     // LOW | MEDIUM | HIGH | CRITICAL
    urgency: string;
    worker_role: string;
    ack_sla_minutes: number;
    booking_id: string;
    property_id: string;
    due_date: string;
    due_time?: string;
    title: string;
    description?: string;
    notes?: string;
    assigned_to?: string;
    created_at: string;
    updated_at: string;
}

export interface WorkerTaskListResponse {
    tenant_id: string;
    count: number;
    tasks: WorkerTask[];
}

// ---------------------------------------------------------------------------
// Phase 205 — DLQ Inspector + Replay (types — methods added to api object above)
// ---------------------------------------------------------------------------

export interface DlqEntry {
    envelope_id: string | null;
    source: string | null;
    replay_result: string | null;
    status: string; // 'pending' | 'applied' | 'error'
    error_reason: string | null;
    created_at: string | null;
    replayed_at: string | null;
    payload_preview: string | null;
    raw_payload?: string | null;
}

export interface DlqListResponse {
    total: number;
    status_filter: string;
    source_filter: string | null;
    entries: DlqEntry[];
}

export interface ReplayResult {
    envelope_id: string;
    row_id: number;
    replay_result: string | null;
    replay_trace_id: string | null;
    already_replayed: boolean;
}

// ---------------------------------------------------------------------------
// Phase 216 — Portfolio Dashboard types (added Phase 288)
// ---------------------------------------------------------------------------

export interface PortfolioProperty {
    property_id: string;
    occupancy: {
        active_bookings: number;
        arrivals_today: number;
        departures_today: number;
        cleanings_today: number;
    };
    revenue: {
        gross_total: string | null;
        net_total: string | null;
        currency: string | null;
        booking_count: number;
        month: string;
    };
    tasks: {
        pending_tasks: number;
        escalated_tasks: number;
    };
    sync_health: {
        last_sync_at: string | null;
        last_sync_status: string | null;
        stale: boolean | null;
        provider_count: number;
    };
}

export interface PortfolioDashboardResponse {
    tenant_id: string;
    as_of: string;
    revenue_month: string;
    generated_at: string;
    property_count: number;
    properties: PortfolioProperty[];
}

// ---------------------------------------------------------------------------
// Phase 289 — Booking History / Amendment / Financial types
// ---------------------------------------------------------------------------

export interface BookingHistoryEntry {
    event_id: string | null;
    event_kind: string;
    occurred_at: string | null;
    payload: Record<string, unknown>;
    version: number | null;
}

export interface BookingAmendment {
    amendment_id?: string;
    booking_id: string;
    amendment_type: string;
    old_value: string | null;
    new_value: string | null;
    changed_at: string | null;
    changed_by: string | null;
}

export interface BookingFinancialDetail {
    booking_id: string;
    tenant_id?: string;
    total_price: string | null;
    net_to_property: string | null;
    currency: string | null;
    lifecycle_status: string | null;
    event_kind: string | null;
    recorded_at: string | null;
    source_confidence: string | null;
    epistemic_tier: string | null;
}

// ---------------------------------------------------------------------------
// Phase 291 — Financial Dashboard: Cashflow Projection
// ---------------------------------------------------------------------------

export interface CashflowWeek {
    week: string;           // ISO week key "YYYY-Www"
    week_start: string;     // ISO date
    expected_gross: string;
    expected_net: string;
    booking_count: number;
    currency: string;
}

export interface CashflowProjectionResponse {
    tenant_id: string;
    period: string;
    base_currency: string | null;
    weeks: CashflowWeek[];
    total_weeks: number;
}

// ---------------------------------------------------------------------------
// Phase 311 — Notification Log (Admin)
// ---------------------------------------------------------------------------

export interface NotificationLogEntry {
    notification_id?: string;
    notification_delivery_id?: string;
    channel: string;
    recipient: string;
    notification_type: string;
    status: string;
    error_message: string | null;
    reference_id: string | null;
    dispatched_at: string;
}

export interface NotificationLogResponse {
    entries: NotificationLogEntry[];
    count: number;
}

// ---------------------------------------------------------------------------
// Phase 312 — Manager Copilot (Morning Briefing)
// ---------------------------------------------------------------------------

export interface CopilotActionItem {
    priority: string;
    action: string;
    description: string;
}

export interface MorningBriefingResponse {
    briefing_text: string;
    generated_by: 'llm' | 'heuristic';
    language: string;
    tenant_id: string;
    generated_at: string;
    action_items: CopilotActionItem[];
    context_signals: {
        operations?: {
            date?: string;
            arrivals_count?: number;
            departures_count?: number;
            cleanings_due?: number;
            active_bookings?: number;
        };
        tasks?: {
            total_open?: number;
            by_priority?: Record<string, number>;
            critical_past_ack_sla?: number;
        };
        dlq?: {
            unprocessed_count?: number;
            alert?: boolean;
        };
        outbound_sync?: {
            failure_rate_24h?: number;
        };
        ai_hints?: Record<string, unknown>;
    };
}

// ---------------------------------------------------------------------------
// Phase 569 — Missing API methods (eliminate last (api as any) casts)
// ---------------------------------------------------------------------------

// Conflicts
export interface ConflictItem {
    conflict_id: string;
    booking_a_id: string;
    booking_b_id: string;
    property_id: string;
    overlap_start: string;
    overlap_end: string;
    status: string;
    resolved_by?: string;
    created_at: string;
}

// Maintenance  
export interface MaintenanceRequestItem {
    id: string;
    property_id: string;
    title: string;
    description: string;
    priority: string;
    status: string;
    assigned_to?: string;
    created_at: string;
    resolved_at?: string;
}

// Extend the api object with missing methods
Object.assign(api, {
    // Phase 569 — Conflicts
    getConflicts: (): Promise<{ conflicts: ConflictItem[] }> =>
        apiFetch('/conflicts'),

    resolveConflict: (conflictId: string, resolution: string): Promise<unknown> =>
        apiFetch(`/conflicts/${conflictId}/resolve`, {
            method: 'POST',
            body: JSON.stringify({ resolution }),
        }),

    // Phase 569 — Exchange rates / Currencies
    getExchangeRates: (): Promise<{ rates: Record<string, number>; base: string }> =>
        apiFetch('/currencies/rates'),

    // Phase 569 — Maintenance
    getMaintenanceRequests: (): Promise<{ requests: MaintenanceRequestItem[] }> =>
        apiFetch('/maintenance'),

    createMaintenanceRequest: (data: {
        property_id: string;
        title: string;
        description: string;
        priority: string;
    }): Promise<MaintenanceRequestItem> =>
        apiFetch('/maintenance', {
            method: 'POST',
            body: JSON.stringify(data),
        }),
});
