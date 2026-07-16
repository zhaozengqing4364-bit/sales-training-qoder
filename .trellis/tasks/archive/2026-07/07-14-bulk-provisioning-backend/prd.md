# 批量开户后端

## Goal

实现可预览、团队内建组、团队级事务、幂等重试和一次性凭据的批量开户 application service 与 API。

## Scope

* UTF-8 CSV 解析及无写入校验预览。
* ProvisioningBatch、团队执行单元和行状态模型。
* 未知团队的草稿、主组长跨行引用和确认编排。
* 团队内全成全败、团队间部分成功、失败团队原批次重试。
* 一次性临时密码响应、响应丢失后的批量重置恢复。
* 脱敏审计、幂等键、并发和可观测指标。

## Acceptance Criteria

* [x] 至少 50 行导入可预览并逐行定位冲突。
* [x] 同一团队任一步骤失败会完整回滚该团队本次新增数据。
* [x] 重复确认或重试不会创建重复账号、团队关系和审计事件。
* [x] 成功行只返回一次临时密码，失败或回滚行不返回凭据。
* [x] 批次结果准确区分 completed/partially_completed/failed。

## Dependencies

* Parent: `../07-14-account-team-lead/prd.md`
* Requires: `../07-14-account-role-foundation/prd.md`, `../07-14-team-domain-scope/prd.md`
