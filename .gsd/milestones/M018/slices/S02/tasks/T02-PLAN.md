---
estimated_steps: 6
estimated_files: 2
skills_used: []
---

# T02: 形成依赖扫描与升级策略 baseline

Why: 只有把扫描节奏、升级门禁和 requirements 同步规则写成 baseline，依赖治理才不再只是口头建议。

Do:
1. 落文档或脚本化流程，定义扫描节奏、升级门禁和 license 检查建议。
2. 明确 backend `requirements.txt` 与依赖源文件的同步规则。
3. 保持流程基于当前真实工具，不引入未接入的外部平台假设。

Done when: 仓库里存在一份可执行的依赖扫描与升级策略 baseline。

## Inputs

- `docs/*`
- `scripts/*`
- `web/package.json`
- `backend/requirements.txt`

## Expected Output

- `docs/*`
- `scripts/*`

## Verification

npm audit --prefix web

## Observability Impact

依赖治理从口头建议变成仓库内可回查的 baseline。
