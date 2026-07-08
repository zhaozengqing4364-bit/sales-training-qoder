import type {
    BusinessEtiquetteTrainingUnitConfig,
    NewcomerPathConfigPayload,
    NewcomerPathModuleConfig,
} from "@/lib/api/types";

import { defaultBusinessEtiquetteLearningUnits } from "./business-etiquette-units";
import {
    audioEvaluationScenarioForModule,
    isAudioEvaluationModuleKey,
    type AudioEvaluationModuleKey,
} from "./audio-evaluation-scenarios";
import { MODULE_DEFINITIONS } from "./config-center-definitions";
import type { NewcomerConfigModuleKey } from "./config-center-types";

export type AudioEditableModuleKey = AudioEvaluationModuleKey;

export interface PathAudioBindingValue {
    readonly materialId: string;
    readonly materialVersionId: string;
    readonly scoringPromptId: string;
}

export interface PathAudioScenarioValue extends PathAudioBindingValue {
    readonly targetUnitId: string;
}

export interface PathBusinessBindingValue {
    readonly examPaperId: string;
    readonly learningUnits: readonly BusinessEtiquetteTrainingUnitConfig[];
    readonly learningContentId: string;
}

const READINESS_CAPABILITY_KEYS_BY_MODULE: Record<string, readonly string[]> = {
    ppt_explanation: ["expression_clarity", "structured_presentation", "product_understanding"],
    business_skills: [
        "business_etiquette",
        "customer_perspective",
        "needs_discovery",
        "objection_handling",
    ],
    elevator_pitch: ["expression_clarity", "structured_presentation", "customer_perspective"],
    company_product_demo: ["expression_clarity", "structured_presentation", "product_understanding"],
};

export function isAudioEditableModuleKey(
    moduleKey: NewcomerConfigModuleKey,
): moduleKey is AudioEditableModuleKey {
    return isAudioEvaluationModuleKey(moduleKey);
}

export function audioBindingValueForModule(
    path: NewcomerPathConfigPayload,
    moduleKey: AudioEditableModuleKey,
): PathAudioBindingValue {
    const value = audioScenarioValueForModule(path, moduleKey);
    return {
        materialId: value.materialId,
        materialVersionId: value.materialVersionId,
        scoringPromptId: value.scoringPromptId,
    };
}

export function audioScenarioValueForModule(
    path: NewcomerPathConfigPayload,
    moduleKey: AudioEditableModuleKey,
): PathAudioScenarioValue {
    const pathModule = path.modules.find((item) => item.module_key === moduleKey) ?? null;
    return {
        targetUnitId: pathModule?.target_unit_id ?? "",
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
    const current = audioScenarioValueForModule(path, moduleKey);
    return updatePathAudioScenario(path, moduleKey, {
        ...current,
        materialId: value.materialId,
        materialVersionId: value.materialVersionId,
        scoringPromptId: value.scoringPromptId,
    });
}

export function updatePathAudioScenario(
    path: NewcomerPathConfigPayload,
    moduleKey: AudioEditableModuleKey,
    value: PathAudioScenarioValue,
): NewcomerPathConfigPayload {
    const nextModule = (pathModule: NewcomerPathModuleConfig): NewcomerPathModuleConfig => ({
        ...pathModule,
        target_unit_id: nullable(value.targetUnitId),
        material_id: nullable(value.materialId),
        material_version_id: nullable(value.materialVersionId),
        scoring_prompt_id: nullable(value.scoringPromptId),
    });
    if (path.modules.some((pathModule) => pathModule.module_key === moduleKey)) {
        return {
            ...path,
            modules: path.modules.map((pathModule) =>
                pathModule.module_key === moduleKey ? nextModule(pathModule) : pathModule,
            ),
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
            modules: path.modules.map((pathModule) =>
                pathModule.module_key === "business_skills" ? nextModule(pathModule) : pathModule,
            ),
        };
    }
    return {
        ...path,
        modules: [...path.modules, nextModule(defaultBusinessModule())],
    };
}

function defaultAudioModule(moduleKey: AudioEditableModuleKey): NewcomerPathModuleConfig {
    const definition = MODULE_DEFINITIONS.find((item) => item.moduleKey === moduleKey);
    const scenario = audioEvaluationScenarioForModule(moduleKey);
    return {
        module_key: moduleKey,
        scenario_key: scenario.scenarioKey,
        module_type: scenario.moduleType,
        enabled: true,
        order_index: scenario.orderIndex,
        title: definition?.title ?? moduleKey,
        description: definition?.description ?? null,
        target_unit_id: null,
        learning_content_id: null,
        exam_paper_id: null,
        disabled_reason: null,
        unlock_after_unit_ids: [],
        capability_keys: READINESS_CAPABILITY_KEYS_BY_MODULE[moduleKey] ?? [],
        completion_rule: scenario.completionRule,
        primary_action_label: scenario.primaryActionLabel,
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
        capability_keys: READINESS_CAPABILITY_KEYS_BY_MODULE.business_skills,
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
