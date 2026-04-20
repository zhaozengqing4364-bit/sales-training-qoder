# M018: Performance / dependency / recovery baselines

## Vision
把审计里“像问题但未证实”的性能、安全、容灾类条目转成有证据的后续 backlog，让慢查询、索引、依赖漏洞、许可证、备份恢复现状都有真实基线，而不是被伪装成已知 fix。

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | S01 | medium | — | ✅ | 有一份 query/index baseline，后续优化 backlog 基于真实证据而不是 audit 猜测。 |
| S02 | S02 | low | — | ✅ | 仓库里有可执行的依赖扫描与升级策略文档/流程。 |
| S03 | S03 | medium | — | ✅ | 有一份按当前部署现状可执行的 backup/recovery runbook。 |
