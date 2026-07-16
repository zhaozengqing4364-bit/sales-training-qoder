# Implementation Notes

## Verified flow

- 路径快速新建评分标准后，前端先写入当前活动的 `scoring_rubric_id`，再调用路径 `PUT /draft`。
- 服务端返回新的 working revision；重新读取路径时仍能取得同一 `scoring_rubric_id`，因此该草稿是服务端持久化版本，不依赖弹窗或页面内存。
- 录音提交冻结 `prompt_snapshot`，评分时优先使用提交快照中的 `system_prompt` 与 `scoring_template`，不会被后续编辑覆盖。

## Deviations and fixes

- 原实现等待草稿保存完成后才调用 `window.open`，真实浏览器可能把它当作异步弹窗拦截。现改为点击时同步打开空白页，保存成功后再切换到编辑路由；保存失败、抽屉关闭或组件卸载时关闭空白页。
- 原评分标准编辑页只保存 working revision，没有在同一流程发布，用户可能看到“保存成功”但后续评分仍使用旧提示词。现改为显式“保存并发布”，先保存可审计修订，再发布为后续评分使用的当前版本；部分失败会明确说明旧版本仍生效并允许重试。

## Provider evidence

- 当前真实评分供应商 smoke：通过。
- 长提示词 smoke：`scoring_template=35,116` 字、转写 `1,960` 字，约 `15.28s` 返回合法 JSON；字段包含 `total_score`、`summary`、`strengths`、`improvements`、`dimension_scores`。
- 该结果证明当前配置可处理与用户示例同量级的输入，但生产耗时仍受上游模型、网络和实际转写长度影响。
