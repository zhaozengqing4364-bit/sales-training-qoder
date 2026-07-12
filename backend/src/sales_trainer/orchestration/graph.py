"""Pure structural validation for a path revision aggregate."""

from __future__ import annotations

from dataclasses import dataclass

from sales_trainer.orchestration.contracts import TrainingPathPayload


@dataclass(frozen=True, slots=True)
class PathIssue:
    code: str
    message: str
    object_id: str
    field_path: str
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class _Node:
    object_id: str
    field_path: str
    prerequisites: tuple[str, ...]


def _duplicate_order_issues(
    *,
    object_ids_and_orders: list[tuple[str, int]],
    field_path_prefix: str,
) -> list[PathIssue]:
    issues: list[PathIssue] = []
    seen: set[int] = set()
    for index, (object_id, order_index) in enumerate(object_ids_and_orders):
        if order_index in seen:
            issues.append(
                PathIssue(
                    code="duplicate_order_index",
                    message="同一层级的排序序号不能重复。",
                    object_id=object_id,
                    field_path=f"{field_path_prefix}[{index}].order_index",
                )
            )
        seen.add(order_index)
    return issues


def _cycle_members(nodes: dict[str, _Node]) -> set[str]:
    index = 0
    indexes: dict[str, int] = {}
    low_links: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    members: set[str] = set()

    def visit(object_id: str) -> None:
        nonlocal index
        indexes[object_id] = index
        low_links[object_id] = index
        index += 1
        stack.append(object_id)
        on_stack.add(object_id)

        for prerequisite_id in nodes[object_id].prerequisites:
            if prerequisite_id not in nodes:
                continue
            if prerequisite_id not in indexes:
                visit(prerequisite_id)
                low_links[object_id] = min(
                    low_links[object_id],
                    low_links[prerequisite_id],
                )
            elif prerequisite_id in on_stack:
                low_links[object_id] = min(
                    low_links[object_id],
                    indexes[prerequisite_id],
                )

        if low_links[object_id] != indexes[object_id]:
            return
        component: list[str] = []
        while stack:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == object_id:
                break
        if len(component) > 1:
            members.update(component)
        elif object_id in nodes[object_id].prerequisites:
            members.add(object_id)

    for object_id in nodes:
        if object_id not in indexes:
            visit(object_id)
    return members


def validate_path_graph(payload: TrainingPathPayload) -> tuple[PathIssue, ...]:
    issues: list[PathIssue] = []
    nodes: dict[str, _Node] = {}
    duplicate_ids: set[str] = set()

    issues.extend(
        _duplicate_order_issues(
            object_ids_and_orders=[
                (phase.phase_id, phase.order_index) for phase in payload.phases
            ],
            field_path_prefix="phases",
        )
    )

    def register(node: _Node) -> None:
        if node.object_id in nodes:
            duplicate_ids.add(node.object_id)
            issues.append(
                PathIssue(
                    code="duplicate_object_id",
                    message="阶段、模块和活动标识必须在路径版本内唯一。",
                    object_id=node.object_id,
                    field_path=f"{node.field_path}.{_id_field(node.field_path)}",
                )
            )
            return
        nodes[node.object_id] = node

    for phase_index, phase in enumerate(payload.phases):
        phase_path = f"phases[{phase_index}]"
        register(
            _Node(
                object_id=phase.phase_id,
                field_path=phase_path,
                prerequisites=(),
            )
        )
        issues.extend(
            _duplicate_order_issues(
                object_ids_and_orders=[
                    (module.module_id, module.order_index) for module in phase.modules
                ],
                field_path_prefix=f"{phase_path}.modules",
            )
        )
        for module_index, module in enumerate(phase.modules):
            module_path = f"{phase_path}.modules[{module_index}]"
            register(
                _Node(
                    object_id=module.module_id,
                    field_path=module_path,
                    prerequisites=tuple(module.prerequisites),
                )
            )
            issues.extend(
                _duplicate_order_issues(
                    object_ids_and_orders=[
                        (activity.activity_id, activity.order_index)
                        for activity in module.activities
                    ],
                    field_path_prefix=f"{module_path}.activities",
                )
            )
            activity_ids = {activity.activity_id for activity in module.activities}
            if module.completion_policy.mode == "at_least_count":
                configured_ids = module.completion_policy.activity_ids
                count = module.completion_policy.count
                if (
                    not configured_ids
                    or count is None
                    or count > len(configured_ids)
                    or not set(configured_ids).issubset(activity_ids)
                    or len(configured_ids) != len(set(configured_ids))
                ):
                    issues.append(
                        PathIssue(
                            code="completion_policy_invalid",
                            message="至少完成数量规则必须引用当前模块内的有效活动。",
                            object_id=module.module_id,
                            field_path=(
                                f"{module_path}.completion_policy.activity_ids"
                            ),
                        )
                    )
            for activity_index, activity in enumerate(module.activities):
                register(
                    _Node(
                        object_id=activity.activity_id,
                        field_path=(
                            f"{module_path}.activities[{activity_index}]"
                        ),
                        prerequisites=tuple(activity.prerequisites),
                    )
                )

    if not duplicate_ids:
        for node in nodes.values():
            missing = [
                prerequisite_id
                for prerequisite_id in node.prerequisites
                if prerequisite_id not in nodes
            ]
            if missing:
                issues.append(
                    PathIssue(
                        code="prerequisite_not_found",
                        message="前置条件引用了当前路径中不存在的对象。",
                        object_id=node.object_id,
                        field_path=f"{node.field_path}.prerequisites",
                    )
                )
        for object_id in sorted(_cycle_members(nodes)):
            node = nodes[object_id]
            issues.append(
                PathIssue(
                    code="cyclic_prerequisite",
                    message="前置条件存在循环依赖。",
                    object_id=object_id,
                    field_path=f"{node.field_path}.prerequisites",
                )
            )

    return tuple(
        sorted(
            issues,
            key=lambda issue: (issue.field_path, issue.code, issue.object_id),
        )
    )


def _id_field(field_path: str) -> str:
    if ".activities[" in field_path:
        return "activity_id"
    if ".modules[" in field_path:
        return "module_id"
    return "phase_id"
