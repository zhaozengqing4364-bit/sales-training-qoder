export type NewcomerTrainingAuditRoute = {
  readonly id: string;
  readonly label: string;
  readonly path: string;
  readonly critical: boolean;
  readonly expectText: readonly (string | RegExp)[];
  readonly forbiddenText: readonly (string | RegExp)[];
};

const forbidden = [
  /trace[_-]?id/i,
  /raw json/i,
  /\bprompt\b/i,
  /\bmock\b/i,
  /\bseed\b/i,
  /\btest\b/i,
  /runtime binding/i,
  /internal error/i,
  /Unhandled Runtime Error/i,
  /Application error/i,
] as const;

export const learnerRoutes: readonly NewcomerTrainingAuditRoute[] = [
  {
    id: "L-01",
    label: "新人训练首页",
    path: "/newcomer-training",
    critical: true,
    expectText: [/新人训练|继续|下一步/],
    forbiddenText: forbidden,
  },
  {
    id: "L-02",
    label: "内容学习活动",
    path: "/newcomer-training/activities/lesson-product_knowledge",
    critical: true,
    expectText: ["当前任务", "为什么要做", "怎么完成", "完成标准", "开始学习"],
    forbiddenText: forbidden,
  },
];

export const activityVisualRoutes: readonly NewcomerTrainingAuditRoute[] = [
  {
    id: "L-03",
    label: "测验活动",
    path: "/newcomer-training/activities/quiz-product_knowledge",
    critical: true,
    expectText: ["当前任务", "为什么要做", "怎么完成", "完成标准", "测验"],
    forbiddenText: forbidden,
  },
  {
    id: "L-04",
    label: "录音讲解活动",
    path: "/newcomer-training/activities/audio-foundation-explanation",
    critical: true,
    expectText: ["当前任务", "为什么要做", "怎么完成", "完成标准", "录音"],
    forbiddenText: forbidden,
  },
  {
    id: "L-05",
    label: "结构化教练活动",
    path: "/newcomer-training/activities/coach-foundation-remediation",
    critical: true,
    expectText: ["当前任务", "为什么要做", "怎么完成", "完成标准", "结构化"],
    forbiddenText: forbidden,
  },
  {
    id: "L-06",
    label: "异步客户场景录音活动",
    path: "/newcomer-training/activities/assignment-foundation-customer-scenario",
    critical: true,
    expectText: ["当前任务", "为什么要做", "怎么完成", "完成标准", "客户场景录音"],
    forbiddenText: forbidden,
  },
];

export const adminRoutes: readonly NewcomerTrainingAuditRoute[] = [
  {
    id: "A-00",
    label: "训练运营总览",
    path: "/admin/newcomer-training",
    critical: true,
    expectText: ["新人训练运营工作台"],
    forbiddenText: forbidden,
  },
  {
    id: "A-01",
    label: "路径编排",
    path: "/admin/newcomer-training/paths",
    critical: true,
    expectText: ["路径与版本", "新建训练路径", "搜索路径"],
    forbiddenText: forbidden,
  },
  {
    id: "A-02",
    label: "学员进度",
    path: "/admin/newcomer-training/learners",
    critical: true,
    expectText: ["学员进度"],
    forbiddenText: forbidden,
  },
  {
    id: "A-03",
    label: "题库审核",
    path: "/admin/newcomer-training/questions",
    critical: true,
    expectText: ["题库审核", "生成候选题", "候选题队列"],
    forbiddenText: forbidden,
  },
  {
    id: "A-04",
    label: "达标复核",
    path: "/admin/newcomer-training/reviews",
    critical: true,
    expectText: ["达标复核"],
    forbiddenText: forbidden,
  },
];
