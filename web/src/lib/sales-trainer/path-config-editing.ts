import type {
    BusinessEtiquetteTrainingUnitConfig,
    NewcomerPathConfigPayload,
    NewcomerPathModuleConfig,
} from "@/lib/api/types";

import { defaultBusinessEtiquetteLearningUnits } from "./business-etiquette-units";
import { MODULE_DEFINITIONS } from "./config-center-definitions";
import type { NewcomerConfigModuleKey } from "./config-center-types";

export type AudioEditableModuleKey = "ppt_explanation" | "elevator_pitch";

export interface PathAudioBindingValue {
    readonly materialId: string;
    readonly materialVersionId: string;
    readonly scoringPromptId: string;
}

export interface PathBusinessBindingValue {
    readonly examPaperId: string;
    readonly learningUnits: readonly BusinessEtiquetteTrainingUnitConfig[];
    readonly learningContentId: string;
}

const AUDIO_MODULE_DEFAULTS: Record<AudioEditableModuleKey, {
    readonly completionRule: "scored";
    readonly moduleType: "audio_scoring" | "audio_scoring_group";
    readonly orderIndex: number;
    readonly primaryActionLabel: string;
}> = {
    ppt_explanation: {
        completionRule: "scored",
        moduleType: "audio_scoring",
        orderIndex: 1,
        primaryActionLabel: "上传录音",
    },
    elevator_pitch: {
        completionRule: "scored",
        moduleType: "audio_scoring_group",
        orderIndex: 3,
        primaryActionLabel: "上传演讲录音",
    },
};

export function isAudioEditableModuleKey(
    moduleKey: NewcomerConfigModuleKey,
): moduleKey is AudioEditableModuleKey {
    return moduleKey === "ppt_explanation" || moduleKey === "elevator_pitch";
}

export function audioBindingValueForModule(
    path: NewcomerPathConfigPayload,
    moduleKey: AudioEditableModuleKey,
): PathAudioBindingValue {
    const pathModule = path.modules.find((item) => item.module_key === moduleKey) ?? null;
    return {
        materialId: pathModule?.material_id ?? "",
        materialVersionId: pathModule?.material_version_id ?? "",
        scoringPromptId: pathModule?.scoring_prompt_id ?? "",
    };
}

export function updatePathAudioBinding(
    path: NewcomerPathConfigPayload,
    moduleKey: AudioEditableModuleKey,
    value: PathAudioBindingValue,
): NewcomerPathConfigPayload {
    const nextModule = (pathModule: NewcomerPathModuleConfig): NewcomerPathModuleConfig => ({
        ...pathModule,
        material_id: nullable(value.materialId),
        material_version_id: nullable(value.materialVersionId),
        scoring_prompt_id: nullable(value.scoringPromptId),
    });
    if (path.modules.some((pathModule) => pathModule.module_key === moduleKey)) {
        return {
            ...path,
            modules: path.modules.map((pathModule) => (
                pathModule.module_key === moduleKey ? nextModule(pathModule) : pathModule
            )),
        };
    }
    return {
        ...path,
        modules: [...path.modules, nextModule(defaultAudioModule(moduleKey))],
    };
}

export function businessBindingValueForModule(
    path: NewcomerPathConfigPayload,
): PathBusinessBindingValue {
    const pathModule = path.modules.find((item) => item.module_key === "business_skills") ?? null;
    return {
        examPaperId: pathModule?.exam_paper_id ?? "",
        learningUnits: pathModule?.learning_units?.length
            ? [...pathModule.learning_units]
            : defaultBusinessEtiquetteLearningUnits(),
        learningContentId: pathModule?.learning_content_id ?? "",
    };
}

export function updatePathBusinessBinding(
    path: NewcomerPathConfigPayload,
    value: PathBusinessBindingValue,
): NewcomerPathConfigPayload {
    const nextModule = (pathModule: NewcomerPathModuleConfig): NewcomerPathModuleConfig => ({
        ...pathModule,
        exam_paper_id: nullable(value.examPaperId),
        learning_content_id: nullable(value.learningContentId),
        learning_units: [...value.learningUnits],
    });
    if (path.modules.some((pathModule) => pathModule.module_key === "business_skills")) {
        return {
            ...path,
            modules: path.modules.map((pathModule) => (
                pathModule.module_key === "business_skills" ? nextModule(pathModule) : pathModule
            )),
        };
    }
    return {
        ...path,
        modules: [...path.modules, nextModule(defaultBusinessModule())],
    };
}

function defaultAudioModule(moduleKey: AudioEditableModuleKey): NewcomerPathModuleConfig {
    const definition = MODULE_DEFINITIONS.find((item) => item.moduleKey === moduleKey);
    const defaults = AUDIO_MODULE_DEFAULTS[moduleKey];
    return {
        module_key: moduleKey,
        module_type: defaults.moduleType,
        enabled: true,
        order_index: defaults.orderIndex,
        title: definition?.title ?? moduleKey,
        description: definition?.description ?? null,
        target_unit_id: null,
        learning_content_id: null,
        exam_paper_id: null,
        disabled_reason: null,
        unlock_after_unit_ids: [],
        completion_rule: defaults.completionRule,
        primary_action_label: defaults.primaryActionLabel,
        retry_action_label: null,
        review_action_label: null,
        guidance_templates: {},
        learning_units: defaultBusinessEtiquetteLearningUnits(),
        duration_options: [],
    };
}

function defaultBusinessModule(): NewcomerPathModuleConfig {
    const definition = MODULE_DEFINITIONS.find((item) => item.moduleKey === "business_skills");
    return {
        module_key: "business_skills",
        module_type: "article_exam",
        enabled: true,
        order_index: 2,
        title: definition?.title ?? "商务技巧",
        description: definition?.description ?? null,
        target_unit_id: null,
        learning_content_id: null,
        exam_paper_id: null,
        disabled_reason: null,
        unlock_after_unit_ids: [],
        completion_rule: "passed",
        primary_action_label: "开始学习",
        retry_action_label: null,
        review_action_label: null,
        guidance_templates: {},
    };
}

function nullable(value: string): string | null {
    return value.trim() ? value : null;
}
