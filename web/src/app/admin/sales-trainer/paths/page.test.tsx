import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerPathsPage from "./page";
import {
    defaultLearningContentsResponse,
    defaultMaterialsResponse,
    defaultPapersResponse,
    defaultPathConfigResponse,
    defaultPathRevisionsResponse,
    defaultPublishPreviewResponse,
    defaultScorePromptsResponse,
    defaultSettingsResponse,
    defaultUnitsResponse,
    pathConfigWithWorkingRevision,
    pathRevisionsWithRollbackTarget,
} from "./page.test-data";

const {
    getCapabilitiesMock,
    getPathConfigMock,
    getSettingsMock,
    listPathConfigRevisionsMock,
    listLearningContentsMock,
    listMaterialsMock,
    listPapersMock,
    listScorePromptsMock,
    listUnitsMock,
    previewPathConfigPublishMock,
    publishPathConfigMock,
    rollbackPathConfigMock,
    savePathConfigMock,
    searchParamsMock,
} = vi.hoisted(() => ({
    getCapabilitiesMock: vi.fn(),
    getPathConfigMock: vi.fn(),
    getSettingsMock: vi.fn(),
    listPathConfigRevisionsMock: vi.fn(),
    listLearningContentsMock: vi.fn(),
    listMaterialsMock: vi.fn(),
    listPapersMock: vi.fn(),
    listScorePromptsMock: vi.fn(),
    listUnitsMock: vi.fn(),
    previewPathConfigPublishMock: vi.fn(),
    publishPathConfigMock: vi.fn(),
    rollbackPathConfigMock: vi.fn(),
    savePathConfigMock: vi.fn(),
    searchParamsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/paths",
    useRouter: () => ({ push: vi.fn() }),
    useSearchParams: searchParamsMock,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    getCapabilities: getCapabilitiesMock,
                    getSettings: getSettingsMock,
                    listMaterials: listMaterialsMock,
                    listScorePrompts: listScorePromptsMock,
                    listUnits: listUnitsMock,
                },
                newcomerTraining: {
                    ...actual.api.admin.newcomerTraining,
                    getPathConfig: getPathConfigMock,
                    listPathConfigRevisions: listPathConfigRevisionsMock,
                    listPapers: listPapersMock,
                    previewPathConfigPublish: previewPathConfigPublishMock,
                    publishPathConfig: publishPathConfigMock,
                    rollbackPathConfig: rollbackPathConfigMock,
                    savePathConfig: savePathConfigMock,
                },
            },
            learningContents: {
                ...actual.api.learningContents,
                list: listLearningContentsMock,
            },
        },
    };
});

describe("SalesTrainerPathsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getCapabilitiesMock.mockResolvedValue({
            role: "admin",
            role_label: "管理员",
            capabilities: {
                admin_full_access: false,
                manage_content: false,
                manage_questions: false,
                manage_modules: true,
                manage_prompts: false,
                view_records: false,
                view_global_records: false,
                retry_jobs: false,
                regrade_history: false,
                view_logs: false,
                view_settings: false,
            },
            capability_keys: ["manage_modules"],
        });
        listUnitsMock.mockResolvedValue(defaultUnitsResponse());
        getPathConfigMock.mockResolvedValue(defaultPathConfigResponse());
        listPathConfigRevisionsMock.mockResolvedValue(defaultPathRevisionsResponse());
        listLearningContentsMock.mockResolvedValue(defaultLearningContentsResponse());
        listPapersMock.mockResolvedValue(defaultPapersResponse());
        listMaterialsMock.mockResolvedValue(defaultMaterialsResponse());
        listScorePromptsMock.mockResolvedValue(defaultScorePromptsResponse());
        getSettingsMock.mockResolvedValue(defaultSettingsResponse());
        previewPathConfigPublishMock.mockResolvedValue(defaultPublishPreviewResponse());
        savePathConfigMock.mockResolvedValue(defaultPathConfigResponse());
        publishPathConfigMock.mockResolvedValue(defaultPathConfigResponse());
        rollbackPathConfigMock.mockResolvedValue(defaultPathConfigResponse());
        searchParamsMock.mockReturnValue(new URLSearchParams());
    });

    it("renders a newcomer training path configuration center with diagnostics", async () => {
        render(<SalesTrainerPathsPage />);

        await waitFor(() => {
            expect(listUnitsMock).toHaveBeenCalledWith({
                include_archived: true,
                limit: 200,
            });
        });

        expect(listLearningContentsMock).toHaveBeenCalled();
        expect(getPathConfigMock).toHaveBeenCalled();
        expect(listPathConfigRevisionsMock).toHaveBeenCalled();
        expect(previewPathConfigPublishMock).not.toHaveBeenCalled();
        expect(listPapersMock).toHaveBeenCalledWith({ include_archived: true, limit: 100 });
        expect(listMaterialsMock).toHaveBeenCalledWith({ include_archived: true, limit: 100 });
        expect(listScorePromptsMock).toHaveBeenCalledWith({ include_archived: true });
        expect(getSettingsMock).toHaveBeenCalled();

        expect(screen.getByRole("heading", { name: "新人训练路径配置中心" })).toBeTruthy();
        expect(screen.getByText("第一关")).toBeTruthy();
        expect(screen.getByText("PPT 讲解录音")).toBeTruthy();
        expect(screen.getByText("第二关")).toBeTruthy();
        expect(screen.getByText("商务技巧新修订")).toBeTruthy();
        expect(screen.queryByText("模块二：旧商务技巧")).toBeNull();
        expect(screen.getByText("当前生效版本 v2")).toBeTruthy();
        expect(screen.getByText("路径级发布配置")).toBeTruthy();
        expect(screen.getByText("第三关")).toBeTruthy();
        expect(screen.getByText("电梯演讲")).toBeTruthy();
        expect(screen.getByText("第四关")).toBeTruthy();
        expect(screen.getByText("实时对练占位")).toBeTruthy();
        expect(screen.getByText("学习文章：见客户前商务礼仪（1 节）")).toBeTruthy();
        expect(screen.getByText("考卷：商务技巧考卷（0 题）")).toBeTruthy();
        expect(screen.getAllByText("缺少路径配置中心里的关卡配置。").length).toBeGreaterThan(0);
        expect(screen.getAllByRole("link", { name: "配置路径模块" })[0].getAttribute("href")).toBe(
            "/admin/sales-trainer/paths?module=ppt_explanation",
        );
        expect(screen.getAllByRole("link", { name: "选择评分标准" })[0].getAttribute("href")).toBe(
            "/admin/sales-trainer/paths?module=ppt_explanation",
        );
        expect(screen.getAllByRole("link", { name: "选择材料版本" })[0].getAttribute("href")).toBe(
            "/admin/sales-trainer/paths?module=ppt_explanation",
        );
        expect(screen.getAllByRole("link", { name: "选择材料版本" })[0].querySelector("button")).toBeNull();
        expect(screen.getByRole("link", { name: "选择 PPT 材料" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/materials?module=ppt_explanation&purpose=ppt_pitch",
        );
        expect(screen.getByRole("link", { name: "选择 PPT 材料" }).querySelector("button")).toBeNull();
        expect(screen.getByRole("link", { name: "配置商务技巧文章" }).getAttribute("href")).toBe("/admin/sales-trainer/articles");
        expect(screen.getByRole("link", { name: "查看配置健康" }).getAttribute("href")).toBe("/admin/sales-trainer/settings");
        expect(screen.getByRole("link", { name: "查看配置健康" }).querySelector("button")).toBeNull();
        expect(screen.getByText(/编辑会保存为新的待发布修订/)).toBeTruthy();
        expect(screen.getByLabelText("本次变更说明")).toBeTruthy();
        expect(screen.queryByText(/复制为新草稿/)).toBeNull();
        expect(screen.getAllByText("需补齐后发布").length).toBeGreaterThan(0);
        expect(screen.getAllByText("待配置").length).toBeGreaterThan(0);
        expect(screen.queryByRole("button", { name: "编辑关卡" })).toBeNull();
    });

    it("focuses the target module when opened from a diagnostic remediation link", async () => {
        searchParamsMock.mockReturnValue(new URLSearchParams("module=ppt_explanation"));

        render(<SalesTrainerPathsPage />);

        expect(await screen.findByText("正在配置：PPT 讲解录音")).toBeTruthy();
        expect(screen.getByRole("region", { name: "正在配置 PPT 讲解录音" })).toBeTruthy();
    });

    it("keeps the configuration center visible and surfaces missing article binding content", async () => {
        getPathConfigMock.mockResolvedValue({
            ...defaultPathConfigResponse(),
            path: {
                ...defaultPathConfigResponse().path,
                modules: [{
                    ...defaultPathConfigResponse().path.modules[0],
                    learning_content_id: "missing-content",
                }],
            },
        });

        render(<SalesTrainerPathsPage />);

        expect(await screen.findByRole("heading", { name: "新人训练路径配置中心" })).toBeTruthy();
        expect(await screen.findByText("第一关")).toBeTruthy();
        expect(screen.getByText("商务技巧新修订")).toBeTruthy();
        expect(screen.getByText("商务技巧文章绑定状态读取失败：当前路径配置绑定的商务技巧文章不在内容列表中：missing-content")).toBeTruthy();
        expect(screen.queryByText("缺少已发布商务技巧学习文章绑定。")).toBeNull();
        expect(screen.getByRole("link", { name: "配置商务技巧文章" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/articles",
        );
    });

    it("saves the current path config as a future-only working revision", async () => {
        render(<SalesTrainerPathsPage />);

        fireEvent.change(await screen.findByLabelText("本次变更说明"), {
            target: { value: "更新商务技巧考卷绑定" },
        });
        fireEvent.click(await screen.findByRole("button", { name: "保存当前配置为新修订" }));

        await waitFor(() => {
            expect(savePathConfigMock).toHaveBeenCalledWith({
                ...defaultPathConfigResponse().path,
                reason: "更新商务技巧考卷绑定",
            });
        });
        expect(await screen.findByText("已保存为待发布修订，发布后只影响后续学员。")).toBeTruthy();
    });

    it("requires a change reason before saving or publishing", async () => {
        getPathConfigMock.mockResolvedValue(pathConfigWithWorkingRevision());

        render(<SalesTrainerPathsPage />);

        expect(await screen.findByRole("button", { name: "保存当前配置为新修订" })).toHaveProperty("disabled", true);
        expect(screen.getByRole("button", { name: "发布并生效" })).toHaveProperty("disabled", true);
    });

    it("publishes a working revision without requiring administrators to swap bindings", async () => {
        getPathConfigMock.mockResolvedValue(pathConfigWithWorkingRevision());

        render(<SalesTrainerPathsPage />);

        fireEvent.change(await screen.findByLabelText("本次变更说明"), {
            target: { value: "发布试运行后的路径配置" },
        });
        fireEvent.click(await screen.findByRole("button", { name: "发布并生效" }));

        await waitFor(() => {
            expect(publishPathConfigMock).toHaveBeenCalledWith({
                reason: "发布试运行后的路径配置",
            });
        });
        expect(await screen.findByText("路径配置已发布生效；历史学员记录不会被改写。")).toBeTruthy();
    });

    it("shows publish preview impact when a working revision exists", async () => {
        getPathConfigMock.mockResolvedValue(pathConfigWithWorkingRevision());

        render(<SalesTrainerPathsPage />);

        expect((await screen.findAllByText("发布预览")).length).toBeGreaterThan(0);
        expect(previewPathConfigPublishMock).toHaveBeenCalled();
        expect(screen.getAllByText(/medium 风险/).length).toBeGreaterThan(0);
        expect(screen.getByText("medium 风险 / 影响 business_skills")).toBeTruthy();
    });

    it("keeps the center visible when publish preview fails provider readiness", async () => {
        getPathConfigMock.mockResolvedValue(pathConfigWithWorkingRevision());
        previewPathConfigPublishMock.mockRejectedValue(
            new Error("[NEWCOMER_REALTIME_PROVIDER_NOT_READY] provider 未就绪"),
        );

        render(<SalesTrainerPathsPage />);

        expect(await screen.findByRole("heading", { name: "新人训练路径配置中心" })).toBeTruthy();
        expect(await screen.findByText(/发布预览失败/)).toBeTruthy();
        expect(screen.getAllByText(/\[NEWCOMER_REALTIME_PROVIDER_NOT_READY\] provider 未就绪/).length).toBeGreaterThan(0);
    });

    it("rolls back a non-active path revision through the future-only rollback API", async () => {
        listPathConfigRevisionsMock.mockResolvedValue(pathRevisionsWithRollbackTarget());

        render(<SalesTrainerPathsPage />);

        const rollbackButtons = await screen.findAllByRole("button", { name: "回滚到此版本" });
        fireEvent.click(rollbackButtons[1]);
        expect(rollbackPathConfigMock).not.toHaveBeenCalled();

        fireEvent.change(screen.getByLabelText("回滚原因（版本 v2）"), {
            target: { value: "恢复到培训试运行版本" },
        });
        fireEvent.click(rollbackButtons[1]);

        await waitFor(() => {
            expect(rollbackPathConfigMock).toHaveBeenCalledWith({
                revision_id: "path-revision-2",
                reason: "恢复到培训试运行版本",
            });
        });
        expect(await screen.findByText("路径配置已回滚；回滚只影响后续学员。")).toBeTruthy();
    });

    it("fails closed before loading path config when capabilities are unavailable", async () => {
        getCapabilitiesMock.mockRejectedValueOnce(new Error("capability unavailable"));

        render(<SalesTrainerPathsPage />);

        expect(await screen.findByText("页面访问受限")).toBeTruthy();
        expect(screen.getByText("capability unavailable")).toBeTruthy();
        expect(listUnitsMock).not.toHaveBeenCalled();
        expect(getPathConfigMock).not.toHaveBeenCalled();
        expect(listPathConfigRevisionsMock).not.toHaveBeenCalled();
        expect(listLearningContentsMock).not.toHaveBeenCalled();
        expect(listPapersMock).not.toHaveBeenCalled();
        expect(listMaterialsMock).not.toHaveBeenCalled();
        expect(listScorePromptsMock).not.toHaveBeenCalled();
        expect(getSettingsMock).not.toHaveBeenCalled();
    });
});
