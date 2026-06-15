import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminPromptsPage from "./page";
import type { PromptTemplateGovernanceStatus } from "@/lib/api/types";

const {
    pushMock,
    errorToastMock,
    successToastMock,
    getMeMock,
    getPromptTemplatesMock,
    getScenarioPromptsMock,
    getPromptTemplateGovernanceStatusMock,
    getPromptTemplateOptionsMock,
    repairPromptTemplateDefaultsMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    errorToastMock: vi.fn(),
    successToastMock: vi.fn(),
    getMeMock: vi.fn(),
    getPromptTemplatesMock: vi.fn(),
    getScenarioPromptsMock: vi.fn(),
    getPromptTemplateGovernanceStatusMock: vi.fn(),
    getPromptTemplateOptionsMock: vi.fn(),
    repairPromptTemplateDefaultsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: pushMock,
    }),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" {...props}>
            {children}
        </button>
    ),
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
        <div {...props}>{children}</div>
    ),
}));

vi.mock("@/components/ui/badge", () => ({
    Badge: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
        <div {...props}>{children}</div>
    ),
}));

vi.mock("@/components/ui/input", () => ({
    Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} />,
}));

vi.mock("@/components/ui/confirm-dialog", () => ({
    ConfirmDialog: ({ open, title, description, confirmText, onConfirm }: {
        open: boolean;
        title: string;
        description: string;
        confirmText?: string;
        onConfirm: () => void;
    }) => open ? (
        <div role="dialog" aria-label={title}>
            <p>{description}</p>
            <button type="button" onClick={onConfirm}>{confirmText ?? "确认"}</button>
        </div>
    ) : null,
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        success: successToastMock,
        error: errorToastMock,
    }),
}));

vi.mock("@/lib/debug", () => ({
    debug: {
        error: vi.fn(),
    },
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            user: {
                ...actual.api.user,
                getMe: getMeMock,
            },
            admin: {
                ...actual.api.admin,
                getPromptTemplates: getPromptTemplatesMock,
                getScenarioPrompts: getScenarioPromptsMock,
                getPromptTemplateGovernanceStatus: getPromptTemplateGovernanceStatusMock,
                getPromptTemplateOptions: getPromptTemplateOptionsMock,
                repairPromptTemplateDefaults: repairPromptTemplateDefaultsMock,
                getPromptTemplateImpact: vi.fn(),
                clonePromptTemplate: vi.fn(),
                remediateInvalidPromptTemplates: vi.fn(),
                migrateInvalidPromptTemplates: vi.fn(),
                rollbackPromptTemplateGovernance: vi.fn(),
                updatePromptTemplate: vi.fn(),
                setDefaultPromptTemplate: vi.fn(),
                createScenarioPrompt: vi.fn(),
                deleteScenarioPrompt: vi.fn(),
            },
        },
    };
});

const governanceStatus: PromptTemplateGovernanceStatus = {
    allowed_prompt_types: ["summary", "realtime_scoring", "report"],
    policy: {
        variables_schema: "list[str]",
        invalid_history_runtime_behavior: "visible_in_governance_and_disabled_before_runtime_lookup",
        rollback: "restore from audit snapshot",
        audit_action: "prompt_template.governance.remediate_invalid",
    },
    invalid_count: 1,
    invalid_templates: [
        {
            id: "123e4567-e89b-12d3-a456-426614174003",
            name: "legacy variable object",
            prompt_type: "realtime_scoring",
            category: "sales",
            variables: { score: "number" },
            is_active: true,
            is_default: true,
            updated_at: null,
            issues: [
                {
                    code: "variables_object_schema",
                    severity: "blocking",
                    message: "variables must be a list[str]",
                },
            ],
            runtime_status: "disabled_required",
            remediation: "disable_and_clear_default",
        },
    ],
    limit: 1000,
    checked_count: 1,
    active_invalid_count: 1,
    invalid_active_count: 1,
    default_conflict_count: 0,
    issues: [
        {
            template_id: "123e4567-e89b-12d3-a456-426614174003",
            name: "legacy variable object",
            issue_codes: ["variables_object_schema"],
            messages: ["variables must be a list[str]"],
            recommended_action: "disable_and_clear_default",
        },
    ],
    rollback_policy: "restore from audit snapshot",
    audit_log_action: "prompt_template.governance.remediate_invalid",
};

describe("AdminPromptsPage governance UI", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getMeMock.mockResolvedValue({ role: "admin" });
        getScenarioPromptsMock.mockResolvedValue([]);
        getPromptTemplateGovernanceStatusMock.mockResolvedValue(governanceStatus);
        getPromptTemplateOptionsMock.mockResolvedValue({
            allowed_prompt_types: [
                { value: "summary", label: "总结" },
                { value: "realtime_scoring", label: "实时评分" },
                { value: "report", label: "综合报告" },
            ],
            sales_allowed_prompt_types: ["summary", "realtime_scoring", "report"],
            variables_schema: "list[str]",
            invalid_history_runtime_behavior: "visible_in_governance_and_disabled_before_runtime_lookup",
            rollback_policy: "restore from audit snapshot",
        });
        repairPromptTemplateDefaultsMock.mockImplementation((request: { dry_run?: boolean }) => {
            if (request.dry_run) {
                return Promise.resolve({
                    dry_run: true,
                    checked: 1,
                    repaired: 1,
                    items: [
                        {
                            template_id: "123e4567-e89b-12d3-a456-426614174003",
                            name: "legacy variable object",
                            actions: ["migrate_variables_to_list"],
                        },
                    ],
                    audit_action: null,
                });
            }
            return Promise.resolve({
                dry_run: false,
                checked: 1,
                repaired: 1,
                items: [],
                audit_action: "prompt_template.governance.repair_defaults",
            });
        });
        getPromptTemplatesMock.mockResolvedValue([
            {
                id: "123e4567-e89b-12d3-a456-426614174004",
                name: "Needs review template",
                prompt_type: "realtime_scoring",
                category: "sales",
                template: "Score {{ score }}",
                variables: ["score"],
                is_active: true,
                is_default: false,
                is_system: false,
                created_at: "2026-04-27T00:00:00.000Z",
                updated_at: "2026-04-27T00:00:00.000Z",
                governance_status: "needs_review",
                governance_issues: ["variables_object_schema", "invalid_prompt_type"],
            },
            {
                id: "123e4567-e89b-12d3-a456-426614174005",
                name: "新人训练路径商务技巧 AI 对话教练生成 v1",
                prompt_type: "stage",
                category: "sales_trainer_ai_coach",
                template: "为商务技巧 AI 教练生成对话与互动卡片。",
                variables: ["module_key"],
                is_active: true,
                is_default: false,
                is_system: true,
                created_at: "2026-06-15T00:00:00.000Z",
                updated_at: "2026-06-15T00:00:00.000Z",
                governance_status: "valid",
                governance_issues: [],
            },
            {
                id: "123e4567-e89b-12d3-a456-426614174006",
                name: "新人训练路径商务技巧 AI 教练题目生成 v1",
                prompt_type: "stage",
                category: "sales_trainer_ai_coach",
                template: "为商务礼仪章节生成题目草稿。",
                variables: ["chapter_content"],
                is_active: true,
                is_default: false,
                is_system: true,
                created_at: "2026-06-15T00:00:00.000Z",
                updated_at: "2026-06-15T00:00:00.000Z",
                governance_status: "valid",
                governance_issues: [],
            },
        ]);
    });

    it("surfaces invalid historical templates and triggers remediation", async () => {
        render(<AdminPromptsPage />);

        expect(await screen.findByText(/提示词治理发现 1 条非法历史模板/)).toBeTruthy();
        expect(screen.getByText(/变量规则：字符串数组/)).toBeTruthy();

        fireEvent.click(screen.getAllByRole("button", { name: "禁用非法历史模板" })[0]);
        await waitFor(() => {
            expect(repairPromptTemplateDefaultsMock).toHaveBeenCalledWith({
                reason: "运营后台预览提示词治理修复",
                dry_run: true,
            });
        });
        fireEvent.click(await screen.findByRole("button", { name: "执行修复" }));
        const dialog = screen.getByRole("dialog", { name: "执行治理修复" });
        fireEvent.click(within(dialog).getByRole("button", { name: "执行修复" }));

        await waitFor(() => {
            expect(repairPromptTemplateDefaultsMock).toHaveBeenCalledWith({
                reason: "运营后台执行提示词治理修复",
                dry_run: false,
            });
        });
        expect(successToastMock).toHaveBeenCalledWith("治理修复完成：1 项");
    });

    it("renders backend governance issue codes as operator-readable copy", async () => {
        render(<AdminPromptsPage />);
        expect(await screen.findByText(/提示词治理发现 1 条非法历史模板/)).toBeTruthy();
        expect(screen.getAllByText(/历史变量对象已标记待迁移/).length).toBeGreaterThan(0);
    });

    it("surfaces newcomer AI coach conversation and question prompt entry points", async () => {
        render(<AdminPromptsPage />);

        expect(await screen.findByText("新人训练 AI 教练提示词")).toBeTruthy();
        expect(await screen.findByText("Needs review template")).toBeTruthy();
        expect(screen.getByText("AI 教练对话系统提示词")).toBeTruthy();
        expect(screen.getByText("商务礼仪题目生成提示词")).toBeTruthy();
        expect(screen.getAllByText("新人训练路径商务技巧 AI 对话教练生成 v1").length).toBeGreaterThan(0);
        expect(screen.getAllByText("新人训练路径商务技巧 AI 教练题目生成 v1").length).toBeGreaterThan(0);
        expect(screen.getByText("分类：新人训练 AI 教练")).toBeTruthy();
    });

    it("keeps loaded prompt data visible when the governance status request fails", async () => {
        getPromptTemplateGovernanceStatusMock.mockRejectedValueOnce(new Error("governance down"));

        render(<AdminPromptsPage />);

        expect(await screen.findByText("部分提示词治理数据加载失败")).toBeTruthy();
        expect(screen.getByText("治理状态加载失败：governance down")).toBeTruthy();
        expect(screen.getAllByText("Needs review template").length).toBeGreaterThan(0);
        
    });
});
