import { render, screen, waitFor } from "@testing-library/react";
import type { ComponentProps, ReactNode } from "react";
import { beforeEach, describe, expect, expectTypeOf, it, vi } from "vitest";

import KnowledgePage from "./knowledge/page";
import PersonasPage from "./personas/page";
import PresentationsPage from "./presentations/page";
import VoiceRuntimePage from "./voice-runtime/page";
import { AssetGovernanceOverview, AssetGovernanceSummaryCard } from "@/components/admin/asset-governance";
import type { AssetGovernanceSubject, AssetGovernanceSummary } from "@/lib/api/types";

const {
    successToastMock,
    errorToastMock,
    getKnowledgeBasesMock,
    getPersonasMock,
    getPersonaPolicyHealthMock,
    listPresentationsMock,
    getVoiceRuntimeProfilesMock,
} = vi.hoisted(() => ({
    successToastMock: vi.fn(),
    errorToastMock: vi.fn(),
    getKnowledgeBasesMock: vi.fn(),
    getPersonasMock: vi.fn(),
    getPersonaPolicyHealthMock: vi.fn(),
    listPresentationsMock: vi.fn(),
    getVoiceRuntimeProfilesMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        success: successToastMock,
        error: errorToastMock,
    }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                getKnowledgeBases: getKnowledgeBasesMock,
                getPersonas: getPersonasMock,
                getPersonaPolicyHealth: getPersonaPolicyHealthMock,
                getVoiceRuntimeProfiles: getVoiceRuntimeProfilesMock,
            },
            presentations: {
                ...actual.api.presentations,
                list: listPresentationsMock,
            },
        },
    };
});

const governanceSummary = {
    impact_summary: {
        impact_level: "high",
        recent_session_count: 18,
        active_session_count: 3,
        impacted_user_count: 7,
        last_session_at: "2026-03-26T09:30:00Z",
    },
    recent_change_summary: {
        last_changed_at: "2026-03-25T08:00:00Z",
        latest_change_type: "config_update",
        latest_change_label: "切换 KB 锁模式",
        change_count_7d: 2,
        sessions_since_change: 5,
    },
    health_summary: {
        status: "blocking",
        anomaly_count: 2,
        blocking_count: 1,
        warning_count: 1,
        sample_anomalies: [
            {
                source: "support_runtime",
                kind: "kb_lock_blocked_search_failed",
                severity: "blocking",
                summary: "知识库锁定模式下检索失败，最近 3 个会话被阻断。",
                detected_at: "2026-03-26T09:00:00Z",
                session_id: "session-1",
            },
        ],
    },
} satisfies AssetGovernanceSummary;

beforeEach(() => {
    successToastMock.mockReset();
    errorToastMock.mockReset();
    getKnowledgeBasesMock.mockReset();
    getPersonasMock.mockReset();
    getPersonaPolicyHealthMock.mockReset();
    listPresentationsMock.mockReset();
    getVoiceRuntimeProfilesMock.mockReset();

    getKnowledgeBasesMock.mockResolvedValue({
        items: [
            {
                id: "kb-1",
                name: "石犀产品知识库",
                description: "销售资料",
                category: "product",
                status: "active",
                document_count: 4,
                total_chunks: 22,
                created_at: "2026-03-20T00:00:00Z",
                updated_at: "2026-03-25T08:00:00Z",
                governance_summary: governanceSummary,
            },
        ],
        total: 1,
    });

    getPersonasMock.mockResolvedValue({
        items: [
            {
                id: "persona-1",
                name: "强压客户",
                description: "追问 ROI 证据",
                category: "customer",
                difficulty: "hard",
                status: "active",
                system_prompt: "请持续追问证据。",
                governance_summary: governanceSummary,
            },
        ],
        total: 1,
    });

    getPersonaPolicyHealthMock.mockResolvedValue({
        generated_at: "2026-03-26T09:10:00Z",
        summary: {
            total: 1,
            healthy: 0,
            with_issues: 1,
        },
        issue_type_counts: {
            pressure_model_legacy_only: 1,
        },
        sample_issues: [
            {
                persona_id: "persona-1",
                persona_name: "强压客户",
                issue_types: ["pressure_model_legacy_only"],
                policy_version: 1,
                require_kb_grounding: true,
                pressure_source: "legacy_sales_focus_extensions",
            },
        ],
    });

    listPresentationsMock.mockResolvedValue([
        {
            presentation_id: "ppt-1",
            title: "标准销售演示",
            status: "ready",
            version_number: 3,
            file_size_bytes: 2 * 1024 * 1024,
            page_count: 12,
            uploaded_by_admin_id: "admin-1",
            created_at: "2026-03-24T00:00:00Z",
            governance_summary: governanceSummary,
        },
    ]);

    getVoiceRuntimeProfilesMock.mockResolvedValue({
        items: [
            {
                id: "runtime-1",
                name: "销售默认 Realtime",
                description: "线上主配置",
                is_default: true,
                is_active: true,
                voice_mode: "stepfun_realtime",
                model_name: "step-audio-2",
                voice_name: "qingchunshaonv",
                temperature: 0.7,
                input_audio_format: "pcm16",
                output_audio_format: "pcm16",
                output_sample_rate: 24000,
                turn_detection: null,
                tool_policy: {
                    kb_lock_mode: "strict_audit",
                    max_questions_per_turn: 1,
                },
                governance_summary: governanceSummary,
            },
        ],
        total: 1,
    });
});

describe("admin asset governance pages", () => {
    it("narrows governance overview items to the shared frontend contract", () => {
        expectTypeOf<ComponentProps<typeof AssetGovernanceOverview>["items"]>()
            .toEqualTypeOf<AssetGovernanceSubject[]>();
    });

    it("narrows governance card props to the shared frontend contract", () => {
        expectTypeOf<ComponentProps<typeof AssetGovernanceSummaryCard>["summary"]>()
            .toEqualTypeOf<AssetGovernanceSummary | null | undefined>();
    });

    it.each([
        ["knowledge_base", "知识库"],
        ["persona", "角色"],
        ["presentation", "PPT"],
        ["runtime_profile", "运行时配置"],
    ])("uses the shared registry label for %s governance overview", (assetType, assetLabel) => {
        render(
            <AssetGovernanceOverview
                assetType={assetType}
                items={[{ governance_summary: governanceSummary }]}
            />,
        );

        expect(screen.getByText(`已覆盖 1/1 个${assetLabel}`)).toBeTruthy();
        expect(screen.getByText(`${assetLabel}中当前最可能影响范围较大的项`)).toBeTruthy();
    });

    it("shows governance overview and inline summary on the knowledge page", async () => {
        render(<KnowledgePage />);

        expect(await screen.findByText("治理视图")).toBeTruthy();
        expect(screen.getByText("高影响资产")).toBeTruthy();
        expect(screen.getAllByText("石犀产品知识库").length).toBeGreaterThan(0);
        expect(screen.getAllByText("高影响").length).toBeGreaterThan(0);
        expect(screen.getAllByText(/影响 7 名操作者 · 最近 18 个会话 · 活跃 3/).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/切换 KB 锁模式 · 近 7 天 2 次变更 · 变更后 5 个会话/).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/知识库锁定模式下检索失败，最近 3 个会话被阻断。/).length).toBeGreaterThan(0);
    });

    it("shows policy audit and governance context on the personas page", async () => {
        render(<PersonasPage />);

        expect(await screen.findByText("Persona 策略审计")).toBeTruthy();
        expect(screen.getByText("治理视图")).toBeTruthy();
        expect(screen.getAllByText("强压客户").length).toBeGreaterThan(0);
        expect(screen.getAllByText(/仍依赖 legacy 压测字段/).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/切换 KB 锁模式 · 近 7 天 2 次变更 · 变更后 5 个会话/).length).toBeGreaterThan(0);
    });

    it("shows governance context inside the presentations list", async () => {
        render(<PresentationsPage />);

        expect(await screen.findByText("治理视图")).toBeTruthy();
        expect(screen.getAllByText("标准销售演示").length).toBeGreaterThan(0);
        expect(screen.getAllByText(/影响 7 名操作者 · 最近 18 个会话 · 活跃 3/).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/知识库锁定模式下检索失败，最近 3 个会话被阻断。/).length).toBeGreaterThan(0);
    });

    it("shows governance context in the runtime profile list and selected editor pane", async () => {
        render(<VoiceRuntimePage />);

        expect(await screen.findByText("当前治理上下文")).toBeTruthy();
        expect(screen.getByText("销售默认 Realtime")).toBeTruthy();
        expect(screen.getAllByText(/影响 7 名操作者 · 最近 18 个会话 · 活跃 3/).length).toBeGreaterThan(1);
        expect(screen.getAllByText(/切换 KB 锁模式 · 近 7 天 2 次变更 · 变更后 5 个会话/).length).toBeGreaterThan(1);
    });
});
