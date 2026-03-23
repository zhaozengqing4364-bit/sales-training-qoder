import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ScorePanel } from "./ScorePanel";

describe("ScorePanel", () => {
    it("renders the new sales scoring dimensions with sales-first labels", () => {
        render(
            <ScorePanel
                scores={{
                    overall_score: 84,
                    turn_count: 5,
                    stage_name: "异议处理",
                    suggestions: ["先用案例佐证 ROI，再处理价格追问"],
                    dimension_scores: {
                        价值表达: 88,
                        客户收益连接: 82,
                        证据使用: 76,
                        异议处理: 85,
                        推进下一步: 79,
                    },
                }}
            />,
        );

        expect(screen.getByText("价值表达")).toBeTruthy();
        expect(screen.getByText("客户收益连接")).toBeTruthy();
        expect(screen.getByText("证据使用")).toBeTruthy();
        expect(screen.getAllByText("异议处理").length).toBeGreaterThan(0);
        expect(screen.getByText("推进下一步")).toBeTruthy();
        expect(screen.getByText("先用案例佐证 ROI，再处理价格追问")).toBeTruthy();
    });

    it("keeps unknown dimensions visible instead of dropping them", () => {
        render(
            <ScorePanel
                scores={{
                    overall_score: 71,
                    turn_count: 2,
                    suggestions: [],
                    dimension_scores: {
                        新增维度: 63,
                    },
                }}
            />,
        );

        expect(screen.getByText("新增维度")).toBeTruthy();
        expect(screen.getByText("63")).toBeTruthy();
    });

    it("still supports legacy generic payloads as a visible fallback", () => {
        render(
            <ScorePanel
                scores={{
                    overall_score: 78,
                    turn_count: 3,
                    suggestions: [],
                    dimension_scores: {
                        professional: 80,
                        communication: 75,
                        objection: 79,
                    },
                }}
            />,
        );

        expect(screen.getByText("professional")).toBeTruthy();
        expect(screen.getByText("communication")).toBeTruthy();
        expect(screen.getByText("objection")).toBeTruthy();
    });
});
