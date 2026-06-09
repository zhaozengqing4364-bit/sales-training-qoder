import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BusinessSkillsPage from "./page";
import { ApiRequestError } from "@/lib/api/client";

const { getArticleMock, listUnitsMock, useSearchParamsMock } = vi.hoisted(() => ({
    getArticleMock: vi.fn(),
    listUnitsMock: vi.fn(),
    useSearchParamsMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("next/navigation", () => ({
    useSearchParams: () => useSearchParamsMock(),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => <button type="button" {...props}>{children}</button>,
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            salesTrainer: {
                ...actual.api.salesTrainer,
                listUnits: listUnitsMock,
            },
            newcomerTraining: {
                ...actual.api.newcomerTraining,
                getModuleArticle: getArticleMock,
            },
        },
    };
});

describe("BusinessSkillsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        window.localStorage.clear();
        useSearchParamsMock.mockReturnValue(new URLSearchParams("unitId=business-unit"));
        listUnitsMock.mockResolvedValue({
            items: [{
                unit_id: "business-unit",
                config: {
                    path: {
                        learning_content_id: "article-1",
                        exam_paper_id: "paper-1",
                    },
                },
            }],
            total: 1,
        });
        getArticleMock.mockResolvedValue({
            module_key: "business_skills",
            learning_content_id: "article-1",
            title: "见客户前商务礼仪",
            summary: "summary",
            owner: "新人训练路径",
            source: null,
            chapters: [
                {
                    chapter_id: "chapter-1",
                    title: "准备动作",
                    content: "![商务礼仪图](https://example.com/business.png)\n\n拜访前确认客户背景。",
                    order_index: 1,
                },
                {
                    chapter_id: "chapter-2",
                    title: "到场礼仪",
                    content: "提前到场并确认会议材料。",
                    order_index: 2,
                },
            ],
        });
    });

    it("requires reading all configurable chapters before linking to the exam page", async () => {
        render(<BusinessSkillsPage />);

        expect(await screen.findByRole("heading", { name: "商务技巧学习" })).toBeTruthy();
        expect(screen.getByText("见客户前商务礼仪")).toBeTruthy();
        expect(screen.getByRole("button", { name: /第一节 准备动作/ })).toBeTruthy();
        expect(screen.getByRole("button", { name: /第二节 到场礼仪/ })).toBeTruthy();
        expect(screen.getByText("拜访前确认客户背景。")).toBeTruthy();
        expect(screen.getByRole("img", { name: "商务礼仪图" }).getAttribute("src")).toBe(
            "https://example.com/business.png",
        );
        expect(screen.queryByRole("link", { name: /进入考试/ })).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "完成本节" }));
        fireEvent.click(screen.getByRole("button", { name: /第二节 到场礼仪/ }));
        expect(screen.getByText("提前到场并确认会议材料。")).toBeTruthy();
        expect(screen.queryByRole("link", { name: /进入考试/ })).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "完成本节" }));
        expect(screen.getByRole("link", { name: /进入考试/ }).getAttribute("href")).toBe(
            "/sales-trainer/business-skills/exam?unitId=business-unit",
        );
        await waitFor(() => {
            expect(getArticleMock).toHaveBeenCalledWith("business_skills", {
                learning_content_id: "article-1",
            });
        });
    });

    it("ignores stale completed chapter ids from an older article version", async () => {
        window.localStorage.setItem(
            "newcomer-business-skills:article-1:completed-chapters",
            JSON.stringify(["old-chapter-1", "old-chapter-2"]),
        );

        render(<BusinessSkillsPage />);

        expect(await screen.findByText("见客户前商务礼仪")).toBeTruthy();
        expect(screen.getByText((_, element) => element?.textContent === "0/2 已完成")).toBeTruthy();
        expect(screen.getByText("完成全部章节后开放考试入口。")).toBeTruthy();
        expect(screen.queryByRole("link", { name: /进入考试/ })).toBeNull();
    });

    it("falls back to module article binding when selected unit has no article binding", async () => {
        listUnitsMock.mockResolvedValueOnce({
            items: [{
                unit_id: "business-unit",
                config: { path: { exam_paper_id: "paper-1" } },
            }],
            total: 1,
        });

        render(<BusinessSkillsPage />);

        expect(await screen.findByText("见客户前商务礼仪")).toBeTruthy();
        expect(getArticleMock).toHaveBeenCalledWith("business_skills", undefined);
    });

    it("shows an actionable remediation message when the article binding is missing", async () => {
        getArticleMock.mockRejectedValueOnce(new ApiRequestError({
            status: 404,
            errorCode: "[NEWCOMER_MODULE_BINDING_MISSING]",
            message: "article not bound",
        }));

        render(<BusinessSkillsPage />);

        expect(await screen.findByText(/商务技巧学习内容暂不可用/)).toBeTruthy();
        expect(screen.getByText(/新人训练路径配置中心 → 商务技巧 → 学习文章/)).toBeTruthy();
        expect(screen.queryByRole("link", { name: /进入考试/ })).toBeNull();
    });

    it("shows an actionable remediation message when the article has no chapters", async () => {
        getArticleMock.mockRejectedValueOnce(new ApiRequestError({
            status: 409,
            errorCode: "[LEARNING_CONTENT_CHAPTERS_MISSING]",
            message: "empty chapters",
        }));

        render(<BusinessSkillsPage />);

        expect(await screen.findByText(/商务技巧学习内容暂不可用/)).toBeTruthy();
        expect(screen.getByText(/商务技巧文章还没有学习章节/)).toBeTruthy();
        expect(screen.queryByRole("link", { name: /进入考试/ })).toBeNull();
    });
});
