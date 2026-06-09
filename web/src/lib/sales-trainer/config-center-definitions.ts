import type { ModuleDefinition } from "./config-center-types";

export const MODULE_DEFINITIONS = [
    {
        moduleKey: "ppt_explanation",
        title: "PPT 讲解录音",
        orderLabel: "第一关",
        description: "绑定 PPT 材料和录音评分标准，学员上传讲解录音后获得转写与评分。",
        remediationHref: "/admin/sales-trainer/materials?module=ppt_explanation&purpose=ppt_pitch",
        learnerPreview: "学习 PPT 讲解要点，确认材料版本后上传录音。",
    },
    {
        moduleKey: "business_skills",
        title: "商务技巧",
        orderLabel: "第二关",
        description: "绑定学习文章和商务技巧考卷，学员先学习章节再考试。",
        remediationHref: "/admin/sales-trainer/articles",
        learnerPreview: "阅读章节内容，完成后进入商务技巧考卷。",
    },
    {
        moduleKey: "elevator_pitch",
        title: "电梯演讲",
        orderLabel: "第三关",
        description: "配置多个录音时长选项，学员选择时长后上传演讲录音。",
        remediationHref: "/admin/sales-trainer/materials?module=elevator_pitch&purpose=elevator_pitch",
        learnerPreview: "选择后台配置的演讲时长，上传录音并查看 AI 评分。",
    },
    {
        moduleKey: "realtime_roleplay_placeholder",
        title: "实时对练占位",
        orderLabel: "第四关",
        description: "仅展示未开放状态，不启动实时机器人会话。",
        remediationHref: "/admin/sales-trainer/paths",
        learnerPreview: "展示暂不开放原因，不进入实时对练。",
    },
] as const satisfies readonly ModuleDefinition[];
