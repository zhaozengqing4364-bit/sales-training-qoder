# API Audit Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正 API 审计报告误报，修复 Admin Users 更新缺陷，清理明确冗余的前端 API wrapper，并做三个小型前端页面增强。

**Architecture:** 采用保守策略：前端未调用不等于后端无用，后端 API 不直接删除。变更集中在 API client、Admin 用户页、Dashboard、报告页和审计文档，避免触碰无关后端路由。

**Tech Stack:** Next.js App Router、React 19、TypeScript、Vitest、FastAPI API 契约文档。

---

## Worktree and commit rule

当前工作区已有大量未提交改动。执行本计划时不要自动 commit。每个任务完成后只汇报改动文件和验证结果，除非用户明确要求提交。

## Files

- Modify: `docs/api-contract/api-audit-anomaly-report.md`  
  修正误报，增加安全删除准则，将后端未被前端调用的能力归类为 backlog/保留。
- Modify: `web/src/lib/api/client.ts`  
  修复 `api.admin.updateUser` 方法，新增 `api.admin.updateUserRole`，删除 `adminPresentations` 和独立 `audioSegments` wrapper。
- Modify: `web/src/lib/api/types.ts`  
  增加更窄的 Admin 用户更新 payload 类型。
- Modify: `web/src/app/admin/users/page.tsx`  
  普通资料和角色分步更新，桌面表格增加“部门”列。
- Modify: `web/src/app/admin/users/page.test.tsx`  
  增加 Admin 用户编辑调用断言，覆盖 role 分离与部门列。
- Modify: `web/src/app/(dashboard)/page.tsx`  
  使用已有 `api.dashboard.getGrowth()` 响应展示简洁成长卡片。
- Modify: `web/src/app/(dashboard)/page.test.tsx`  
  覆盖成长卡片展示。
- Modify: `web/src/app/(user)/practice/[sessionId]/report/page.tsx`  
  在下一步推荐包含 `source_session_id` 时展示源报告链接。
- Modify: `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`  
  覆盖源报告链接。

## Task 1: 修正审计报告误报和删除准则

**Files:**
- Modify: `docs/api-contract/api-audit-anomaly-report.md`

- [ ] **Step 1: 定位需要修正的段落**

Run:
```bash
grep -n "featureFlags\|getPublicLeaderboard\|getMyRank\|markNotificationRead\|testModelConfig\|前端未调用\|后端定义但前端" docs/api-contract/api-audit-anomaly-report.md
```

Expected: 输出包含功能开关、排行榜、通知标记、模型配置测试和汇总统计段落。

- [ ] **Step 2: 修正 Feature Flags 误报**

将第 1.8 和 2.1 中“仅测试使用/页面未调用”的说法替换为：

```markdown
**修正后现状**：`api.featureFlags.get()` 已在 `web/src/app/(user)/exam/[sessionId]/page.tsx` 中用于读取 examiner 开关，因此不属于孤立 API。该端点保留，不进入删除或补 UI 清单。
```

- [ ] **Step 3: 修正 Dashboard Leaderboard 误报**

将 `api.dashboard.getPublicLeaderboard` 和 `api.dashboard.getMyRank` 的“仅定义”说明替换为：

```markdown
**修正后现状**：`api.dashboard.getPublicLeaderboard()` 与 `api.dashboard.getMyRank()` 已在 `web/src/app/(dashboard)/leaderboard/page.tsx` 使用。它们不是孤立方法，应从未使用统计中移除。
```

- [ ] **Step 4: 修正 markNotificationRead 反向误报**

将“只有 markNotificationRead 有页面调用”替换为：

```markdown
**修正后现状**：`api.dashboard.markNotificationRead` 仅在 API client 中定义，当前未发现生产页面调用。通知列表与已读操作应作为 Dashboard 通知中心 backlog 处理，而不是已接入能力。
```

- [ ] **Step 5: 修正 Model Configs 测试误报**

将 4.2 “无页面使用”替换为：

```markdown
**修正后现状**：`api.admin.testModelConfig` 与 `api.admin.testModelConfigInline` 已在 `web/src/app/admin/settings/page.tsx` 使用，不属于未接入 API。该项应从异常清单移除。
```

- [ ] **Step 6: 增加后端 API 删除准则**

在汇总统计前新增：

```markdown
### 删除准则

后端 API 不能仅因“前端未调用”删除。只有同时满足以下条件，才允许进入删除候选：无生产前端调用、无后端测试、无 API 契约文档、无 `router_registry.py` 兼容别名、无 release/governance/admin-only/ops 语义、无外部集成文档或脚本引用。

不满足任一条件时，应选择保留、标记 backlog，或走 deprecated 迁移计划。
```

- [ ] **Step 7: 验证文档无旧误报残留**

Run:
```bash
grep -n "featureFlags.*仅\|getPublicLeaderboard.*仅定义\|getMyRank.*仅定义\|testModelConfig.*无页面\|markNotificationRead.*有页面" docs/api-contract/api-audit-anomaly-report.md
```

Expected: 无匹配，或仅匹配“修正后现状”中的反向说明。

## Task 2: 修复 API client 中 Admin Users 更新契约

**Files:**
- Modify: `web/src/lib/api/types.ts`
- Modify: `web/src/lib/api/client.ts`
- Test: `web/src/lib/api/client-domains.test.ts` 或新建 `web/src/lib/api/client-admin-users.test.ts`

- [ ] **Step 1: 编写失败测试**

如果没有合适的 API client 测试文件，新建 `web/src/lib/api/client-admin-users.test.ts`：

```typescript
import { beforeEach, describe, expect, it, vi } from "vitest";

const fetchMock = vi.fn();

vi.stubGlobal("fetch", fetchMock);

describe("admin users api client", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ success: true, data: { id: "u1" } }),
    });
  });

  it("updates user profile with PUT and profile-only payload", async () => {
    const { api } = await import("./client");

    await api.admin.updateUser("u1", {
      name: "张三",
      email: "zhang@example.com",
      department: "销售部",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/admin/users/u1"),
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({
          name: "张三",
          email: "zhang@example.com",
          department: "销售部",
        }),
      }),
    );
  });

  it("updates user role through the dedicated role endpoint", async () => {
    const { api } = await import("./client");

    await api.admin.updateUserRole("u1", { role: "admin" });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/admin/users/u1/role"),
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ role: "admin" }),
      }),
    );
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd web && npx vitest run src/lib/api/client-admin-users.test.ts
```

Expected: FAIL，原因是 `updateUser` 仍是 `PATCH` 或 `updateUserRole` 不存在。

- [ ] **Step 3: 增加类型**

在 `web/src/lib/api/types.ts` 的 `AdminUser` 后增加：

```typescript
export interface AdminUserUpdatePayload {
    name?: string;
    email?: string;
    department?: string;
    is_active?: boolean;
    audit_reason?: string;
}

export interface AdminUserRoleUpdatePayload {
    role: string;
    audit_reason?: string;
}
```

- [ ] **Step 4: 修改 client 方法**

在 `web/src/lib/api/client.ts` 导入或使用新增类型后，将 admin 域中的方法改为：

```typescript
updateUser: async (id: string, data: AdminUserUpdatePayload) => {
    return apiFetch<AdminUser>(`/admin/users/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
    });
},

updateUserRole: async (id: string, data: AdminUserRoleUpdatePayload) => {
    return apiFetch<AdminUser>(`/admin/users/${id}/role`, {
        method: "PUT",
        body: JSON.stringify(data),
    });
},
```

- [ ] **Step 5: 运行 API client 测试**

Run:
```bash
cd web && npx vitest run src/lib/api/client-admin-users.test.ts
```

Expected: PASS。

## Task 3: 修复 Admin 用户页提交逻辑并增加部门列

**Files:**
- Modify: `web/src/app/admin/users/page.tsx`
- Modify: `web/src/app/admin/users/page.test.tsx`

- [ ] **Step 1: 扩展 test mock**

在 `web/src/app/admin/users/page.test.tsx` 的 hoisted mock 中加入 `updateUserRoleMock`，并在 `api.admin` mock 中暴露：

```typescript
updateUserRole: updateUserRoleMock,
```

在 `beforeEach` 中加入：

```typescript
updateUserRoleMock.mockReset();
```

- [ ] **Step 2: 增加失败测试，普通编辑不传 role/display_name**

在 `UsersPage` describe 末尾增加：

```typescript
it("updates profile fields separately from role changes", async () => {
    getUsersMock.mockResolvedValue({
        items: [
            { id: "row-1", user_id: "uid-01", display_name: "张三", email: "old@test.com", department: "销售部", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
        ],
        total: 1,
        page: 1,
        page_size: 10,
        has_more: false,
    });
    updateUserMock.mockResolvedValue({});
    updateUserRoleMock.mockResolvedValue({});

    render(<UsersPage />);

    await waitFor(() => {
        expect(screen.getAllByText("张三").length).toBeGreaterThanOrEqual(1);
    });

    fireEvent.click(screen.getAllByRole("button", { name: /编辑/ })[0]);
    fireEvent.change(screen.getByLabelText(/姓名/), { target: { value: "张三新" } });
    fireEvent.change(screen.getByLabelText(/邮箱/), { target: { value: "new@test.com" } });
    fireEvent.change(screen.getByLabelText(/角色/), { target: { value: "admin" } });
    fireEvent.click(screen.getByRole("button", { name: /保存/ }));

    await waitFor(() => {
        expect(updateUserMock).toHaveBeenCalledWith("row-1", {
            name: "张三新",
            email: "new@test.com",
            department: "销售部",
        });
    });
    expect(updateUserRoleMock).toHaveBeenCalledWith("row-1", { role: "admin" });
});
```

If labels differ in the actual modal, use `screen.debug()` and adjust selectors to existing accessible labels. Do not weaken assertions to implementation details.

- [ ] **Step 3: 运行测试确认失败**

Run:
```bash
cd web && npx vitest run 'src/app/admin/users/page.test.tsx'
```

Expected: FAIL，原因是 `updateUserRoleMock` 未调用或 payload 仍含 `display_name/role`。

- [ ] **Step 4: 修改提交逻辑**

在 `web/src/app/admin/users/page.tsx` 的 `handleUpdateUser` 中替换提交逻辑为：

```typescript
const profilePayload = {
    name: editForm.name || undefined,
    email: editForm.email || undefined,
    department: editForm.department || undefined,
};

await api.admin.updateUser(editingUser.id, profilePayload);

if (editForm.role && editForm.role !== editingUser.role) {
    await api.admin.updateUserRole(editingUser.id, { role: editForm.role });
}
```

- [ ] **Step 5: 增加部门列**

在桌面表格 header 中加入：

```tsx
<th className="px-4 py-3 text-left text-sm font-medium text-gray-500">部门</th>
```

在用户行中加入：

```tsx
<td className="px-4 py-3 text-sm text-gray-700">{user.department || "未设置"}</td>
```

保持移动端现有字段不变，避免范围扩大。

- [ ] **Step 6: 增加部门列测试**

如果现有测试没有覆盖桌面列，增加：

```typescript
it("renders department column in the user table", async () => {
    getUsersMock.mockResolvedValue({
        items: [
            { id: "1", user_id: "u1", display_name: "张三", department: "销售部", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
        ],
        total: 1,
        page: 1,
        page_size: 10,
        has_more: false,
    });

    render(<UsersPage />);

    expect(await screen.findByText("部门")).toBeTruthy();
    expect(await screen.findByText("销售部")).toBeTruthy();
});
```

- [ ] **Step 7: 运行页面测试**

Run:
```bash
cd web && npx vitest run 'src/app/admin/users/page.test.tsx'
```

Expected: PASS。

## Task 4: 删除明确冗余的前端 API wrapper

**Files:**
- Modify: `web/src/lib/api/client.ts`
- Update tests only if they import removed wrappers.

- [ ] **Step 1: 确认生产引用为空**

Run:
```bash
grep -R "adminPresentations\|api\.audioSegments" -n web/src web/tests
```

Expected: 只出现定义或测试 mock。若出现生产调用，停止本任务并记录引用，不删除对应 wrapper。

- [ ] **Step 2: 删除 `adminPresentations` 域**

在 `web/src/lib/api/client.ts` 删除对象属性：

```typescript
adminPresentations: {
    ...
}
```

删除范围只覆盖该对象，不删除 `api.presentations.*`。

- [ ] **Step 3: 删除独立 `audioSegments` 域**

在 `web/src/lib/api/client.ts` 删除顶层：

```typescript
audioSegments: {
    createUploadUrl: ...,
    register: ...,
    registerFailure: ...,
}
```

保留 `api.practice.audioSegments.*`。

- [ ] **Step 4: 验证无残留引用**

Run:
```bash
grep -R "adminPresentations\|api\.audioSegments" -n web/src web/tests
```

Expected: 无生产引用。测试引用若存在，按实际 API 调整或删除。

## Task 5: Dashboard 增加简洁成长卡片

**Files:**
- Modify: `web/src/app/(dashboard)/page.tsx`
- Modify: `web/src/app/(dashboard)/page.test.tsx`

- [ ] **Step 1: 编写成长卡片测试**

在 `web/src/app/(dashboard)/page.test.tsx` 增加：

```typescript
it("renders growth achievements and unread notification summary", async () => {
    getGrowthMock.mockResolvedValue({
        achievements: {
            unlocked: [
                {
                    achievement_id: "ach-1",
                    code: "first_practice",
                    name: "首次训练",
                    description: "完成第一次训练",
                    icon_key: "sparkles",
                    unlocked_at: "2026-05-18T00:00:00Z",
                },
            ],
        },
        notifications: {
            items: [
                {
                    notification_id: "n1",
                    type: "achievement",
                    title: "新成就",
                    content: "你解锁了首次训练",
                    is_read: false,
                },
            ],
            unread_count: 1,
        },
        goal: null,
    });

    render(<DashboardPage />);

    expect(await screen.findByText("成长动态")).toBeTruthy();
    expect(await screen.findByText("首次训练")).toBeTruthy();
    expect(await screen.findByText("1 条未读提醒")).toBeTruthy();
});
```

Use the actual imported page component name from the file if it differs.

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd web && npx vitest run 'src/app/(dashboard)/page.test.tsx'
```

Expected: FAIL，页面尚未渲染“成长动态”。

- [ ] **Step 3: 保存 growth 响应状态**

在 `web/src/app/(dashboard)/page.tsx` 增加状态：

```typescript
const [growthDashboard, setGrowthDashboard] = useState<GrowthDashboardResponse | null>(null);
```

在已有 `api.dashboard.getGrowth()` 成功分支中调用：

```typescript
setGrowthDashboard(growthResult);
```

失败分支设置为 `null`。

- [ ] **Step 4: 渲染卡片**

在首页上方统计区后加入：

```tsx
{growthDashboard && (
    <GlassCard className="p-4">
        <div className="flex items-center justify-between gap-3">
            <div>
                <h2 className="text-base font-semibold text-slate-900">成长动态</h2>
                <p className="text-sm text-slate-500">
                    {growthDashboard.notifications.unread_count > 0
                        ? `${growthDashboard.notifications.unread_count} 条未读提醒`
                        : "暂无未读提醒"}
                </p>
            </div>
            {growthDashboard.achievements.unlocked[0] && (
                <div className="rounded-full bg-amber-50 px-3 py-1 text-sm font-medium text-amber-700">
                    {growthDashboard.achievements.unlocked[0].name}
                </div>
            )}
        </div>
    </GlassCard>
)}
```

- [ ] **Step 5: 运行 Dashboard 测试**

Run:
```bash
cd web && npx vitest run 'src/app/(dashboard)/page.test.tsx'
```

Expected: PASS。

## Task 6: 报告页增加源报告链接

**Files:**
- Modify: `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- Modify: `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`

- [ ] **Step 1: 编写失败测试**

在报告页测试中找到 next recommendation mock，将 `source_session_id: "session-source-1"` 加入 mock，并断言：

```typescript
expect(await screen.findByRole("link", { name: /查看来源报告/ })).toHaveAttribute(
    "href",
    "/practice/session-source-1/report",
);
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd web && npx vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
```

Expected: FAIL，链接尚未渲染。

- [ ] **Step 3: 添加 Link import**

如果文件未导入 `Link`，增加：

```typescript
import Link from "next/link";
```

- [ ] **Step 4: 渲染来源链接**

在下一步推荐卡片展示 `source_session_id` 的位置附近加入：

```tsx
{nextRecommendation?.source_session_id && (
    <Link
        href={`/practice/${nextRecommendation.source_session_id}/report`}
        className="text-sm font-medium text-blue-600 hover:text-blue-700"
    >
        查看来源报告
    </Link>
)}
```

- [ ] **Step 5: 运行报告页测试**

Run:
```bash
cd web && npx vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
```

Expected: PASS。

## Task 7: 全量静态验证和残留检查

**Files:**
- No direct edits unless verification exposes issues.

- [ ] **Step 1: 检查误报文档残留**

Run:
```bash
grep -n "featureFlags.*仅\|getPublicLeaderboard.*仅定义\|getMyRank.*仅定义\|testModelConfig.*无页面\|markNotificationRead.*有页面" docs/api-contract/api-audit-anomaly-report.md
```

Expected: 无旧误报残留。

- [ ] **Step 2: 检查删除 wrapper 残留**

Run:
```bash
grep -R "adminPresentations\|api\.audioSegments" -n web/src web/tests
```

Expected: 无生产引用。

- [ ] **Step 3: 运行相关测试**

Run:
```bash
cd web && npx vitest run \
  src/lib/api/client-admin-users.test.ts \
  'src/app/admin/users/page.test.tsx' \
  'src/app/(dashboard)/page.test.tsx' \
  'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
```

Expected: PASS。

- [ ] **Step 4: 运行类型检查**

Run:
```bash
cd web && npx tsc --noEmit
```

Expected: exit code 0。

- [ ] **Step 5: 记录未解决项**

如果任何检查失败，记录：失败命令、失败文件、是否由本次改动引起、下一步修复路径。不要删除测试来通过。

## Self-review

- Spec coverage: 文档修正、Admin Users 修复、前端 wrapper 清理、三个 UI 增强和验证命令均已覆盖。
- Red-flag scan: 未发现未完成占位或模糊任务。
- Type consistency: 使用 `AdminUserUpdatePayload`、`AdminUserRoleUpdatePayload`，与后续 client 和页面任务一致。
- Scope control: 后端 API 删除被排除在本轮实施之外，符合 A 策略。
