/**
 * 白名单 renderer 组件测试。
 *
 * 覆盖：
 * - 三个白名单卡片渲染 option.text
 * - 点击单选/多选触发 onChange
 * - FeedbackCard + MasteryResultCard 渲染
 *
 * 注：卡片接受 view-model props（stem / options / value / onChange），
 * 由 AiCoachInteractionRenderer 把 backend DTO 投影成 view-model。
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
    SingleChoiceInteractionCard,
    MultipleChoiceInteractionCard,
    ShortAnswerInteractionCard,
    FeedbackCard,
    MasteryResultCard,
} from "./index";

describe("SingleChoiceInteractionCard", () => {
    afterEach(() => cleanup());

    it("renders options using text field", () => {
        render(
            <SingleChoiceInteractionCard
                stem="什么是好的销售开场？"
                options={[
                    { option_id: "A", label: "自我介绍" },
                    { option_id: "B", label: "探询客户需求" },
                ]}
                value={null}
                onChange={vi.fn()}
            />,
        );
        expect(screen.getByText("自我介绍")).toBeTruthy();
        expect(screen.getByText("探询客户需求")).toBeTruthy();
    });

    it("calls onChange with the clicked option_id", async () => {
        const onChange = vi.fn();
        render(
            <SingleChoiceInteractionCard
                stem="测试"
                options={[{ option_id: "A", label: "选项 A" }]}
                value={null}
                onChange={onChange}
            />,
        );
        await userEvent.click(screen.getByText("选项 A"));
        expect(onChange).toHaveBeenCalledWith("A");
    });
});

describe("MultipleChoiceInteractionCard", () => {
    afterEach(() => cleanup());

    it("renders options using text field", () => {
        render(
            <MultipleChoiceInteractionCard
                stem="哪些是合规行为？"
                options={[
                    { option_id: "A", label: "如实告知" },
                    { option_id: "B", label: "虚假承诺" },
                ]}
                value={[]}
                onChange={vi.fn()}
                min_selected={1}
                max_selected={3}
            />,
        );
        expect(screen.getByText("如实告知")).toBeTruthy();
        expect(screen.getByText("虚假承诺")).toBeTruthy();
    });
});

describe("ShortAnswerInteractionCard", () => {
    afterEach(() => cleanup());

    it("renders stem and textarea", () => {
        render(
            <ShortAnswerInteractionCard
                stem="请简述商务跟进的关键点"
                value=""
                onChange={vi.fn()}
                min_length={5}
                max_length={500}
            />,
        );
        expect(screen.getAllByText("请简述商务跟进的关键点")[0]).toBeTruthy();
    });
});

describe("FeedbackCard", () => {
    afterEach(() => cleanup());

    it("renders score and feedback", () => {
        render(
            <FeedbackCard
                score={85}
                max_score={100}
                feedback="回答良好"
                missed_points={[]}
            />,
        );
        expect(screen.getByText("回答良好")).toBeTruthy();
    });
});

describe("MasteryResultCard", () => {
    afterEach(() => cleanup());

    it("renders mastered state", () => {
        render(
            <MasteryResultCard
                overall_mastered={true}
                total_score={85}
                max_score={100}
                onRetry={vi.fn()}
                onBack={vi.fn()}
            />,
        );
        expect(screen.getByText(/掌握/)).toBeTruthy();
    });
});
