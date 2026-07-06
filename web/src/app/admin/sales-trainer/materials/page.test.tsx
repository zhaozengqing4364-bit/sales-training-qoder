import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerMaterialsPage from "./page";

const {
    getCapabilitiesMock,
    listMaterialsMock,
    toastErrorMock,
    uploadMaterialVersionMock,
} = vi.hoisted(() => ({
    getCapabilitiesMock: vi.fn(),
    listMaterialsMock: vi.fn(),
    toastErrorMock: vi.fn(),
    uploadMaterialVersionMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/materials",
    useSearchParams: () => new URLSearchParams("module=ppt_explanation&purpose=ppt_pitch"),
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        success: vi.fn(),
        error: toastErrorMock,
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
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    getCapabilities: getCapabilitiesMock,
                    listMaterials: listMaterialsMock,
                    createMaterial: vi.fn(),
                    createMaterialVersion: vi.fn(),
                    uploadMaterialVersion: uploadMaterialVersionMock,
                    publishMaterialVersion: vi.fn(),
                },
            },
        },
    };
});

describe("SalesTrainerMaterialsPage", () => {
    beforeEach(() => {
        getCapabilitiesMock.mockReset();
        listMaterialsMock.mockReset();
        toastErrorMock.mockReset();
        uploadMaterialVersionMock.mockReset();
        uploadMaterialVersionMock.mockResolvedValue({ version_id: "version-upload" });
        getCapabilitiesMock.mockResolvedValue({
            role: "admin",
            role_label: "管理员",
            capabilities: {
                admin_full_access: false,
                manage_content: true,
                manage_questions: false,
                manage_modules: false,
                manage_prompts: false,
                view_records: false,
                view_global_records: false,
                retry_jobs: false,
                regrade_history: false,
                view_logs: false,
                view_settings: false,
            },
            capability_keys: ["manage_content"],
        });
        listMaterialsMock.mockResolvedValue({
            items: [
                {
                    material_id: "material-1",
                    material_key: "company_master_deck",
                    name: "公司主胶片",
                    material_type: "ppt_deck",
                    description: "新人路径 PPT",
                    purpose: "ppt_pitch",
                    status: "published",
                    current_version_id: "version-1",
                    current_version: {
                        version_id: "version-1",
                        material_id: "material-1",
                        version_label: "v2026.06",
                        title: "公司主胶片 2026-06",
                        file_name: "deck.pptx",
                        content_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        file_size_bytes: 1024,
                        storage_key: "cos://deck.pptx",
                        file_hash: null,
                        release_notes: null,
                        status: "published",
                        published_at: "2026-06-01T00:00:00Z",
                        published_by: "admin-1",
                        created_by: "admin-1",
                        created_at: "2026-06-01T00:00:00Z",
                        updated_at: "2026-06-01T00:00:00Z",
                    },
                    versions: [
                        {
                            version_id: "version-1",
                            material_id: "material-1",
                            version_label: "v2026.06",
                            title: "公司主胶片 2026-06",
                            file_name: "deck.pptx",
                            content_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            file_size_bytes: 1024,
                            storage_key: "cos://deck.pptx",
                            file_hash: null,
                            release_notes: null,
                            status: "published",
                            published_at: "2026-06-01T00:00:00Z",
                            published_by: "admin-1",
                            created_by: "admin-1",
                            created_at: "2026-06-01T00:00:00Z",
                            updated_at: "2026-06-01T00:00:00Z",
                        },
                    ],
                    created_by: "admin-1",
                    updated_by: "admin-1",
                    created_at: "2026-06-01T00:00:00Z",
                    updated_at: "2026-06-01T00:00:00Z",
                },
            ],
            total: 1,
        });
    });

    it("shows material purpose and lifecycle status in business language", async () => {
        render(<SalesTrainerMaterialsPage />);

        await waitFor(() => {
            expect(listMaterialsMock).toHaveBeenCalledWith({
                include_archived: true,
                limit: 100,
            });
        });

        expect((await screen.findAllByText("公司主胶片")).length).toBeGreaterThan(0);
        expect(screen.getAllByText("已发布").length).toBeGreaterThan(0);
        expect(screen.getAllByText("PPT 讲解录音").length).toBeGreaterThan(0);
        expect(screen.queryByText("ppt_pitch")).toBeNull();
        expect(screen.queryByText("published")).toBeNull();
    });

    it("explains the PPT material configuration flow when opened from diagnostics", async () => {
        render(<SalesTrainerMaterialsPage />);

        expect(await screen.findByRole("heading", { name: "PPT 讲解录音材料配置" })).toBeTruthy();
        expect(screen.getByText("1. 新建材料主档")).toBeTruthy();
        expect(screen.getByText("2. 上传文件生成材料版本")).toBeTruthy();
        expect(screen.getByText("3. 回到路径配置中心发布绑定")).toBeTruthy();
        expect(await screen.findByText("上传 PPT 或文档")).toBeTruthy();
        expect(screen.queryByText("文件存储地址")).toBeNull();
        expect(screen.queryByText("Storage Key")).toBeNull();
        expect(screen.queryByText("模块单元")).toBeNull();
        const purposeSelect = screen.getByLabelText("用途");
        expect(purposeSelect).toBeInstanceOf(HTMLSelectElement);
        if (!(purposeSelect instanceof HTMLSelectElement)) {
            throw new Error("用途字段应该是可选择的材料用途。");
        }
        expect(purposeSelect.value).toBe("ppt_pitch");
        expect(screen.getAllByText("PPT 讲解录音").length).toBeGreaterThan(0);
        const pathCenterLink = screen.getByRole("link", { name: "去路径配置中心发布绑定" });
        expect(pathCenterLink.getAttribute("href")).toBe("/admin/sales-trainer/paths?module=ppt_explanation");
        expect(pathCenterLink.querySelector("button")).toBeNull();
    });

    it("uploads a selected document as a new material version draft", async () => {
        render(<SalesTrainerMaterialsPage />);

        await screen.findByText("上传 PPT 或文档");
        const file = new File(["deck"], "new-deck.pptx", {
            type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        });
        fireEvent.change(screen.getByLabelText("上传 PPT 或文档"), {
            target: { files: [file] },
        });
        fireEvent.change(screen.getByLabelText("版本号"), {
            target: { value: "v2026.07" },
        });
        fireEvent.change(screen.getByLabelText("版本标题"), {
            target: { value: "公司主胶片 2026-07" },
        });
        fireEvent.click(screen.getByRole("button", { name: "上传并创建版本" }));

        await waitFor(() => {
            expect(uploadMaterialVersionMock).toHaveBeenCalledWith(
                "material-1",
                {
                    file,
                    version_label: "v2026.07",
                    title: "公司主胶片 2026-07",
                    release_notes: null,
                },
            );
        });
    });

    it("shows an explicit load error instead of an empty material library and recovers on retry", async () => {
        listMaterialsMock
            .mockRejectedValueOnce(new Error("materials forbidden"))
            .mockResolvedValueOnce({
                items: [
                    {
                        material_id: "material-2",
                        material_key: "product_deck",
                        name: "产品胶片",
                        material_type: "ppt_deck",
                        description: null,
                        purpose: "ppt_pitch",
                        status: "published",
                        current_version_id: null,
                        current_version: null,
                        versions: [],
                        created_by: "admin-1",
                        updated_by: "admin-1",
                        created_at: "2026-06-01T00:00:00Z",
                        updated_at: "2026-06-01T00:00:00Z",
                    },
                ],
                total: 1,
            });

        render(<SalesTrainerMaterialsPage />);

        expect(await screen.findByText("材料库加载失败")).toBeTruthy();
        expect(screen.getByText("materials forbidden")).toBeTruthy();
        expect(screen.queryByLabelText("材料标识")).toBeNull();
        expect(screen.queryByText("暂无训练材料")).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "重新加载材料" }));

        expect((await screen.findAllByText("产品胶片")).length).toBeGreaterThan(0);
        expect(screen.queryByText("材料库加载失败")).toBeNull();
    });

    it("fails closed before loading materials when capabilities are unavailable", async () => {
        getCapabilitiesMock.mockRejectedValueOnce(new Error("capability unavailable"));

        render(<SalesTrainerMaterialsPage />);

        expect(await screen.findByText("页面访问受限")).toBeTruthy();
        expect(screen.getByText("capability unavailable")).toBeTruthy();
        expect(listMaterialsMock).not.toHaveBeenCalled();
        expect(screen.queryByLabelText("材料标识")).toBeNull();
    });
});
