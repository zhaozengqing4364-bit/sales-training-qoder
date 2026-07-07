import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { LearnerStudyContent, SalesTrainerUnit, SalesTrainerUnitBrief } from "@/lib/api/types";

import SalesTrainerLearnPage from "./page";

const {
    getContentMock,
    getUnitMock,
    getUnitBriefMock,
    listPathsMock,
    listUnitsMock,
} = vi.hoisted(() => ({
    getContentMock: vi.fn(),
    getUnitMock: vi.fn(),
    getUnitBriefMock: vi.fn(),
    listPathsMock: vi.fn(),
    listUnitsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ unitId: "unit-1" }),
    useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/components/sales-trainer/coo-chapter-reader", () => ({
    CooChapterReader: ({
        chapter,
        pathTitle,
        levelTitle,
        totalChapters,
    }: {
        chapter: { title: string };
        pathTitle: string;
        levelTitle: string;
        totalChapters: number;
    }) => (
        <section>
            <h1>{chapter.title}</h1>
            <p>{pathTitle}</p>
            <p>{levelTitle}</p>
            <p>共 {totalChapters} 章</p>
        </section>
    ),
    CooChapterReaderTerminal: ({ title, message }: { title: string; message: string }) => (
        <section>
            <h1>{title}</h1>
            <p>{message}</p>
        </section>
    ),
}));

vi.mock("@/components/sales-trainer/training-materials-section", () => ({
    TrainingMaterialsSection: ({ materials, title, emptyHint }: {
        materials: Array<{
            material_id: string;
            name: string;
            learner_note: string | null;
            current_version: { version_id: string };
        }>;
        title: string;
        emptyHint: string;
    }) => (
        <div data-testid="training-materials-section">
            <h2>{title}</h2>
            {materials.length === 0 ? (
                <p>{emptyHint}</p>
            ) : (
                <ul>
                    {materials.map((m) => (
                        <li key={m.material_id} data-testid="material-item">
                            {m.name}
                            {m.learner_note ? <p>{m.learner_note}</p> : null}
                            <a href={`/sales-trainer/materials/versions/${m.current_version.version_id}/file`}>
                                下载材料
                            </a>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    ),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>(
        "@/lib/api/client",
    );
    return {
        ...actual,
        api: {
            ...actual.api,
            learnerStudy: {
                ...actual.api.learnerStudy,
                getContent: getContentMock,
            },
            salesTrainer: {
                ...actual.api.salesTrainer,
                getUnit: getUnitMock,
                getUnitBrief: getUnitBriefMock,
                listPaths: listPathsMock,
                listUnits: listUnitsMock,
            },
        },
    };
});

function unit(overrides: Partial<SalesTrainerUnit> = {}): SalesTrainerUnit {
    return {
        unit_id: "unit-1",
        name: "商务礼仪阅读",
        description: "阅读 COO 讲义",
        unit_type: "quiz",
        config: {
            learner: {
                learning_content_id: "content-1",
                chapter_order_index: 2,
            },
        },
        status: "published",
        created_by: "admin",
        updated_by: "admin",
        created_at: "2026-06-01T00:00:00Z",
        updated_at: "2026-06-01T00:00:00Z",
        questions: [],
        ...overrides,
    } as SalesTrainerUnit;
}

function content(): LearnerStudyContent {
    return {
        learning_content_id: "content-1",
        title: "商务礼仪",
        summary: "COO 训练内容",
        owner: "sales_trainer",
        source: "active_path_unit",
        chapters: [
            {
                chapter_id: "chapter-1",
                learning_content_id: "content-1",
                title: "第一章",
                content: "第一章内容",
                order_index: 1,
                created_at: "2026-06-01T00:00:00Z",
                updated_at: "2026-06-01T00:00:00Z",
            },
            {
                chapter_id: "chapter-2",
                learning_content_id: "content-1",
                title: "第二章",
                content: "第二章内容",
                order_index: 2,
                created_at: "2026-06-01T00:00:00Z",
                updated_at: "2026-06-01T00:00:00Z",
            },
        ],
        progress: {
            completed_chapter_ids: [],
            completed_count: 0,
            total_chapters: 2,
            is_completed: false,
            state: "not_started",
            primary_cta: "开始学习",
        },
    } as LearnerStudyContent;
}

function brief(overrides?: { materials?: unknown[] }): SalesTrainerUnitBrief {
    return {
        unit: unit(),
        task_brief: {
            enabled: true,
            title: "任务",
            purpose: "学习",
            scenario: null,
            instructions: [],
            success_criteria: [],
            common_mistakes: [],
            upload_guidance: null,
            submission_context: null,
        },
        materials: overrides?.materials ?? [],
        score_scheme: null,
    } as unknown as SalesTrainerUnitBrief;
}

describe("SalesTrainerLearnPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getUnitMock.mockResolvedValue(unit());
        getContentMock.mockResolvedValue(content());
        getUnitBriefMock.mockResolvedValue(brief());
        listPathsMock.mockRejectedValue(new Error("legacy paths unavailable"));
        listUnitsMock.mockRejectedValue(new Error("legacy units unavailable"));
    });

    it("uses the current unit learner config without legacy paths or units fallback", async () => {
        render(<SalesTrainerLearnPage />);

        expect(await screen.findByText("第二章")).toBeTruthy();
        expect(screen.getByText("新人训练")).toBeTruthy();
        expect(screen.getByText("第 2 章")).toBeTruthy();
        expect(screen.getByText("共 2 章")).toBeTruthy();
        expect(getUnitMock).toHaveBeenCalledWith("unit-1");
        expect(getContentMock).toHaveBeenCalledWith("content-1");
        expect(listPathsMock).not.toHaveBeenCalled();
        expect(listUnitsMock).not.toHaveBeenCalled();
    });

    it("stops before content loading when the unit has no governed learner chapter config", async () => {
        getUnitMock.mockResolvedValue(unit({ config: {} }));

        render(<SalesTrainerLearnPage />);

        expect(await screen.findByText("无法阅读本章")).toBeTruthy();
        expect(screen.getByText("本训练单元未配置章节阅读，请从新人训练路径进入。")).toBeTruthy();
        await waitFor(() => {
            expect(getUnitMock).toHaveBeenCalledWith("unit-1");
        });
        expect(getContentMock).not.toHaveBeenCalled();
        expect(listPathsMock).not.toHaveBeenCalled();
        expect(listUnitsMock).not.toHaveBeenCalled();
    });

    it("renders training materials section with download links from the unit brief", async () => {
        getUnitBriefMock.mockResolvedValue(
            brief({
                materials: [
                    {
                        material_id: "mat-1",
                        material_key: "ppt_deck",
                        name: "产品 PPT 模板",
                        material_type: "ppt_deck",
                        description: null,
                        purpose: "ppt_pitch",
                        required: false,
                        confirmation_required: false,
                        learner_note: "参考此模板完成录音",
                        display_order: 0,
                        current_version: {
                            version_id: "ver-1",
                            material_id: "mat-1",
                            version_label: "v1.0",
                            title: "标准模板",
                            file_name: "ppt.pptx",
                            content_type: "application/vnd.ms-powerpoint",
                            file_size_bytes: 2048,
                            file_hash: null,
                            release_notes: null,
                            status: "published",
                            published_at: "2026-06-01T00:00:00Z",
                        },
                    },
                ],
            }),
        );

        render(<SalesTrainerLearnPage />);

        expect(await screen.findByText("本关训练材料")).toBeTruthy();
        expect(screen.getByText("产品 PPT 模板")).toBeTruthy();
        expect(screen.getByText("参考此模板完成录音")).toBeTruthy();
        const downloadLink = screen.getByRole("link", { name: /下载材料/ });
        expect(downloadLink.getAttribute("href")).toContain("/sales-trainer/materials/versions/ver-1/file");
    });

    it("shows empty hint when the unit brief has no materials", async () => {
        getUnitBriefMock.mockResolvedValue(brief({ materials: [] }));

        render(<SalesTrainerLearnPage />);

        expect(await screen.findByText("本关训练材料")).toBeTruthy();
        expect(screen.getByText("本关暂无训练材料")).toBeTruthy();
        expect(screen.queryByRole("link", { name: /下载材料/ })).toBeNull();
    });
});
