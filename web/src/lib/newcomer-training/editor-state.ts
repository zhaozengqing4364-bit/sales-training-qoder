import type {
    ActivityConfig,
    ModuleConfig,
    PhaseConfig,
    TrainingPathPayload,
} from "@/lib/api/types/newcomer-training";

export type IdFactory = () => string;
export type MovePosition = "before" | "after";
export type EditorSelection =
    | { kind: "path" }
    | { kind: "phase"; phase_id: string }
    | { kind: "module"; module_id: string }
    | { kind: "activity"; activity_id: string };

type Ordered = { order_index: number };

export function normalizeOrder<T extends Ordered>(items: readonly T[]): T[] {
    return items.map((item, index) => ({ ...item, order_index: index + 1 }));
}

export function addPhase(path: TrainingPathPayload, phase: PhaseConfig): TrainingPathPayload {
    return { ...path, phases: normalizeOrder([...path.phases, phase]) };
}

export function addModule(
    path: TrainingPathPayload,
    phaseId: string,
    module: ModuleConfig,
): TrainingPathPayload {
    return mapPhase(path, phaseId, (phase) => ({
        ...phase,
        modules: normalizeOrder([...phase.modules, module]),
    }));
}

export function addActivity(
    path: TrainingPathPayload,
    moduleId: string,
    activity: ActivityConfig,
): TrainingPathPayload {
    return mapModule(path, moduleId, (module) => ({
        ...module,
        activities: normalizeOrder([...module.activities, activity]),
    }));
}

export function duplicatePhase(
    path: TrainingPathPayload,
    phaseId: string,
    nextId: IdFactory,
): TrainingPathPayload {
    const index = path.phases.findIndex((phase) => phase.phase_id === phaseId);
    if (index < 0) return path;
    const duplicate = clonePhase(path.phases[index], nextId);
    const phases = [...path.phases];
    phases.splice(index + 1, 0, duplicate);
    return { ...path, phases: normalizeOrder(phases) };
}

export function duplicateModule(
    path: TrainingPathPayload,
    moduleId: string,
    nextId: IdFactory,
): TrainingPathPayload {
    return mapContainingModule(path, moduleId, (modules, index) => {
        const duplicate = cloneModule(modules[index], nextId);
        const next = [...modules];
        next.splice(index + 1, 0, duplicate);
        return normalizeOrder(next);
    });
}

export function duplicateActivity(
    path: TrainingPathPayload,
    activityId: string,
    nextId: IdFactory,
): TrainingPathPayload {
    return mapContainingActivity(path, activityId, (activities, index) => {
        const duplicate = cloneActivity(activities[index], nextId());
        const next = [...activities];
        next.splice(index + 1, 0, duplicate);
        return normalizeOrder(next);
    });
}

export function deletePhase(path: TrainingPathPayload, phaseId: string): TrainingPathPayload {
    return {
        ...path,
        phases: normalizeOrder(path.phases.filter((phase) => phase.phase_id !== phaseId)),
    };
}

export function deleteModule(path: TrainingPathPayload, moduleId: string): TrainingPathPayload {
    return {
        ...path,
        phases: path.phases.map((phase) => ({
            ...phase,
            modules: normalizeOrder(phase.modules.filter((module) => module.module_id !== moduleId)),
        })),
    };
}

export function deleteActivity(path: TrainingPathPayload, activityId: string): TrainingPathPayload {
    return {
        ...path,
        phases: path.phases.map((phase) => ({
            ...phase,
            modules: phase.modules.map((module) => ({
                ...module,
                activities: normalizeOrder(
                    module.activities.filter((activity) => activity.activity_id !== activityId),
                ),
            })),
        })),
    };
}

export function movePhase(
    path: TrainingPathPayload,
    phaseId: string,
    position: MovePosition,
    targetPhaseId: string,
): TrainingPathPayload {
    return { ...path, phases: moveSibling(path.phases, "phase_id", phaseId, position, targetPhaseId) };
}

export function moveModule(
    path: TrainingPathPayload,
    moduleId: string,
    position: MovePosition,
    targetModuleId: string,
): TrainingPathPayload {
    return mapContainingModule(path, moduleId, (modules) =>
        moveSibling(modules, "module_id", moduleId, position, targetModuleId),
    );
}

export function moveActivity(
    path: TrainingPathPayload,
    activityId: string,
    position: MovePosition,
    targetActivityId: string,
): TrainingPathPayload {
    return mapContainingActivity(path, activityId, (activities) =>
        moveSibling(activities, "activity_id", activityId, position, targetActivityId),
    );
}

export function updateSelectedObject(
    path: TrainingPathPayload,
    selection: EditorSelection,
    patch: Record<string, unknown>,
): TrainingPathPayload {
    if (selection.kind === "path") return { ...path, ...patch } as TrainingPathPayload;
    if (selection.kind === "phase") {
        return mapPhase(path, selection.phase_id, (phase) => ({ ...phase, ...patch } as PhaseConfig));
    }
    if (selection.kind === "module") {
        return mapModule(path, selection.module_id, (module) => ({ ...module, ...patch } as ModuleConfig));
    }
    return mapActivity(path, selection.activity_id, (activity) => ({
        ...activity,
        ...patch,
    } as ActivityConfig));
}

export function collectPathIds(path: TrainingPathPayload): {
    phaseIds: string[];
    moduleIds: string[];
    activityIds: string[];
} {
    return {
        phaseIds: path.phases.map((phase) => phase.phase_id),
        moduleIds: path.phases.flatMap((phase) => phase.modules.map((module) => module.module_id)),
        activityIds: path.phases.flatMap((phase) =>
            phase.modules.flatMap((module) => module.activities.map((activity) => activity.activity_id)),
        ),
    };
}

function clonePhase(phase: PhaseConfig, nextId: IdFactory): PhaseConfig {
    return {
        ...phase,
        phase_id: nextId(),
        title: `${phase.title}（副本）`,
        modules: phase.modules.map((module) => cloneModule(module, nextId)),
    };
}

function cloneModule(module: ModuleConfig, nextId: IdFactory): ModuleConfig {
    const activityIds = new Map(module.activities.map((activity) => [activity.activity_id, nextId()]));
    return {
        ...module,
        module_id: nextId(),
        title: `${module.title}（副本）`,
        prerequisites: [],
        completion_policy: {
            ...module.completion_policy,
            activity_ids: module.completion_policy.activity_ids.map((id) => activityIds.get(id) ?? id),
        },
        activities: module.activities.map((activity) => ({
            ...cloneActivity(activity, activityIds.get(activity.activity_id) as string),
            prerequisites: activity.prerequisites.map((id) => activityIds.get(id) ?? id),
        })),
    };
}

function cloneActivity(activity: ActivityConfig, activityId: string): ActivityConfig {
    return {
        ...activity,
        activity_id: activityId,
        title: `${activity.title}（副本）`,
        config: { ...activity.config },
    } as ActivityConfig;
}

function moveSibling<T extends Ordered, K extends keyof T>(
    items: readonly T[],
    key: K,
    sourceId: T[K],
    position: MovePosition,
    targetId: T[K],
): T[] {
    const sourceIndex = items.findIndex((item) => item[key] === sourceId);
    const targetIndex = items.findIndex((item) => item[key] === targetId);
    if (sourceIndex < 0 || targetIndex < 0 || sourceIndex === targetIndex) return [...items];
    const next = [...items];
    const [source] = next.splice(sourceIndex, 1);
    const adjustedTarget = next.findIndex((item) => item[key] === targetId);
    next.splice(adjustedTarget + (position === "after" ? 1 : 0), 0, source);
    return normalizeOrder(next);
}

function mapPhase(
    path: TrainingPathPayload,
    phaseId: string,
    mapper: (phase: PhaseConfig) => PhaseConfig,
): TrainingPathPayload {
    return { ...path, phases: path.phases.map((phase) => phase.phase_id === phaseId ? mapper(phase) : phase) };
}

function mapModule(
    path: TrainingPathPayload,
    moduleId: string,
    mapper: (module: ModuleConfig) => ModuleConfig,
): TrainingPathPayload {
    return {
        ...path,
        phases: path.phases.map((phase) => ({
            ...phase,
            modules: phase.modules.map((module) => module.module_id === moduleId ? mapper(module) : module),
        })),
    };
}

function mapActivity(
    path: TrainingPathPayload,
    activityId: string,
    mapper: (activity: ActivityConfig) => ActivityConfig,
): TrainingPathPayload {
    return {
        ...path,
        phases: path.phases.map((phase) => ({
            ...phase,
            modules: phase.modules.map((module) => ({
                ...module,
                activities: module.activities.map((activity) =>
                    activity.activity_id === activityId ? mapper(activity) : activity),
            })),
        })),
    };
}

function mapContainingModule(
    path: TrainingPathPayload,
    moduleId: string,
    mapper: (modules: ModuleConfig[], index: number) => ModuleConfig[],
): TrainingPathPayload {
    return {
        ...path,
        phases: path.phases.map((phase) => {
            const index = phase.modules.findIndex((module) => module.module_id === moduleId);
            return index < 0 ? phase : { ...phase, modules: mapper(phase.modules, index) };
        }),
    };
}

function mapContainingActivity(
    path: TrainingPathPayload,
    activityId: string,
    mapper: (activities: ActivityConfig[], index: number) => ActivityConfig[],
): TrainingPathPayload {
    return {
        ...path,
        phases: path.phases.map((phase) => ({
            ...phase,
            modules: phase.modules.map((module) => {
                const index = module.activities.findIndex((activity) => activity.activity_id === activityId);
                return index < 0 ? module : { ...module, activities: mapper(module.activities, index) };
            }),
        })),
    };
}
