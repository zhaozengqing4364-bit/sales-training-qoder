import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CooChapterReader } from "./coo-chapter-reader";

const { completeChapterMock, pushMock } = vi.hoisted(() => ({
    completeChapterMock: vi.fn(),
    pushMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: pushMock }),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, onClick, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" onClick={onClick} {...props}>{children}</button>
    ),
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ui/badge", () => ({
    Badge: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            learnerStudy: {
                ...actual.api.learnerStudy,
                completeChapter: completeChapterMock,
            },
        },
    };
});

const baseProps = {
    contentId: "lc-coo",
    contentTitle: "COO 销售讲义",
    contentSummary: "摘要",
    chapter: {
        chapter_id: "chapter-1",
        learning_content_id: "lc-coo",
        title: "开场技巧",
        content: "## 要点\n\n- **确认背景**",
        order_index: 1,
        created_at: "2026-05-28T00:00:00Z",
        updated_at: "2026-05-28T00:00:00Z",
    },
    progress: {
        completed_chapter_ids: [],
        completed_count: 0,
        total_chapters: 15,
        is_completed: false,
        state: "not_started" as const,
        primary_cta: "开始学习",
    },
    pathTitle: "新人闯关",
    levelTitle: "第一关",
    chapterIndex: 1,
    totalChapters: 15,
    unitId: "quiz-unit-1",
    returnTo: "/sales-trainer",
    prevUnitId: null,
    nextUnitId: "quiz-unit-2",
    onProgressUpdated: vi.fn(),
};

describe("CooChapterReader", () => {
    beforeEach(() => {
        completeChapterMock.mockReset();
        pushMock.mockReset();
        sessionStorage.clear();
    });

    it("renders markdown headings instead of raw markers", () => {
        render(<CooChapterReader {...baseProps} />);
        expect(screen.getByRole("heading", { name: "要点" })).toBeTruthy();
        expect(screen.queryByText("## 要点")).toBeNull();
        expect(screen.getByText("确认背景")).toBeTruthy();
    });

    it("navigates back to return path and links quiz CTA", () => {
        render(<CooChapterReader {...baseProps} />);
        expect(screen.getByRole("link", { name: /开始本章测验/ }).getAttribute("href")).toBe(
            "/sales-trainer/quiz/quiz-unit-1",
        );
        expect(screen.getByRole("link", { name: /下一章/ }).getAttribute("href")).toContain(
            "/sales-trainer/learn/quiz-unit-2",
        );
        fireEvent.click(screen.getAllByRole("button", { name: /返回/ })[0]);
        expect(pushMock).toHaveBeenCalledWith("/sales-trainer");
    });

    it("marks chapter complete via learnerStudy API", async () => {
        completeChapterMock.mockResolvedValue({
            chapter_id: "chapter-1",
            already_completed: false,
            progress: {
                ...baseProps.progress,
                completed_chapter_ids: ["chapter-1"],
                completed_count: 1,
            },
        });
        const onProgressUpdated = vi.fn();
        render(<CooChapterReader {...baseProps} onProgressUpdated={onProgressUpdated} />);

        fireEvent.click(screen.getByRole("button", { name: /标记本章已读/ }));

        await waitFor(() => {
            expect(completeChapterMock).toHaveBeenCalledWith("lc-coo", "chapter-1");
        });
        expect(onProgressUpdated).toHaveBeenCalled();
    });
});
