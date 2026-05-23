import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import RetrievalStrategiesPage from "./page";

vi.mock("@/components/admin/knowledge-answer/knowledge-answer-console", () => ({
    KnowledgeAnswerConsole: () => <div data-testid="knowledge-answer-console" />,
}));

describe("RetrievalStrategiesPage", () => {
    it("shows global scope banner before the console", () => {
        render(<RetrievalStrategiesPage />);

        expect(screen.getByText("影响范围：全部知识库")).toBeTruthy();
        expect(screen.getByText(/激活后对所有知识库生效/)).toBeTruthy();
        expect(screen.getByTestId("knowledge-answer-console")).toBeTruthy();
    });
});
