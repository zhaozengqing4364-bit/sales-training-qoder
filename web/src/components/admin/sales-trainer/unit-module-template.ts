import type {
    SalesTrainerAudioScorePrompt,
    SalesTrainerMaterial,
    SalesTrainerUnit,
} from "@/lib/api/types";
import { NEWCOMER_TRAINING_PATH_KEY } from "@/lib/sales-trainer/module-path";
import {
    AUDIO_EVALUATION_SCENARIOS,
    type AudioEvaluationModuleKey,
} from "@/lib/sales-trainer/audio-evaluation-scenarios";

type TemplateContext = {
    readonly materials: readonly SalesTrainerMaterial[];
    readonly moduleKey: string | null;
    readonly prompts: readonly SalesTrainerAudioScorePrompt[];
};

type AudioModuleTemplate = {
    readonly audioPurpose: string;
    readonly description: string;
    readonly levelDescription: string;
    readonly levelTitle: string;
    readonly materialRequired: boolean;
    readonly moduleKey: AudioEvaluationModuleKey;
    readonly moduleType: "audio_scoring" | "audio_scoring_group";
    readonly name: string;
    readonly orderIndex: number;
    readonly primaryActionLabel: string;
    readonly taskBriefPurpose: string;
    readonly taskBriefScenario: string;
    readonly taskBriefTitle: string;
};

const AUDIO_MODULE_TEMPLATES = AUDIO_EVALUATION_SCENARIOS.map((scenario) => ({
    audioPurpose: scenario.purposeKey,
    description: scenario.description,
    levelDescription: scenario.learnerPreview,
    levelTitle: `${scenario.orderLabel}：${scenario.title}`,
    materialRequired: scenario.materialRequired,
    moduleKey: scenario.moduleKey,
    moduleType: scenario.moduleType,
    name: `${scenario.orderLabel}：${scenario.title}`,
    orderIndex: scenario.orderIndex,
    primaryActionLabel: scenario.primaryActionLabel,
    taskBriefPurpose: scenario.taskBriefPurpose,
    taskBriefScenario: scenario.taskBriefScenario,
    taskBriefTitle: scenario.taskBriefTitle,
})) satisfies readonly AudioModuleTemplate[];

export function buildUnitTemplateForModule({
    materials,
    moduleKey,
    prompts,
}: TemplateContext): SalesTrainerUnit | null {
    const template = templateForModule(moduleKey);
    if (!template) {
        return null;
    }
    const promptId =
        prompts.find(
            (prompt) => prompt.status === "published" && prompt.purpose === template.audioPurpose,
        )?.prompt_id ?? "";
    const materialId =
        materials.find(
            (material) =>
                material.status === "published" &&
                material.purpose === template.audioPurpose &&
                Boolean(material.current_version_id),
        )?.material_id ?? "";
    return {
        unit_id: "",
        name: template.name,
        description: template.description,
        unit_type: "audio_scoring",
        config: {
            audio: {
                scoring_prompt_id: promptId,
                purpose: template.audioPurpose,
                scenario_key: template.moduleKey,
            },
            task_brief: {
                enabled: true,
                title: template.taskBriefTitle,
                purpose: template.taskBriefPurpose,
                scenario: template.taskBriefScenario,
            },
            ...(materialId && template.materialRequired
                ? {
                      materials: {
                          require_latest_confirmation: true,
                          bindings: [
                              {
                                  material_id: materialId,
                                  required: true,
                                  confirmation_required: true,
                                  version_policy: "current_published",
                                  display_order: 1,
                              },
                          ],
                      },
                  }
                : {}),
            path: {
                enabled: true,
                path_key: NEWCOMER_TRAINING_PATH_KEY,
                module_key: template.moduleKey,
                scenario_key: template.moduleKey,
                module_type: template.moduleType,
                path_title: "新人训练路径",
                level_title: template.levelTitle,
                level_description: template.levelDescription,
                order_index: template.orderIndex,
                completion_rule: "scored",
                primary_action_label: template.primaryActionLabel,
                retry_action_label: "重新上传",
                review_action_label: "查看评分结果",
            },
        },
        status: "draft",
        created_by: null,
        updated_by: null,
        created_at: "",
        updated_at: "",
        questions: [],
    };
}

function templateForModule(moduleKey: string | null): AudioModuleTemplate | null {
    return AUDIO_MODULE_TEMPLATES.find((template) => template.moduleKey === moduleKey) ?? null;
}
