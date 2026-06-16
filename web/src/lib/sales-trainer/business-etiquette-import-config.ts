import type { BusinessEtiquetteReleaseStrategy } from "@/lib/api/types";

export const BUSINESS_ETIQUETTE_IMPORT_DEFAULTS = {
    acceptedFileTypes: ".md,.markdown,text/markdown",
    allowOverwriteDraft: true,
    importReason: "导入商务礼仪训练包 v1",
    releaseReason: "发布商务礼仪训练包新版",
    trainingPackKey: "business_etiquette_v1",
} as const;

export const BUSINESS_ETIQUETTE_IMPORT_COPY = {
    pageTitle: "商务礼仪资料导入",
    pageDescription: "导入 Markdown 后生成训练包资料草稿，发布前不影响学员端。",
    emptyFileLabel: "未选择文件",
    fileRequired: "请先选择 Markdown 文件。",
    importingLabel: "导入中...",
    submitLabel: "生成草稿版本",
    submitSuccess: "商务礼仪资料草稿已生成",
} as const;

export const BUSINESS_ETIQUETTE_RELEASE_STRATEGY_LABELS: Record<
    BusinessEtiquetteReleaseStrategy,
    string
> = {
    future_learners_only: "仅新学员使用新版",
    allow_voluntary_switch: "允许老学员自愿切换",
    assign_retraining: "指定人群重练新版",
};

export const BUSINESS_ETIQUETTE_RELEASE_COPY = {
    assignedUsersRequired: "指定人群重练必须填写用户 ID。",
    changeTypeLabels: {
        added: "新增",
        changed: "变更",
        removed: "移除",
    },
    publishSuccessPrefix: "已发布训练包 v",
    panelEyebrow: "发布影响分析",
    panelTitle: "新版生效前检查",
    panelDescription: "发布策略、重练名单和影响范围由后端统一计算并写审计日志。",
    refreshButton: "刷新影响",
    metrics: {
        changedChapters: "章节变更",
        impactedLearningUnits: "受影响小单元",
        activeLearners: "在学人员",
        recommendedRetraining: "建议重练",
    },
    lists: {
        chapterTitle: "章节 diff",
        chapterEmpty: "暂无章节变更",
        learningUnitTitle: "受影响小单元",
        learningUnitEmpty: "暂无受影响小单元",
        questionTitle: "题目与草稿",
        questionEmpty: "暂无题目影响",
        capabilityTitle: "能力点",
        capabilityEmpty: "暂无能力点影响",
        activeLearnerTitle: "旧版本在学人员",
        activeLearnerEmpty: "暂无旧版本在学人员",
    },
    strategyLabel: "发布影响范围",
    defaultStrategyPrefix: "默认策略：",
    releaseReasonLabel: "发布原因",
    assignedUsersLabel: "指定重练用户 ID",
    assignedUsersPlaceholder: "每行一个 user_id，或用逗号分隔",
    assignedUsersCountPrefix: "已解析",
    assignedUsersLimitPrefix: "单次上限",
    publishingLabel: "发布中...",
    publishButton: "确认发布新版",
    oldSnapshotNotice: "发布后，旧训练记录继续引用旧版本快照。",
    loadingImpact: "正在计算影响分析...",
    noImpact: "暂无影响分析。",
} as const;
