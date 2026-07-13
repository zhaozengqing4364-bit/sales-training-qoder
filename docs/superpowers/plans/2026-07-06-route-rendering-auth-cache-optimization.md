# Route Rendering Auth Cache Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 解决点击任意页面后长时间停在 `Rendering` 的共享链路问题，让路由切换先稳定完成，鉴权和页面数据改为有缓存、有超时、有降级。

**Architecture:** 保留后端 session 作为权限边界，但把前端展示链路变轻：服务端 layout 鉴权加超时和请求内去重，客户端 current-user 进入全局 React Query 缓存，登录和 dashboard 关键接口统一超时。Dashboard 首页从手写 effect 冷请求逐步迁到 query 层，单块加载、失败、stale 数据互不阻塞。

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, TanStack Query 5, Vitest, Testing Library, FastAPI.

## 2026-07-13 实测闭环

- 开发模式两轮 10 次栏目切换：内容稳定中位数 284ms、P95 2275ms，3 次观察到
  `Rendering ...`；首次训练、排行榜、历史记录的 Next.js 开发编译分别占 2.10s、1.09s、1.01s。
- 同一提交的生产模式：内容稳定中位数 201ms、P95 266ms，`Rendering ...` 为 0 次；
  首轮目标栏目的 RSC 请求为 8–12ms。
- 公网 `3445` 最终生产模式复测：内容稳定中位数 147ms、P95 268ms，
  `Rendering ...` 仍为 0 次，控制台错误为 0。
- 根因是公网误用 `next dev`，不是 `/users/me`、页面 API 或 React 重渲染。本轮新增独立的
  production runner 和 `scripts/app-up.sh`，保留 `dev-up.sh` 的本地热更新语义。

---

## File Structure

- Modify: `web/src/hooks/use-current-user.ts`
  - 让 `useCurrentUser(initialData)` 使用全局 QueryClient 的 `initialData`，不再为有初始用户时创建独立 QueryClient。
- Modify: `web/src/hooks/use-current-user.test.tsx`
  - 删除“无 Provider 也能调用 hook”的旧契约，新增“服务端用户写入共享 query cache”的契约。
- Modify: `web/src/lib/query/auth.ts`
  - 给 `/users/me` 单独设置 5-10 分钟缓存窗口。
- Modify: `web/src/lib/server-auth.ts`
  - 给服务端 `/users/me` 请求加 8 秒超时；用 React `cache()` 做同一次服务端 render 内去重。
- Modify: `web/src/lib/server-auth.test.ts`
  - 覆盖服务端 session 请求超时后不无限 pending。
- Modify: `web/src/lib/api/domains/shared.ts`
  - 给通用 request option 增加 `timeoutMs` / `timeoutMessage`。
- Modify: `web/src/lib/api/client.ts`
  - 在 `apiFetch` / `apiFetchBlob` 中支持超时 abort；将超时归一化为 `ApiRequestError`。
  - 给 `auth.login`、`auth.devLogin`、`auth.getProviders`、`user.getMe`、dashboard 关键接口设置明确 timeout。
- Modify: `web/src/lib/api/client.auth.test.ts`
  - 覆盖登录超时、`/users/me` 超时、dashboard 慢接口超时。
- Modify: `web/src/app/(auth)/login/page.tsx`
  - 登录超时显示 toast + inline error，按钮必须在 `finally` 恢复。
- Modify: `web/src/app/(auth)/login/page.test.tsx`
  - 覆盖登录超时文案和按钮恢复。
- Create: `web/src/lib/query/dashboard.ts`
  - 定义 dashboard query keys、query options、staleTime、gcTime。
- Create: `web/src/hooks/use-dashboard-data.ts`
  - 封装 dashboard 8 个区块查询，返回每块独立 loading/error/stale/refetch 状态。
- Create: `web/src/hooks/use-dashboard-data.test.tsx`
  - 覆盖单接口 pending 不阻塞其他区块、失败只降级对应区块、30-60 秒缓存生效。
- Modify: `web/src/app/(dashboard)/page.tsx`
  - 用 `useDashboardData` 替换手写冷启动 effect；保留现有产品化 fallback 文案。
- Modify: `web/src/app/(dashboard)/page.test.tsx`
  - 更新首页区块 loading/degraded/cache 行为测试。
- Modify: `web/src/components/layout/sidebar.tsx`
  - 显式开启 Next Link prefetch，并在 hover 时预取 dashboard 高频数据。
- Modify: `web/src/components/layout/sidebar.test.tsx`
  - 覆盖导航 hover 预取不会触发页面跳转。
- Review only: `backend/src/common/auth/service.py`
  - 检查 `get_current_user` 是否有不必要关联表、角色/组织 N+1。
- Review only: `backend/src/common/api/users.py`
  - 检查 `/users/me` 是否只返回基础用户信息。
- Optional modify after measurement: backend auth/user tests under `backend/tests/unit/common/test_api_users.py` and `backend/tests/integration/test_auth_login_api.py`.

执行前注意：当前工作区已有用户改动，尤其是 `web/src/app/(dashboard)/page.tsx` 和 `web/src/app/(dashboard)/page.test.tsx`。实现时必须先 `git diff -- <file>`，在现有改动上增量修改，不得回滚用户内容。

---

### Task 1: Production Baseline And Repro

**Files:**
- Read: `web/package.json`
- Read: `web/next.config.ts`
- No source modification.

- [x] **Step 1: Build production bundle**

Run from `web/`:

```bash
npm run build
```

Expected: build exits 0. If it fails, capture the first real TypeScript/build error and fix only if it blocks this plan.

- [x] **Step 2: Run production server**

Run from `web/`:

```bash
npm run start
```

Expected: Next starts successfully. Use the printed local URL.

- [x] **Step 3: Compare dev and production route switching**

Manual check:

```text
1. Login.
2. Click 首页 -> 训练模式 -> 新人训练路径 -> 排行榜 -> 历史记录.
3. Record whether the URL changes within 100-300ms.
4. Record whether shell/sidebar remains visible while page data loads.
5. Record whether any request stays pending for more than 10s.
```

Expected result after implementation:

```text
URL/shell first, data second.
No whole-page infinite Rendering.
Slow sections show local loading/degraded state.
```

- [x] **Step 4: Commit baseline notes if a doc is updated**

Only if you add a short evidence note:

```bash
git add docs/superpowers/plans/2026-07-06-route-rendering-auth-cache-optimization.md
git commit -m "docs: record route rendering baseline"
```

---

### Task 2: Current User Query Cache

**Files:**
- Modify: `web/src/hooks/use-current-user.ts`
- Modify: `web/src/hooks/use-current-user.test.tsx`
- Modify: `web/src/lib/query/auth.ts`

- [ ] **Step 1: Write failing cache test**

Replace the old SSR-without-provider test in `web/src/hooks/use-current-user.test.tsx` with this provider-based cache contract:

```tsx
import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { currentUserQueryKey } from "@/lib/query/auth";
import { createAppQueryClient } from "@/lib/query/client";
import type { CurrentUser } from "@/lib/auth/current-user";

import { useCurrentUser } from "./use-current-user";

const currentUser = {
    id: "user-1",
    user_id: "user-1",
    name: "王小明",
    display_name: "王小明",
    email: "learner@example.com",
    role: "user",
    is_active: true,
    created_at: "2026-04-01T00:00:00Z",
} as const satisfies CurrentUser;

function createWrapper(queryClient: QueryClient) {
    return function Wrapper({ children }: { children: React.ReactNode }) {
        return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    };
}

describe("useCurrentUser", () => {
    it("seeds the shared current-user query cache from server-provided user data", async () => {
        const queryClient = createAppQueryClient();

        const { result } = renderHook(() => useCurrentUser(currentUser), {
            wrapper: createWrapper(queryClient),
        });

        await waitFor(() => {
            expect(result.current.data?.display_name).toBe("王小明");
        });

        expect(queryClient.getQueryData(currentUserQueryKey)).toMatchObject({
            id: "user-1",
            display_name: "王小明",
        });
    });
});
```

- [ ] **Step 2: Run the failing test**

Run from `web/`:

```bash
npx vitest run src/hooks/use-current-user.test.tsx
```

Expected: FAIL before implementation because the initial user is stored in a detached QueryClient, not the provider cache.

- [ ] **Step 3: Simplify `useCurrentUser` to use provider cache**

Change `web/src/hooks/use-current-user.ts` to:

```ts
"use client";

import { useQuery } from "@tanstack/react-query";

import type { CurrentUser } from "@/lib/auth/current-user";
import { getCurrentUserQueryOptions } from "@/lib/query/auth";

export function useCurrentUser(initialData?: CurrentUser) {
    return useQuery(getCurrentUserQueryOptions(initialData));
}
```

- [ ] **Step 4: Tune auth query stale time**

Change `web/src/lib/query/auth.ts`:

```ts
const CURRENT_USER_STALE_TIME_MS = 5 * 60_000;
const CURRENT_USER_GC_TIME_MS = 10 * 60_000;

export function getCurrentUserQueryOptions(
    initialData?: CurrentUser,
): UseQueryOptions<CurrentUser, Error, CurrentUser, typeof currentUserQueryKey> {
    return {
        queryKey: currentUserQueryKey,
        queryFn: () => api.user.getMe(),
        initialData,
        staleTime: CURRENT_USER_STALE_TIME_MS,
        gcTime: CURRENT_USER_GC_TIME_MS,
    };
}
```

- [ ] **Step 5: Run auth hook tests**

Run from `web/`:

```bash
npx vitest run src/hooks/use-current-user.test.tsx src/hooks/use-auth-protection.test.tsx src/components/layout/dashboard-shell.test.tsx src/components/layout/admin-shell.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/hooks/use-current-user.ts src/hooks/use-current-user.test.tsx src/lib/query/auth.ts
git commit -m "fix: cache current user in shared query client"
```

---

### Task 3: Server Layout Auth Timeout

**Files:**
- Modify: `web/src/lib/server-auth.ts`
- Modify: `web/src/lib/server-auth.test.ts`

- [ ] **Step 1: Write failing timeout test**

Append to `web/src/lib/server-auth.test.ts`:

```ts
it("returns null when the server session lookup times out", async () => {
    vi.useFakeTimers();
    headersMock.mockResolvedValue(
        new Headers({
            cookie: "session=slow-cookie",
        }),
    );

    vi.stubGlobal(
        "fetch",
        vi.fn((_url: string, options?: RequestInit) => {
            return new Promise((_resolve, reject) => {
                options?.signal?.addEventListener("abort", () => {
                    reject(new DOMException("The operation was aborted.", "AbortError"));
                });
            });
        }),
    );

    const { getServerSessionUser } = await import("./server-auth");
    const sessionPromise = getServerSessionUser();

    await vi.advanceTimersByTimeAsync(8_000);

    await expect(sessionPromise).resolves.toBeNull();
    vi.useRealTimers();
});
```

- [ ] **Step 2: Run failing test**

Run from `web/`:

```bash
npx vitest run src/lib/server-auth.test.ts
```

Expected: FAIL because `server-auth.ts` does not currently abort slow `/users/me`.

- [ ] **Step 3: Add request-scoped cache and timeout**

Modify `web/src/lib/server-auth.ts`:

```ts
import { cache } from "react";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

const SERVER_SESSION_TIMEOUT_MS = 8_000;

function isAbortError(error: unknown): boolean {
    return error instanceof Error && error.name === "AbortError";
}

async function getServerSessionUserUncached(): Promise<CurrentUser | null> {
    const requestHeaders = await headers();
    const cookieHeader = requestHeaders.get("cookie");
    const traceHeaders = buildTraceHeaders({
        traceId: requestHeaders.get("x-trace-id"),
        traceparent: requestHeaders.get("traceparent"),
        tracestate: requestHeaders.get("tracestate"),
    });

    if (!cookieHeader) {
        return null;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), SERVER_SESSION_TIMEOUT_MS);

    let response: Response;

    try {
        response = await fetch(`${SERVER_API_BASE_URL}/users/me`, {
            method: "GET",
            cache: "no-store",
            credentials: "include",
            signal: controller.signal,
            headers: {
                cookie: cookieHeader,
                Accept: "application/json",
                ...traceHeaders,
            },
        });
    } catch (error) {
        if (isFetchNetworkFailure(error) || isAbortError(error)) {
            return null;
        }
        throw error;
    } finally {
        clearTimeout(timeoutId);
    }

    if (response.status === 401 || response.status === 403) {
        return null;
    }

    if (!response.ok) {
        throw new Error(`Failed to resolve server session: HTTP ${response.status}`);
    }

    const payload = unwrapApiPayload(await response.json().catch(() => null));
    return payload ? normalizeCurrentUser(payload) : null;
}

export const getServerSessionUser = cache(getServerSessionUserUncached);
```

- [ ] **Step 4: Run server auth tests**

Run from `web/`:

```bash
npx vitest run src/lib/server-auth.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/server-auth.ts src/lib/server-auth.test.ts
git commit -m "fix: bound server session lookup latency"
```

---

### Task 4: API Timeout And Login Recovery

**Files:**
- Modify: `web/src/lib/api/domains/shared.ts`
- Modify: `web/src/lib/api/client.ts`
- Modify: `web/src/lib/api/client.auth.test.ts`
- Modify: `web/src/app/(auth)/login/page.tsx`
- Modify: `web/src/app/(auth)/login/page.test.tsx`

- [ ] **Step 1: Extend API option type**

Change `web/src/lib/api/domains/shared.ts`:

```ts
export type ApiRequestOptions = RequestInit & {
    signal?: AbortSignal;
    skipSessionExpiredHandling?: boolean;
    timeoutMs?: number;
    timeoutMessage?: string;
};
```

Also update `ApiFetchOptions` in `web/src/lib/api/client.ts`:

```ts
type ApiFetchOptions = RequestInit & {
    skipSessionExpiredHandling?: boolean;
    timeoutMs?: number;
    timeoutMessage?: string;
};
```

- [ ] **Step 2: Write failing timeout tests**

Append to `web/src/lib/api/client.auth.test.ts`:

```ts
it("aborts password login after the configured timeout", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
        "fetch",
        vi.fn((_url: string, options?: RequestInit) => {
            return new Promise((_resolve, reject) => {
                options?.signal?.addEventListener("abort", () => {
                    reject(new DOMException("The operation was aborted.", "AbortError"));
                });
            });
        }),
    );

    const request = api.auth.login({
        email: "admin@test.com",
        password: "password",
    });

    await vi.advanceTimersByTimeAsync(8_000);

    await expect(request).rejects.toMatchObject({
        name: "ApiRequestError",
        errorCode: "[REQUEST_TIMEOUT]",
        message: "登录超时，请重试。",
    });
    vi.useRealTimers();
});

it("aborts current-user requests instead of leaving navigation pending forever", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
        "fetch",
        vi.fn((_url: string, options?: RequestInit) => {
            return new Promise((_resolve, reject) => {
                options?.signal?.addEventListener("abort", () => {
                    reject(new DOMException("The operation was aborted.", "AbortError"));
                });
            });
        }),
    );

    const request = api.user.getMe();

    await vi.advanceTimersByTimeAsync(8_000);

    await expect(request).rejects.toMatchObject({
        name: "ApiRequestError",
        errorCode: "[REQUEST_TIMEOUT]",
    });
    vi.useRealTimers();
});
```

- [ ] **Step 3: Implement timeout helper in `client.ts`**

Add near `apiFetch`:

```ts
const DEFAULT_INTERACTIVE_TIMEOUT_MS = 10_000;
const AUTH_REQUEST_TIMEOUT_MS = 8_000;
const DASHBOARD_REQUEST_TIMEOUT_MS = 8_000;

function isAbortError(error: unknown): boolean {
    return error instanceof Error && error.name === "AbortError";
}

function createTimeoutError(message = "请求超时，请稍后重试。"): ApiRequestError {
    return new ApiRequestError({
        status: 0,
        errorCode: "[REQUEST_TIMEOUT]",
        message,
    });
}

function createTimeoutSignal(
    externalSignal: AbortSignal | undefined,
    timeoutMs: number | undefined,
): { signal: AbortSignal; cleanup: () => void; timedOut: () => boolean } {
    const controller = new AbortController();
    let didTimeout = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    if (externalSignal) {
        if (externalSignal.aborted) {
            controller.abort();
        } else {
            externalSignal.addEventListener("abort", () => controller.abort(), { once: true });
        }
    }

    if (typeof timeoutMs === "number" && timeoutMs > 0) {
        timeoutId = setTimeout(() => {
            didTimeout = true;
            controller.abort();
        }, timeoutMs);
    }

    return {
        signal: controller.signal,
        cleanup: () => {
            if (timeoutId) {
                clearTimeout(timeoutId);
            }
        },
        timedOut: () => didTimeout,
    };
}
```

Then use it in `apiFetch` and `apiFetchBlob`:

```ts
const {
    skipSessionExpiredHandling = false,
    timeoutMs = DEFAULT_INTERACTIVE_TIMEOUT_MS,
    timeoutMessage,
    ...requestOptions
} = options;
const timeout = createTimeoutSignal(requestOptions.signal, timeoutMs);

try {
    const response = await fetchWithLoopbackRetry(url, {
        ...requestOptions,
        signal: timeout.signal,
        credentials: resolvedCredentials,
        headers,
    });
    // existing response handling
} catch (error) {
    if (isAbortError(error) && timeout.timedOut()) {
        throw createTimeoutError(timeoutMessage);
    }
    if (error instanceof Error && error.name === "AbortError") {
        throw error;
    }
    // existing network normalization
} finally {
    timeout.cleanup();
    activeRequests.delete(requestId);
}
```

Do not add a timeout to `apiStream` in this task; streaming endpoints have different lifetime semantics.

- [ ] **Step 4: Set explicit auth and dashboard timeouts**

In `web/src/lib/api/client-domains.ts`, use:

```ts
getProviders: async () => {
    return request<AuthProvidersResponse>("/auth/providers", {
        method: "GET",
        cache: "no-store",
        skipSessionExpiredHandling: true,
        timeoutMs: 8_000,
        timeoutMessage: "登录配置加载超时，请刷新页面后重试。",
    });
},

login: async (credentials: { email: string; password: string }) => {
    return request<{ token?: string; access_token?: string; user: User & { id?: string } }>("/auth/login", {
        method: "POST",
        body: JSON.stringify(credentials),
        skipSessionExpiredHandling: true,
        timeoutMs: 8_000,
        timeoutMessage: "登录超时，请重试。",
    });
},

devLogin: async () => {
    return request<{ access_token: string; token_type: string; user: User }>("/auth/dev-login", {
        method: "POST",
        skipSessionExpiredHandling: true,
        timeoutMs: 8_000,
        timeoutMessage: "登录超时，请重试。",
    });
},
```

In `web/src/lib/api/client.ts`, set `/users/me` and dashboard wrappers to 8 seconds:

```ts
const profile = await apiFetch<...>("/users/me", {
    timeoutMs: AUTH_REQUEST_TIMEOUT_MS,
    timeoutMessage: "用户信息加载超时，请稍后重试。",
});

return apiFetch<DashboardStats>("/dashboard/stats", {
    timeoutMs: DASHBOARD_REQUEST_TIMEOUT_MS,
    timeoutMessage: "训练统计加载较慢，请稍后刷新。",
});
```

- [ ] **Step 5: Add login toast recovery**

Modify `web/src/app/(auth)/login/page.tsx`:

```tsx
import { useToast } from "@/components/ui/toast";

export default function LoginPage() {
    const toast = useToast();

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsPasswordLoginLoading(true);
        setError("");

        try {
            await api.auth.login({ email, password });
            // existing remember-email logic
            router.push("/");
        } catch (err: unknown) {
            const message = getApiErrorMessage(err);
            setError(message);
            if (message.includes("超时")) {
                toast.error("登录超时，请重试");
            }
        } finally {
            setIsPasswordLoginLoading(false);
        }
    };
}
```

Apply the same pattern to `handleDevLogin`.

- [ ] **Step 6: Run timeout/login tests**

Run from `web/`:

```bash
npx vitest run src/lib/api/client.auth.test.ts 'src/app/(auth)/login/page.test.tsx'
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/lib/api/domains/shared.ts src/lib/api/client.ts src/lib/api/client-domains.ts src/lib/api/client.auth.test.ts 'src/app/(auth)/login/page.tsx' 'src/app/(auth)/login/page.test.tsx'
git commit -m "fix: recover from slow auth and api requests"
```

---

### Task 5: Dashboard Query Layer And Section Degradation

**Files:**
- Create: `web/src/lib/query/dashboard.ts`
- Create: `web/src/hooks/use-dashboard-data.ts`
- Create: `web/src/hooks/use-dashboard-data.test.tsx`
- Modify: `web/src/app/(dashboard)/page.tsx`
- Modify: `web/src/app/(dashboard)/page.test.tsx`

- [ ] **Step 1: Create dashboard query options**

Create `web/src/lib/query/dashboard.ts`:

```ts
import { queryOptions } from "@tanstack/react-query";

import { api } from "@/lib/api/client";

const DASHBOARD_STALE_TIME_MS = 45_000;
const DASHBOARD_GC_TIME_MS = 5 * 60_000;

export const dashboardQueryKeys = {
    all: ["dashboard"] as const,
    stats: () => [...dashboardQueryKeys.all, "stats"] as const,
    recommendation: () => [...dashboardQueryKeys.all, "recommendation"] as const,
    history: (limit: number) => [...dashboardQueryKeys.all, "history", limit] as const,
    openIntervention: () => [...dashboardQueryKeys.all, "open-intervention"] as const,
    retrainingTasks: () => [...dashboardQueryKeys.all, "retraining-tasks"] as const,
    momentumHistory: () => [...dashboardQueryKeys.all, "momentum-history"] as const,
    growth: () => [...dashboardQueryKeys.all, "growth"] as const,
    learningPathNextTask: () => [...dashboardQueryKeys.all, "learning-path-next-task"] as const,
};

export function dashboardStatsQueryOptions() {
    return queryOptions({
        queryKey: dashboardQueryKeys.stats(),
        queryFn: () => api.dashboard.getStats(),
        staleTime: DASHBOARD_STALE_TIME_MS,
        gcTime: DASHBOARD_GC_TIME_MS,
    });
}

export function dashboardRecommendationQueryOptions() {
    return queryOptions({
        queryKey: dashboardQueryKeys.recommendation(),
        queryFn: () => api.dashboard.getRecommendation(),
        staleTime: DASHBOARD_STALE_TIME_MS,
        gcTime: DASHBOARD_GC_TIME_MS,
    });
}

export function dashboardHistoryQueryOptions(limit = 30) {
    return queryOptions({
        queryKey: dashboardQueryKeys.history(limit),
        queryFn: () => api.dashboard.getHistory(limit),
        staleTime: DASHBOARD_STALE_TIME_MS,
        gcTime: DASHBOARD_GC_TIME_MS,
    });
}

export function dashboardOpenInterventionQueryOptions() {
    return queryOptions({
        queryKey: dashboardQueryKeys.openIntervention(),
        queryFn: () => api.user.getOpenIntervention(),
        staleTime: DASHBOARD_STALE_TIME_MS,
        gcTime: DASHBOARD_GC_TIME_MS,
    });
}

export function dashboardRetrainingTasksQueryOptions() {
    return queryOptions({
        queryKey: dashboardQueryKeys.retrainingTasks(),
        queryFn: () => api.retraining.listTasks(),
        staleTime: DASHBOARD_STALE_TIME_MS,
        gcTime: DASHBOARD_GC_TIME_MS,
    });
}

export function dashboardMomentumHistoryQueryOptions() {
    return queryOptions({
        queryKey: dashboardQueryKeys.momentumHistory(),
        queryFn: () => api.user.getMyHistory({ page: 1, page_size: 50 }),
        staleTime: DASHBOARD_STALE_TIME_MS,
        gcTime: DASHBOARD_GC_TIME_MS,
    });
}

export function dashboardGrowthQueryOptions() {
    return queryOptions({
        queryKey: dashboardQueryKeys.growth(),
        queryFn: () => api.dashboard.getGrowth(),
        staleTime: DASHBOARD_STALE_TIME_MS,
        gcTime: DASHBOARD_GC_TIME_MS,
    });
}

export function dashboardLearningPathNextTaskQueryOptions() {
    return queryOptions({
        queryKey: dashboardQueryKeys.learningPathNextTask(),
        queryFn: () => api.learningPath.getNextTask(),
        staleTime: DASHBOARD_STALE_TIME_MS,
        gcTime: DASHBOARD_GC_TIME_MS,
    });
}
```

- [ ] **Step 2: Create `useDashboardData` hook**

Create `web/src/hooks/use-dashboard-data.ts`:

```ts
"use client";

import { useQuery } from "@tanstack/react-query";

import {
    dashboardGrowthQueryOptions,
    dashboardHistoryQueryOptions,
    dashboardLearningPathNextTaskQueryOptions,
    dashboardMomentumHistoryQueryOptions,
    dashboardOpenInterventionQueryOptions,
    dashboardRecommendationQueryOptions,
    dashboardRetrainingTasksQueryOptions,
    dashboardStatsQueryOptions,
} from "@/lib/query/dashboard";

export function useDashboardData(reloadVersion = 0) {
    const stats = useQuery(dashboardStatsQueryOptions());
    const recommendation = useQuery(dashboardRecommendationQueryOptions());
    const history = useQuery(dashboardHistoryQueryOptions(30));
    const openIntervention = useQuery(dashboardOpenInterventionQueryOptions());
    const retrainingTasks = useQuery(dashboardRetrainingTasksQueryOptions());
    const momentumHistory = useQuery(dashboardMomentumHistoryQueryOptions());
    const growth = useQuery(dashboardGrowthQueryOptions());
    const learningPathNextTask = useQuery(dashboardLearningPathNextTaskQueryOptions());

    const refetchAll = () => Promise.allSettled([
        stats.refetch(),
        recommendation.refetch(),
        history.refetch(),
        openIntervention.refetch(),
        retrainingTasks.refetch(),
        momentumHistory.refetch(),
        growth.refetch(),
        learningPathNextTask.refetch(),
    ]);

    void reloadVersion;

    return {
        stats,
        recommendation,
        history,
        openIntervention,
        retrainingTasks,
        momentumHistory,
        growth,
        learningPathNextTask,
        refetchAll,
    };
}
```

If `dashboardReloadVersion` must continue forcing refresh, add an effect in the hook:

```ts
useEffect(() => {
    if (reloadVersion > 0) {
        void refetchAll();
    }
}, [reloadVersion]);
```

- [ ] **Step 3: Write hook tests**

Create `web/src/hooks/use-dashboard-data.test.tsx`:

```tsx
import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createAppQueryClient } from "@/lib/query/client";
import { useDashboardData } from "./use-dashboard-data";

const { getStatsMock, getRecommendationMock, getHistoryMock } = vi.hoisted(() => ({
    getStatsMock: vi.fn(),
    getRecommendationMock: vi.fn(),
    getHistoryMock: vi.fn(),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            dashboard: {
                ...actual.api.dashboard,
                getStats: getStatsMock,
                getRecommendation: getRecommendationMock,
                getHistory: getHistoryMock,
                getGrowth: vi.fn().mockResolvedValue(null),
            },
            user: {
                ...actual.api.user,
                getOpenIntervention: vi.fn().mockResolvedValue(null),
                getMyHistory: vi.fn().mockResolvedValue({ sessions: [] }),
            },
            retraining: {
                ...actual.api.retraining,
                listTasks: vi.fn().mockResolvedValue([]),
            },
            learningPath: {
                ...actual.api.learningPath,
                getNextTask: vi.fn().mockResolvedValue(null),
            },
        },
    };
});

function wrapper(queryClient: QueryClient) {
    return function Wrapper({ children }: { children: React.ReactNode }) {
        return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    };
}

describe("useDashboardData", () => {
    beforeEach(() => {
        getStatsMock.mockReset();
        getRecommendationMock.mockReset();
        getHistoryMock.mockReset();
    });

    it("lets one slow section remain loading while other dashboard sections resolve", async () => {
        getStatsMock.mockReturnValue(new Promise(() => undefined));
        getRecommendationMock.mockResolvedValue({
            title: "继续练习",
            reason: "根据最近记录推荐",
            action_label: "开始训练",
            target_path: "/training",
        });
        getHistoryMock.mockResolvedValue([]);

        const queryClient = createAppQueryClient();
        const { result } = renderHook(() => useDashboardData(), {
            wrapper: wrapper(queryClient),
        });

        await waitFor(() => {
            expect(result.current.recommendation.data?.title).toBe("继续练习");
            expect(result.current.history.data).toEqual([]);
        });

        expect(result.current.stats.isLoading).toBe(true);
    });
});
```

- [ ] **Step 4: Refactor dashboard page carefully**

In `web/src/app/(dashboard)/page.tsx`, replace the large `useEffect` starting around the dashboard data loading block with `useDashboardData(dashboardReloadVersion)`.

Map old state to query state:

```ts
const dashboardData = useDashboardData(dashboardReloadVersion);

const isStatsLoading = dashboardData.stats.isLoading;
const isRecommendationLoading = dashboardData.recommendation.isLoading;
const isHistoryLoading = dashboardData.history.isLoading;
const isLearningPathLoading = dashboardData.learningPathNextTask.isLoading;

const stats = dashboardData.stats.data ?? DEFAULT_STATS;
const recommendation = dashboardData.recommendation.data ?? DEFAULT_RECOMMENDATION;
const historyItems = (dashboardData.history.data ?? []).slice(0, 5);
const openIntervention = dashboardData.openIntervention.data ?? null;
const retrainingTasks = (dashboardData.retrainingTasks.data ?? [])
    .filter((task) => task.status === "todo" || task.status === "in_progress");
const momentumSessions = (dashboardData.momentumHistory.data?.sessions ?? [])
    .map(mapHistorySummaryToMomentumSource);
const growthDashboard = dashboardData.growth.data ?? null;
const learningPathNextTask = dashboardData.learningPathNextTask.data ?? null;

const dashboardDegradedSections = [
    dashboardData.stats.isError ? "训练统计" : null,
    dashboardData.recommendation.isError ? "推荐入口" : null,
    dashboardData.history.isError ? "最近记录" : null,
    dashboardData.retrainingTasks.isError ? "复训任务" : null,
    dashboardData.learningPathNextTask.isError ? "学习路径" : null,
].filter((section): section is string => Boolean(section));
```

Keep the existing fallback copy and avoid changing unrelated UI layout.

- [ ] **Step 5: Run dashboard tests**

Run from `web/`:

```bash
npx vitest run src/hooks/use-dashboard-data.test.tsx 'src/app/(dashboard)/page.test.tsx'
```

Expected: PASS. Existing tests that asserted one manual effect call may need to assert query outcomes instead.

- [ ] **Step 6: Commit**

```bash
git add src/lib/query/dashboard.ts src/hooks/use-dashboard-data.ts src/hooks/use-dashboard-data.test.tsx 'src/app/(dashboard)/page.tsx' 'src/app/(dashboard)/page.test.tsx'
git commit -m "refactor: cache dashboard sections independently"
```

---

### Task 6: Route Prefetch For Frequent Navigation

**Files:**
- Modify: `web/src/components/layout/sidebar.tsx`
- Modify: `web/src/components/layout/sidebar.test.tsx`

- [ ] **Step 1: Add hover prefetch for dashboard entry**

Modify `NavLink` in `web/src/components/layout/sidebar.tsx`:

```tsx
import { useQueryClient } from "@tanstack/react-query";
import {
    dashboardHistoryQueryOptions,
    dashboardRecommendationQueryOptions,
    dashboardStatsQueryOptions,
} from "@/lib/query/dashboard";

function prefetchRouteData(queryClient: ReturnType<typeof useQueryClient>, href: string) {
    if (href !== "/") {
        return;
    }

    void Promise.allSettled([
        queryClient.prefetchQuery(dashboardStatsQueryOptions()),
        queryClient.prefetchQuery(dashboardRecommendationQueryOptions()),
        queryClient.prefetchQuery(dashboardHistoryQueryOptions(30)),
    ]);
}

export function NavLink(...) {
    const queryClient = useQueryClient();

    const linkContent = (
        <Link
            href={item.href}
            prefetch
            onMouseEnter={() => prefetchRouteData(queryClient, item.href)}
            onFocus={() => prefetchRouteData(queryClient, item.href)}
            ...
        >
            ...
        </Link>
    );
}
```

- [ ] **Step 2: Test hover prefetch**

Add a test in `web/src/components/layout/sidebar.test.tsx` that renders `NavLink` inside a `QueryClientProvider`, hovers the 首页 link, and asserts `api.dashboard.getStats` was called once without route navigation.

- [ ] **Step 3: Run sidebar tests**

Run from `web/`:

```bash
npx vitest run src/components/layout/sidebar.test.tsx src/components/layout/dashboard-shell.test.tsx
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/components/layout/sidebar.tsx src/components/layout/sidebar.test.tsx
git commit -m "perf: prefetch frequent dashboard route data"
```

---

### Task 7: Backend `/users/me` And Dashboard Slow Path Audit

**Files:**
- Review: `backend/src/common/auth/service.py`
- Review: `backend/src/common/api/users.py`
- Review: `backend/src/common/api/practice.py`
- Review: `backend/src/common/api/growth.py`
- Optional modify: backend tests only if code changes are justified by measurement.

- [ ] **Step 1: Inspect `/users/me` dependency chain**

Read:

```bash
nl -ba backend/src/common/auth/service.py | sed -n '480,560p'
nl -ba backend/src/common/api/users.py | sed -n '140,190p'
```

Expected: `/users/me` should only resolve session, load one user row, and build a small response.

- [ ] **Step 2: Look for accidental heavy joins or repeated relationship loading**

Search:

```bash
rg -n "joinedload|selectinload|organization|roles|permissions|interventions|history" backend/src/common/auth/service.py backend/src/common/api/users.py
```

Expected: no heavy relationships in the auth dependency for the basic current-user endpoint.

- [ ] **Step 3: Add backend timing evidence before optimizing**

If `/users/me` is slow, add structured timing around the auth dependency using the existing logger style in the file. Do not print. The log fields must avoid token/cookie values:

```python
logger.info(
    "auth.current_user.resolved",
    user_id=str(user.user_id),
    duration_ms=duration_ms,
    auth_source=auth_source,
)
```

- [ ] **Step 4: Only optimize after evidence**

Allowed backend optimizations if evidence shows a real issue:

```text
- Remove unnecessary relationship loading from current-user lookup.
- Ensure user lookup filters by indexed user_id/email/session token path.
- Keep /users/me response limited to id, display_name, avatar_url, role, department, email.
- Do not add frontend-only permission trust; backend still owns authorization.
```

- [ ] **Step 5: Run focused backend tests if modified**

Run from `backend/`:

```bash
pytest tests/unit/common/test_api_users.py tests/integration/test_auth_login_api.py
```

Expected: PASS.

- [ ] **Step 6: Commit only if backend changed**

```bash
git add src/common/auth/service.py src/common/api/users.py tests/unit/common/test_api_users.py tests/integration/test_auth_login_api.py
git commit -m "perf: slim current user auth lookup"
```

---

### Task 8: Final Verification Matrix

**Files:**
- No required source modification.

- [ ] **Step 1: Run frontend unit tests for touched surfaces**

Run from `web/`:

```bash
npx vitest run \
  src/hooks/use-current-user.test.tsx \
  src/hooks/use-auth-protection.test.tsx \
  src/lib/server-auth.test.ts \
  src/lib/api/client.auth.test.ts \
  src/components/providers/app-providers.test.tsx \
  src/components/layout/dashboard-shell.test.tsx \
  src/components/layout/admin-shell.test.tsx \
  src/components/layout/sidebar.test.tsx \
  src/hooks/use-dashboard-data.test.tsx \
  'src/app/(auth)/login/page.test.tsx' \
  'src/app/(dashboard)/page.test.tsx'
```

Expected: PASS.

- [ ] **Step 2: Run type check and lint**

Run from `web/`:

```bash
npx tsc --noEmit
npx eslint . --quiet
```

Expected: PASS.

- [ ] **Step 3: Run production build**

Run from `web/`:

```bash
npm run build
```

Expected: PASS.

- [ ] **Step 4: Manual route switching acceptance**

Run production server and verify:

```text
1. Login password request aborts around 8 seconds when backend is held pending.
2. Button text returns from 登录中... to 登录.
3. Toast shows 登录超时，请重试.
4. Clicking dashboard nav updates URL and shell before slow card data completes.
5. /users/me does not refetch on every same-session route click within 5 minutes unless invalidated.
6. Dashboard slow stats request degrades only stats block; recommendation/history still appear.
7. Session expiry still redirects to /login on 401.
8. Admin role mismatch still redirects away from admin routes.
```

- [ ] **Step 5: Risk and rollback note**

Record in the final delivery:

```text
Risk level: P1 because auth/session and route shell behavior are touched.
Rollback: revert commits for current-user cache, server-auth timeout, API timeout, dashboard query layer, and sidebar prefetch independently.
Feature flag: not required for frontend-only timeout/cache changes; if backend auth lookup changes are made, release behind normal deployment rollback.
```

---

## Self-Review

Spec coverage:

- Production-mode validation: Task 1 and Task 8.
- Login timeout and button recovery: Task 4.
- `/users/me` caching and non-blocking route transitions: Task 2 and Task 3.
- Layout auth/light shell: Task 2 and Task 3.
- Dashboard independent loading/degradation/cache: Task 5.
- Route prefetch: Task 6.
- Backend `/users/me` and slow endpoint audit: Task 7.

No new dependency is introduced. TanStack Query is already installed and configured.

Main implementation risk:

- `web/src/app/(dashboard)/page.tsx` is already modified in the working tree. The implementation must preserve those edits and avoid broad UI rewrites.
- Adding a default timeout to every JSON request can break long-running admin actions. This plan adds timeout support globally, then applies explicit short timeouts first to auth/current-user/dashboard route-critical requests. Broader endpoint-by-endpoint timeout inventory should be a follow-up after measuring long-running admin APIs.
