import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { BusinessEtiquetteCapabilitySnapshotResponse } from "@/lib/api/types";

import BusinessEtiquetteCapabilitiesPage from "./page";

const {
    getAdminCapabilitiesMock,
    archiveCapabilityMock,
    getBusinessCapabilitiesMock,
    publishCapabilityMock,
    saveCapabilitiesMock,
    toastApi,
    toastSuccessMock,
} = vi.hoisted(() => {
    const toastError = vi.fn();
    const toastSuccess = vi.fn();
    return {
        getAdminCapabilitiesMock: vi.fn(),
        archiveCapabilityMock: vi.fn(),
        getBusinessCapabilitiesMock: vi.fn(),
        publishCapabilityMock: vi.fn(),
        saveCapabilitiesMock: vi.fn(),
        toastApi: {
            error: toastError,
            success: toastSuccess,
        },
        toastSuccessMock: toastSuccess,
    };
});

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/articles/capabilities",
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => toastApi,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>(
        "@/lib/api/client",
    );
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    archiveBusinessEtiquetteCapability: archiveCapabilityMock,
                    getBusinessEtiquetteCapabilities: getBusinessCapabilitiesMock,
                    getCapabilities: getAdminCapabilitiesMock,
                    publishBusinessEtiquetteCapability: publishCapabilityMock,
                    saveBusinessEtiquetteCapabilities: saveCapabilitiesMock,
                },
            },
        },
    };
});

function snapshot(
    overrides: Partial<BusinessEtiquetteCapabilitySnapshotResponse> = {},
): BusinessEtiquetteCapabilitySnapshotResponse {
    return {
        training_pack_key: "business_etiquette_v1",
        source: "default_seed",
        working_revision_id: "revision-1",
        working_revision_no: 1,
        active_revision_id: null,
        active_revision_no: null,
        has_unpublished_revision: true,
        schema_version: 1,
        original_chapter_count: 8,
        needs_save: true,
        management_entry: "/admin/sales-trainer/articles/capabilities",
        permission: "sales_trainer.manage_modules",
        effective_timing: "training_pack_revision_publish_time",
        capabilities: [
            {
                capability_key: "respect_boundaries",
                display_name: "尊重与分寸感",
                description: "能识别商务场景中的边界。",
                mastery_levels: [{
                    level_key: "basic_mastery",
                    display_name: "基本掌握",
                    min_score: 70,
                    description: "默认达标线。",
                }],
                default_threshold: 70,
                evidence_rules: [{
                    evidence_type: "quiz_question",
                    weight: 1,
                    required: true,
                    description: "小测命中该能力点。",
                }],
                owner_scope: "business_etiquette_training_pack",
                status: "draft",
            },
            {
                capability_key: "professional_image",
                display_name: "职业形象与仪态",
                description: "能管理着装、仪态和第一印象。",
                mastery_levels: [{
                    level_key: "basic_mastery",
                    display_name: "基本掌握",
                    min_score: 70,
                    description: "默认达标线。",
                }],
                default_threshold: 70,
                evidence_rules: [{
                    evidence_type: "ai_coach_card",
                    weight: 1,
                    required: true,
                    description: "AI 教练训练卡通过。",
                }],
                owner_scope: "business_etiquette_training_pack",
                status: "draft",
            },
        ],
        chapter_bindings: [
            {
                chapter_order: 1,
                capability_keys: ["respect_boundaries"],
            },
            {
                chapter_order: 2,
                capability_keys: ["professional_image"],
            },
        ],
        ...overrides,
    };
}

describe("BusinessEtiquetteCapabilitiesPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getAdminCapabilitiesMock.mockResolvedValue({
            role: "admin",
            role_label: "管理员",
            capabilities: {
                admin_full_access: false,
                manage_content: true,
                manage_modules: false,
                manage_prompts: false,
                manage_questions: false,
                view_records: false,
                view_settings: false,
                view_logs: false,
            },
        });
        getBusinessCapabilitiesMock.mockResolvedValue(snapshot());
        saveCapabilitiesMock.mockImplementation(async (payload) => ({
            ...snapshot({ source: "working_revision", needs_save: false }),
            capabilities: payload.capabilities,
            chapter_bindings: payload.chapter_bindings,
        }));
        publishCapabilityMock.mockResolvedValue(snapshot({
            source: "working_revision",
            needs_save: false,
            capabilities: [
                {
                    ...snapshot().capabilities[0],
                    status: "published",
                },
                snapshot().capabilities[1],
            ],
        }));
        archiveCapabilityMock.mockResolvedValue(snapshot({
            source: "working_revision",
            needs_save: false,
        }));
    });

    it("loads capability seed and saves a snapshot draft", async () => {
        render(<BusinessEtiquetteCapabilitiesPage />);

        expect(await screen.findByDisplayValue("尊重与分寸感")).toBeTruthy();
        expect(getBusinessCapabilitiesMock).toHaveBeenCalledTimes(1);
        expect(screen.getByText("默认种子")).toBeTruthy();
        expect(screen.getByText(/请保存为训练包草稿/)).toBeTruthy();

        fireEvent.change(screen.getByDisplayValue("尊重与分寸感"), {
            target: { value: "尊重与边界意识" },
        });
        fireEvent.click(screen.getByRole("button", { name: "保存能力点快照" }));

        await waitFor(() => {
            expect(saveCapabilitiesMock).toHaveBeenCalledWith(
                expect.objectContaining({
                    training_pack_key: "business_etiquette_v1",
                    reason: "保存商务礼仪能力点快照",
                }),
            );
        });
        const payload = saveCapabilitiesMock.mock.calls[0][0];
        expect(payload.capabilities[0].display_name).toBe("尊重与边界意识");
        expect(payload.chapter_bindings[0].capability_keys).toEqual([
            "respect_boundaries",
        ]);
        expect(toastSuccessMock).toHaveBeenCalledWith("能力点快照已保存为训练包草稿版本。");
    });

    it("publishes a single capability through the governed endpoint", async () => {
        render(<BusinessEtiquetteCapabilitiesPage />);

        await screen.findByDisplayValue("尊重与分寸感");
        fireEvent.click(screen.getAllByRole("button", { name: "发布" })[0]);

        await waitFor(() => {
            expect(publishCapabilityMock).toHaveBeenCalledWith(
                "respect_boundaries",
                expect.objectContaining({
                    training_pack_key: "business_etiquette_v1",
                }),
            );
        });
        expect(toastSuccessMock).toHaveBeenCalledWith("能力点已标记为已发布。");
    });

    it("fails closed before loading capability snapshot without content management permission", async () => {
        getAdminCapabilitiesMock.mockResolvedValue({
            role: "viewer",
            role_label: "只读成员",
            capabilities: {
                admin_full_access: false,
                manage_content: false,
                manage_modules: false,
                manage_prompts: false,
                manage_questions: false,
                view_records: true,
                view_settings: false,
                view_logs: false,
            },
        });

        render(<BusinessEtiquetteCapabilitiesPage />);

        expect(await screen.findByText("能力点管理权限不足")).toBeTruthy();
        expect(getBusinessCapabilitiesMock).not.toHaveBeenCalled();
        expect(saveCapabilitiesMock).not.toHaveBeenCalled();
        expect(publishCapabilityMock).not.toHaveBeenCalled();
        expect(screen.queryByRole("button", { name: "新增能力点" })).toBeNull();
        expect(screen.queryByRole("button", { name: "保存能力点快照" })).toBeNull();
        expect(screen.queryByRole("button", { name: "发布" })).toBeNull();
    });
});
