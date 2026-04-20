---
estimated_steps: 7
estimated_files: 3
skills_used: []
---

# T02: 补齐 learner 统一帮助/反馈入口

Why: 帮助/反馈入口必须优先收口到 shared learner shell 或共享卡片模式，才能避免之后再次分散。

Do:
1. 在 learner shell 或首页/profile 的合适位置增加统一帮助/反馈入口。
2. 补最小角色/权限说明，让 learner 知道遇到问题时去哪里、为什么有些入口看不到。
3. 优先复用 sidebar/home 卡片模式，不新增完整帮助中心。
4. 保持文案诚实，不承诺未实现的支持系统。

Done when: learner 从主要入口页都能通过同一套模式找到帮助/反馈入口。

## Inputs

- `web/src/components/layout/sidebar.tsx`
- `web/src/app/(dashboard)/*`
- `web/src/components/dashboard/*`

## Expected Output

- `web/src/components/layout/sidebar.tsx`
- `web/src/app/(dashboard)/*`
- `web/src/components/dashboard/*`

## Verification

npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx"

## Observability Impact

帮助入口进入共享 learner shell，后续页面不需各自发明支持路径。
