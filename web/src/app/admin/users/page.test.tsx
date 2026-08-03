import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import UsersPage from "./page";
import { ApiRequestError } from "@/lib/api/client";

const {
    pushMock,
    successToastMock,
    errorToastMock,
    getUsersMock,
    getTeamsMock,
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
    getUserMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    successToastMock: vi.fn(),
    errorToastMock: vi.fn(),
    getUsersMock: vi.fn(),
    getTeamsMock: vi.fn(),
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
    getUserMock: vi.fn(),
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
    ConfirmDialog: ({ open, title, confirmText = "确认", isLoading, confirmDisabled, onConfirm, children }: {
        open: boolean;
        title: string;
        confirmText?: string;
        isLoading?: boolean;
        confirmDisabled?: boolean;
        onConfirm: () => void;
        children?: ReactNode;
    }) => open ? (
        <section aria-label={title}>
            <h2>{title}</h2>
            {children}
            <button disabled={isLoading || confirmDisabled} onClick={onConfirm}>
                {isLoading ? "处理中..." : confirmText}
            </button>
        </section>
    ) : null,
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
                getTeams: getTeamsMock,
                createUser: createUserMock,
                updateUser: updateUserMock,
                updateUserRole: updateUserRoleMock,
                getUser: getUserMock,
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
        getTeamsMock.mockReset();
        getOperatingPackMock.mockReset();
        createUserMock.mockReset();
        updateUserMock.mockReset();
        updateUserRoleMock.mockReset();
        getUserMock.mockReset();
        suspendUserMock.mockReset();
        activateUserMock.mockReset();
        deleteUserMock.mockReset();
        exportUsersMock.mockReset();
        listPracticeTemplatesMock.mockReset();
        batchAssignMock.mockReset();

        suspendUserMock.mockResolvedValue({ status: "inactive", changed: true });
        activateUserMock.mockResolvedValue({ status: "active", changed: true });
        getUserMock.mockResolvedValue({
            id: "u1",
            display_name: "张三",
            role: "user",
            status: "active",
            credential_version: 1,
        });

        getUsersMock.mockResolvedValue({
            items: [],
            total: 0,
            page: 1,
            page_size: 10,
            has_more: false,
        });
        getTeamsMock.mockResolvedValue({ items: [], total: 0 });
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
                active_teams: 0,
                at_risk_users: 0,
                improving_users: 0,
                top_issue_family: null,
                top_blocker_family: null,
                top_not_evaluable_reason: null,
                top_degraded_reason: null,
            },
            cohort_issue_buckets: [],
            team_issue_buckets: [],
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

    it("renders the Team filter from authoritative active Team records", async () => {
        getTeamsMock.mockResolvedValue({
            items: [
                { team_id: "team-sales", code: "sales", name: "销售组", is_active: true, leader_user_ids: [], leaders: [], members: [], member_count: 0 },
                { team_id: "team-tech", code: "tech", name: "技术组", is_active: true, leader_user_ids: [], leaders: [], members: [], member_count: 0 },
                { team_id: "team-retired", code: "retired", name: "已停用组", is_active: false, leader_user_ids: [], leaders: [], members: [], member_count: 0 },
            ],
            total: 3,
        });
        getUsersMock.mockResolvedValue({
            items: [
                { id: "1", user_id: "u1", display_name: "张三", team: { team_id: "team-sales", code: "sales", name: "销售组" }, role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
                { id: "2", user_id: "u2", display_name: "李四", team: { team_id: "team-tech", code: "tech", name: "技术组" }, role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
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

        const teamSelect = screen.getByRole("combobox", { name: /团队筛选/i });
        await waitFor(() => expect(teamSelect.querySelector("option[value='team-sales']")).toBeTruthy());
        expect(teamSelect.querySelector("option[value='all']")).toBeTruthy();
        expect(teamSelect.querySelector("option[value='team-tech']")).toBeTruthy();
        expect(teamSelect.querySelector("option[value='team-retired']")).toBeNull();
    });

    it("passes the selected Team id to the server-side user filter", async () => {
        getTeamsMock.mockResolvedValue({
            items: [
                { team_id: "team-sales", code: "sales", name: "销售组", is_active: true, leader_user_ids: [], leaders: [], members: [], member_count: 0 },
                { team_id: "team-tech", code: "tech", name: "技术组", is_active: true, leader_user_ids: [], leaders: [], members: [], member_count: 0 },
            ],
            total: 2,
        });
        getUsersMock.mockResolvedValue({
            items: [
                { id: "1", user_id: "u1", display_name: "张三", team: { team_id: "team-sales", code: "sales", name: "销售组" }, role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
                { id: "2", user_id: "u2", display_name: "李四", team: { team_id: "team-tech", code: "tech", name: "技术组" }, role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
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

        getUsersMock.mockResolvedValue({
            items: [
                { id: "1", user_id: "u1", display_name: "张三", team: { team_id: "team-sales", code: "sales", name: "销售组" }, role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
            ],
            total: 1,
            page: 1,
            page_size: 10,
            has_more: false,
        });
        const teamSelect = screen.getByRole("combobox", { name: /团队筛选/i });
        await waitFor(() => expect(teamSelect.querySelector("option[value='team-sales']")).toBeTruthy());
        fireEvent.change(teamSelect, { target: { value: "team-sales" } });

        await waitFor(() => expect(getUsersMock).toHaveBeenLastCalledWith(expect.objectContaining({
            team_id: "team-sales",
        })));
        await waitFor(() => expect(screen.queryAllByText("李四")).toHaveLength(0));
    });

    it("renders multi-select checkboxes when users are loaded", async () => {
        getUsersMock.mockResolvedValue({
            items: [
                { id: "1", user_id: "u1", display_name: "张三", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
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
                { id: "1", user_id: "u1", display_name: "张三", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
                { id: "2", user_id: "u2", display_name: "李四", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
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

    it("uses reversible account status language and removes physical delete action", async () => {
        getUsersMock.mockResolvedValue({
            items: [
                { id: "u1", display_name: "张三", email: "zhang@example.com", role: "user", status: "active", is_active: true, credential_version: 1, created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
            ],
            total: 1,
        });

        render(<UsersPage />);

        expect((await screen.findAllByRole("button", { name: /停用账户/ })).length).toBeGreaterThan(0);
        expect(screen.queryByRole("button", { name: /删除用户/ })).toBeNull();
        expect(screen.queryByText(/不可撤销/)).toBeNull();
    });

    it("keeps account mutation loading scoped to the target account", async () => {
        let releaseSuspend: (() => void) | undefined;
        suspendUserMock.mockImplementation(() => new Promise((resolve) => {
            releaseSuspend = () => resolve({ status: "inactive", changed: true });
        }));
        getUsersMock.mockResolvedValue({
            items: [
                { id: "u1", display_name: "张三", role: "user", status: "active", is_active: true, credential_version: 1, created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
                { id: "u2", display_name: "李四", role: "user", status: "active", is_active: true, credential_version: 1, created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
            ],
            total: 2,
        });

        render(<UsersPage />);
        const suspendButtons = await screen.findAllByRole("button", { name: /停用账户/ });
        fireEvent.click(suspendButtons[0]);
        fireEvent.change(screen.getByLabelText("操作原因"), { target: { value: "员工离职" } });
        fireEvent.click(screen.getByRole("button", { name: "确认停用" }));

        await waitFor(() => expect(suspendUserMock).toHaveBeenCalled());
        expect(screen.getByRole("button", { name: "处理中..." }).hasAttribute("disabled")).toBe(true);
        expect(suspendButtons.some((button) => !button.hasAttribute("disabled"))).toBe(true);

        releaseSuspend?.();
    });

    it("reconciles authoritative status after a possible-write timeout", async () => {
        suspendUserMock.mockRejectedValue(new ApiRequestError({
            status: 0,
            errorCode: "[REQUEST_TIMEOUT]",
            message: "账户停用请求超时",
        }));
        getUserMock.mockResolvedValue({
            id: "u1",
            display_name: "张三",
            role: "user",
            status: "inactive",
            credential_version: 2,
        });
        getUsersMock.mockResolvedValue({
            items: [
                { id: "u1", display_name: "张三", role: "user", status: "active", is_active: true, credential_version: 1, created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
            ],
            total: 1,
        });

        render(<UsersPage />);
        fireEvent.click((await screen.findAllByRole("button", { name: /停用账户/ }))[0]);
        fireEvent.change(screen.getByLabelText("操作原因"), { target: { value: "员工离职" } });
        fireEvent.click(screen.getByRole("button", { name: "确认停用" }));

        expect(await screen.findByText("停用响应超时，但已核对：账号状态已经生效。")).toBeTruthy();
        expect(getUserMock).toHaveBeenCalledWith("u1");
        expect(screen.queryByLabelText("操作原因")).toBeNull();
    });

    it("selects only the clicked learner when the API returns canonical id without legacy user_id", async () => {
        getUsersMock.mockResolvedValue({
            items: [
                { id: "u1", display_name: "张三", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
                { id: "u2", display_name: "李四", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
            ],
            total: 2,
        });

        render(<UsersPage />);

        const zhangCheckboxes = await screen.findAllByRole("checkbox", { name: "选择 张三" });
        fireEvent.click(zhangCheckboxes[0]);

        expect(screen.getByText("已选择 1 位学员")).toBeTruthy();
        expect(screen.getAllByRole("checkbox", { name: "选择 张三" }).every((checkbox) => (checkbox as HTMLInputElement).checked)).toBe(true);
        expect(screen.getAllByRole("checkbox", { name: "选择 李四" }).every((checkbox) => !(checkbox as HTMLInputElement).checked)).toBe(true);
    });

    it("sends user_id payload and renders assigned/skipped/failed result from batch assign", async () => {
        getUsersMock.mockResolvedValue({
            items: [
                { id: "uid-01", display_name: "张三", email: "zhang@test.com", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
                { id: "uid-02", display_name: "李四", email: "li@test.com", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
                { id: "uid-03", display_name: "王五", email: "wang@test.com", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
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
                { id: "row-1", user_id: "uid-01", display_name: "张三", email: "old@test.com", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
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

        // Change role to admin — click the edit dialog's "平台管理员" role card (index 1: after create dialog's card at index 0)
        const adminRoles = screen.getAllByText("平台管理员");
        fireEvent.click(adminRoles[1]);

        fireEvent.click(screen.getByRole("button", { name: "保存修改" }));

        await waitFor(() => {
            expect(updateUserMock).toHaveBeenCalledWith("row-1", {
                name: "张三新",
                email: "new@test.com",
            });
        });
        expect(updateUserRoleMock).toHaveBeenCalledWith("row-1", { role: "admin" });
    });

    it("refreshes list with partial-failure message when profile update succeeds but role update fails", async () => {
        getUsersMock.mockResolvedValue({
            items: [
                { id: "row-1", user_id: "uid-01", display_name: "张三", email: "old@test.com", role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
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
        const adminRoles = screen.getAllByText("平台管理员");
        fireEvent.click(adminRoles[1]);

        fireEvent.click(screen.getByRole("button", { name: "保存修改" }));

        await waitFor(() => {
            expect(updateUserMock).toHaveBeenCalledWith("row-1", {
                name: "张三",
                email: "old@test.com",
            });
            expect(updateUserRoleMock).toHaveBeenCalledWith("row-1", { role: "admin" });
        });

        await waitFor(() => {
            expect(getUsersMock).toHaveBeenCalledTimes(2);
        });

        expect(successToastMock).toHaveBeenCalledWith("资料已更新，但角色更新失败，请重试");
        expect(errorToastMock).not.toHaveBeenCalled();
    });

    it("shows an explicit unassigned state when a learner has no Team", async () => {
        getUsersMock.mockResolvedValue({
            items: [
                { id: "1", user_id: "u1", display_name: "张三", team: null, role: "user", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
            ],
            total: 1, page: 1, page_size: 10, has_more: false,
        });

        render(<UsersPage />);

        await waitFor(() => {
            expect(screen.getAllByText("张三").length).toBeGreaterThanOrEqual(1);
        });

        const headers = screen.getAllByRole("columnheader");
        expect(headers.find((header) => header.textContent === "团队")).toBeTruthy();
        expect(screen.getAllByText("未分配").length).toBeGreaterThanOrEqual(1);
    });

    it("labels a training manager as sales leader only when an explicit team relationship exists", async () => {
        getUsersMock.mockResolvedValue({
            items: [
                { id: "lead-1", display_name: "李组长", role: "training_manager", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
                { id: "manager-1", display_name: "王培训", role: "training_manager", is_active: true, status: "active", created_at: "2026-01-01T00:00:00Z", total_sessions: 0, total_duration_minutes: 0, average_score: 0 },
            ],
            total: 2,
        });
        getTeamsMock.mockResolvedValue({
            items: [{
                team_id: "team-1",
                code: "east",
                name: "华东组",
                is_active: true,
                leader_user_ids: ["lead-1"],
                leaders: [{ user_id: "lead-1", name: "李组长", assignment_role: "primary" }],
                members: [],
                member_count: 0,
            }],
            total: 1,
        });

        render(<UsersPage />);

        expect((await screen.findAllByText("销售组长")).length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText("培训管理员").length).toBeGreaterThanOrEqual(1);
    });
});
