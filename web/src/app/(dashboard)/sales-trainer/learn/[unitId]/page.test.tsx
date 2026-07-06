import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { LearnerStudyContent, SalesTrainerUnit } from "@/lib/api/types";

import SalesTrainerLearnPage from "./page";

const {
    getContentMock,
    getUnitMock,
    listPathsMock,
    listUnitsMock,
} = vi.hoisted(() => ({
    getContentMock: vi.fn(),
    getUnitMock: vi.fn(),
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

describe("SalesTrainerLearnPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getUnitMock.mockResolvedValue(unit());
        getContentMock.mockResolvedValue(content());
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
});
