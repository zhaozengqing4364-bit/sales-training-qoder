import type {
    SalesTrainerAudioScorePrompt,
    SalesTrainerMaterial,
    SalesTrainerUnit,
} from "@/lib/api/types";
import { NEWCOMER_TRAINING_PATH_KEY } from "@/lib/sales-trainer/module-path";

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
    readonly moduleKey: "ppt_explanation" | "elevator_pitch";
    readonly moduleType: "audio_scoring" | "audio_scoring_group";
    readonly name: string;
    readonly orderIndex: number;
    readonly primaryActionLabel: string;
    readonly taskBriefPurpose: string;
    readonly taskBriefScenario: string;
    readonly taskBriefTitle: string;
};

const PPT_EXPLANATION_TEMPLATE: AudioModuleTemplate = {
    audioPurpose: "ppt_pitch",
    description: "学习并讲解当前 PPT 材料，上传录音后由 AI 转写和评分。",
    levelDescription: "确认最新 PPT 材料后完成讲解录音。",
    levelTitle: "第一关：PPT 讲解录音",
    moduleKey: "ppt_explanation",
    moduleType: "audio_scoring",
    name: "第一关：PPT 讲解录音",
    orderIndex: 1,
    primaryActionLabel: "上传讲解录音",
    taskBriefPurpose: "让新人先掌握公司介绍、产品价值和客户沟通结构。",
    taskBriefScenario: "面向首次见客户前的内部演练，按最新 PPT 材料完成讲解。",
    taskBriefTitle: "PPT 讲解录音",
};

const ELEVATOR_PITCH_TEMPLATE: AudioModuleTemplate = {
    audioPurpose: "elevator_pitch",
    description: "配置金字塔演讲录音任务，学员按后台材料与时长要求上传演讲录音。",
    levelDescription: "按配置的金字塔演讲材料和时长要求完成录音。",
    levelTitle: "第三关：金字塔演讲",
    moduleKey: "elevator_pitch",
    moduleType: "audio_scoring_group",
    name: "第三关：金字塔演讲",
    orderIndex: 3,
    primaryActionLabel: "上传金字塔演讲录音",
    taskBriefPurpose: "训练新人用短时间讲清公司、产品价值和下一步邀约。",
    taskBriefScenario: "客户给你一段有限时间介绍机会，需要按金字塔结构完成清晰、有重点的价值说明。",
    taskBriefTitle: "金字塔演讲录音",
};

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
            },
            task_brief: {
                enabled: true,
                title: template.taskBriefTitle,
                purpose: template.taskBriefPurpose,
                scenario: template.taskBriefScenario,
            },
            ...(materialId
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
    switch (moduleKey) {
        case "ppt_explanation":
            return PPT_EXPLANATION_TEMPLATE;
        case "elevator_pitch":
            return ELEVATOR_PITCH_TEMPLATE;
        default:
            return null;
    }
}
