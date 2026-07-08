import type {
    NewcomerPathModuleConfig,
    SalesTrainerUnit,
} from "@/lib/api/types";

import type {
    NewcomerConfigCenterInput,
    NewcomerConfigIssue,
} from "./config-center-types";
import {
    audioEvaluationScenarioForModule,
    type AudioEvaluationModuleKey,
} from "./audio-evaluation-scenarios";

interface AudioBindingRefs {
    readonly materialId: string | null;
    readonly materialVersionId: string | null;
    readonly scoringPromptId: string | null;
}

export function appendAudioIssues(
    moduleKey: AudioEvaluationModuleKey,
    issues: NewcomerConfigIssue[],
    units: readonly SalesTrainerUnit[],
    input: NewcomerConfigCenterInput,
    pathModule: NewcomerPathModuleConfig | null,
): void {
    const scenario = audioEvaluationScenarioForModule(moduleKey);
    const refs = audioBindingRefs(pathModule, units);
    const promptOk = Boolean(
        refs.scoringPromptId
        && input.scorePrompts.some((prompt) => (
            prompt.prompt_id === refs.scoringPromptId && prompt.status === "published"
        )),
    );
    const materialOk = Boolean(
        refs.materialId
        && input.materials.some((material) => (
            material.material_id === refs.materialId
            && material.status === "published"
            && material.current_version_id
            && (!refs.materialVersionId || material.current_version_id === refs.materialVersionId)
        )),
    );
    if (!promptOk) {
        issues.push({
            code: "score_prompt_missing",
            message: "缺少已发布录音评分标准。",
            href: `/admin/sales-trainer/training-tasks/${scenario.slug}`,
        });
    }
    if (scenario.materialRequired && !materialOk) {
        issues.push({
            code: "material_missing",
            message: "缺少已发布材料或当前版本。",
            href: `/admin/sales-trainer/training-tasks/${scenario.slug}`,
        });
    }
}

export function audioBindings(
    units: readonly SalesTrainerUnit[],
    input: NewcomerConfigCenterInput,
    pathModule: NewcomerPathModuleConfig | null,
): string[] {
    const refs = audioBindingRefs(pathModule, units);
    const prompt = input.scorePrompts.find((item) => item.prompt_id === refs.scoringPromptId);
    const material = input.materials.find((item) => item.material_id === refs.materialId);
    return [
        prompt ? `评分标准：${prompt.name} v${prompt.version}` : "评分标准：未绑定",
        material ? `材料：${material.name}（${material.current_version?.version_label ?? "无当前版本"}）` : "材料：未绑定",
    ];
}

function audioBindingRefs(
    pathModule: NewcomerPathModuleConfig | null,
    units: readonly SalesTrainerUnit[],
): AudioBindingRefs {
    const legacy = legacyAudioBindingRefs(units);
    return {
        materialId: pathModule?.material_id ?? legacy.materialId,
        materialVersionId: pathModule?.material_version_id ?? legacy.materialVersionId,
        scoringPromptId: pathModule?.scoring_prompt_id ?? legacy.scoringPromptId,
    };
}

function legacyAudioBindingRefs(units: readonly SalesTrainerUnit[]): AudioBindingRefs {
    const firstUnit = units[0];
    const binding = firstUnit?.config.materials?.bindings?.[0] ?? null;
    return {
        materialId: binding?.material_id ?? null,
        materialVersionId: binding?.locked_version_id ?? null,
        scoringPromptId: firstUnit?.config.audio?.scoring_prompt_id ?? null,
    };
}
