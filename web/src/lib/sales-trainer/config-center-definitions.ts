import { AUDIO_EVALUATION_SCENARIOS } from "./audio-evaluation-scenarios";
import type { ModuleDefinition } from "./config-center-types";

const AUDIO_MODULE_DEFINITIONS = AUDIO_EVALUATION_SCENARIOS.map((scenario) => ({
    moduleKey: scenario.moduleKey,
    title: scenario.title,
    orderLabel: scenario.orderLabel,
    description: scenario.description,
    remediationHref: `/admin/sales-trainer/training-tasks/${scenario.slug}`,
    learnerPreview: scenario.learnerPreview,
})) satisfies readonly ModuleDefinition[];

const pptDefinition = AUDIO_MODULE_DEFINITIONS.find(
    (definition) => definition.moduleKey === "ppt_explanation",
);
const elevatorDefinition = AUDIO_MODULE_DEFINITIONS.find(
    (definition) => definition.moduleKey === "elevator_pitch",
);

export const CORE_MODULE_DEFINITIONS = [
    ...(pptDefinition ? [pptDefinition] : []),
    {
        moduleKey: "business_skills",
        title: "学习专题",
        orderLabel: "学习专题",
        description: "绑定学习专题和小测，商务礼仪是当前第一个专题，后续可扩展销售技巧、客户常见质疑等专题。",
        remediationHref: "/admin/sales-trainer/articles",
        learnerPreview: "阅读专题内容，完成后查看得分；专题得分不阻塞后续训练任务。",
    },
    ...(elevatorDefinition ? [elevatorDefinition] : []),
    {
        moduleKey: "realtime_roleplay_placeholder",
        title: "实时对练占位",
        orderLabel: "第四关",
        description: "仅展示未开放状态，不启动实时机器人会话。",
        remediationHref: "/admin/sales-trainer/paths",
        learnerPreview: "展示暂不开放原因，不进入实时对练。",
    },
] as const satisfies readonly ModuleDefinition[];

export const MODULE_DEFINITIONS = [
    ...AUDIO_MODULE_DEFINITIONS,
    ...CORE_MODULE_DEFINITIONS.filter((definition) =>
        !AUDIO_EVALUATION_SCENARIOS.some((scenario) => scenario.moduleKey === definition.moduleKey),
    ),
] as const satisfies readonly ModuleDefinition[];
