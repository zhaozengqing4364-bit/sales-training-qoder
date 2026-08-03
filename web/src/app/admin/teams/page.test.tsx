import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminTeamsPage from "./page";

const {
    getTeamsMock,
    getUsersMock,
    getTeamLeaderCandidatesMock,
    assignTeamMemberMock,
    assignTeamLeaderMock,
    createTeamMock,
    createUserMock,
    successToastMock,
} = vi.hoisted(() => ({
    getTeamsMock: vi.fn(),
    getUsersMock: vi.fn(),
    getTeamLeaderCandidatesMock: vi.fn(),
    assignTeamMemberMock: vi.fn(),
    assignTeamLeaderMock: vi.fn(),
    createTeamMock: vi.fn(),
    createUserMock: vi.fn(),
    successToastMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({
        href,
        children,
        prefetch,
    }: {
        href: string;
        children: ReactNode;
        prefetch?: boolean;
    }) => <a href={href} data-prefetch={String(prefetch)}>{children}</a>,
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({ success: successToastMock, error: vi.fn() }),
}));

vi.mock("@/lib/api/client", () => ({
    api: {
        admin: {
            getTeams: getTeamsMock,
            getUsers: getUsersMock,
            getTeamLeaderCandidates: getTeamLeaderCandidatesMock,
            assignTeamMember: assignTeamMemberMock,
            assignTeamLeader: assignTeamLeaderMock,
            createTeam: createTeamMock,
            createUser: createUserMock,
        },
    },
}));

const team = {
    team_id: "team-1",
    code: "east-sales",
    name: "华东销售组",
    is_active: true,
    leader_user_ids: ["lead-1"],
    leaders: [{ user_id: "lead-1", name: "李组长", email: "lead@qoder.ai", assignment_role: "primary" }],
    members: [{ user_id: "learner-1", name: "张学员", email: "learner@qoder.ai", membership_role: "primary" }],
    member_count: 1,
};

describe("AdminTeamsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getTeamsMock.mockResolvedValue({ items: [team], total: 1 });
        getUsersMock.mockResolvedValue({
            items: [
                { id: "learner-1", display_name: "张学员", email: "learner@qoder.ai", role: "user", status: "active" },
                { id: "learner-2", display_name: "王学员", email: "new@qoder.ai", role: "user", status: "active" },
            ],
            total: 2,
        });
        getTeamLeaderCandidatesMock.mockResolvedValue({
            items: [
                { user_id: "lead-1", name: "李组长", email: "lead@qoder.ai" },
                { user_id: "lead-2", name: "赵主管", email: "proxy@qoder.ai" },
            ],
        });
        assignTeamMemberMock.mockResolvedValue({ membership_id: "membership-2" });
        assignTeamLeaderMock.mockResolvedValue({ assignment_id: "assignment-2" });
        createUserMock.mockResolvedValue({
            id: "learner-3",
            display_name: "新学员",
            email: "newlearner@qoder.ai",
            role: "user",
            temporary_password: "Temp-123456",
        });
    });

    it("explains the account-to-team configuration path and shows current relationships", async () => {
        render(<AdminTeamsPage />);

        expect(await screen.findByRole("heading", { name: "华东销售组" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "返回用户管理" }).getAttribute("data-prefetch"))
            .toBe("false");
        expect(screen.getByText("1. 创建账号")).toBeTruthy();
        expect(screen.getByText("2. 建立团队关系")).toBeTruthy();
        expect(screen.getByText("3. 分配学员")).toBeTruthy();
        expect(screen.getByText(/本期销售组长只读查看结果/)).toBeTruthy();
        expect(screen.getByText("张学员")).toBeTruthy();
        expect(screen.getByText(/主组长：/).parentElement?.textContent).toContain("李组长");
    });

    it("assigns one learner to the selected team and reloads the relationship", async () => {
        render(<AdminTeamsPage />);
        const learnerSelect = await screen.findByRole("combobox", { name: "待分配学员" });

        fireEvent.change(learnerSelect, { target: { value: "learner-2" } });
        fireEvent.click(screen.getByRole("button", { name: "分配到当前团队" }));

        await waitFor(() => {
            expect(assignTeamMemberMock).toHaveBeenCalledWith("team-1", "learner-2");
        });
        expect(getTeamsMock.mock.calls.length).toBeGreaterThanOrEqual(2);
        expect(successToastMock).toHaveBeenCalledWith("学员已分配到团队");
    });

    it("updates the explicit primary leader relationship", async () => {
        render(<AdminTeamsPage />);
        const leaderSelect = await screen.findByRole("combobox", { name: "销售组长账号" });

        fireEvent.change(leaderSelect, { target: { value: "lead-2" } });
        fireEvent.click(screen.getByRole("button", { name: "保存组长关系" }));

        await waitFor(() => {
            expect(assignTeamLeaderMock).toHaveBeenCalledWith("team-1", {
                leader_user_id: "lead-2",
                assignment_role: "primary",
            });
        });
    });

    it("creates a missing learner account in flow and keeps the one-time credential visible", async () => {
        render(<AdminTeamsPage />);
        fireEvent.click(await screen.findByRole("button", { name: "没有学员账号？在此创建并继续分配" }));
        fireEvent.change(screen.getByRole("textbox", { name: "快速创建姓名" }), { target: { value: "新学员" } });
        fireEvent.change(screen.getByRole("textbox", { name: "快速创建邮箱" }), { target: { value: "newlearner@qoder.ai" } });
        fireEvent.click(screen.getByRole("button", { name: "创建并选中" }));

        await waitFor(() => {
            expect(createUserMock).toHaveBeenCalledWith({
                name: "新学员",
                email: "newlearner@qoder.ai",
                role: "user",
            });
        });
        expect(await screen.findByText("Temp-123456")).toBeTruthy();
        expect(screen.getByText("账号已创建，临时密码仅显示一次")).toBeTruthy();
    });
});
