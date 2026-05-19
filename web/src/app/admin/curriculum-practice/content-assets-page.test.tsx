import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminContentAssetsPage } from "./content-assets-page";

const {
    listCaseItemsMock,
    createCaseItemMock,
    publishCaseItemMock,
    archiveCaseItemMock,
    listRoleProfilesMock,
    createRoleProfileMock,
    updateRoleProfileMock,
    publishRoleProfileMock,
    archiveRoleProfileMock,
    cloneRoleProfileVoiceMock,
} = vi.hoisted(() => ({
    listCaseItemsMock: vi.fn(),
    createCaseItemMock: vi.fn(),
    publishCaseItemMock: vi.fn(),
    archiveCaseItemMock: vi.fn(),
    listRoleProfilesMock: vi.fn(),
    createRoleProfileMock: vi.fn(),
    updateRoleProfileMock: vi.fn(),
    publishRoleProfileMock: vi.fn(),
    archiveRoleProfileMock: vi.fn(),
    cloneRoleProfileVoiceMock: vi.fn(),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                listCaseItems: listCaseItemsMock,
                createCaseItem: createCaseItemMock,
                publishCaseItem: publishCaseItemMock,
                archiveCaseItem: archiveCaseItemMock,
                listRoleProfiles: listRoleProfilesMock,
                createRoleProfile: createRoleProfileMock,
                updateRoleProfile: updateRoleProfileMock,
                publishRoleProfile: publishRoleProfileMock,
                archiveRoleProfile: archiveRoleProfileMock,
                cloneRoleProfileVoice: cloneRoleProfileVoiceMock,
            },
        },
    };
});

vi.mock("@/lib/debug", () => ({
    debug: { warn: vi.fn() },
}));

const caseItem = {
    case_item_id: "case-1",
    industry: "制造业",
    company_profile: "大型制造客户",
    customer_role: "采购总监",
    pain_points: ["成本高"],
    objections: ["预算不足"],
    hidden_information: "竞品报价更低",
    success_criteria: ["确认试点"],
    allowed_disclosure_policy: { phases: ["discovery"] },
    content_hash: "sha256:case",
    version: 1,
    status: "draft",
    published_at: null,
    created_at: "2026-05-13T00:00:00Z",
    updated_at: "2026-05-13T00:00:00Z",
};

const roleProfile = {
    role_profile_id: "role-1",
    role_type: "customer" as const,
    role_name: "谨慎型采购总监",
    persona_ref: "persona-1",
    communication_style: "谨慎、重视证据",
    pressure_level: "high" as const,
    knowledge_boundary: ["价格", "交付"],
    behavior_rules: ["持续追问 ROI"],
    voice_style_hint: "低沉、慢速",
    voice_id: null,
    voice_sample_url: null,
    content_hash: "sha256:role",
    version: 1,
    status: "draft",
    published_at: null,
    created_at: "2026-05-13T00:00:00Z",
    updated_at: "2026-05-13T00:00:00Z",
};

describe("AdminContentAssetsPage", () => {
    beforeEach(() => {
        listCaseItemsMock.mockResolvedValue({ items: [caseItem], total: 1 });
        createCaseItemMock.mockReset();
        publishCaseItemMock.mockReset();
        archiveCaseItemMock.mockReset();
        listRoleProfilesMock.mockResolvedValue({ items: [roleProfile], total: 1 });
        createRoleProfileMock.mockReset();
        updateRoleProfileMock.mockReset();
        publishRoleProfileMock.mockReset();
        archiveRoleProfileMock.mockReset();
        cloneRoleProfileVoiceMock.mockReset();
    });

    it("lists CaseItems with search and status controls", async () => {
        render(<AdminContentAssetsPage assetType="case-item" />);

        expect(await screen.findByRole("heading", { name: "CaseItem 案例库" })).toBeTruthy();
        expect(screen.getByText("制造业 · 采购总监")).toBeTruthy();
        expect(screen.getByText("草稿 · v1")).toBeTruthy();
        fireEvent.change(screen.getByLabelText("搜索"), { target: { value: "不存在" } });
        expect(screen.getByText("暂无资产")).toBeTruthy();
    });

    it("creates CaseItems and reports CSV row-level errors", async () => {
        createCaseItemMock.mockResolvedValue({ ...caseItem, case_item_id: "case-2", industry: "金融业" });
        render(<AdminContentAssetsPage assetType="case-item" />);
        await screen.findByText("制造业 · 采购总监");

        fireEvent.change(screen.getByLabelText("行业"), { target: { value: "金融业" } });
        fireEvent.change(screen.getByLabelText("客户角色"), { target: { value: "CFO" } });
        fireEvent.change(screen.getByLabelText("公司画像"), { target: { value: "增长型客户" } });
        fireEvent.change(screen.getByLabelText("隐藏信息"), { target: { value: "预算紧张" } });
        fireEvent.change(screen.getByLabelText("痛点（逗号分隔）"), { target: { value: "效率低,成本高" } });
        fireEvent.change(screen.getByLabelText("异议（逗号分隔）"), { target: { value: "太贵" } });
        fireEvent.change(screen.getByLabelText("成功标准（逗号分隔）"), { target: { value: "约定试点" } });
        fireEvent.change(screen.getByLabelText("Content Hash"), { target: { value: "sha256:new" } });
        fireEvent.click(screen.getByRole("button", { name: "创建资产" }));

        await waitFor(() => {
            expect(createCaseItemMock).toHaveBeenCalledWith(expect.objectContaining({
                industry: "金融业",
                pain_points: ["效率低", "成本高"],
                allowed_disclosure_policy: { phases: ["discovery", "proposal"] },
            }));
        });

        fireEvent.change(screen.getByPlaceholderText(/industry,company_profile/), { target: { value: "bad,row" } });
        fireEvent.click(screen.getByRole("button", { name: "校验 CSV" }));
        expect(screen.getByText(/第 1 行/)).toBeTruthy();
        fireEvent.click(screen.getByRole("button", { name: "导入 CSV" }));
        expect(createCaseItemMock).toHaveBeenCalledTimes(1);
    });

    it("imports valid CSV rows without silently dropping invalid rows", async () => {
        createCaseItemMock.mockResolvedValue({ ...caseItem, case_item_id: "case-3", industry: "零售业" });
        render(<AdminContentAssetsPage assetType="case-item" />);
        await screen.findByText("制造业 · 采购总监");

        fireEvent.change(screen.getByPlaceholderText(/industry,company_profile/), {
            target: { value: "零售业,连锁门店,店长,客流少;转化低,预算不足,竞品促销,预约试用;确认预算,sha256:csv" },
        });
        fireEvent.click(screen.getByRole("button", { name: "导入 CSV" }));

        await waitFor(() => {
            expect(createCaseItemMock).toHaveBeenCalledWith(expect.objectContaining({
                industry: "零售业",
                pain_points: ["客流少", "转化低"],
                objections: ["预算不足"],
            }));
        });
        expect(screen.getByText(/CSV 导入完成：1 行/)).toBeTruthy();
    });

    it("reports backend validation failures with CSV row numbers", async () => {
        createCaseItemMock.mockRejectedValueOnce(new Error("content_hash mismatch"));
        render(<AdminContentAssetsPage assetType="case-item" />);
        await screen.findByText("制造业 · 采购总监");

        fireEvent.change(screen.getByPlaceholderText(/industry,company_profile/), {
            target: { value: "零售业,连锁门店,店长,客流少,预算不足,竞品促销,预约试用,sha256:bad" },
        });
        fireEvent.click(screen.getByRole("button", { name: "导入 CSV" }));

        await waitFor(() => {
            expect(screen.getByText(/CSV 导入部分失败：1 行未导入/)).toBeTruthy();
        });
        expect(screen.getByText(/第 1 行：content_hash mismatch/)).toBeTruthy();
    });

    it("publishes and archives a CaseItem from row actions", async () => {
        publishCaseItemMock.mockResolvedValue({ ...caseItem, status: "published" });
        archiveCaseItemMock.mockResolvedValue({ ...caseItem, status: "archived" });
        render(<AdminContentAssetsPage assetType="case-item" />);
        await screen.findByText("制造业 · 采购总监");

        fireEvent.click(screen.getByRole("button", { name: "发布资产" }));
        expect(publishCaseItemMock).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole("button", { name: "确认发布" }));
        await waitFor(() => expect(publishCaseItemMock).toHaveBeenCalledWith("case-1"));
        expect(screen.getByText(/发布完成/)).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: "归档资产" }));
        expect(archiveCaseItemMock).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole("button", { name: "确认归档" }));
        await waitFor(() => expect(archiveCaseItemMock).toHaveBeenCalledWith("case-1"));
    });

    it("lists RoleProfiles and submits voice clone fields", async () => {
        cloneRoleProfileVoiceMock.mockResolvedValue({ voice_id: "voice-1", retryable: false });
        render(<AdminContentAssetsPage assetType="role-profile" />);
        await screen.findByText("谨慎型采购总监");

        fireEvent.click(screen.getByRole("button", { name: "编辑资产" }));
        fireEvent.change(screen.getByLabelText("声音名称"), { target: { value: "谨慎采购" } });
        fireEvent.change(screen.getByLabelText("声音样本 URL"), { target: { value: "https://cdn.example/voice.wav" } });
        fireEvent.change(screen.getByLabelText("声音音频 Base64"), { target: { value: "UklGRg==" } });
        fireEvent.click(screen.getByRole("button", { name: "提交声音克隆" }));

        await waitFor(() => {
            expect(cloneRoleProfileVoiceMock).toHaveBeenCalledWith("role-1", expect.objectContaining({
                voice_name: "谨慎采购",
                voice_sample_url: "https://cdn.example/voice.wav",
                audio_base64: "UklGRg==",
            }));
        });
    });
});
