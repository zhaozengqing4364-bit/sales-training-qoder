export type NewcomerTrainingAuditRoute = {
  readonly id: string;
  readonly label: string;
  readonly path: string;
  readonly critical: boolean;
  readonly expectText: readonly (string | RegExp)[];
  readonly forbiddenText: readonly (string | RegExp)[];
};

export const learnerStaticRoutes: readonly NewcomerTrainingAuditRoute[] = [
  {
    id: "L-01",
    label: "新人训练入口",
    path: "/sales-trainer",
    critical: true,
    expectText: ["新人训练路径"],
    forbiddenText: [/TrainingJourney/i, /\brevision\b/i, /trace[_-]?id/i, /\bE2E\b/i, /\be2e\b/, /\bmock\b/i, /\bseed\b/i, /\[HTTP_/],
  },
  {
    id: "L-02",
    label: "学习中心",
    path: "/sales-trainer/learn/hub",
    critical: true,
    expectText: [/学习|商务|专题/],
    forbiddenText: [/TrainingJourney/i, /\brevision\b/i, /trace[_-]?id/i, /\bE2E\b/i, /\be2e\b/, /\bmock\b/i, /\bseed\b/i, /\[HTTP_/],
  },
  {
    id: "L-03",
    label: "商务礼仪学习专题",
    path: "/sales-trainer/learning-topics/business-etiquette",
    critical: true,
    expectText: [/商务礼仪|学习专题|小单元/],
    forbiddenText: [/TrainingJourney/i, /\brevision\b/i, /trace[_-]?id/i, /\bE2E\b/i, /\be2e\b/, /\bmock\b/i, /\bseed\b/i, /\[HTTP_/],
  },
  {
    id: "L-09",
    label: "旧商务技巧入口",
    path: "/sales-trainer/business-skills",
    critical: true,
    expectText: [/商务礼仪|学习|小单元/],
    forbiddenText: [/TrainingJourney/i, /\brevision\b/i, /trace[_-]?id/i, /\bE2E\b/i, /\be2e\b/, /\bmock\b/i, /\bseed\b/i, /\[HTTP_/],
  },
  {
    id: "L-10",
    label: "旧商务技巧考试入口",
    path: "/sales-trainer/business-skills/exam",
    critical: true,
    expectText: [/考试|小测|商务/],
    forbiddenText: [/TrainingJourney/i, /\brevision\b/i, /trace[_-]?id/i, /\bE2E\b/i, /\be2e\b/, /\bmock\b/i, /\bseed\b/i, /\[HTTP_/],
  },
  {
    id: "L-11",
    label: "旧商务技巧 AI 教练入口",
    path: "/sales-trainer/business-skills/coach",
    critical: true,
    expectText: [/AI 教练|商务|训练/],
    forbiddenText: [/TrainingJourney/i, /\brevision\b/i, /trace[_-]?id/i, /\bE2E\b/i, /\be2e\b/, /\bmock\b/i, /\bseed\b/i, /\[HTTP_/],
  },
];

export const learnerDynamicRouteTemplates: readonly Omit<NewcomerTrainingAuditRoute, "path">[] = [
  {
    id: "L-04",
    label: "单元学习",
    critical: true,
    expectText: [/新人训练|第 \d+\/\d+ 章|标记本章已读|开始本章测验|无法阅读本章/],
    forbiddenText: [/TrainingJourney/i, /\brevision\b/i, /trace[_-]?id/i, /\bE2E\b/i, /\be2e\b/, /\bmock\b/i, /\bseed\b/i, /\[HTTP_/],
  },
  {
    id: "L-05",
    label: "单元考试",
    critical: true,
    expectText: [/提交答案|做题训练|训练单元/],
    forbiddenText: [/TrainingJourney/i, /\brevision\b/i, /trace[_-]?id/i, /\bE2E\b/i, /\be2e\b/, /\bmock\b/i, /\bseed\b/i, /\[HTTP_/],
  },
  {
    id: "L-06",
    label: "考试结果",
    critical: true,
    expectText: [/做题结果|总分|状态/],
    forbiddenText: [/TrainingJourney/i, /\brevision\b/i, /trace[_-]?id/i, /\bE2E\b/i, /\be2e\b/, /\bmock\b/i, /\bseed\b/i, /\[HTTP_/],
  },
  {
    id: "L-07",
    label: "录音上传",
    critical: true,
    expectText: [/上传|录音|任务简报|语音作业/],
    forbiddenText: [/TrainingJourney/i, /\brevision\b/i, /trace[_-]?id/i, /\bE2E\b/i, /\be2e\b/, /\bmock\b/i, /\bseed\b/i, /\[HTTP_/],
  },
  {
    id: "L-08",
    label: "录音评分结果",
    critical: true,
    expectText: [/评分|录音|结果|处理中|待重试/],
    forbiddenText: [/TrainingJourney/i, /\brevision\b/i, /trace[_-]?id/i, /\bE2E\b/i, /\be2e\b/, /\bmock\b/i, /\bseed\b/i, /\[HTTP_/],
  },
];

const adminForbiddenText = [
  /\[object Object\]/,
  /Unhandled Runtime Error/i,
  /Application error/i,
  /\[HTTP_404\]/,
] as const;

export const adminRoutes: readonly NewcomerTrainingAuditRoute[] = [
  { id: "A-01", label: "后台工作台", path: "/admin/sales-trainer", critical: true, expectText: ["新人训练路径工作台"], forbiddenText: adminForbiddenText },
  { id: "A-02", label: "录音管理总览", path: "/admin/sales-trainer/audio", critical: true, expectText: ["录音管理"], forbiddenText: adminForbiddenText },
  { id: "A-03", label: "PPT 讲解录音任务", path: "/admin/sales-trainer/audio/ppt-explanation", critical: true, expectText: ["PPT 讲解"], forbiddenText: adminForbiddenText },
  { id: "A-03B", label: "公司产品 Demo 录音任务", path: "/admin/sales-trainer/audio/company-product-demo", critical: true, expectText: ["公司产品 Demo"], forbiddenText: adminForbiddenText },
  { id: "A-04", label: "录音材料库", path: "/admin/sales-trainer/audio/materials", critical: true, expectText: [/材料|上传/], forbiddenText: adminForbiddenText },
  { id: "A-05", label: "录音评分标准", path: "/admin/sales-trainer/audio/score-standards", critical: true, expectText: [/录音评分标准|评分标准/], forbiddenText: adminForbiddenText },
  { id: "A-06", label: "录音提交", path: "/admin/sales-trainer/audio/submissions", critical: true, expectText: [/学员录音|录音提交|提交/], forbiddenText: adminForbiddenText },
  { id: "A-07", label: "录音评分结果", path: "/admin/sales-trainer/audio/results", critical: true, expectText: [/评分结果|录音/], forbiddenText: adminForbiddenText },
  { id: "A-08", label: "学习专题总览", path: "/admin/sales-trainer/learning-topics", critical: true, expectText: ["学习专题"], forbiddenText: adminForbiddenText },
  { id: "A-09", label: "商务礼仪专题配置", path: "/admin/sales-trainer/learning-topics/business-etiquette", critical: true, expectText: [/商务礼仪|专题/], forbiddenText: adminForbiddenText },
  { id: "A-10", label: "学习内容导入", path: "/admin/sales-trainer/learning-topics/import", critical: true, expectText: [/导入|学习/], forbiddenText: adminForbiddenText },
  { id: "A-11", label: "专题能力配置", path: "/admin/sales-trainer/learning-topics/capabilities", critical: true, expectText: [/能力|专题/], forbiddenText: adminForbiddenText },
  { id: "A-12", label: "专题题库", path: "/admin/sales-trainer/learning-topics/questions", critical: true, expectText: [/题目|题库|学习专题/], forbiddenText: adminForbiddenText },
  { id: "A-13", label: "新建题目", path: "/admin/sales-trainer/learning-topics/questions/new", critical: true, expectText: [/新建|题目/], forbiddenText: adminForbiddenText },
  { id: "A-14", label: "题目草稿", path: "/admin/sales-trainer/learning-topics/questions/drafts", critical: true, expectText: [/草稿|题目/], forbiddenText: adminForbiddenText },
  { id: "A-15", label: "试题预览", path: "/admin/sales-trainer/learning-topics/questions/quiz-preview", critical: true, expectText: [/预览|小测|题目/], forbiddenText: adminForbiddenText },
  { id: "A-16", label: "专题考卷", path: "/admin/sales-trainer/learning-topics/papers", critical: true, expectText: [/考卷|小测|学习专题/], forbiddenText: adminForbiddenText },
  { id: "A-17", label: "新建考卷", path: "/admin/sales-trainer/learning-topics/papers/new", critical: true, expectText: [/新建|考卷|小测/], forbiddenText: adminForbiddenText },
  { id: "A-18", label: "路径配置", path: "/admin/sales-trainer/paths", critical: true, expectText: [/路径|发布/], forbiddenText: adminForbiddenText },
  { id: "A-19", label: "模块单元", path: "/admin/sales-trainer/units", critical: true, expectText: [/模块单元|训练单元|新建/], forbiddenText: adminForbiddenText },
  { id: "A-20", label: "AI 教练配置", path: "/admin/sales-trainer/ai-coach", critical: true, expectText: [/AI 教练|配置/], forbiddenText: adminForbiddenText },
  { id: "A-21", label: "达标验收", path: "/admin/sales-trainer/readiness", critical: true, expectText: [/达标|验收/], forbiddenText: adminForbiddenText },
  { id: "A-22", label: "训练记录", path: "/admin/sales-trainer/training-records", critical: true, expectText: [/训练记录/], forbiddenText: adminForbiddenText },
  { id: "A-23", label: "Journey 分析", path: "/admin/sales-trainer/analytics", critical: true, expectText: [/Journey|分析|训练/], forbiddenText: adminForbiddenText },
  { id: "A-24", label: "配置中心", path: "/admin/sales-trainer/settings", critical: true, expectText: [/配置|治理/], forbiddenText: adminForbiddenText },
  { id: "A-25", label: "操作记录", path: "/admin/sales-trainer/operation-logs", critical: true, expectText: [/操作记录|审计/], forbiddenText: adminForbiddenText },
  { id: "C-01", label: "旧文章入口", path: "/admin/sales-trainer/articles", critical: true, expectText: ["学习专题"], forbiddenText: adminForbiddenText },
  { id: "C-02", label: "旧材料入口", path: "/admin/sales-trainer/materials", critical: true, expectText: [/材料/], forbiddenText: adminForbiddenText },
  { id: "C-03", label: "旧评分标准入口", path: "/admin/sales-trainer/score-standards", critical: true, expectText: [/评分标准|录音/], forbiddenText: adminForbiddenText },
  { id: "C-04", label: "旧考卷入口", path: "/admin/sales-trainer/papers", critical: true, expectText: [/考卷|小测/], forbiddenText: adminForbiddenText },
  { id: "C-05", label: "旧题库入口", path: "/admin/sales-trainer/questions", critical: true, expectText: [/题库|题目/], forbiddenText: adminForbiddenText },
  { id: "C-06", label: "旧录音提交入口", path: "/admin/sales-trainer/audio-submissions", critical: true, expectText: [/学员录音|录音/], forbiddenText: adminForbiddenText },
  { id: "C-07", label: "旧评分结果入口", path: "/admin/sales-trainer/score-results", critical: true, expectText: [/评分结果/], forbiddenText: adminForbiddenText },
  { id: "C-08", label: "旧训练任务入口", path: "/admin/sales-trainer/training-tasks", critical: true, expectText: [/训练任务|录音/], forbiddenText: adminForbiddenText },
];
