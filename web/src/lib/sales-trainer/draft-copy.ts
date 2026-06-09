import type {
    NewcomerExamPaper,
    NewcomerExamPaperCreateRequest,
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScorePromptCreateRequest,
    SalesTrainerQuestion,
    SalesTrainerQuestionCreateRequest,
    SalesTrainerUnit,
    SalesTrainerUnitConfig,
    SalesTrainerUnitCreateRequest,
} from "@/lib/api/types";

function copyName(value: string): string {
    return value.endsWith(" (副本)") ? value : `${value} (副本)`;
}

function copyKey(value: string): string {
    const suffix = Date.now().toString(36);
    return `${value}_copy_${suffix}`;
}

function unitDraftConfig(unit: SalesTrainerUnit): SalesTrainerUnitConfig {
    const { path, ...restConfig } = unit.config;
    if (!path) {
        return unit.config;
    }
    const { target_unit_id: _targetUnitId, ...pathWithoutTargetUnit } = path;
    return {
        ...restConfig,
        path: pathWithoutTargetUnit,
    };
}

export function questionDraftCopyPayload(
    question: SalesTrainerQuestion,
): SalesTrainerQuestionCreateRequest {
    return {
        title: copyName(question.title),
        stem: question.stem,
        category_id: question.category_id,
        question_type: question.question_type,
        difficulty: question.difficulty,
        tags: question.tags,
        department: question.department,
        safety_flagged: question.safety_flagged,
        options: question.options,
        correct_answer: question.correct_answer,
        correct_answers: question.correct_answers,
        correct_bool: question.correct_bool,
        reference_answer: question.reference_answer,
        scoring_dimensions: question.scoring_dimensions,
        explanation: question.explanation,
        ai_scoring: question.ai_scoring,
    };
}

export function unitDraftCopyPayload(unit: SalesTrainerUnit): SalesTrainerUnitCreateRequest {
    return {
        name: copyName(unit.name),
        description: unit.description,
        unit_type: unit.unit_type,
        config: unitDraftConfig(unit),
        questions: unit.questions.map((question) => ({
            question_id: question.question_id,
            order_index: question.order_index,
            points: question.points,
        })),
    };
}

export function scorePromptDraftCopyPayload(
    prompt: SalesTrainerAudioScorePrompt,
): SalesTrainerAudioScorePromptCreateRequest {
    return {
        name: copyName(prompt.name),
        purpose: prompt.purpose,
        system_prompt: prompt.system_prompt,
        scoring_template: prompt.scoring_template,
        output_schema: prompt.output_schema,
        learner_rubric: prompt.learner_rubric,
    };
}

export function paperDraftCopyPayload(
    paper: NewcomerExamPaper,
): NewcomerExamPaperCreateRequest {
    return {
        paper_key: copyKey(paper.paper_key),
        title: copyName(paper.title),
        description: paper.description,
        module_key: paper.module_key,
        pass_threshold: paper.pass_threshold,
        questions: paper.questions.map((question) => ({
            question_id: question.question_id,
            order_index: question.order_index,
            points: question.points,
        })),
    };
}
