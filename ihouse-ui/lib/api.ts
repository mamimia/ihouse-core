// Phase 153 — iHouse Core API client
// Phase 163 — Financial Dashboard API methods added
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

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export const api = {
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
