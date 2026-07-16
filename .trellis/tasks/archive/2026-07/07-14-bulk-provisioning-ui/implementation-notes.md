# Implementation Notes

## Completed

- 新增 `/admin/users/import` 独立批量开户流程及用户管理入口。
- 支持模板下载、文件校验、团队分组、就地补团队名称/主组长、确认、部分成功和失败团队重试。
- 一次性凭证以持久结果区显示，可复制/导出；刷新丢失后可显式重置。
- 覆盖 loading、empty、error、partial success、重复提交禁用和窄屏布局。

## Deviations

- 凭证 CSV 仅在浏览器生成，不在服务端生成含明文密码的下载文件。
