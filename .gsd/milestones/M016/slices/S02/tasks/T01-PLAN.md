---
estimated_steps: 6
estimated_files: 4
skills_used: []
---

# T01: 定位高频 API surface 的错误 shape 漂移点

Why: 只有先找到哪些 route family 正在 outward 暴露漂移的错误 shape，后续收口才不会扩成全 backend 扫荡。

Do:
1. 盘点 prompt templates、presentations、auth 等高噪声 route family 的错误返回形状。
2. 标出裸 `HTTPException`、通用 `except Exception` 和 frontend page-local 解析分叉。
3. 找出最小的一组 shared contract seam。

Done when: 已有一份高频 API surface 错误 shape 漂移清单，足够指导后续统一收口。

## Inputs

- `backend/src/prompt_templates/api/routes.py`
- `backend/src/presentation_coach/api/presentations.py`
- `backend/src/common/auth/service.py`
- `web/src/lib/api/client.ts`

## Expected Output

- `backend/src/prompt_templates/api/routes.py`
- `backend/src/presentation_coach/api/presentations.py`
- `backend/src/common/auth/service.py`
- `web/src/lib/api/client.ts`

## Verification

rg -n "HTTPException|except Exception" backend/src/prompt_templates backend/src/presentation_coach backend/src/common/auth

## Observability Impact

形成高频 API surface 的错误 shape 漂移图。
