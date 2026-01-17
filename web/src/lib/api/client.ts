/**
 * API Client - Unified API access layer
 * 
 * Handles authentication, error handling, and API calls.
 * Follows Constitution Principle I: No user-visible errors.
 */

import {
    ApiResponse,
    DashboardStats,
    SessionItem,
    Recommendation,
    Agent,
    Persona,
    AnalyticsOverview,
    AnalyticsTrends,
    AnalyticsAgents,
    AnalyticsLeaderboard,
    User,
    AdminUser,
    AdminAgent,
    AdminPersona,
    AdminKnowledgeBase,
    AdminKnowledgeDocument,
    UserDetailStats,
    UserSessionsResponse,
    UserProgressResponse,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// Get auth token from localStorage
function getAuthToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("token");
}

// Create headers with auth
function createHeaders(includeContentType = true): HeadersInit {
    const headers: HeadersInit = {};

    if (includeContentType) {
        headers["Content-Type"] = "application/json";
    }

    const token = getAuthToken();
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    return headers;
}

// Generic fetch wrapper
async function apiFetch<T>(
    endpoint: string,
    options: RequestInit = {}
): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;

    const response = await fetch(url, {
        ...options,
        headers: {
            ...createHeaders(),
            ...options.headers,
        },
    });

    if (!response.ok) {
        // Handle 401 - redirect to login
        if (response.status === 401) {
            if (typeof window !== "undefined") {
                localStorage.removeItem("token");
                localStorage.removeItem("user");
                window.location.href = "/login";
            }
            throw new Error("Unauthorized");
        }

        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || errorData.error || `HTTP ${response.status}`);
    }

    const data = await response.json();

    // Handle API response wrapper
    if (data.success === false) {
        throw new Error(data.message || data.error || "API Error");
    }

    return data.data !== undefined ? data.data : data;
}

// File upload fetch wrapper
async function apiUpload<T>(
    endpoint: string,
    formData: FormData
): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const token = getAuthToken();

    const response = await fetch(url, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || errorData.error || `HTTP ${response.status}`);
    }

    const data = await response.json();
    return data.data !== undefined ? data.data : data;
}

// API methods organized by domain
export const api = {
    // Authentication
    auth: {
        login: async (credentials: { email: string; password: string }) => {
            return apiFetch<{ access_token: string; user: User }>("/auth/login", {
                method: "POST",
                body: JSON.stringify(credentials),
            });
        },

        devLogin: async () => {
            return apiFetch<{ access_token: string; token_type: string; user: User }>("/auth/dev-login", {
                method: "POST",
            });
        },

        logout: async () => {
            return apiFetch<void>("/auth/logout", { method: "POST" });
        },
    },

    // User
    user: {
        getMe: async () => {
            return apiFetch<User>("/users/me");
        },

        updateProfile: async (data: Partial<User>) => {
            return apiFetch<User>("/users/me", {
                method: "PATCH",
                body: JSON.stringify(data),
            });
        },
    },

    // Dashboard
    dashboard: {
        getStats: async () => {
            return apiFetch<DashboardStats>("/dashboard/stats");
        },

        getRecommendation: async () => {
            return apiFetch<Recommendation>("/recommendations/latest");
        },

        getHistory: async (limit = 5) => {
            const result = await apiFetch<{ items: any[]; total: number }>(`/practice/history?page_size=${limit}`);
            // Map session_id to id for frontend compatibility
            return (result.items || []).map((item, index) => ({
                ...item,
                id: item.session_id || item.id || `session-${index}`,
                title: item.title || item.agent_name || "练习记录",
                scenario_type: item.scenario_type || "sales",
                overall_score: item.overall_score || 0,
                duration_seconds: item.duration_seconds || item.total_duration_seconds || 0,
            }));
        },
    },

    // Training / Practice
    training: {
        getSalesAgents: async () => {
            const result = await apiFetch<{ agents: Agent[]; total: number }>("/agents?category=sales&status=published");
            return result.agents || [];
        },

        getCustomerAgents: async () => {
            const result = await apiFetch<{ agents: Agent[]; total: number }>("/agents?category=customer_service&status=published");
            return result.agents || [];
        },

        createSession: async (data: { agent_id: string; persona_id?: string }) => {
            return apiFetch<{ session_id: string }>("/practice/sessions", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },
    },

    // Practice / Sessions
    practice: {
        createSession: async (data: { agent_id: string; persona_id?: string }) => {
            return apiFetch<{ session_id: string }>("/practice/sessions", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        getSession: async (sessionId: string) => {
            return apiFetch<SessionItem>(`/practice/sessions/${sessionId}`);
        },
    },

    // Sessions
    sessions: {
        getEnhancedReport: async (sessionId: string) => {
            return apiFetch<any>(`/practice/sessions/${sessionId}/report`);
        },
    },

    // Agents (user-facing)
    agents: {
        list: async (params?: { category?: string; status?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.category) searchParams.set("category", params.category);
            if (params?.status) searchParams.set("status", params.status);

            const result = await apiFetch<{ agents: Agent[]; total: number }>(`/agents?${searchParams}`);
            return result.agents || [];
        },

        getList: async (category: string) => {
            const result = await apiFetch<{ agents: Agent[]; total: number }>(`/agents?category=${category}&status=published`);
            return result.agents || [];
        },

        get: async (id: string) => {
            return apiFetch<Agent>(`/agents/${id}`);
        },

        getAgentWithPersonas: async (agentId: string) => {
            // Fetch agent and personas separately, then combine
            const [agent, personasResult] = await Promise.all([
                apiFetch<Agent>(`/agents/${agentId}`),
                apiFetch<{ personas: Persona[] }>(`/agents/${agentId}/personas`),
            ]);
            return {
                ...agent,
                personas: personasResult.personas || [],
            };
        },
    },

    // Personas (user-facing)
    personas: {
        list: async (params?: { category?: string; status?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.category) searchParams.set("category", params.category);
            if (params?.status) searchParams.set("status", params.status);

            return apiFetch<Persona[]>(`/personas?${searchParams}`);
        },

        get: async (id: string) => {
            return apiFetch<Persona>(`/personas/${id}`);
        },
    },

    // Admin - Analytics
    analytics: {
        getOverview: async (params?: { time_range?: string; scenario_type?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (params?.scenario_type) searchParams.set("scenario_type", params.scenario_type);

            return apiFetch<AnalyticsOverview>(`/admin/analytics/overview?${searchParams}`);
        },

        getTrends: async (params?: { time_range?: string; granularity?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (params?.granularity) searchParams.set("granularity", params.granularity);

            return apiFetch<AnalyticsTrends>(`/admin/analytics/trends?${searchParams}`);
        },

        getAgents: async (params?: { time_range?: string; limit?: number }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (params?.limit) searchParams.set("limit", params.limit.toString());

            return apiFetch<AnalyticsAgents>(`/admin/analytics/agents?${searchParams}`);
        },

        getLeaderboard: async (params?: { time_range?: string; limit?: number }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (params?.limit) searchParams.set("limit", params.limit.toString());

            return apiFetch<AnalyticsLeaderboard>(`/admin/analytics/leaderboard?${searchParams}`);
        },

        exportReport: async (params?: { time_range?: string; format?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (params?.format) searchParams.set("format", params.format);

            const url = `${API_BASE_URL}/admin/analytics/export?${searchParams}`;
            const token = getAuthToken();

            const response = await fetch(url, {
                headers: token ? { Authorization: `Bearer ${token}` } : {},
            });

            if (!response.ok) {
                throw new Error("Export failed");
            }

            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = downloadUrl;
            a.download = `analytics_report.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(downloadUrl);
        },
    },

    // Admin operations
    admin: {
        // Training Records
        getTrainingRecords: async (params: {
            search?: string;
            category?: string;
            page?: number;
            page_size?: number;
        }) => {
            const searchParams = new URLSearchParams();
            if (params.search) searchParams.set("search", params.search);
            if (params.category && params.category !== "all") {
                searchParams.set("scenario_type", params.category);
            }
            if (params.page) searchParams.set("page", params.page.toString());
            if (params.page_size) searchParams.set("page_size", params.page_size.toString());

            const result = await apiFetch<{ items: SessionItem[]; total: number }>(`/admin/training-records?${searchParams}`);
            return result.items;
        },

        deleteTrainingRecord: async (id: string) => {
            return apiFetch<{ deleted: boolean }>(`/admin/training-records/${id}`, {
                method: "DELETE",
            });
        },

        // Users
        getUsers: async (params?: { page?: number; page_size?: number; search?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.page) searchParams.set("page", params.page.toString());
            if (params?.page_size) searchParams.set("page_size", params.page_size.toString());
            if (params?.search) searchParams.set("search", params.search);

            return apiFetch<{ items: AdminUser[]; total: number }>(`/admin/users?${searchParams}`);
        },

        createUser: async (data: { display_name: string; email?: string; department?: string; role?: string }) => {
            return apiFetch<AdminUser>("/admin/users", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updateUser: async (id: string, data: Partial<AdminUser>) => {
            return apiFetch<AdminUser>(`/admin/users/${id}`, {
                method: "PATCH",
                body: JSON.stringify(data),
            });
        },

        deleteUser: async (id: string) => {
            return apiFetch<void>(`/admin/users/${id}`, { method: "DELETE" });
        },

        suspendUser: async (id: string) => {
            return apiFetch<AdminUser>(`/admin/users/${id}/suspend`, { method: "POST" });
        },

        activateUser: async (id: string) => {
            return apiFetch<AdminUser>(`/admin/users/${id}/activate`, { method: "POST" });
        },

        // User Details API
        getUserStats: async (userId: string, params?: { time_range?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);

            return apiFetch<UserDetailStats>(`/admin/users/${userId}/stats?${searchParams}`);
        },

        getUserSessions: async (userId: string, params?: { page?: number; page_size?: number; status?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.page) searchParams.set("page", params.page.toString());
            if (params?.page_size) searchParams.set("page_size", params.page_size.toString());
            if (params?.status) searchParams.set("status", params.status);

            return apiFetch<UserSessionsResponse>(`/admin/users/${userId}/sessions?${searchParams}`);
        },

        getUserProgress: async (userId: string, params?: { time_range?: string; granularity?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (params?.granularity) searchParams.set("granularity", params.granularity);

            return apiFetch<UserProgressResponse>(`/admin/users/${userId}/progress?${searchParams}`);
        },

        exportUsers: async (format: string, params?: { search?: string }) => {
            const searchParams = new URLSearchParams();
            searchParams.set("format", format);
            if (params?.search) searchParams.set("search", params.search);

            const url = `${API_BASE_URL}/admin/users/export?${searchParams}`;
            const token = getAuthToken();

            const response = await fetch(url, {
                headers: token ? { Authorization: `Bearer ${token}` } : {},
            });

            if (!response.ok) throw new Error("Export failed");

            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = downloadUrl;
            a.download = `users.${format}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(downloadUrl);
        },

        // Agents
        getAgents: async (params?: { page?: number; page_size?: number; search?: string; category?: string; status?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.page) searchParams.set("page", params.page.toString());
            if (params?.page_size) searchParams.set("page_size", params.page_size.toString());
            if (params?.search) searchParams.set("search", params.search);
            if (params?.category) searchParams.set("category", params.category);
            if (params?.status) searchParams.set("status", params.status);

            const result = await apiFetch<any>(`/admin/agents?${searchParams}`);
            return {
                items: (result.agents || result.items || []) as AdminAgent[],
                total: result.total || 0
            };
        },

        getAgent: async (id: string) => {
            return apiFetch<AdminAgent>(`/admin/agents/${id}`);
        },

        createAgent: async (data: Partial<AdminAgent>) => {
            return apiFetch<AdminAgent>("/admin/agents", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updateAgent: async (id: string, data: Partial<AdminAgent>) => {
            return apiFetch<AdminAgent>(`/admin/agents/${id}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        deleteAgent: async (id: string) => {
            return apiFetch<void>(`/admin/agents/${id}`, { method: "DELETE" });
        },

        publishAgent: async (id: string) => {
            return apiFetch<AdminAgent>(`/admin/agents/${id}/publish`, { method: "POST" });
        },

        unpublishAgent: async (id: string) => {
            return apiFetch<AdminAgent>(`/admin/agents/${id}/unpublish`, { method: "POST" });
        },

        archiveAgent: async (id: string) => {
            return apiFetch<AdminAgent>(`/admin/agents/${id}/archive`, { method: "POST" });
        },

        getAgentPersonas: async (agentId: string) => {
            const result = await apiFetch<any>(`/admin/agents/${agentId}/personas`);
            return (result.personas || result.items || []) as AdminPersona[];
        },

        addPersonaToAgent: async (agentId: string, data: { persona_id: string; is_default?: boolean }) => {
            return apiFetch<void>(`/admin/agents/${agentId}/personas`, {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        removePersonaFromAgent: async (agentId: string, personaId: string) => {
            return apiFetch<void>(`/admin/agents/${agentId}/personas/${personaId}`, {
                method: "DELETE",
            });
        },

        updateAgentPersona: async (agentId: string, personaId: string, data: { is_default?: boolean }) => {
            return apiFetch<void>(`/admin/agents/${agentId}/personas/${personaId}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        // Personas
        getPersonas: async (params?: { page?: number; page_size?: number; search?: string; category?: string; status?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.page) searchParams.set("page", params.page.toString());
            if (params?.page_size) searchParams.set("page_size", params.page_size.toString());
            if (params?.search) searchParams.set("search", params.search);
            if (params?.category) searchParams.set("category", params.category);
            if (params?.status) searchParams.set("status", params.status);

            const result = await apiFetch<any>(`/admin/personas?${searchParams}`);
            return {
                items: (result.personas || result.items || []) as AdminPersona[],
                total: result.total || 0
            };
        },

        getPersona: async (id: string) => {
            return apiFetch<AdminPersona>(`/admin/personas/${id}`);
        },

        createPersona: async (data: Partial<AdminPersona>) => {
            return apiFetch<AdminPersona>("/admin/personas", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updatePersona: async (id: string, data: Partial<AdminPersona>) => {
            return apiFetch<AdminPersona>(`/admin/personas/${id}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        deletePersona: async (id: string) => {
            return apiFetch<void>(`/admin/personas/${id}`, { method: "DELETE" });
        },

        // Knowledge Bases
        getKnowledgeBases: async (params?: { page?: number; page_size?: number; search?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.page) searchParams.set("page", params.page.toString());
            if (params?.page_size) searchParams.set("page_size", params.page_size.toString());
            if (params?.search) searchParams.set("search", params.search);

            const result = await apiFetch<any>(`/admin/knowledge?${searchParams}`);
            return {
                items: (result.knowledge_bases || result.items || []) as AdminKnowledgeBase[],
                total: result.total || 0
            };
        },

        getKnowledgeBase: async (id: string) => {
            return apiFetch<AdminKnowledgeBase>(`/admin/knowledge/${id}`);
        },

        createKnowledgeBase: async (data: { name: string; description?: string; category?: string }) => {
            return apiFetch<AdminKnowledgeBase>("/admin/knowledge", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updateKnowledgeBase: async (id: string, data: Partial<AdminKnowledgeBase>) => {
            return apiFetch<AdminKnowledgeBase>(`/admin/knowledge/${id}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        deleteKnowledgeBase: async (id: string) => {
            return apiFetch<void>(`/admin/knowledge/${id}`, { method: "DELETE" });
        },

        // Knowledge Base Documents
        getKnowledgeBaseDocuments: async (kbId: string) => {
            const result = await apiFetch<any>(`/admin/knowledge/${kbId}/documents`);
            return (result.documents || result.items || []) as AdminKnowledgeDocument[];
        },

        uploadDocument: async (kbId: string, formData: FormData) => {
            return apiUpload<AdminKnowledgeDocument>(`/admin/knowledge/${kbId}/documents`, formData);
        },

        deleteDocument: async (kbId: string, docId: string) => {
            return apiFetch<void>(`/admin/knowledge/${kbId}/documents/${docId}`, {
                method: "DELETE",
            });
        },

        getDocumentPreview: async (kbId: string, docId: string) => {
            return apiFetch<{ chunks: string[] }>(`/admin/knowledge/${kbId}/documents/${docId}/preview`);
        },

        // Model Configs
        getModelConfigs: async () => {
            return apiFetch<any[]>("/admin/model-configs");
        },

        getModelConfig: async (id: string) => {
            return apiFetch<any>(`/admin/model-configs/${id}`);
        },

        createModelConfig: async (data: any) => {
            return apiFetch<any>("/admin/model-configs", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updateModelConfig: async (id: string, data: any) => {
            return apiFetch<any>(`/admin/model-configs/${id}`, {
                method: "PATCH",
                body: JSON.stringify(data),
            });
        },

        deleteModelConfig: async (id: string) => {
            return apiFetch<void>(`/admin/model-configs/${id}`, { method: "DELETE" });
        },

        testModelConfig: async (id: string) => {
            return apiFetch<{ success: boolean; message: string; latency_ms?: number }>(`/admin/model-configs/${id}/test`, {
                method: "POST",
            });
        },

        testModelConfigInline: async (data: any) => {
            return apiFetch<{ success: boolean; message: string; latency_ms?: number }>("/admin/model-configs/test", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },
    },
};
