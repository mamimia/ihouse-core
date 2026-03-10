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

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
    const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(init?.headers as Record<string, string>),
    };
    if (_token) headers["Authorization"] = `Bearer ${_token}`;

    const resp = await fetch(`${BASE_URL}${path}`, { ...init, headers });
    if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        // Phase 186: auto-logout on 401/403 (expired or invalid token)
        if (resp.status === 401 || resp.status === 403) {
            // Only auto-logout if we had a token (avoid redirect loop on /login calls)
            if (_token) {
                performClientLogout('/login');
            }
        }
        throw new ApiError(resp.status, body?.error || "UNKNOWN_ERROR", body);
    }
    return resp.json();
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

export interface DlqEntry {
    id: number;
    provider: string;
    event_type: string;
    rejection_code: string;
    received_at: string;
    status: string;
}

export interface DlqListResponse {
    tenant_id: string;
    count: number;
    entries: DlqEntry[];
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
    expires_in: number;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export const api = {
    // Phase 179 — Auth
    login: (tenant_id: string, secret: string): Promise<LoginResponse> =>
        apiFetch('/auth/token', {
            method: 'POST',
            body: JSON.stringify({ tenant_id, secret }),
        }),

    // Phase 186 — Logout
    logout: async (): Promise<void> => {
        try {
            // Best-effort: call server to clear cookie. Ignore errors.
            await fetch(`${BASE_URL}/auth/logout`, { method: 'POST' });
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

    getDlq: (params?: {
        status?: string;
        limit?: number;
    }): Promise<DlqListResponse> => {
        const q = new URLSearchParams();
        if (params?.status) q.set("status", params.status);
        if (params?.limit) q.set("limit", String(params.limit));
        return apiFetch(`/admin/dlq${q.size ? "?" + q : ""}`);
    },

    // Phase 157 — Worker task actions
    getWorkerTasks: (params?: {
        status?: string;
        priority?: string;
        limit?: number;
    }): Promise<WorkerTaskListResponse> => {
        const q = new URLSearchParams();
        if (params?.status) q.set("status", params.status);
        if (params?.priority) q.set("priority", params.priority);
        if (params?.limit) q.set("limit", String(params.limit));
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
};

// Phase 157 — Worker task types
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
    created_at: string;
    updated_at: string;
}

export interface WorkerTaskListResponse {
    tenant_id: string;
    count: number;
    tasks: WorkerTask[];
}
