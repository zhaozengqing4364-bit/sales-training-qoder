---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: 定位高频 API surface 的错误 shape 漂移点

盘点 prompt templates、presentations、auth 等高噪声 route family 的错误返回形状，标出裸 HTTPException / 通用 except Exception / page-local frontend 解析分叉。

## Inputs

- `backend/src/prompt_templates/api/routes.py`
- `backend/src/presentation_coach/api/presentations.py`
- `backend/src/common/auth/service.py`
- `web/src/lib/api/client.ts`

## Expected Output

- `error-shape inventory`

## Verification

rg -n "HTTPException|except Exception" backend/src/prompt_templates backend/src/presentation_coach backend/src/common/auth

## Observability Impact

current error-shape inventory
