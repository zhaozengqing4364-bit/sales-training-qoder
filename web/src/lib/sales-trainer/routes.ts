import {
    Activity,
    BarChart3,
    BookOpen,
    Bot,
    ClipboardCheck,
    ClipboardList,
    FileText,
    Headphones,
    LayoutDashboard,
    Library,
    ListChecks,
    Mic,
    Milestone,
    Route,
    ScrollText,
    Settings,
    SlidersHorizontal,
    Target,
    UploadCloud,
    Users,
    type LucideIcon,
} from "lucide-react";

import type {
    SalesTrainerAdminCapabilities,
    SalesTrainerAdminCapabilityKey,
} from "@/lib/api/types";

export interface SalesTrainerAdminRouteItem {
    readonly href: string;
    readonly icon: LucideIcon;
    readonly key: string;
    readonly label: string;
}

export interface SalesTrainerAdminContextNavGroup {
    readonly items: readonly SalesTrainerAdminRouteItem[];
    readonly label: string;
    readonly root: string;
    readonly roots?: readonly string[];
}

export const SALES_TRAINER_ADMIN_ROUTES = {
    workbench: {
        key: "workbench",
        label: "工作台",
        icon: LayoutDashboard,
        href: "/admin/newcomer-training/path",
    },
    audioManagement: {
        key: "audioManagement",
        label: "录音管理",
        icon: Mic,
        href: "/admin/sales-trainer/audio",
    },
    audioMaterials: {
        key: "audioMaterials",
        label: "材料",
        icon: Library,
        href: "/admin/sales-trainer/audio/materials",
    },
    audioScoreStandards: {
        key: "audioScoreStandards",
        label: "评分标准",
        icon: SlidersHorizontal,
        href: "/admin/sales-trainer/audio/score-standards",
    },
    audioSubmissionsInManagement: {
        key: "audioSubmissionsInManagement",
        label: "学员录音",
        icon: Activity,
        href: "/admin/sales-trainer/audio/submissions",
    },
    audioScoreResults: {
        key: "audioScoreResults",
        label: "评分结果",
        icon: Headphones,
        href: "/admin/sales-trainer/audio/results",
    },
    learningTopics: {
        key: "learningTopics",
        label: "学习专题",
        icon: BookOpen,
        href: "/admin/sales-trainer/learning-topics",
    },
    learningTopicQuestions: {
        key: "learningTopicQuestions",
        label: "题目",
        icon: FileText,
        href: "/admin/sales-trainer/learning-topics/questions",
    },
    learningTopicPapers: {
        key: "learningTopicPapers",
        label: "小测/考卷",
        icon: ClipboardList,
        href: "/admin/sales-trainer/learning-topics/papers",
    },
    trainingTasks: {
        key: "trainingTasks",
        label: "训练任务",
        icon: Target,
        href: "/admin/sales-trainer/training-tasks",
    },
    units: {
        key: "units",
        label: "模块单元",
        icon: Target,
        href: "/admin/sales-trainer/units",
    },
    paths: {
        key: "paths",
        label: "路径编排",
        icon: Milestone,
        href: "/admin/newcomer-training/path",
    },
    learnerProgress: {
        key: "learnerProgress",
        label: "学员进度",
        icon: Users,
        href: "/admin/newcomer-training/learners",
    },
    aiCoach: {
        key: "aiCoach",
        label: "AI 教练配置",
        icon: Bot,
        href: "/admin/sales-trainer/ai-coach",
    },
    questions: {
        key: "questions",
        label: "题库管理",
        icon: FileText,
        href: "/admin/sales-trainer/questions",
    },
    scoreStandards: {
        key: "scoreStandards",
        label: "录音评分标准",
        icon: Mic,
        href: "/admin/sales-trainer/score-standards",
    },
    articles: {
        key: "articles",
        label: "学习专题",
        icon: BookOpen,
        href: "/admin/sales-trainer/learning-topics",
    },
    papers: {
        key: "papers",
        label: "考卷管理",
        icon: ClipboardList,
        href: "/admin/sales-trainer/papers",
    },
    materials: {
        key: "materials",
        label: "材料库",
        icon: Library,
        href: "/admin/sales-trainer/materials",
    },
    trainingRecords: {
        key: "trainingRecords",
        label: "训练记录",
        icon: ListChecks,
        href: "/admin/sales-trainer/training-records",
    },
    readiness: {
        key: "readiness",
        label: "达标验收",
        icon: ClipboardCheck,
        href: "/admin/sales-trainer/readiness",
    },
    audioSubmissions: {
        key: "audioSubmissions",
        label: "学员录音",
        icon: Activity,
        href: "/admin/sales-trainer/audio-submissions",
    },
    scoreResults: {
        key: "scoreResults",
        label: "评分结果",
        icon: BarChart3,
        href: "/admin/sales-trainer/score-results",
    },
    analytics: {
        key: "analytics",
        label: "Journey 分析",
        icon: BarChart3,
        href: "/admin/sales-trainer/analytics",
    },
    settings: {
        key: "settings",
        label: "系统治理",
        icon: Settings,
        href: "/admin/sales-trainer/settings",
    },
    operationLogs: {
        key: "operationLogs",
        label: "操作记录",
        icon: ScrollText,
        href: "/admin/sales-trainer/operation-logs",
    },
} as const satisfies Record<string, SalesTrainerAdminRouteItem>;

export const SALES_TRAINER_ADMIN_CONTENT_NAV_ITEMS = [
    SALES_TRAINER_ADMIN_ROUTES.paths,
] as const satisfies readonly SalesTrainerAdminRouteItem[];

export const SALES_TRAINER_ADMIN_RECORD_NAV_ITEMS = [
    SALES_TRAINER_ADMIN_ROUTES.learnerProgress,
    SALES_TRAINER_ADMIN_ROUTES.readiness,
    SALES_TRAINER_ADMIN_ROUTES.trainingRecords,
    SALES_TRAINER_ADMIN_ROUTES.analytics,
] as const satisfies readonly SalesTrainerAdminRouteItem[];

const SALES_TRAINER_ADMIN_RECORD_CAPABILITY_NAV_ITEMS = [
    {
        ...SALES_TRAINER_ADMIN_ROUTES.audioSubmissionsInManagement,
        label: "录音管理",
        icon: Mic,
    },
    ...SALES_TRAINER_ADMIN_RECORD_NAV_ITEMS,
] as const satisfies readonly SalesTrainerAdminRouteItem[];

export const SALES_TRAINER_ADMIN_NAV_ITEMS = [
    ...SALES_TRAINER_ADMIN_CONTENT_NAV_ITEMS,
    ...SALES_TRAINER_ADMIN_RECORD_NAV_ITEMS,
    SALES_TRAINER_ADMIN_ROUTES.settings,
    SALES_TRAINER_ADMIN_ROUTES.operationLogs,
] as const satisfies readonly SalesTrainerAdminRouteItem[];

export const SALES_TRAINER_ADMIN_CAPABILITY_NAV = [
    {
        capability: "manage_content",
        items: [
            SALES_TRAINER_ADMIN_ROUTES.paths,
        ],
    },
    {
        capability: "manage_modules",
        items: [
            SALES_TRAINER_ADMIN_ROUTES.paths,
        ],
    },
    {
        capability: "manage_prompts",
        items: [
            SALES_TRAINER_ADMIN_ROUTES.paths,
        ],
    },
    {
        capability: "manage_questions",
        items: [SALES_TRAINER_ADMIN_ROUTES.paths],
    },
    {
        capability: "view_records",
        items: SALES_TRAINER_ADMIN_RECORD_CAPABILITY_NAV_ITEMS,
    },
    {
        capability: "view_settings",
        items: [SALES_TRAINER_ADMIN_ROUTES.settings],
    },
    {
        capability: "view_logs",
        items: [SALES_TRAINER_ADMIN_ROUTES.operationLogs],
    },
] as const satisfies ReadonlyArray<{
    readonly capability: SalesTrainerAdminCapabilityKey;
    readonly items: readonly SalesTrainerAdminRouteItem[];
}>;

const SALES_TRAINER_ADMIN_CAPABILITY_ACCESS_ROOTS = [
    {
        capability: "manage_content",
        roots: [
            "/admin/sales-trainer/audio/materials",
            "/admin/sales-trainer/audio/score-standards",
            "/admin/sales-trainer/score-standards",
            "/admin/sales-trainer/score-prompts",
            "/admin/sales-trainer/materials",
            "/admin/sales-trainer/learning-topics",
            "/admin/sales-trainer/articles",
            "/admin/sales-trainer/papers",
        ],
    },
    {
        capability: "manage_modules",
        roots: [
            "/admin/sales-trainer/audio",
            "/admin/sales-trainer/training-tasks",
            "/admin/sales-trainer/units",
            "/admin/newcomer-training/path",
            "/admin/sales-trainer/ai-coach",
            "/admin/sales-trainer/learning-topics",
            "/admin/sales-trainer/articles",
        ],
    },
    {
        capability: "manage_prompts",
        roots: [
            "/admin/sales-trainer/audio/score-standards",
            "/admin/sales-trainer/score-standards",
            "/admin/sales-trainer/score-prompts",
            "/admin/sales-trainer/ai-coach",
        ],
    },
    {
        capability: "manage_questions",
        roots: [
            "/admin/sales-trainer/learning-topics/questions",
            "/admin/sales-trainer/questions",
        ],
    },
    {
        capability: "view_records",
        roots: [
            "/admin/newcomer-training/learners",
            "/admin/sales-trainer/audio/submissions",
            "/admin/sales-trainer/audio/results",
            "/admin/sales-trainer/audio-submissions",
            "/admin/sales-trainer/score-results",
            "/admin/sales-trainer/quiz-attempts",
        ],
    },
] as const satisfies ReadonlyArray<{
    readonly capability: SalesTrainerAdminCapabilityKey;
    readonly roots: readonly string[];
}>;

export function salesTrainerAdminItemsForCapabilities(
    capabilities: SalesTrainerAdminCapabilities | null | undefined,
): SalesTrainerAdminRouteItem[] {
    if (!capabilities) {
        return [];
    }
    if (capabilities.capabilities.admin_full_access) {
        return [...SALES_TRAINER_ADMIN_NAV_ITEMS];
    }
    const items: SalesTrainerAdminRouteItem[] = [];
    const seen = new Set<string>();
    for (const entry of SALES_TRAINER_ADMIN_CAPABILITY_NAV) {
        if (!capabilities.capabilities[entry.capability]) {
            continue;
        }
        for (const item of entry.items) {
            if (seen.has(item.href)) {
                continue;
            }
            if ([...seen].some((href) =>
                href !== SALES_TRAINER_ADMIN_ROUTES.workbench.href
                && item.href.startsWith(`${href}/`),
            )) {
                continue;
            }
            seen.add(item.href);
            items.push(item);
        }
    }
    return items;
}

export function filterSalesTrainerAdminRouteItemsForCapabilities(
    items: readonly SalesTrainerAdminRouteItem[],
    capabilities: SalesTrainerAdminCapabilities | null | undefined,
): SalesTrainerAdminRouteItem[] {
    if (!capabilities) {
        return [];
    }
    if (capabilities.capabilities.admin_full_access) {
        return [...items];
    }
    return items.filter((item) =>
        isSalesTrainerAdminPathAllowedForCapabilities(item.href, capabilities),
    );
}

export function isSalesTrainerAdminPathAllowedForCapabilities(
    currentPath: string,
    capabilities: SalesTrainerAdminCapabilities | null | undefined,
): boolean {
    if (!capabilities) {
        return false;
    }
    if (capabilities.capabilities.admin_full_access) {
        return true;
    }
    const visibleRouteAllowed = salesTrainerAdminItemsForCapabilities(capabilities).some(
        (item) =>
            currentPath === item.href ||
            (item.href !== SALES_TRAINER_ADMIN_ROUTES.workbench.href &&
                currentPath.startsWith(`${item.href}/`)),
    );
    if (visibleRouteAllowed) {
        return true;
    }
    return SALES_TRAINER_ADMIN_CAPABILITY_ACCESS_ROOTS.some(
        (entry) =>
            capabilities.capabilities[entry.capability] &&
            entry.roots.some((root) => currentPath === root || currentPath.startsWith(`${root}/`)),
    );
}

export const SALES_TRAINER_ADMIN_CONTEXT_NAV_GROUPS: readonly SalesTrainerAdminContextNavGroup[] = [
    {
        root: "/admin/sales-trainer/audio",
        label: "录音管理",
        roots: [
            "/admin/sales-trainer/audio",
            "/admin/sales-trainer/training-tasks",
            "/admin/sales-trainer/materials",
            "/admin/sales-trainer/score-standards",
            "/admin/sales-trainer/score-prompts",
            "/admin/sales-trainer/audio-submissions",
            "/admin/sales-trainer/score-results",
        ],
        items: [
            SALES_TRAINER_ADMIN_ROUTES.audioManagement,
            SALES_TRAINER_ADMIN_ROUTES.audioMaterials,
            SALES_TRAINER_ADMIN_ROUTES.audioScoreStandards,
            {
                ...SALES_TRAINER_ADMIN_ROUTES.audioSubmissionsInManagement,
                icon: Mic,
            },
            SALES_TRAINER_ADMIN_ROUTES.audioScoreResults,
        ],
    },
    {
        root: "/admin/sales-trainer/learning-topics",
        label: "学习专题",
        roots: [
            "/admin/sales-trainer/learning-topics",
            "/admin/sales-trainer/articles",
            "/admin/sales-trainer/papers",
            "/admin/sales-trainer/questions",
        ],
        items: [
            SALES_TRAINER_ADMIN_ROUTES.learningTopics,
            {
                key: "learningTopicImport",
                href: "/admin/sales-trainer/learning-topics/import",
                label: "资料导入",
                icon: UploadCloud,
            },
            {
                key: "learningTopicCapabilities",
                href: "/admin/sales-trainer/learning-topics/capabilities",
                label: "能力点",
                icon: Target,
            },
            SALES_TRAINER_ADMIN_ROUTES.learningTopicQuestions,
            SALES_TRAINER_ADMIN_ROUTES.learningTopicPapers,
        ],
    },
    {
        root: "/admin/newcomer-training/path",
        label: "路径与达标",
        roots: [
            "/admin/newcomer-training/path",
            "/admin/newcomer-training/learners",
            "/admin/sales-trainer/units",
            "/admin/sales-trainer/ai-coach",
            "/admin/sales-trainer/readiness",
            "/admin/sales-trainer/training-records",
            "/admin/sales-trainer/analytics",
        ],
        items: [
            {
                ...SALES_TRAINER_ADMIN_ROUTES.paths,
                label: "路径配置",
                icon: Route,
            },
            SALES_TRAINER_ADMIN_ROUTES.learnerProgress,
            SALES_TRAINER_ADMIN_ROUTES.units,
            SALES_TRAINER_ADMIN_ROUTES.aiCoach,
            SALES_TRAINER_ADMIN_ROUTES.readiness,
            SALES_TRAINER_ADMIN_ROUTES.trainingRecords,
            SALES_TRAINER_ADMIN_ROUTES.analytics,
        ],
    },
    {
        root: "/admin/sales-trainer/settings",
        label: "系统治理",
        roots: [
            "/admin/sales-trainer/settings",
            "/admin/sales-trainer/operation-logs",
        ],
        items: [
            {
                ...SALES_TRAINER_ADMIN_ROUTES.settings,
                label: "配置健康",
            },
            SALES_TRAINER_ADMIN_ROUTES.operationLogs,
        ],
    },
    {
        root: "/admin/sales-trainer",
        label: "工作台",
        items: [SALES_TRAINER_ADMIN_ROUTES.workbench],
    },
] as const;

export const SALES_TRAINER_ADMIN_WORKBENCH_LINKS = SALES_TRAINER_ADMIN_CONTEXT_NAV_GROUPS.filter(
    (group) => group.root !== "/admin/sales-trainer",
).map((group) => group.items[0]);

export function isSalesTrainerAdminPathInGroup(currentPath: string, root: string): boolean {
    if (root === "/admin/sales-trainer") {
        return currentPath === root;
    }
    return currentPath === root || currentPath.startsWith(`${root}/`);
}

export function getSalesTrainerAdminContextNavGroup(
    currentPath: string,
): SalesTrainerAdminContextNavGroup {
    return (
        SALES_TRAINER_ADMIN_CONTEXT_NAV_GROUPS.find((group) =>
            (group.roots ?? [group.root]).some((root) =>
                isSalesTrainerAdminPathInGroup(currentPath, root),
            ),
        ) ??
        SALES_TRAINER_ADMIN_CONTEXT_NAV_GROUPS[SALES_TRAINER_ADMIN_CONTEXT_NAV_GROUPS.length - 1]
    );
}

export function getSalesTrainerAdminContextNavGroupForCapabilities(
    currentPath: string,
    capabilities: SalesTrainerAdminCapabilities | null | undefined,
): SalesTrainerAdminContextNavGroup {
    const group = getSalesTrainerAdminContextNavGroup(currentPath);
    return {
        ...group,
        items: filterSalesTrainerAdminRouteItemsForCapabilities(group.items, capabilities),
    };
}
