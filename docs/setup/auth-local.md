# 本地认证配置指南

## 1) 配置环境变量

在 `backend/.env`（或项目根 `.env`）中至少配置一个：

```env
AUTH_SHARED_PASSWORD=change-me
AUTH_USER_PASSWORDS_JSON={"admin@qoder.ai":"admin123","support@qoder.ai":"support123"}
```

规则：
- `AUTH_USER_PASSWORDS_JSON` 对命中邮箱优先；
- 未命中邮箱回退到 `AUTH_SHARED_PASSWORD`；
- 两者都未配置时，`POST /api/v1/auth/login` 返回 `503 [AUTH_SERVICE_UNAVAILABLE]`。

## 2) 初始化管理员账号

```bash
cd backend
python scripts/bootstrap_auth_admin.py --email admin@qoder.ai --name 管理员 --role admin
```

可选：

```bash
python scripts/bootstrap_auth_admin.py --email support@qoder.ai --name 支持工程师 --role support
```

## 3) 启动后检查

后端启动日志会输出认证配置诊断（不含明文口令）：
- 是否配置共享口令；
- 用户覆盖条目数；
- 覆盖配置 JSON 是否有效；
- 登录能力是否就绪。
