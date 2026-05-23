import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CurriculumConfigChecklist } from "./curriculum-config-checklist";

const {
    getKnowledgeBasesMock,
    getPersonasMock,
    getAgentsMock,
    getVoiceRuntimeProfilesMock,
    listScoringRulesetsMock,
    listCaseItemsMock,
    listRoleProfilesMock,
    learningContentsListMock,
    listQuestionsMock,
    listPracticeTemplatesMock,
    getKnowledgeAnswerAdminConfigMock,
} = vi.hoisted(() => ({
    getKnowledgeBasesMock: vi.fn(),
    getPersonasMock: vi.fn(),
    getAgentsMock: vi.fn(),
    getVoiceRuntimeProfilesMock: vi.fn(),
    listScoringRulesetsMock: vi.fn(),
    listCaseItemsMock: vi.fn(),
    listRoleProfilesMock: vi.fn(),
    learningContentsListMock: vi.fn(),
    listQuestionsMock: vi.fn(),
    listPracticeTemplatesMock: vi.fn(),
    getKnowledgeAnswerAdminConfigMock: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
    api: {
        admin: {
            getKnowledgeBases: getKnowledgeBasesMock,
            getPersonas: getPersonasMock,
            getAgents: getAgentsMock,
            getVoiceRuntimeProfiles: getVoiceRuntimeProfilesMock,
            listScoringRulesets: listScoringRulesetsMock,
            listCaseItems: listCaseItemsMock,
            listRoleProfiles: listRoleProfilesMock,
            listPracticeTemplates: listPracticeTemplatesMock,
            getKnowledgeAnswerAdminConfig: getKnowledgeAnswerAdminConfigMock,
        },
        learningContents: {
            list: learningContentsListMock,
        },
        testBank: {
            listQuestions: listQuestionsMock,
        },
    },
    getApiErrorMessage: (error: unknown) => String(error),
}));

describe("CurriculumConfigChecklist", () => {
    beforeEach(() => {
        getKnowledgeBasesMock.mockResolvedValue({
            items: [{ id: "kb-1", document_count: 2 }],
            total: 1,
        });
        getPersonasMock.mockResolvedValue({ items: [{ id: "p-1", status: "active" }], total: 1 });
        getAgentsMock.mockResolvedValue({ items: [{ id: "a-1", status: "published" }], total: 1 });
        getVoiceRuntimeProfilesMock.mockResolvedValue({
            items: [{ id: "vr-1", is_active: true }],
            total: 1,
        });
        listScoringRulesetsMock.mockResolvedValue({
            items: [{ id: "s-1", status: "published" }],
            total: 1,
        });
        listCaseItemsMock.mockResolvedValue({ items: [{ case_item_id: "case-1" }], total: 1 });
        listRoleProfilesMock.mockResolvedValue({ items: [{ role_profile_id: "role-1" }], total: 1 });
        learningContentsListMock.mockResolvedValue({ items: [{ id: "lc-1" }], total: 1 });
        listQuestionsMock.mockResolvedValue({ items: [{ id: "q-1" }], total: 1 });
        listPracticeTemplatesMock.mockResolvedValue({
            items: [{ template_id: "tpl-1", status: "published" }],
            total: 1,
        });
        getKnowledgeAnswerAdminConfigMock.mockResolvedValue({
            active_version: { id: "cfg-1", version_name: "v1" },
        });
    });

    it("renders nine steps and marks all done when assets exist", async () => {
        render(<CurriculumConfigChecklist />);

        expect(await screen.findByText("课程闭环配置清单")).toBeTruthy();
        expect(screen.getByText(/完成 9\/9 步/)).toBeTruthy();
        expect(screen.getByText("步骤 1")).toBeTruthy();
        expect(screen.getByText("学员路径试跑")).toBeTruthy();

        await waitFor(() => {
            expect(getKnowledgeBasesMock).toHaveBeenCalled();
            expect(listQuestionsMock).toHaveBeenCalled();
        });
    });

    it("shows pending progress when retrieval is not active", async () => {
        getKnowledgeAnswerAdminConfigMock.mockResolvedValue({ active_version: null });
        getKnowledgeBasesMock.mockResolvedValue({
            items: [{ id: "kb-1", document_count: 0 }],
            total: 1,
        });
        getPersonasMock.mockResolvedValue({ items: [], total: 0 });

        render(<CurriculumConfigChecklist />);

        await waitFor(() => {
            expect(screen.getByText(/完成 0\/9 步/)).toBeTruthy();
        });
    });
});
