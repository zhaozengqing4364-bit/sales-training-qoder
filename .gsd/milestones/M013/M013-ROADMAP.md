# M013: 

## Vision
把 SYSTEM_AUDIT_REPORT 中的所有条目分成"已修 / 真实缺口 / 需 discovery / 当前 defer"，形成可信 backlog；同时锁定后续所有 repair slice 的验证命令集合，确保后续执行模型只处理真实问题，不被 stale finding 误导。

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | SYSTEM_AUDIT_REPORT 条目归一化 | medium | — | ✅ | 归一化矩阵覆盖所有 audit section，每个条目有 disposition、证据路径和后续 slice 归属 |
| S02 | 审计相关验证基线补齐 | low | S01 | ⬜ | 每个后续 slice 至少有一条已存在的 focused verification command 可直接执行 |
