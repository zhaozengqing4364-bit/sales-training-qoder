import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AudioAssessmentActivity } from "@/lib/api/types/newcomer-training";
import { AiCoachEditor } from "./ai-coach-editor";
import { AssignmentEditor } from "./assignment-editor";
import { AudioAssessmentEditor } from "./audio-assessment-editor";
import { LessonEditor } from "./lesson-editor";
import { QuizEditor } from "./quiz-editor";
import { RealtimeRoleplayEditor } from "./realtime-roleplay-editor";

const resources = {
    learning_contents: [{ id: "content-1", title: "产品知识", status: "published" }],
    exam_papers: [{ id: "paper-1", title: "产品小测", status: "published" }],
    scoring_rubrics: [{ id: "rubric-1", title: "讲解评分标准", status: "published" }],
    materials: [{ id: "material-1", title: "产品 PPT", status: "published" }],
    practice_templates: [{ id: "practice-1", title: "客户沟通", status: "published" }],
    runtime_profiles: [{ id: "runtime-1", title: "标准语音", status: "published" }],
    coach_profiles: [{ id: "coach-1", title: "产品教练", status: "published" }],
};

const base = { activity_id: "activity-1", title: "活动", description: null, objective: null, why_it_matters: null, steps: [], success_criteria: [], primary_action_label: null, order_index: 1, required: true, estimated_minutes: 10, prerequisites: [] };

describe("activity editors", () => {
    it("edits audio assessment without exposing prompt IDs or JSON", async () => {
        const onChange = vi.fn();
        const value: AudioAssessmentActivity = { ...base, type: "audio_assessment", config: { scoring_rubric_id: "rubric-1", material_id: "material-1", pass_score: 80, max_attempts: null, example_transcript: null } };
        const { rerender } = render(<AudioAssessmentEditor value={value} resources={resources} onChange={onChange} />);

        expect(screen.getByLabelText("评分标准")).toBeTruthy();
        expect(screen.getByLabelText("通过分")).toBeTruthy();
        expect(screen.getByText("学员会在录音前看到这段文字，请提供一份可模仿的完整讲解。")).toBeTruthy();
        expect(screen.queryByText(/prompt_id|raw JSON|runtime_binding/i)).toBeNull();
        fireEvent.change(screen.getByLabelText("优秀讲解示例（文字版）"), {
            target: { value: "先说客户问题，再讲产品价值。  " },
        });
        expect(onChange).toHaveBeenLastCalledWith({
            ...value,
            config: {
                ...value.config,
                example_transcript: "先说客户问题，再讲产品价值。  ",
            },
        });
        const configuredValue: AudioAssessmentActivity = {
            ...value,
            config: { ...value.config, example_transcript: "先说客户问题，再讲产品价值。  " },
        };
        rerender(<AudioAssessmentEditor value={configuredValue} resources={resources} onChange={onChange} />);
        onChange.mockClear();
        fireEvent.change(screen.getByLabelText("优秀讲解示例（文字版）"), {
            target: { value: "" },
        });
        expect(onChange).toHaveBeenLastCalledWith({
            ...value,
            config: { ...value.config, example_transcript: null },
        });
    });

    it("renders business fields for all six activity types", () => {
        const onChange = vi.fn();
        const common = { resources, onChange };
        const { unmount } = render(<LessonEditor {...common} value={{ ...base, type: "lesson", config: { learning_content_id: "content-1", completion_mode: "all_chapters" } }} />);
        expect(screen.getByLabelText("学习内容")).toBeTruthy(); unmount();
        const quiz = render(<QuizEditor {...common} value={{ ...base, type: "quiz", config: { exam_paper_id: "paper-1", pass_score: 80, max_attempts: null } }} />);
        expect(screen.getByLabelText("试卷")).toBeTruthy(); quiz.unmount();
        const realtime = render(<RealtimeRoleplayEditor {...common} value={{ ...base, type: "realtime_roleplay", config: { practice_template_id: "practice-1", runtime_profile_id: "runtime-1", completion_mode: "session_completed" } }} />);
        expect(screen.getByLabelText("对练模板")).toBeTruthy(); realtime.unmount();
        const coach = render(<AiCoachEditor {...common} value={{ ...base, type: "ai_coach", config: { coach_profile_id: "coach-1", completion_mode: "session_completed" } }} />);
        expect(screen.getByLabelText("教练方案")).toBeTruthy(); coach.unmount();
        render(<AssignmentEditor {...common} value={{ ...base, type: "assignment", config: { submission_type: "text_or_file", review_mode: "manual_review", max_file_size_bytes: 10_485_760 } }} />);
        expect(screen.getByLabelText("提交形式")).toBeTruthy();
    });
});
