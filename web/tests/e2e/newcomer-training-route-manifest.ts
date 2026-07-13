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
  /prompt id/i,
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
    label: "PPT 讲解录音准备",
    path: "/newcomer-training/activities/ppt-intro-audio",
    critical: true,
    expectText: ["录音前，先看完这 3 项", "本次材料", "评分会关注", /优秀讲解示例|参考表达结构/],
    forbiddenText: forbidden,
  },
];

export const adminRoutes: readonly NewcomerTrainingAuditRoute[] = [
  {
    id: "A-01",
    label: "路径编排",
    path: "/admin/newcomer-training/path",
    critical: true,
    expectText: ["新人训练路径", "训练路径大纲", "预览学员页面", "检查"],
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
];
