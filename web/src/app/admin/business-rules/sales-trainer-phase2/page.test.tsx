import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import SalesTrainerPhase2BusinessRulePage from "./page";

vi.mock("../_components/governed-business-rule-page", () => ({
    GovernedBusinessRulePage: ({
        configKey,
        title,
        description,
    }: {
        configKey: string;
        title: string;
        description: string;
    }) => (
        <section>
            <h1>{title}</h1>
            <p>{description}</p>
            <code>{configKey}</code>
        </section>
    ),
}));

describe("SalesTrainerPhase2BusinessRulePage", () => {
    it("opens the governed phase 2 closed-loop policy", () => {
        render(<SalesTrainerPhase2BusinessRulePage />);

        expect(screen.getByText("销售训练阶段 2 闭环策略")).toBeTruthy();
        expect(screen.getByText("sales_trainer.phase2.closed_loop_policy")).toBeTruthy();
        expect(screen.getByText(/主管干预动作和补救入口/)).toBeTruthy();
    });
});
