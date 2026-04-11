# M014: Learner 入口与体验闭环补齐

## Vision
把首页 / auth / history / profile / practice 里真正影响首次使用和复练的缺口补齐，确保第一次打开系统能顺畅走完"登录 → 看懂首页 → 选对训练 → 完成首练 → 看到报告 → 想再练一次"。

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | S01 | medium | — | ✅ | 首页不再有“点了没反应”的主按钮/CTA，首屏有最小 onboarding 指引 |
| S02 | S02 | high | — | ⬜ | 用户可从 profile 走到正式修改密码路径，语速偏好刷新后保留，forgot/reset 体验完整 |
| S03 | Learner 导航、反馈入口与系统壳层补齐 | medium | S01 | ⬜ | 从首页/profile/history 任一页都能找到帮助/反馈入口 |
| S04 | 训练前预期管理与中断恢复 UX 收口 | medium | S01, S02 | ⬜ | 用户在开始录音前能理解本次练习目标，暂停/恢复/结束失败时有清晰指引 |
