import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ContentAssetFormPage } from "@/components/admin/curriculum-practice/content-asset-form-page";
import { ContentAssetImportWizard } from "@/components/admin/curriculum-practice/content-asset-import-wizard";
import { ContentAssetIndex } from "@/components/admin/curriculum-practice/content-asset-index";

const {
    listCaseItemsMock,
    createCaseItemMock,
    publishCaseItemMock,
    archiveCaseItemMock,
    duplicateCaseItemMock,
    unpublishCaseItemMock,
    getCaseItemMock,
    getCaseItemTemplateReferencesMock,
    listRoleProfilesMock,
    createRoleProfileMock,
    updateRoleProfileMock,
    publishRoleProfileMock,
    archiveRoleProfileMock,
    cloneRoleProfileVoiceMock,
    getPersonaMock,
    getRoleProfileMock,
} = vi.hoisted(() => ({
    listCaseItemsMock: vi.fn(),
    createCaseItemMock: vi.fn(),
    publishCaseItemMock: vi.fn(),
    archiveCaseItemMock: vi.fn(),
    duplicateCaseItemMock: vi.fn(),
    unpublishCaseItemMock: vi.fn(),
    getCaseItemMock: vi.fn(),
    getCaseItemTemplateReferencesMock: vi.fn(),
    listRoleProfilesMock: vi.fn(),
    createRoleProfileMock: vi.fn(),
    updateRoleProfileMock: vi.fn(),
    publishRoleProfileMock: vi.fn(),
    archiveRoleProfileMock: vi.fn(),
    cloneRoleProfileVoiceMock: vi.fn(),
    getPersonaMock: vi.fn(),
    getRoleProfileMock: vi.fn(),
}));

const searchParamsState = vi.hoisted(() => ({ value: new URLSearchParams() }));

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn() }),
    useSearchParams: () => searchParamsState.value,
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({ success: vi.fn(), error: vi.fn(), showToast: vi.fn() }),
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
                duplicateCaseItem: duplicateCaseItemMock,
                unpublishCaseItem: unpublishCaseItemMock,
                getCaseItem: getCaseItemMock,
                getCaseItemTemplateReferences: getCaseItemTemplateReferencesMock,
                listRoleProfiles: listRoleProfilesMock,
                createRoleProfile: createRoleProfileMock,
                updateRoleProfile: updateRoleProfileMock,
                publishRoleProfile: publishRoleProfileMock,
                archiveRoleProfile: archiveRoleProfileMock,
                cloneRoleProfileVoice: cloneRoleProfileVoiceMock,
                getPersona: getPersonaMock,
                getRoleProfile: getRoleProfileMock,
            },
        },
    };
});

vi.mock("@/components/admin/persona-ref-picker", () => ({
    PersonaRefPicker: ({ value, onChange }: { value: string; onChange: (id: string) => void }) => (
        <label>
            关联 Persona（可选）
            <input
                aria-label="关联 Persona（可选）"
                value={value}
                onChange={(event) => onChange(event.target.value)}
            />
        </label>
    ),
}));

vi.mock("@/lib/debug", () => ({
    debug: { warn: vi.fn(), log: vi.fn() },
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

describe("ContentAssetIndex", () => {
    beforeEach(() => {
        listCaseItemsMock.mockResolvedValue({ items: [caseItem], total: 1 });
        publishCaseItemMock.mockReset();
        archiveCaseItemMock.mockReset();
        duplicateCaseItemMock.mockReset();
        getCaseItemTemplateReferencesMock.mockResolvedValue({ items: [], total: 0 });
        listRoleProfilesMock.mockResolvedValue({ items: [roleProfile], total: 1 });
    });

    it("shows published immutability guide and duplicate action", async () => {
        listCaseItemsMock.mockResolvedValue({
            items: [{ ...caseItem, status: "published" }],
            total: 1,
        });
        render(<ContentAssetIndex assetType="case-item" />);
        await screen.findByText("制造业 · 采购总监");
        expect(screen.getByText(/已发布内容不可修改/)).toBeTruthy();
        expect(screen.getByRole("button", { name: "复制为新草稿" })).toBeTruthy();
        expect(screen.queryByRole("link", { name: "编辑资产" })).toBeNull();
    });

    it("duplicates a published CaseItem from row action", async () => {
        listCaseItemsMock.mockResolvedValue({
            items: [{ ...caseItem, status: "published" }],
            total: 1,
        });
        duplicateCaseItemMock.mockResolvedValue({ ...caseItem, case_item_id: "case-copy", status: "draft", customer_role: "采购总监 (副本)" });
        render(<ContentAssetIndex assetType="case-item" />);
        await screen.findByText("制造业 · 采购总监");
        fireEvent.click(screen.getByRole("button", { name: "复制为新草稿" }));
        await waitFor(() => expect(duplicateCaseItemMock).toHaveBeenCalledWith("case-1"));
    });

    it("lists CaseItems with search controls", async () => {
        render(<ContentAssetIndex assetType="case-item" />);

        expect(await screen.findByRole("heading", { name: "训练案例库" })).toBeTruthy();
        expect(screen.getByText("制造业 · 采购总监")).toBeTruthy();
        fireEvent.change(screen.getByLabelText("搜索"), { target: { value: "不存在" } });
        expect(screen.getByText("暂无资产")).toBeTruthy();
    });

    it("publishes and archives a CaseItem from row actions", async () => {
        publishCaseItemMock.mockResolvedValue({ ...caseItem, status: "published" });
        archiveCaseItemMock.mockResolvedValue({ ...caseItem, status: "archived" });
        render(<ContentAssetIndex assetType="case-item" />);
        await screen.findByText("制造业 · 采购总监");

        fireEvent.click(screen.getByRole("button", { name: "发布资产" }));
        fireEvent.click(screen.getByRole("button", { name: "确认发布" }));
        await waitFor(() => expect(publishCaseItemMock).toHaveBeenCalledWith("case-1"));

        fireEvent.click(screen.getByRole("button", { name: "归档资产" }));
        fireEvent.click(screen.getByRole("button", { name: "确认归档" }));
        await waitFor(() => expect(archiveCaseItemMock).toHaveBeenCalledWith("case-1"));
    });

    it("lists RoleProfiles on role-profile index", async () => {
        render(<ContentAssetIndex assetType="role-profile" />);
        expect(await screen.findByRole("heading", { name: "客户角色库" })).toBeTruthy();
        expect(screen.getByText("谨慎型采购总监")).toBeTruthy();
    });
});

describe("ContentAssetImportWizard", () => {
    beforeEach(() => {
        createCaseItemMock.mockReset();
    });

    it("reports CSV row-level errors on import page", async () => {
        render(<ContentAssetImportWizard assetType="case-item" />);
        fireEvent.change(screen.getByPlaceholderText(/industry,company_profile/), { target: { value: "bad,row" } });
        fireEvent.click(screen.getByRole("button", { name: "校验 CSV" }));
        expect(screen.getByText(/第 1 行/)).toBeTruthy();
    });

    it("imports valid CSV rows", async () => {
        createCaseItemMock.mockResolvedValue({ ...caseItem, case_item_id: "case-3", industry: "零售业" });
        render(<ContentAssetImportWizard assetType="case-item" />);

        fireEvent.change(screen.getByPlaceholderText(/industry,company_profile/), {
            target: { value: "零售业,连锁门店,店长,客流少;转化低,预算不足,竞品促销,预约试用;确认预算,sha256:csv" },
        });
        fireEvent.click(screen.getByRole("button", { name: "导入 CSV" }));

        await waitFor(() => {
            expect(createCaseItemMock).toHaveBeenCalledWith(expect.objectContaining({
                industry: "零售业",
                pain_points: ["客流少", "转化低"],
            }));
        });
        expect(screen.getByText(/CSV 导入完成：1 行/)).toBeTruthy();
    });
});

describe("ContentAssetFormPage", () => {
    beforeEach(() => {
        createCaseItemMock.mockReset();
        updateRoleProfileMock.mockReset();
        getPersonaMock.mockReset();
        getCaseItemMock.mockReset();
        getRoleProfileMock.mockResolvedValue(roleProfile);
        listRoleProfilesMock.mockResolvedValue({ items: [roleProfile], total: 1 });
    });

    it("prefills create form from published source via from query", async () => {
        searchParamsState.value = new URLSearchParams("from=case-1");
        getCaseItemMock.mockResolvedValue({ ...caseItem, status: "published" });

        render(<ContentAssetFormPage assetType="case-item" mode="create" />);

        expect(await screen.findByDisplayValue("采购总监 (副本)")).toBeTruthy();
        expect(screen.getByText(/已基于已发布资产预填/)).toBeTruthy();
        searchParamsState.value = new URLSearchParams();
    });

    it("loads draft CaseItem for edit via getCaseItem", async () => {
        getCaseItemMock.mockResolvedValue(caseItem);
        render(<ContentAssetFormPage assetType="case-item" mode="edit" assetId="case-1" />);
        await screen.findByRole("button", { name: "保存资产" });
        expect(getCaseItemMock).toHaveBeenCalledWith("case-1");
    });

    it("creates CaseItems from dedicated form page", async () => {
        createCaseItemMock.mockResolvedValue({ ...caseItem, case_item_id: "case-2", industry: "金融业" });
        render(<ContentAssetFormPage assetType="case-item" mode="create" />);

        fireEvent.change(screen.getByLabelText("行业"), { target: { value: "金融业" } });
        fireEvent.change(screen.getByLabelText("案例内客户描述（文本剧本，非角色库）"), { target: { value: "CFO" } });
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
            }));
        });
    });

    it("rejects RoleProfile save when persona_ref does not exist", async () => {
        getRoleProfileMock.mockResolvedValue(roleProfile);
        getPersonaMock.mockRejectedValue(new Error("Persona not found"));
        render(<ContentAssetFormPage assetType="role-profile" mode="edit" assetId="role-1" />);
        await screen.findByRole("button", { name: "保存资产" });

        fireEvent.change(screen.getByLabelText("关联 Persona（可选）"), {
            target: { value: "missing-persona" },
        });
        fireEvent.click(screen.getByRole("button", { name: "保存资产" }));

        await waitFor(() => {
            expect(screen.getByText(/保存失败：所选 Persona 不存在/)).toBeTruthy();
        });
        expect(updateRoleProfileMock).not.toHaveBeenCalled();
    });

    it("submits voice clone fields on role profile edit page", async () => {
        cloneRoleProfileVoiceMock.mockResolvedValue({ voice_id: "voice-1", retryable: false });
        render(<ContentAssetFormPage assetType="role-profile" mode="edit" assetId="role-1" />);
        await screen.findByRole("button", { name: "提交声音克隆" });

        fireEvent.change(screen.getByLabelText("声音名称"), { target: { value: "谨慎采购" } });
        fireEvent.change(screen.getByLabelText("声音样本 URL"), { target: { value: "https://cdn.example/voice.wav" } });
        fireEvent.change(screen.getByLabelText("声音音频 Base64"), { target: { value: "UklGRg==" } });
        fireEvent.click(screen.getByRole("button", { name: "提交声音克隆" }));

        await waitFor(() => {
            expect(cloneRoleProfileVoiceMock).toHaveBeenCalledWith("role-1", expect.objectContaining({
                voice_name: "谨慎采购",
            }));
        });
    });
});
