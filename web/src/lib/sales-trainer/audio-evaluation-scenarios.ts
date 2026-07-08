import type { NewcomerPathModuleType } from "@/lib/api/types";

export type AudioEvaluationScenarioKey =
    | "ppt_explanation"
    | "company_product_demo"
    | "elevator_pitch";

export type AudioEvaluationModuleKey = AudioEvaluationScenarioKey;

export interface AudioEvaluationScenarioDefinition {
    readonly scenarioKey: AudioEvaluationScenarioKey;
    readonly moduleKey: AudioEvaluationModuleKey;
    readonly slug: string;
    readonly purposeKey: string;
    readonly title: string;
    readonly orderLabel: string;
    readonly description: string;
    readonly learnerPreview: string;
    readonly moduleType: Extract<NewcomerPathModuleType, "audio_scoring" | "audio_scoring_group">;
    readonly completionRule: "passed" | "scored" | "submitted";
    readonly orderIndex: number;
    readonly primaryActionLabel: string;
    readonly materialRequired: boolean;
    readonly capabilityKeys: readonly string[];
    readonly taskBriefTitle: string;
    readonly taskBriefPurpose: string;
    readonly taskBriefScenario: string;
}

export const AUDIO_EVALUATION_SCENARIOS = [
    {
        scenarioKey: "ppt_explanation",
        moduleKey: "ppt_explanation",
        slug: "ppt-explanation",
        purposeKey: "ppt_pitch",
        title: "PPT 讲解",
        orderLabel: "第一关",
        description: "绑定 PPT 材料和录音评测标准，学员确认材料后上传讲解录音。",
        learnerPreview: "学习 PPT 讲解要点，确认材料版本后上传录音。",
        moduleType: "audio_scoring",
        completionRule: "passed",
        orderIndex: 1,
        primaryActionLabel: "上传讲解录音",
        materialRequired: true,
        capabilityKeys: ["expression_clarity", "structured_presentation", "product_understanding"],
        taskBriefTitle: "PPT 讲解",
        taskBriefPurpose: "让新人先掌握公司介绍、产品价值和客户沟通结构。",
        taskBriefScenario: "面向首次见客户前的内部演练，按最新 PPT 材料完成讲解。",
    },
    {
        scenarioKey: "company_product_demo",
        moduleKey: "company_product_demo",
        slug: "company-product-demo",
        purposeKey: "company_product_demo",
        title: "公司产品 Demo",
        orderLabel: "训练任务",
        description: "绑定产品资料或 Demo 脚本，学员上传产品讲解录音后由 AI 评测。",
        learnerPreview: "按后台绑定的产品资料或 Demo 脚本完成讲解录音。",
        moduleType: "audio_scoring",
        completionRule: "passed",
        orderIndex: 2,
        primaryActionLabel: "上传 Demo 讲解录音",
        materialRequired: true,
        capabilityKeys: ["expression_clarity", "structured_presentation", "product_understanding"],
        taskBriefTitle: "公司产品 Demo",
        taskBriefPurpose: "训练新人把产品价值、关键功能和客户收益讲清楚。",
        taskBriefScenario: "面向客户产品演示前的内部演练，按后台绑定的产品资料或 Demo 脚本完成讲解。",
    },
    {
        scenarioKey: "elevator_pitch",
        moduleKey: "elevator_pitch",
        slug: "elevator-pitch",
        purposeKey: "elevator_pitch",
        title: "金字塔演讲",
        orderLabel: "第三关",
        description: "配置多个录音时长选项，学员选择时长后上传演讲录音。",
        learnerPreview: "选择后台配置的演讲时长，上传录音并查看 AI 评分。",
        moduleType: "audio_scoring_group",
        completionRule: "passed",
        orderIndex: 3,
        primaryActionLabel: "上传金字塔演讲录音",
        materialRequired: false,
        capabilityKeys: ["expression_clarity", "structured_presentation", "customer_perspective"],
        taskBriefTitle: "金字塔演讲",
        taskBriefPurpose: "训练新人用短时间讲清公司、产品价值和下一步邀约。",
        taskBriefScenario: "客户给你一段有限时间介绍机会，需要按金字塔结构完成清晰、有重点的价值说明。",
    },
] as const satisfies readonly AudioEvaluationScenarioDefinition[];

export function isAudioEvaluationModuleKey(
    moduleKey: string | null | undefined,
): moduleKey is AudioEvaluationModuleKey {
    return AUDIO_EVALUATION_SCENARIOS.some((scenario) => scenario.moduleKey === moduleKey);
}

export function audioEvaluationScenarioForModule(
    moduleKey: AudioEvaluationModuleKey,
): AudioEvaluationScenarioDefinition {
    return AUDIO_EVALUATION_SCENARIOS.find((scenario) => scenario.moduleKey === moduleKey)
        ?? AUDIO_EVALUATION_SCENARIOS[0];
}

export function audioEvaluationScenarioForSlug(
    slug: string | null | undefined,
): AudioEvaluationScenarioDefinition | null {
    return AUDIO_EVALUATION_SCENARIOS.find((scenario) => scenario.slug === slug) ?? null;
}

export function audioEvaluationScenarioForPurpose(
    purposeKey: string | null | undefined,
): AudioEvaluationScenarioDefinition | null {
    return AUDIO_EVALUATION_SCENARIOS.find((scenario) => scenario.purposeKey === purposeKey)
        ?? null;
}
