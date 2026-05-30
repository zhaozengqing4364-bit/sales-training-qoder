import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerQuizPage from "./page";

const { getUnitMock, submitQuizAttemptMock, pushMock } = vi.hoisted(() => ({
    getUnitMock: vi.fn(),
    submitQuizAttemptMock: vi.fn(),
    pushMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => <button type="button" {...props}>{children}</button>,
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, className }: { children: ReactNode; className?: string }) => <div className={className}>{children}</div>,
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ unitId: "unit-1" }),
    useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            salesTrainer: {
                ...actual.api.salesTrainer,
                getUnit: getUnitMock,
                submitQuizAttempt: submitQuizAttemptMock,
            },
        },
    };
});

describe("SalesTrainerQuizPage", () => {
    beforeEach(() => {
        getUnitMock.mockResolvedValue({
            unit_id: "unit-1",
            name: "COO系列之1：陌拜实战测验",
            description: "",
            unit_type: "quiz",
            questions: [
                {
                    question_id: "q1",
                    title: "S.O.S原则",
                    stem: "题干1",
                    question_type: "single_choice",
                    order_index: 1,
                    points: 10,
                    options: [{ label: "A选项", value: "A" }],
                },
                {
                    question_id: "q2",
                    title: "破门技巧",
                    stem: "题干2",
                    question_type: "short_answer",
                    order_index: 2,
                    points: 10,
                },
            ],
        });
        submitQuizAttemptMock.mockResolvedValue({ attempt_id: "attempt-1" });
        pushMock.mockReset();
    });

    it("shows dynamic question count in subtitle", async () => {
        render(<SalesTrainerQuizPage />);

        expect(await screen.findByText("共 2 题，请按顺序完成本次做题训练。")).toBeTruthy();
    });

    it("maps network submit failure to actionable copy", async () => {
        const { ApiRequestError } = await import("@/lib/api/client");
        submitQuizAttemptMock.mockRejectedValue(
            new ApiRequestError({
                status: 0,
                errorCode: "[NETWORK_ERROR]",
                message: "fetch failed",
            }),
        );

        render(<SalesTrainerQuizPage />);
        await screen.findByText("共 2 题，请按顺序完成本次做题训练。");

        fireEvent.click(screen.getByRole("button", { name: "提交答案" }));

        expect(await screen.findByText(/网络连接失败，请检查后端服务或网络设置后重试/)).toBeTruthy();
    });

    it("navigates to result page after successful submit", async () => {
        render(<SalesTrainerQuizPage />);
        await screen.findByText("共 2 题，请按顺序完成本次做题训练。");

        fireEvent.click(screen.getByRole("button", { name: "提交答案" }));

        await waitFor(() => {
            expect(pushMock).toHaveBeenCalledWith("/sales-trainer/quiz/result/attempt-1");
        });
    });
});
