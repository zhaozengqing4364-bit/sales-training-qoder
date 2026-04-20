import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TrainingCategoriesPage from "./page";

const getCategoriesMock = vi.hoisted(() => vi.fn());

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, className }: { children: ReactNode; className?: string }) => <div className={className}>{children}</div>,
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
            training: {
                ...actual.api.training,
                getCategories: getCategoriesMock,
            },
        },
    };
});

describe("TrainingCategoriesPage", () => {
    beforeEach(() => {
        getCategoriesMock.mockReset();
    });

    it("distinguishes backend failure from a genuinely empty category response", async () => {
        getCategoriesMock
            .mockRejectedValueOnce(new Error("training unavailable"))
            .mockResolvedValueOnce([
                {
                    id: "sales",
                    title: "后端恢复的销售训练",
                    description: "恢复后从后端返回的训练入口。",
                    icon_key: "Mic",
                    color_theme: "bg-blue-50 text-blue-600",
                    agent_count: 1,
                    tags: ["恢复"],
                    status: "active",
                },
            ]);

        render(<TrainingCategoriesPage />);

        expect(await screen.findByText("训练分类暂不可用，当前展示的是本地兜底入口，不代表后端没有训练模式。")).toBeTruthy();
        expect(screen.getByText("销售能力训练")).toBeTruthy();
        expect(screen.getByRole("button", { name: "重试训练分类" })).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: "重试训练分类" }));

        expect(await screen.findByText("后端恢复的销售训练")).toBeTruthy();
        expect(screen.queryByText(/训练分类暂不可用/)).toBeNull();
    });

    it("uses fallback categories for empty success without showing degraded copy", async () => {
        getCategoriesMock.mockResolvedValueOnce([]);

        render(<TrainingCategoriesPage />);

        expect(await screen.findByText("销售能力训练")).toBeTruthy();
        expect(screen.queryByText(/训练分类暂不可用/)).toBeNull();
    });
});
