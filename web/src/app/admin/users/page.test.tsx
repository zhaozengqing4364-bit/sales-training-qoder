import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import UsersPage from "./page";

const {
    pushMock,
    successToastMock,
    errorToastMock,
    getUsersMock,
    getOperatingPackMock,
    createUserMock,
    updateUserMock,
    suspendUserMock,
    activateUserMock,
    deleteUserMock,
    exportUsersMock,
    listPracticeTemplatesMock,
    batchAssignMock,
    updateUserRoleMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    successToastMock: vi.fn(),
    errorToastMock: vi.fn(),
    getUsersMock: vi.fn(),
    getOperatingPackMock: vi.fn(),
    createUserMock: vi.fn(),
    updateUserMock: vi.fn(),
    suspendUserMock: vi.fn(),
    activateUserMock: vi.fn(),
    deleteUserMock: vi.fn(),
    exportUsersMock: vi.fn(),
    listPracticeTemplatesMock: vi.fn(),
    batchAssignMock: vi.fn(),
    updateUserRoleMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => (
        <a href={href}>{children}</a>
    ),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: pushMock,
    }),
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        success: successToastMock,
        error: errorToastMock,
    }),
}));

vi.mock("@/components/ui/glass-modal", () => ({
    Dialog: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
    DialogContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogDescription: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogFooter: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ui/glass-tooltip", () => ({
    TooltipProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
    Tooltip: ({ children }: { children: ReactNode }) => <>{children}</>,
    TooltipTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
    TooltipContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ui/mobile-table-card", () => ({
    MobileTableCard: ({ children, title }: { children?: ReactNode; title?: ReactNode }) => (
        <div>
            <div>{title}</div>
            {children}
        </div>
    ),
}));

vi.mock("@/components/ui/confirm-dialog", () => ({
    ConfirmDialog: () => null,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                getUsers: getUsersMock,
                createUser: createUserMock,
                updateUser: updateUserMock,
                updateUserRole: updateUserRoleMock,
                suspendUser: suspendUserMock,
                activateUser: activateUserMock,
                deleteUser: deleteUserMock,
                exportUsers: exportUsersMock,
                listPracticeTemplates: listPracticeTemplatesMock,
            },
            analytics: {
                ...actual.api.analytics,
                getOperatingPack: getOperatingPackMock,
            },
            trainingTasks: {
                ...actual.api.trainingTasks,
                batchAssign: batchAssignMock,
            },
        },
    };
});

describe("UsersPage", () => {
    beforeEach(() => {
        pushMock.mockReset();
        successToastMock.mockReset();
        errorToastMock.mockReset();
        getUsersMock.mockReset();
        getOperatingPackMock.mockReset();
        createUserMock.mockReset();
        updateUserMock.mockReset();
        updateUserRoleMock.mockReset();
        suspendUserMock.mockReset();
        activateUserMock.mockReset();
        deleteUserMock.mockReset();
        exportUsersMock.mockReset();
        listPracticeTemplatesMock.mockReset();
        batchAssignMock.mockReset();

        getUsersMock.mockResolvedValue({
            items: [],
            total: 0,
            page: 1,
            page_size: 10,
            has_more: false,
        });
        listPracticeTemplatesMock.mockResolvedValue({
            items: [],
            total: 0,
        });
    });

    it("falls back to the shared empty manager-lite lists when the operating-pack payload omits manager_lists", async () => {
        getOperatingPackMock.mockResolvedValue({
            score_basis: "session_evidence_projection_evaluable_only",
            weekly_summary: {
                window_days: 7,
                window_start: "2026-03-19T00:00:00Z",
                window_end: "2026-03-26T00:00:00Z",
                completed_sessions: 0,
                evaluable_sessions: 0,
                not_evaluable_sessions: 0,
                degraded_sessions: 0,
                active_departments: 0,
                at_risk_users: 0,
                improving_users: 0,
                top_issue_family: null,
                top_blocker_family: null,
                top_not_evaluable_reason: null,
                top_degraded_reason: null,
            },
            cohort_issue_buckets: [],
            department_issue_buckets: [],
            repeated_blocker_families: [],
            degradation_breakdown: {
                not_evaluable_reasons: [],
                degraded_reasons: [],
            },
        });

        render(<UsersPage />);

        await waitFor(() => {
            expect(getOperatingPackMock).toHaveBeenCalledWith({
                time_range: "7d",
                limit: 10,
                inactive_days: 7,
            });
        });

        expect(await screen.findByText("本周经营名单 drill-in")).toBeTruthy();
        expect(screen.getByText("当前没有风险成员。")).toBeTruthy();
        expect(screen.getByText("当前没有连续未练成员。")).toBeTruthy();
        expect(screen.getByText("当前没有显著回升成员。")).toBeTruthy();
    });

    it("renders department filter dropdown with unique departments from loaded users", async () => {
        getUsersMock.mockResolvedValue({
            items: [
                { id: "1", user_id: "u1", display_name: "张三", department: "销售部", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
                { id: "2", user_id: "u2", display_name: "李四", department: "技术部", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
            ],
            total: 2,
            page: 1,
            page_size: 10,
            has_more: false,
        });

        render(<UsersPage />);

        await waitFor(() => {
            expect(screen.getAllByText("张三").length).toBeGreaterThanOrEqual(1);
        });

        const deptSelect = screen.getByRole("combobox", { name: /部门筛选/i });
        expect(deptSelect).toBeTruthy();
        expect(deptSelect.querySelector("option[value='all']")).toBeTruthy();
        expect(deptSelect.querySelector("option[value='销售部']")).toBeTruthy();
        expect(deptSelect.querySelector("option[value='技术部']")).toBeTruthy();
    });

    it("filters displayed users by selected department", async () => {
        getUsersMock.mockResolvedValue({
            items: [
                { id: "1", user_id: "u1", display_name: "张三", department: "销售部", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
                { id: "2", user_id: "u2", display_name: "李四", department: "技术部", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
            ],
            total: 2,
            page: 1,
            page_size: 10,
            has_more: false,
        });

        render(<UsersPage />);

        await waitFor(() => {
            expect(screen.getAllByText("张三").length).toBeGreaterThanOrEqual(1);
        });
        expect(screen.getAllByText("李四").length).toBeGreaterThanOrEqual(1);

        const deptSelect = screen.getByRole("combobox", { name: /部门筛选/i });
        fireEvent.change(deptSelect, { target: { value: "销售部" } });

        expect(screen.getAllByText("张三").length).toBeGreaterThanOrEqual(1);
        expect(screen.queryAllByText("李四").length).toBe(0);
    });

    it("renders multi-select checkboxes when users are loaded", async () => {
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

        await waitFor(() => {
            expect(screen.getAllByText("张三").length).toBeGreaterThanOrEqual(1);
        });

        const checkboxes = screen.getAllByRole("checkbox");
        const userCheckboxes = checkboxes.filter(cb => cb.getAttribute("aria-label")?.includes("选择 张三") || cb.closest("label")?.getAttribute("aria-label")?.includes("选择"));
        expect(userCheckboxes.length).toBeGreaterThanOrEqual(1);
    });

    it("shows batch assign button when users are selected", async () => {
        getUsersMock.mockResolvedValue({
            items: [
                { id: "1", user_id: "u1", display_name: "张三", department: "销售部", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
                { id: "2", user_id: "u2", display_name: "李四", department: "技术部", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
            ],
            total: 2,
            page: 1,
            page_size: 10,
            has_more: false,
        });

        render(<UsersPage />);

        await waitFor(() => {
            expect(screen.getAllByText("张三").length).toBeGreaterThanOrEqual(1);
        });

        expect(screen.queryByText(/已选择 \d+ 位学员/)).toBeNull();

        const checkboxes = screen.getAllByRole("checkbox");
        const userCbs = checkboxes.filter(cb =>
            cb.getAttribute("aria-label")?.includes("选择 张三")
        );
        expect(userCbs.length).toBeGreaterThanOrEqual(2);
        fireEvent.click(userCbs[0]);

        expect(screen.getByText(/已选择 1 位学员/)).toBeTruthy();
        expect(screen.getAllByText(/批量分配训练任务/).length).toBeGreaterThanOrEqual(1);
    });

    it("sends user_id payload and renders assigned/skipped/failed result from batch assign", async () => {
        getUsersMock.mockResolvedValue({
            items: [
                { id: "row-1", user_id: "uid-01", display_name: "张三", email: "zhang@test.com", department: "销售部", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
                { id: "row-2", user_id: "uid-02", display_name: "李四", email: "li@test.com", department: "销售部", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
                { id: "row-3", user_id: "uid-03", display_name: "王五", email: "wang@test.com", department: "销售部", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
            ],
            total: 3,
            page: 1,
            page_size: 10,
            has_more: false,
        });
        listPracticeTemplatesMock.mockResolvedValue({
            items: [
                {
                    template_id: "tpl-1",
                    name: "销售实战",
                    description: "基础销售训练",
                    scenario_type: "sales",
                    mode: "examiner",
                    status: "published",
                    agent_id: "a1",
                    persona_id: "p1",
                    runtime_profile_id: "r1",
                    voice_mode: "legacy",
                    scoring_ruleset_id: "s1",
                    knowledge_base_refs: [],
                    version: 1,
                    content_hash: "abc",
                    created_at: "2026-01-01T00:00:00Z",
                    updated_at: "2026-01-01T00:00:00Z",
                    curriculum_plan: {
                        name: "销售基础课程",
                        stages: [
                            {
                                template_stage_key: "stage-1",
                                order: 1,
                                name: "学习阶段",
                                template_ref: {
                                    asset_type: "practice_template",
                                    asset_id: "tpl-1",
                                    version: 1,
                                    hash: "abc",
                                    snapshot_label: "published",
                                },
                                completion_policy: {
                                    min_score: 70,
                                    min_rounds: 1,
                                    max_duration_seconds: 3600,
                                },
                            },
                        ],
                    },
                },
            ],
            total: 1,
        });
        batchAssignMock.mockResolvedValue({
            assigned_count: 2,
            skipped_count: 1,
            failed_count: 1,
            assigned: [
                { user_id: "uid-01", task_id: "task-a" },
                { user_id: "uid-02", task_id: "task-b" },
            ],
            skipped: [
                { user_id: "uid-03", reason: "已有进行中任务" },
            ],
            failed: [
                { user_id: "uid-04", reason: "用户不存在" },
            ],
        });

        render(<UsersPage />);

        await waitFor(() => {
            expect(screen.getAllByText("张三").length).toBeGreaterThanOrEqual(1);
        });

        const zhangCb = screen.getAllByRole("checkbox", { name: "选择 张三" })[0];
        const liCb = screen.getAllByRole("checkbox", { name: "选择 李四" })[0];
        fireEvent.click(zhangCb);
        fireEvent.click(liCb);

        expect(screen.getByText(/已选择 2 位学员/)).toBeTruthy();

        const assignBtn = screen.getByRole("button", { name: /批量分配训练任务/ });
        fireEvent.click(assignBtn);

        await waitFor(() => {
            expect(listPracticeTemplatesMock).toHaveBeenCalled();
        });

        const confirmBtn = screen.getByRole("button", { name: "确认分配" });
        fireEvent.click(confirmBtn);

        await waitFor(() => {
            expect(batchAssignMock).toHaveBeenCalledWith(
                expect.objectContaining({
                    user_ids: expect.arrayContaining(["uid-01", "uid-02"]),
                }),
            );
        });

        await waitFor(() => {
            expect(screen.getByText("2")).toBeTruthy();
        });

        const zhangs = screen.getAllByText("张三");
        expect(zhangs.length).toBeGreaterThanOrEqual(1);

        const skipResult = screen.getByText("已有进行中任务");
        expect(skipResult).toBeTruthy();

        const failResult = screen.getByText("用户不存在");
        expect(failResult).toBeTruthy();
    });

    it("updates profile fields separately from role changes", async () => {
        getUsersMock.mockResolvedValue({
            items: [
                { id: "row-1", user_id: "uid-01", display_name: "张三", email: "old@test.com", department: "销售部", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
            ],
            total: 1, page: 1, page_size: 10, has_more: false,
        });
        updateUserMock.mockResolvedValue({});
        updateUserRoleMock.mockResolvedValue({});

        render(<UsersPage />);

        await waitFor(() => {
            expect(screen.getAllByText("张三").length).toBeGreaterThanOrEqual(1);
        });

        // Open edit dialog via "编辑权限" in action menu
        fireEvent.click(screen.getByRole("button", { name: "编辑权限" }));

        // Change name
        const nameInput = screen.getByDisplayValue("张三");
        fireEvent.change(nameInput, { target: { value: "张三新" } });

        // Change email
        const emailInput = screen.getByDisplayValue("old@test.com");
        fireEvent.change(emailInput, { target: { value: "new@test.com" } });

        // Change role to admin — click the edit dialog's "管理员" role card (index 1: after create dialog's card at index 0)
        const adminRoles = screen.getAllByText("管理员");
        fireEvent.click(adminRoles[1]);

        fireEvent.click(screen.getByRole("button", { name: "保存修改" }));

        await waitFor(() => {
            expect(updateUserMock).toHaveBeenCalledWith("row-1", {
                name: "张三新",
                email: "new@test.com",
                department: "销售部",
            });
        });
        expect(updateUserRoleMock).toHaveBeenCalledWith("row-1", { role: "admin" });
    });

    it("refreshes list with partial-failure message when profile update succeeds but role update fails", async () => {
        getUsersMock.mockResolvedValue({
            items: [
                { id: "row-1", user_id: "uid-01", display_name: "张三", email: "old@test.com", department: "销售部", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
            ],
            total: 1, page: 1, page_size: 10, has_more: false,
        });
        updateUserMock.mockResolvedValue({});
        updateUserRoleMock.mockRejectedValue(new Error("Role update permission denied"));

        render(<UsersPage />);

        await waitFor(() => {
            expect(screen.getAllByText("张三").length).toBeGreaterThanOrEqual(1);
        });

        fireEvent.click(screen.getByRole("button", { name: "编辑权限" }));
        const adminRoles = screen.getAllByText("管理员");
        fireEvent.click(adminRoles[1]);

        fireEvent.click(screen.getByRole("button", { name: "保存修改" }));

        await waitFor(() => {
            expect(updateUserMock).toHaveBeenCalledWith("row-1", expect.objectContaining({
                department: "销售部",
            }));
            expect(updateUserRoleMock).toHaveBeenCalledWith("row-1", { role: "admin" });
        });

        await waitFor(() => {
            expect(getUsersMock).toHaveBeenCalledTimes(2);
        });

        expect(successToastMock).toHaveBeenCalledWith("资料已更新，但角色更新失败，请重试");
        expect(errorToastMock).not.toHaveBeenCalled();
    });

    it("renders department column in the user table", async () => {
        getUsersMock.mockResolvedValue({
            items: [
                { id: "1", user_id: "u1", display_name: "张三", department: "销售部", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
            ],
            total: 1, page: 1, page_size: 10, has_more: false,
        });

        render(<UsersPage />);

        await waitFor(() => {
            expect(screen.getAllByText("张三").length).toBeGreaterThanOrEqual(1);
        });

        const headers = screen.getAllByRole("columnheader");
        const deptHeader = headers.find(h => h.textContent === "部门");
        expect(deptHeader).toBeTruthy();
        expect(screen.getAllByText("销售部").length).toBeGreaterThanOrEqual(1);
    });
});
