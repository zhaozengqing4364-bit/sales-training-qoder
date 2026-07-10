# Gate 1A Architecture Fitness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Completed on 2026-07-10. This closes the architecture guard Gate only;
Gate 0B/0C, Gate 1B, and the dependency-removal migrations remain open.

**Evidence:** The current AST inventory is 49 cross-package edges and one
12-package baseline SCC, with `supervisor` separate. Changed-file Ruff passed;
the architecture and retained boundary suite finished with
`36 passed, 1 warning`; the CLI passes from both repo root and `backend/`.
The temporary `sales_bot -> supervisor` probe produced both the unexpected-edge
and expanded-SCC violations, was deleted, and the CLI returned to green.
Core work commits: `2e04bd77` and `0a1010ff`.

**Goal:** 把当前后端跨包依赖和强连通分量转化为可执行 CI 合同，禁止新增边、扩大循环和永久例外。

**Architecture:** 使用仓库内纯 Python AST 扫描静态 import 与字面量 dynamic import；目标允许边和临时例外写入 YAML policy；Tarjan SCC 检查允许现有大 SCC 缩小但不允许扩大。CodeGraph 继续用于理解和影响分析，CI 不依赖 `.codegraph` 索引状态。

**Tech Stack:** Python 3.12 标准库、PyYAML、pytest、Bash。

## Global Constraints

- 不新增第三方依赖。
- 扫描必须确定性、离线、从 repo root 或 backend 目录均能定位文件。
- `TYPE_CHECKING`、函数内 import 也计为代码依赖；字面量 `import_module`/`__import__` 计入。
- 非字面量 plugin path 暂不由 AST guard 推断，继续由 runtime plugin contract 测试保护。
- 当前例外只能缩减；新增例外必须修改 ADR/policy 并给出 owner、reason、retire_when、expires_on。
- 不因当前 12 包 SCC 而一次性移动业务代码；本 Gate 只建立护栏。

---

## File Map

- `backend/scripts/architecture_dependency_guard.py`：扫描、policy 校验、SCC 和 CLI。
- `backend/tests/unit/test_architecture_dependency_guard.py`：扫描器和当前仓库 policy 回归。
- `docs/architecture/module-dependency-policy.yaml`：目标允许边、临时例外和 SCC 基线。
- `docs/architecture.md`：说明 executable policy 与迁移状态。
- `scripts/critical-quality-gate.sh`：在主门禁运行 guard。

### Task 1: 用测试定义 import graph 和 SCC 算法

**Files:**
- Create: `backend/tests/unit/test_architecture_dependency_guard.py`
- Create later in Task 2: `backend/scripts/architecture_dependency_guard.py`

**Interfaces:**
- Produces contract: `collect_edges(src_root, packages) -> dict[Edge, set[str]]`；`strongly_connected_components(packages, edges) -> list[frozenset[str]]`。
- `Edge` 是 `tuple[str, str]`，分别为 source package 和 target package。

- [x] **Step 1: 创建失败测试**

创建 `backend/tests/unit/test_architecture_dependency_guard.py`：

```python
from __future__ import annotations

from pathlib import Path

from scripts.architecture_dependency_guard import (
    collect_edges,
    strongly_connected_components,
    validate_repository,
)


def _write(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_should_collect_static_local_typing_and_literal_dynamic_imports(tmp_path) -> None:
    src = tmp_path / "src"
    _write(
        src / "alpha" / "module.py",
        """
from typing import TYPE_CHECKING
import beta.service

if TYPE_CHECKING:
    from gamma.types import Contract

def load():
    from delta.runtime import Runtime
    return __import__("epsilon.adapter")
""",
    )
    for package in ("beta", "gamma", "delta", "epsilon"):
        _write(src / package / "module.py", "")

    edges = collect_edges(
        src,
        {"alpha", "beta", "gamma", "delta", "epsilon"},
    )

    assert set(edges) == {
        ("alpha", "beta"),
        ("alpha", "gamma"),
        ("alpha", "delta"),
        ("alpha", "epsilon"),
    }


def test_should_find_strongly_connected_components() -> None:
    edges = {
        ("alpha", "beta"),
        ("beta", "alpha"),
        ("beta", "gamma"),
    }

    components = strongly_connected_components(
        {"alpha", "beta", "gamma"},
        edges,
    )

    assert frozenset({"alpha", "beta"}) in components
    assert frozenset({"gamma"}) in components


def test_current_repository_dependency_policy_is_valid() -> None:
    violations = validate_repository()

    assert violations == []
```

- [x] **Step 2: 运行测试确认缺少实现**

Run:

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml \
  tests/unit/test_architecture_dependency_guard.py -q --no-cov
```

Expected: FAIL with `ModuleNotFoundError: scripts.architecture_dependency_guard`。

### Task 2: 实现离线 architecture guard

**Files:**
- Create: `backend/scripts/architecture_dependency_guard.py`

**Interfaces:**
- Consumes: `docs/architecture/module-dependency-policy.yaml`。
- Produces: `validate_repository(...) -> list[str]` 和 CLI `--check`。

- [x] **Step 1: 创建完整实现**

创建 `backend/scripts/architecture_dependency_guard.py`：

```python
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

Edge = tuple[str, str]
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SRC_ROOT = REPO_ROOT / "backend" / "src"
DEFAULT_POLICY = REPO_ROOT / "docs" / "architecture" / "module-dependency-policy.yaml"


def _literal_dynamic_import(node: ast.Call) -> str | None:
    if not node.args:
        return None
    first = node.args[0]
    if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
        return None
    func = node.func
    direct = isinstance(func, ast.Name) and func.id in {
        "import_module",
        "__import__",
    }
    attribute = isinstance(func, ast.Attribute) and func.attr in {
        "import_module",
        "__import__",
    }
    return first.value if direct or attribute else None


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Call):
            dynamic = _literal_dynamic_import(node)
            if dynamic:
                modules.add(dynamic)
    return modules


def collect_edges(
    src_root: Path,
    packages: set[str],
) -> dict[Edge, set[str]]:
    edges: dict[Edge, set[str]] = defaultdict(set)
    for source in sorted(packages):
        package_root = src_root / source
        if not package_root.exists():
            continue
        for path in sorted(package_root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            for module in _imported_modules(path):
                target = module.split(".", 1)[0]
                if target in packages and target != source:
                    edges[(source, target)].add(path.relative_to(src_root).as_posix())
    return dict(edges)


def strongly_connected_components(
    packages: Iterable[str],
    edges: Iterable[Edge],
) -> list[frozenset[str]]:
    graph: dict[str, set[str]] = {package: set() for package in packages}
    for source, target in edges:
        graph.setdefault(source, set()).add(target)
        graph.setdefault(target, set())

    index = 0
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[frozenset[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indexes[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for target in sorted(graph[node]):
            if target not in indexes:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indexes[target])

        if lowlinks[node] != indexes[node]:
            return
        component: set[str] = set()
        while stack:
            target = stack.pop()
            on_stack.remove(target)
            component.add(target)
            if target == node:
                break
        components.append(frozenset(component))

    for package in sorted(graph):
        if package not in indexes:
            visit(package)
    return components


def _edge(value: Sequence[str]) -> Edge:
    if len(value) != 2:
        raise ValueError(f"Dependency edge must contain source and target: {value}")
    return str(value[0]), str(value[1])


def _temporary_edges(policy: dict[str, Any]) -> tuple[set[Edge], list[str]]:
    edges: set[Edge] = set()
    violations: list[str] = []
    today = date.today()
    for group in policy.get("temporary_edges", []):
        source = str(group.get("source", "")).strip()
        owner = str(group.get("owner", "")).strip()
        reason = str(group.get("reason", "")).strip()
        retire_when = str(group.get("retire_when", "")).strip()
        expires_on = str(group.get("expires_on", "")).strip()
        targets = {str(target).strip() for target in group.get("targets", [])}
        required_values = (source, targets, owner, reason, retire_when, expires_on)
        if not all(required_values):
            violations.append(f"Incomplete temporary dependency group: {group}")
            continue
        try:
            expiry = date.fromisoformat(expires_on)
        except ValueError:
            violations.append(f"Invalid expires_on for {source}: {expires_on}")
            continue
        if expiry < today:
            violations.append(
                f"Expired temporary dependency group {source}->{sorted(targets)} "
                f"owned by {owner}: {expires_on}"
            )
        edges.update((source, target) for target in targets)
    return edges, violations


def validate_repository(
    *,
    src_root: Path = DEFAULT_SRC_ROOT,
    policy_path: Path = DEFAULT_POLICY,
) -> list[str]:
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    packages = {str(item) for item in policy["packages"]}
    actual_with_locations = collect_edges(src_root, packages)
    actual = set(actual_with_locations)
    stable = {_edge(item) for item in policy.get("stable_edges", [])}
    temporary, violations = _temporary_edges(policy)

    unexpected = sorted(actual - stable - temporary)
    for source, target in unexpected:
        locations = sorted(actual_with_locations[(source, target)])
        violations.append(
            f"Unexpected dependency {source}->{target}: {', '.join(locations)}"
        )

    stale = sorted(temporary - actual)
    for source, target in stale:
        violations.append(
            f"Stale temporary dependency exception {source}->{target}; "
            "remove it from policy"
        )

    baseline_sccs = [
        frozenset(str(item) for item in component)
        for component in policy.get("baseline_sccs", [])
    ]
    current_sccs = [
        component
        for component in strongly_connected_components(packages, actual)
        if len(component) > 1
    ]
    for component in current_sccs:
        if not any(component <= baseline for baseline in baseline_sccs):
            violations.append(
                "Expanded strongly connected component: "
                + ", ".join(sorted(component))
            )
    return sorted(violations)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check backend module dependencies")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate repository policy",
    )
    parser.add_argument("--src-root", type=Path, default=DEFAULT_SRC_ROOT)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    violations = validate_repository(
        src_root=args.src_root.resolve(),
        policy_path=args.policy.resolve(),
    )
    if violations:
        for violation in violations:
            print(f"[architecture] {violation}")
        return 1
    print("[architecture] dependency policy satisfied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 2: 运行算法单测，预期只因 policy 尚不存在失败**

Run: 使用 Task 1 Step 2 相同命令。
Expected: 前两个测试通过；repository policy 测试因缺 YAML 失败。

### Task 3: 写入目标 DAG、临时边和 SCC 基线

**Files:**
- Create: `docs/architecture/module-dependency-policy.yaml`

**Interfaces:**
- Produces: architecture guard 的唯一 policy authority。
- Consumes: 当前 13 个顶层包和审计得到的 49 条跨包边。

- [x] **Step 1: 创建 policy**

创建 `docs/architecture/module-dependency-policy.yaml`：

```yaml
version: 1
packages:
  - admin
  - agent
  - common
  - curriculum_analytics
  - curriculum_practice
  - evaluation
  - presentation_coach
  - prompt_templates
  - sales_bot
  - sales_trainer
  - supervisor
  - support
  - training_runtime

stable_edges:
  - [admin, common]
  - [agent, common]
  - [curriculum_analytics, common]
  - [curriculum_practice, common]
  - [curriculum_practice, evaluation]
  - [evaluation, common]
  - [evaluation, prompt_templates]
  - [presentation_coach, common]
  - [prompt_templates, common]
  - [sales_bot, common]
  - [sales_trainer, common]
  - [sales_trainer, prompt_templates]
  - [supervisor, common]
  - [supervisor, evaluation]
  - [support, common]
  - [training_runtime, common]

temporary_edges:
  - source: admin
    targets: [agent, curriculum_analytics, curriculum_practice, presentation_coach, sales_bot, sales_trainer, support]
    owner: platform-architecture
    reason: admin currently aggregates domain governance and runtime diagnostics
    retire_when: admin is delivery-only and each domain exposes a governance port
    expires_on: 2026-10-31
  - source: agent
    targets: [support]
    owner: agent-platform
    reason: agent diagnostics still consume support projections
    retire_when: diagnostics are provided through a neutral observability port
    expires_on: 2026-10-31
  - source: common
    targets: [agent, curriculum_practice, evaluation, prompt_templates]
    owner: platform-architecture
    reason: shared kernel still owns transitional domain projections and composition helpers
    retire_when: common contains only stable kernel types and ports
    expires_on: 2026-10-31
  - source: curriculum_practice
    targets: [admin, agent, sales_trainer, support]
    owner: curriculum-practice
    reason: curriculum publishing and runtime still use transitional governance and content adapters
    retire_when: Roleplay Contract, Configuration Governance and asset ports are neutral
    expires_on: 2026-10-31
  - source: evaluation
    targets: [admin, curriculum_practice, presentation_coach, sales_bot]
    owner: evaluation
    reason: report composition still imports scenario and governance implementations
    retire_when: evaluation consumes only evidence, roleplay and scenario evaluation ports
    expires_on: 2026-10-31
  - source: presentation_coach
    targets: [agent, evaluation, prompt_templates, sales_bot, support]
    owner: presentation-coach
    reason: presentation StepFun runtime inherits sales shared implementation and report helpers
    retire_when: presentation uses RealtimeSessionEngine composition and evidence ports
    expires_on: 2026-10-31
  - source: sales_bot
    targets: [agent, curriculum_practice, evaluation, prompt_templates, sales_trainer, support, training_runtime]
    owner: realtime-platform
    reason: sales realtime still composes provider, roleplay, scoring and runtime selection internally
    retire_when: provider, roleplay, evaluation and scenario hooks are neutral seams
    expires_on: 2026-10-31
  - source: sales_trainer
    targets: [curriculum_practice]
    owner: sales-trainer
    reason: controlled legacy content adapter remains active
    retire_when: curriculum adapter retirement conditions in ADR 2026-06-20 are met
    expires_on: 2026-10-31
  - source: supervisor
    targets: [curriculum_practice]
    owner: supervisor
    reason: supervisor projection still reads curriculum implementation details
    retire_when: supervisor consumes evaluation and training journey projections only
    expires_on: 2026-10-31
  - source: support
    targets: [agent]
    owner: support
    reason: support diagnostics still read agent implementation details
    retire_when: agent diagnostics are registered through observability contributors
    expires_on: 2026-10-31

baseline_sccs:
  - [admin, agent, common, curriculum_analytics, curriculum_practice, evaluation, presentation_coach, prompt_templates, sales_bot, sales_trainer, support, training_runtime]
```

- [x] **Step 2: 运行 policy test 和 CLI**

Run:

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml \
  tests/unit/test_architecture_dependency_guard.py -q --no-cov
.venv/bin/python scripts/architecture_dependency_guard.py --check
```

Expected: 3 passed；CLI 输出 `dependency policy satisfied`。

- [x] **Step 3: 人为验证新增边会失败，然后撤销探针**

临时创建 `backend/src/sales_bot/_architecture_guard_probe.py`：

```python
import supervisor
```

Run:

```bash
cd backend
.venv/bin/python scripts/architecture_dependency_guard.py --check
```

Expected: 非零退出，并同时报告 `Unexpected dependency sales_bot->supervisor` 和扩大
SCC。随后删除临时 probe 文件，重新运行必须通过。该探针不得提交。

- [x] **Step 4: 提交 guard 和 policy 变更包**

```bash
git add backend/scripts/architecture_dependency_guard.py \
  backend/tests/unit/test_architecture_dependency_guard.py \
  docs/architecture/module-dependency-policy.yaml
git commit -m "test(architecture): guard module edges and dependency cycles"
```

### Task 4: 把 executable policy 接入架构文档和主门禁

**Files:**
- Modify: `docs/architecture.md:899`
- Modify: `scripts/critical-quality-gate.sh:632`

**Interfaces:**
- Consumes: canonical `critical-quality-gate.sh`。
- Produces: 主门禁中的 architecture fitness check。

- [x] **Step 1: 更新架构文档，区分目标和当前过渡态**

在 `docs/architecture.md` 模块边界表后加入：

```markdown
### 17.1 可执行依赖政策

`docs/architecture/module-dependency-policy.yaml` 是模块依赖的 CI 权威。表中的
`stable_edges` 表达目标允许方向；`temporary_edges` 是当前迁移例外，必须包含 owner、
原因、退役条件和到期日。`backend/scripts/architecture_dependency_guard.py --check`
禁止新增跨包边、扩大现有强连通分量、保留已经消失的例外或使用过期例外。

当前仍存在一个包含 12 个包的历史 SCC，因此本节描述的是受控迁移目标，而不是声称
代码已经满足无环结构。每删除一条临时边，必须在同一变更中收缩 policy。
```

- [x] **Step 2: 在 Backend ruff 后接入 architecture guard**

向 `scripts/critical-quality-gate.sh` 加入：

```bash
log "Backend architecture dependency guard"
(
  cd "${ROOT_DIR}/backend"
  "${PYTHON_BIN}" scripts/architecture_dependency_guard.py --check
)
```

并向 `BACKEND_GATE_TARGETS` 加入：

```bash
  "tests/unit/test_architecture_dependency_guard.py"
```

- [x] **Step 3: 运行完整 Gate 1A 验证**

Run:

```bash
cd backend
.venv/bin/python -m ruff check \
  scripts/architecture_dependency_guard.py \
  tests/unit/test_architecture_dependency_guard.py
.venv/bin/python -m pytest -c pyproject.toml \
  tests/unit/test_architecture_dependency_guard.py \
  tests/unit/test_runtime_dependency_contract.py \
  tests/unit/test_newcomer_training_path_boundary.py \
  tests/unit/common/test_knowledge_import_boundaries.py \
  -q --no-cov
.venv/bin/python scripts/architecture_dependency_guard.py --check
```

Expected: ruff exit 0；architecture/boundary tests 全部通过；CLI exit 0。

- [x] **Step 4: 提交文档和门禁变更包**

```bash
git add docs/architecture.md scripts/critical-quality-gate.sh
git commit -m "ci: enforce executable module dependency policy"
```

## Self-Review Checklist

- [x] 当前 49 条边全部被 stable 或 temporary policy 解释。
- [x] 当前 12 包 SCC 可通过，但 supervisor 加入会失败。
- [x] 新增同一 SCC 内的额外边也会因 unexpected edge 失败。
- [x] 删除临时边而忘记清 policy 会因 stale exception 失败。
- [x] policy 到期会失败，不存在永久 allowlist。
- [x] 未引入 CodeGraph CI 依赖或第三方图算法库。
- [x] 本 Gate 没有移动业务代码或改变运行时行为。
