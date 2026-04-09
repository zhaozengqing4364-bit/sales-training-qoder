---
estimated_steps: 7
estimated_files: 1
skills_used: []
---

# T03: 首页硬编码用户名和版本号修复

首页修复：将'早安，亚历山大'改为读 currentUser 真实姓名，问候语根据时段动态切换，版本号从 package.json 动态读取，移除硬编码日期。

Steps:
1. 首页从 useCurrentUser hook 读取真实用户名
2. 根据时段切换早安/午安/晚安
3. 无姓名 fallback 到 email 前缀
4. 版本号从 package.json version 读取
5. 移除硬编码的 2026年1月10日

## Inputs

- `web/src/app/(dashboard)/page.tsx`
- `web/package.json`

## Expected Output

- `web/src/app/(dashboard)/page.tsx`

## Verification

npm --prefix web test -- --run dashboard

## Observability Impact

none
