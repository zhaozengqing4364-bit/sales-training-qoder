# Implementation Notes

## Completed

- 新增显式团队 scope、只读 workbench 与成员 drilldown API。
- 支持全部团队/单团队、7/30/90/自定义区间及紧邻同期对比。
- 新人路径和管理员额外任务保持两个独立分母，不生成综合百分比。
- 风险仅来自确定性证据；无排行榜、AI 推断、readiness、calibration 或 retraining 数据。
- 团队、日期、成员搜索下推数据库；直接详情再次执行对象级授权。

## Deviations

- “只看需关注”由已按权限和查询范围返回的确定性结果在前端过滤；团队、日期和成员检索仍在数据库完成。
