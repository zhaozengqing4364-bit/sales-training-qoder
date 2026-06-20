# Project Governance Checkpoints

本页固定 `project-governance-refactor` Ultra Loop 的证据流。它不是新的发布门禁；完整发布门禁仍以 `scripts/critical-quality-gate.sh` 为唯一 executable truth。

## Evidence Root

- 本计划证据根目录：`.omo/evidence/project-governance-refactor/`
- Full gate 原始输出：`.sisyphus/evidence/task-9-quality-gate.txt`
- Full gate 镜像索引：`.omo/evidence/project-governance-refactor/quality-gate/`

## Gate Types

| Gate | 用途 | 证据命名 |
| --- | --- | --- |
| focused gate | 单个任务的最小相关测试、lint、typecheck 或契约检查 | `.omo/evidence/project-governance-refactor/task-<N>-<slug>.txt` |
| slice gate | 一组已完成任务的后端、前端、迁移或脚本组合检查 | `.omo/evidence/project-governance-refactor/slices/<slice>-<slug>.txt` |
| release gate | 发布候选前的完整质量门禁 | `.sisyphus/evidence/task-9-quality-gate.txt`，并镜像到 `.omo/evidence/project-governance-refactor/quality-gate/` |

## Commands

每轮开始或切换任务时，先记录 dry checkpoint：

```bash
bash scripts/project-governance-checkpoint.sh dry-checkpoint \
  .omo/evidence/project-governance-refactor/task-4-dry-checkpoint.txt
```

focused gate 直接把真实命令输出写入任务证据，不允许只写总结：

```bash
{ cd backend && venv/bin/python -m pytest <focused-tests> --no-cov -q; } \
  2>&1 | tee .omo/evidence/project-governance-refactor/task-<N>-<slug>.txt
```

release gate 只能运行现有 full gate：

```bash
bash scripts/critical-quality-gate.sh
bash scripts/project-governance-checkpoint.sh mirror-quality-gate
```

## Mirror Rule

`.sisyphus/evidence/task-9-quality-gate.txt` 是 full gate 原始事实。`.omo/evidence/project-governance-refactor/quality-gate/task-9-quality-gate.txt` 只是镜像，`index.md` 记录 source、mirror、mirror time 和 sha256。后续 release verification 只能引用这条原始事实或其镜像索引，不得维护第二套互相独立的 Go/No-Go 结论。

## Failure Rule

- focused gate 失败：保留失败输出，先判断是否本任务引入。
- slice gate 失败：不得进入下一波依赖任务，除非失败被明确归类为既有环境阻塞且有替代 focused evidence。
- release gate 失败：不得宣称发布可用；保存 `.sisyphus` 原始输出并镜像/索引到 `.omo` 后再分类。
