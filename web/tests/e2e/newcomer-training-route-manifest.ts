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
];

export const adminRoutes: readonly NewcomerTrainingAuditRoute[] = [
  {
    id: "A-01",
    label: "路径编排",
    path: "/admin/newcomer-training/path",
    critical: true,
    expectText: ["新人训练路径", "训练路径大纲", "检查并预览"],
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
