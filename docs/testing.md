# 测试策略

新人训练按契约、执行器、API、页面和闭环五层验证。

## 后端

```bash
cd backend
./.venv/bin/ruff check src/ tests/ scripts/
./.venv/bin/mypy src/
./.venv/bin/pytest tests/unit/ -q
./.venv/bin/pytest tests/integration/ -m integration -q
./.venv/bin/pytest tests/contract/ -m contract -q
./.venv/bin/alembic current
```

聚焦 pytest 可使用 `--no-cov`；完整门禁不得关闭覆盖率。reset 必须先 dry-run，再带固定确认词 apply，随后 seed 两次验证幂等。

## 前端

```bash
cd web
npx tsc --noEmit
npx eslint . --quiet
npx vitest run
npx next build
npx playwright test tests/e2e/newcomer-training-admin.spec.ts tests/e2e/newcomer-training-learner.spec.ts tests/e2e/newcomer-training-closed-loop.spec.ts
```

E2E 普通运行只使用 Fake/local Provider。真实 StepAudio 仅在显式受控 gate 中运行，限制调用次数并验证审计，不输出凭据。
