import type {
    BusinessEtiquetteAiCoachProgressStatus,
    AiCoachNextActionV1,
    AiCoachTrainingCardTypeV1,
} from "@/lib/api/types";

export const BUSINESS_SKILLS_COACH_WORKBENCH_RULES = {
    showFreeFollowup: true,
    allowSkipActiveCard: false,
} as const;

export const BUSINESS_SKILLS_COACH_WORKBENCH_COPY = {
    pageTitle: "商务技巧 AI 教练",
    trainingDeskTitle: "训练卡工作台",
    preparationTitle: "准备开始 AI 教练训练",
    preparationDescription: "先确认当前小单元，再选择继续上一局或新开训练。",
    preparationUnitSummary: "本轮会围绕这个小单元生成训练卡。",
    preparationNoUnit: "暂未读取到可用小单元，进入后按综合训练处理。",
    unavailableTitle: "商务技巧 AI 教练暂不可用",
    unavailableDescription: "AI 教练配置缺失或未启用。",
    activeSessionSubtitle: "对话主导，需要练习时教练会放入卡片",
    startingSessionSubtitle: "正在建立训练局",
    loadingResume: "正在恢复训练局",
    loadingNew: "正在新开训练局",
    sendingText: "正在发送给教练",
    scoringAnswer: "正在批改你的答案",
    defaultThinkingLabel: "正在推进训练",
    streamingAnswerTitle: "教练正在回复",
    streamingAnswerBadge: "生成中",
    retryButton: "重试",
    resumeButton: "继续当前局",
    newSessionButton: "新开一局",
    busyButton: "处理中",
    newSessionBusyButton: "新开中",
    endButton: "结束并总结",
    backLabel: "返回新人训练路径",
    currentUnitLabel: "当前小单元",
    currentCapabilitiesLabel: "训练能力点",
    masteryLabel: "掌握状态",
    aiCoachProgressLabel: "AI 教练达标",
    aiCoachProgressUnavailable: "暂未生成达标进度",
    aiCoachProgressPendingDescription: "完成当前训练卡后生成本轮达标进度。",
    aiCoachSessionMissingUnitSnapshot:
        "当前训练局缺少小单元信息，请点击「新开一局」重新开始。",
    aiCoachProgressError: "达标进度读取失败",
    streamEmptyError: "训练请求没有返回有效结果，请稍后重试。",
    streamErrorTitle: "训练请求未完成",
    aiCoachProgressCards: "已评分训练卡",
    aiCoachProgressRemediation: "补救次数",
    aiCoachWeakCapabilities: "薄弱能力点",
    aiCoachRecommendedChapters: "建议回看章节",
    aiCoachRecommendedCards: "建议重练卡片",
    roundGoalLabel: "本轮目标",
    activityLabel: "训练状态",
    learningUnitsUnavailable:
        "暂未读取到商务礼仪小单元配置，当前卡片按综合训练展示。",
    fallbackUnitTitle: "商务礼仪综合训练",
    fallbackUnitDescription: "本轮会按当前能力点完成训练。",
    noActiveCardTitle: "等待下一张训练卡",
    noActiveCardDescription:
        "可以直接和教练聊；需要验证理解时，教练会在对话里放入练习卡。",
    feedbackTitle: "教练反馈",
    feedbackEmptyTitle: "提交训练卡后查看反馈",
    feedbackEmptyDescription: "系统会展示做对了什么、主要问题、建议表达和下一步训练。",
    didWellLabel: "做得好",
    mainIssueLabel: "主要问题",
    whyInappropriateLabel: "为什么不合适",
    suggestedResponseLabel: "可以这样说",
    nextStepLabel: "下一步",
    missedPointsLabel: "薄弱点",
    endPanelTitle: "结束面板",
    endPanelMastered: "本轮已达标",
    endPanelNotMastered: "本轮继续练习",
    endPanelWhy: "原因",
    endPanelNext: "下一步",
    conversationEvidenceTitle: "教练对话",
    followupPromptTitle: "教练给你的可选方向",
    commandBarLabel: "教练动作",
    followupPlaceholderWhenActive: "可以问教练，也可以先提交当前练习卡",
    followupPlaceholderDefault: "直接和教练聊，或使用上方操作",
    sendAriaLabel: "发送",
    submitCardButton: "提交",
    submittedLabel: "已提交",
    focusPanelEyebrow: "当前任务",
    focusPanelTitle: "先完成当前卡片",
    focusPanelChoosingTitle: "选择下一步训练方向",
    focusPanelReviewTitle: "看反馈，再决定下一步",
    focusPanelDescription: "新人进入后只需要先处理主卡片；提交后教练会判断是否达标，并给出下一步。",
    activeCardInstruction: "先作答，再看反馈和下一步",
    streamingCardTitle: "训练卡生成中",
    streamingCardPreviewBadge: "禁用预览",
    streamingCardActivityFallback: "正在生成",
    streamingCardUnitLabel: "当前小单元",
    streamingCardStemPlaceholder: "教练正在生成本轮题干",
    streamingCardDescription: "题干、选项和评分规则还在生成；你可以先看到卡片结构，生成完成前不能作答。",
    streamingCardOptionPlaceholder: "选项生成中",
    streamingCardSubmitPlaceholder: "生成完成后可提交",
    coachGuidanceTitle: "教练判断",
    coachGuidanceDescription: "这里只保留结论、薄弱点和下一步，不再把所有记录堆在首屏。",
    conversationEvidenceDescription: "历史对话和完整证据仅在需要复盘时展开查看。",
} as const;

export const BUSINESS_SKILLS_COACH_PROGRESS_LABELS: Record<
    BusinessEtiquetteAiCoachProgressStatus,
    string
> = {
    not_started: "未开始",
    in_progress: "训练中",
    not_mastered: "未达标",
    mastered: "已达标",
    ready: "可上场",
    manual_review: "待人工复盘",
};

export const BUSINESS_SKILLS_COACH_COMMAND_LABELS = {
    continue: "继续下一题",
    explain: "讲解一下",
    switch_scenario: "换个场景",
    summarize: "总结本轮",
    end: "结束并总结",
    retry: "重试本题",
} as const;

export const BUSINESS_SKILLS_COACH_PHASE_LABELS = {
    starting: "准备开局",
    answering: "作答中",
    reviewing: "复盘中",
    choosing: "等你选择",
    summarizing: "本轮总结",
    completed: "已结束",
} as const;

export const BUSINESS_SKILLS_COACH_DIFFICULTY_LABELS = {
    warmup: "热身",
    normal: "标准",
    challenge: "挑战",
} as const;

export const BUSINESS_SKILLS_COACH_CARD_TYPE_LABELS: Record<
    AiCoachTrainingCardTypeV1,
    string
> = {
    scenario_judgment: "场景判断卡",
    expression_rewrite: "表达改写卡",
    role_response: "角色回应卡",
};

export const BUSINESS_SKILLS_COACH_NEXT_ACTION_LABELS: Record<
    AiCoachNextActionV1,
    string
> = {
    continue_drill: "继续同主题训练",
    increase_difficulty: "提高情境难度",
    remediate: "先讲解再重练",
    switch_scenario: "切换训练场景",
    summarize: "总结本轮表现",
    ask_user_choice: "等你选择方向",
    end_session: "结束并总结",
};
