import { toCompletionRule } from "@/components/admin/sales-trainer/unit-path-config-section";
import {
    getPathConfig,
    guidanceTemplateText,
    pathConfigModuleType,
    pathConfigNumberText,
    pathConfigString,
} from "@/components/admin/sales-trainer/unit-form-path-model";
import {
    listToText,
    parseOptionalNumber,
    textToGuidanceTemplates,
    textToList,
} from "@/components/admin/sales-trainer/unit-form-utils";
import type {
    SalesTrainerUnitCreateRequest,
    SalesTrainerUnitUpdateRequest,
    SalesTrainerUnit,
    SalesTrainerUnitQuestionBinding,
    SalesTrainerUnitType,
    NewcomerTrainingModuleType,
} from "@/lib/api/types";

export type QuestionSelection = SalesTrainerUnitQuestionBinding;

export interface UnitFormModel {
    readonly audioPurpose: string;
    readonly completionRule: ReturnType<typeof toCompletionRule> | "";
    readonly goalTitle: string;
    readonly guidanceTemplates: string;
    readonly levelDescription: string;
    readonly levelTitle: string;
    readonly materialConfirmationRequired: boolean;
    readonly materialId: string;
    readonly materialLearnerNote: string;
    readonly passThreshold: string;
    readonly pathEnabled: boolean;
    readonly pathKey: string;
    readonly pathModuleKey: string;
    readonly pathModuleType: NewcomerTrainingModuleType | "";
    readonly pathOrderIndex: string;
    readonly pathTitle: string;
    readonly primaryActionLabel: string;
    readonly promptId: string;
    readonly retryActionLabel: string;
    readonly reviewActionLabel: string;
    readonly selectedQuestions: readonly QuestionSelection[];
    readonly taskBriefCommonMistakes: string;
    readonly taskBriefInstructions: string;
    readonly taskBriefPurpose: string;
    readonly taskBriefScenario: string;
    readonly taskBriefSuccessCriteria: string;
    readonly taskBriefTitle: string;
    readonly taskBriefUploadGuidance: string;
    readonly unlockAfterUnitIds: string;
}

interface BuildPayloadInput extends UnitFormModel {
    readonly description: string;
    readonly name: string;
    readonly unitType: SalesTrainerUnitType;
}

export function initialUnitFormModel(unit?: SalesTrainerUnit | null): UnitFormModel {
    const initialPathConfig = getPathConfig(unit);
    const initialTaskBrief = getTaskBrief(unit);
    const initialMaterialBinding = getPrimaryMaterialBinding(unit);
    const completionRuleText = pathConfigString(initialPathConfig, "completion_rule");
    return {
        audioPurpose: getAudioPurpose(unit),
        completionRule: completionRuleText ? toCompletionRule(completionRuleText) : "",
        goalTitle: pathConfigString(initialPathConfig, "goal_title"),
        guidanceTemplates: guidanceTemplateText(initialPathConfig),
        levelDescription: pathConfigString(initialPathConfig, "level_description"),
        levelTitle: pathConfigString(initialPathConfig, "level_title"),
        materialConfirmationRequired: initialMaterialBinding?.confirmation_required !== false,
        materialId: initialMaterialBinding?.material_id ?? "",
        materialLearnerNote: initialMaterialBinding?.learner_note ?? "",
        passThreshold: getPassThreshold(unit),
        pathEnabled: initialPathConfig.enabled === true,
        pathKey: pathConfigString(initialPathConfig, "path_key"),
        pathModuleKey: pathConfigString(initialPathConfig, "module_key"),
        pathModuleType: pathConfigModuleType(initialPathConfig.module_type),
        pathOrderIndex: pathConfigNumberText(initialPathConfig, "order_index"),
        pathTitle: pathConfigString(initialPathConfig, "path_title"),
        primaryActionLabel: pathConfigString(initialPathConfig, "primary_action_label"),
        promptId: getPromptId(unit),
        retryActionLabel: pathConfigString(initialPathConfig, "retry_action_label"),
        reviewActionLabel: pathConfigString(initialPathConfig, "review_action_label"),
    selectedQuestions: unit?.questions.map((question) => ({
            question_id: question.question_id,
            order_index: question.order_index,
            points: question.points,
        })) ?? [],
        taskBriefCommonMistakes: taskBriefListText(initialTaskBrief, "common_mistakes"),
        taskBriefInstructions: taskBriefListText(initialTaskBrief, "instructions"),
        taskBriefPurpose: taskBriefString(initialTaskBrief, "purpose"),
        taskBriefScenario: taskBriefString(initialTaskBrief, "scenario"),
        taskBriefSuccessCriteria: taskBriefListText(initialTaskBrief, "success_criteria"),
        taskBriefTitle: taskBriefString(initialTaskBrief, "title"),
        taskBriefUploadGuidance: taskBriefString(initialTaskBrief, "upload_guidance"),
        unlockAfterUnitIds: listToText(initialPathConfig.unlock_after_unit_ids),
    };
}

export function buildUnitFormPayload(
    input: BuildPayloadInput,
): SalesTrainerUnitCreateRequest | SalesTrainerUnitUpdateRequest {
    const parsedPassThreshold = parseOptionalNumber(input.passThreshold, "音频评分通过线", {
        min: 0,
        max: 100,
    });
    const parsedPathOrderIndex = parseOptionalNumber(input.pathOrderIndex, "关卡顺序", {
        min: 1,
        integer: true,
    });
    const pathConfig = buildPathConfig(input, parsedPathOrderIndex);
    return {
        name: input.name.trim(),
        description: input.description.trim() || null,
        unit_type: input.unitType,
        config: input.unitType === "audio_scoring"
            ? {
                audio: {
                    scoring_prompt_id: input.promptId,
                    purpose: input.audioPurpose.trim(),
                    ...(parsedPassThreshold !== undefined ? { pass_threshold: parsedPassThreshold } : {}),
                },
                ...buildTaskBriefConfig(input),
                ...buildMaterialsConfig(input),
                ...pathConfig,
            }
            : pathConfig,
        questions: input.unitType === "quiz" ? [...input.selectedQuestions] : [],
    };
}

function buildPathConfig(input: BuildPayloadInput, parsedPathOrderIndex: number | undefined) {
    const unlockAfterUnitIdList = textToList(input.unlockAfterUnitIds);
    const customGuidanceTemplates = textToGuidanceTemplates(input.guidanceTemplates);
    return input.pathEnabled
        ? {
            path: {
                enabled: true,
                ...(input.pathKey.trim() ? { path_key: input.pathKey.trim() } : {}),
                ...(input.pathModuleKey.trim() ? { module_key: input.pathModuleKey.trim() } : {}),
                ...(input.pathModuleType ? { module_type: input.pathModuleType } : {}),
                ...(input.pathTitle.trim() ? { path_title: input.pathTitle.trim() } : {}),
                ...(input.goalTitle.trim() ? { goal_title: input.goalTitle.trim() } : {}),
                ...(input.levelTitle.trim() ? { level_title: input.levelTitle.trim() } : {}),
                ...(input.levelDescription.trim() ? { level_description: input.levelDescription.trim() } : {}),
                ...(parsedPathOrderIndex !== undefined ? { order_index: parsedPathOrderIndex } : {}),
                ...(unlockAfterUnitIdList.length ? { unlock_after_unit_ids: unlockAfterUnitIdList } : {}),
                ...(input.completionRule ? { completion_rule: input.completionRule } : {}),
                ...(input.primaryActionLabel.trim() ? { primary_action_label: input.primaryActionLabel.trim() } : {}),
                ...(input.retryActionLabel.trim() ? { retry_action_label: input.retryActionLabel.trim() } : {}),
                ...(input.reviewActionLabel.trim() ? { review_action_label: input.reviewActionLabel.trim() } : {}),
                ...(Object.keys(customGuidanceTemplates).length ? { guidance_templates: customGuidanceTemplates } : {}),
            },
        }
        : {};
}

function buildTaskBriefConfig(input: BuildPayloadInput) {
    return input.unitType === "audio_scoring"
        ? {
            task_brief: {
                enabled: true,
                ...(input.taskBriefTitle.trim() ? { title: input.taskBriefTitle.trim() } : {}),
                ...(input.taskBriefPurpose.trim() ? { purpose: input.taskBriefPurpose.trim() } : {}),
                ...(input.taskBriefScenario.trim() ? { scenario: input.taskBriefScenario.trim() } : {}),
                ...(textToList(input.taskBriefInstructions).length
                    ? { instructions: textToList(input.taskBriefInstructions) }
                    : {}),
                ...(textToList(input.taskBriefSuccessCriteria).length
                    ? { success_criteria: textToList(input.taskBriefSuccessCriteria) }
                    : {}),
                ...(textToList(input.taskBriefCommonMistakes).length
                    ? { common_mistakes: textToList(input.taskBriefCommonMistakes) }
                    : {}),
                ...(input.taskBriefUploadGuidance.trim()
                    ? { upload_guidance: input.taskBriefUploadGuidance.trim() }
                    : {}),
            },
        }
        : {};
}

function buildMaterialsConfig(input: BuildPayloadInput) {
    return input.unitType === "audio_scoring" && input.materialId
        ? {
            materials: {
                require_latest_confirmation: input.materialConfirmationRequired,
                bindings: [
                    {
                        material_id: input.materialId,
                        required: true,
                        confirmation_required: input.materialConfirmationRequired,
                        version_policy: "current_published" as const,
                        display_order: 1,
                        ...(input.materialLearnerNote.trim()
                            ? { learner_note: input.materialLearnerNote.trim() }
                            : {}),
                    },
                ],
            },
        }
        : {};
}

function getPromptId(unit?: SalesTrainerUnit | null): string {
    const rawPromptId = unit?.config?.audio?.scoring_prompt_id;
    return typeof rawPromptId === "string" ? rawPromptId : "";
}

function getPassThreshold(unit?: SalesTrainerUnit | null): string {
    const rawThreshold = unit?.config?.audio?.pass_threshold;
    return typeof rawThreshold === "number" && Number.isFinite(rawThreshold) ? String(rawThreshold) : "";
}

function getAudioPurpose(unit?: SalesTrainerUnit | null): string {
    const rawPurpose = unit?.config?.audio?.purpose;
    return typeof rawPurpose === "string" && rawPurpose.trim() ? rawPurpose : "general_audio_scoring";
}

function getTaskBrief(unit?: SalesTrainerUnit | null): NonNullable<SalesTrainerUnit["config"]["task_brief"]> {
    const config = unit?.config?.task_brief;
    return config && typeof config === "object" && !Array.isArray(config) ? config : {};
}

function taskBriefString(config: NonNullable<SalesTrainerUnit["config"]["task_brief"]>, key: string): string {
    const value = config[key as keyof typeof config];
    return typeof value === "string" ? value : "";
}

function taskBriefListText(
    config: NonNullable<SalesTrainerUnit["config"]["task_brief"]>,
    key: "instructions" | "success_criteria" | "common_mistakes",
): string {
    const value = config[key];
    return Array.isArray(value) ? value.join("\n") : "";
}

function getPrimaryMaterialBinding(unit?: SalesTrainerUnit | null) {
    const bindings = unit?.config?.materials?.bindings;
    return Array.isArray(bindings) ? bindings[0] : undefined;
}
