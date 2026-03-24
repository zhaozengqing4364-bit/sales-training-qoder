import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ScorePanel } from "./ScorePanel";

describe("ScorePanel", () => {
    it("labels the section as sales scoring and keeps fallback dimensions after the five sales dimensions", () => {
        render(
            <ScorePanel
                scores={{
                    overall_score: 84,
                    turn_count: 5,
                    suggestions: ["先用案例佐证 ROI，再处理价格追问"],
                    dimension_scores: {
                        推进下一步: 79,
                        新增维度: 63,
                        证据使用: 76,
                        价值表达: 88,
                        客户收益连接: 82,
                        异议处理: 85,
                    },
                }}
            />,
        );

        expect(screen.getByText("销售维度得分")).toBeTruthy();
        expect(screen.getByText("先用案例佐证 ROI，再处理价格追问")).toBeTruthy();

        const panelText = document.body.textContent ?? "";
        expect(panelText.indexOf("价值表达")).toBeLessThan(panelText.indexOf("客户收益连接"));
        expect(panelText.indexOf("客户收益连接")).toBeLessThan(panelText.indexOf("证据使用"));
        expect(panelText.indexOf("证据使用")).toBeLessThan(panelText.indexOf("异议处理"));
        expect(panelText.indexOf("异议处理")).toBeLessThan(panelText.indexOf("推进下一步"));
        expect(panelText.indexOf("推进下一步")).toBeLessThan(panelText.indexOf("新增维度"));
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
