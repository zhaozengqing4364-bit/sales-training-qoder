import {
    Activity,
    BarChart3,
    BookOpen,
    Bot,
    ClipboardList,
    Eye,
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
    Sparkles,
    Tags,
    Target,
    UploadCloud,
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
        href: "/admin/sales-trainer",
    },
    units: {
        key: "units",
        label: "模块单元",
        icon: Target,
        href: "/admin/sales-trainer/units",
    },
    paths: {
        key: "paths",
        label: "路径配置",
        icon: Milestone,
        href: "/admin/sales-trainer/paths",
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
        label: "商务技巧文章",
        icon: BookOpen,
        href: "/admin/sales-trainer/articles",
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
        label: "配置",
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
    SALES_TRAINER_ADMIN_ROUTES.workbench,
    SALES_TRAINER_ADMIN_ROUTES.units,
    SALES_TRAINER_ADMIN_ROUTES.paths,
    SALES_TRAINER_ADMIN_ROUTES.aiCoach,
    SALES_TRAINER_ADMIN_ROUTES.questions,
    SALES_TRAINER_ADMIN_ROUTES.scoreStandards,
    SALES_TRAINER_ADMIN_ROUTES.articles,
    SALES_TRAINER_ADMIN_ROUTES.papers,
    SALES_TRAINER_ADMIN_ROUTES.materials,
] as const satisfies readonly SalesTrainerAdminRouteItem[];

export const SALES_TRAINER_ADMIN_RECORD_NAV_ITEMS = [
    SALES_TRAINER_ADMIN_ROUTES.trainingRecords,
    SALES_TRAINER_ADMIN_ROUTES.audioSubmissions,
    SALES_TRAINER_ADMIN_ROUTES.scoreResults,
    SALES_TRAINER_ADMIN_ROUTES.analytics,
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
            SALES_TRAINER_ADMIN_ROUTES.workbench,
            SALES_TRAINER_ADMIN_ROUTES.aiCoach,
            SALES_TRAINER_ADMIN_ROUTES.scoreStandards,
            SALES_TRAINER_ADMIN_ROUTES.articles,
            SALES_TRAINER_ADMIN_ROUTES.papers,
            SALES_TRAINER_ADMIN_ROUTES.materials,
        ],
    },
    {
        capability: "manage_modules",
        items: [SALES_TRAINER_ADMIN_ROUTES.units, SALES_TRAINER_ADMIN_ROUTES.paths],
    },
    {
        capability: "manage_prompts",
        items: [SALES_TRAINER_ADMIN_ROUTES.aiCoach],
    },
    {
        capability: "manage_questions",
        items: [SALES_TRAINER_ADMIN_ROUTES.questions],
    },
    {
        capability: "view_records",
        items: SALES_TRAINER_ADMIN_RECORD_NAV_ITEMS,
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
        capability: "view_records",
        roots: ["/admin/sales-trainer/quiz-attempts"],
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
    const allowedHrefs = salesTrainerAdminItemsForCapabilities(capabilities)
        .map((item) => item.href);
    return items.filter((item) =>
        allowedHrefs.some((href) =>
            item.href === href
            || (
                href !== SALES_TRAINER_ADMIN_ROUTES.workbench.href
                && item.href.startsWith(`${href}/`)
            ),
        ),
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
    const visibleRouteAllowed = salesTrainerAdminItemsForCapabilities(capabilities)
        .some((item) =>
            currentPath === item.href
            || (
                item.href !== SALES_TRAINER_ADMIN_ROUTES.workbench.href
                && currentPath.startsWith(`${item.href}/`)
            ),
        );
    if (visibleRouteAllowed) {
        return true;
    }
    return SALES_TRAINER_ADMIN_CAPABILITY_ACCESS_ROOTS.some((entry) =>
        capabilities.capabilities[entry.capability]
        && entry.roots.some((root) =>
            currentPath === root || currentPath.startsWith(`${root}/`),
        ),
    );
}

export const SALES_TRAINER_ADMIN_CONTEXT_NAV_GROUPS: readonly SalesTrainerAdminContextNavGroup[] = [
    {
        root: "/admin/sales-trainer/units",
        label: "模块单元",
        items: [SALES_TRAINER_ADMIN_ROUTES.units],
    },
    {
        root: "/admin/sales-trainer/questions",
        label: "题目生产",
        items: [
            {
                key: "questionBank",
                href: "/admin/sales-trainer/questions",
                label: "正式题目库",
                icon: BookOpen,
            },
            {
                key: "questionDrafts",
                href: "/admin/sales-trainer/questions/drafts",
                label: "AI 出题审核",
                icon: Sparkles,
            },
            {
                key: "questionCategories",
                href: "/admin/sales-trainer/questions/categories",
                label: "题目分类",
                icon: Tags,
            },
            {
                key: "quizPreview",
                href: "/admin/sales-trainer/questions/quiz-preview",
                label: "小测预览",
                icon: Eye,
            },
        ],
    },
    {
        root: "/admin/sales-trainer/score-standards",
        label: "录音评分标准",
        items: [
            {
                key: "scoreStandards",
                href: "/admin/sales-trainer/score-standards",
                label: "标准列表",
                icon: SlidersHorizontal,
            },
        ],
    },
    {
        root: "/admin/sales-trainer/paths",
        label: "路径配置",
        roots: ["/admin/sales-trainer/paths", "/admin/sales-trainer/ai-coach"],
        items: [
            {
                ...SALES_TRAINER_ADMIN_ROUTES.paths,
                icon: Route,
            },
            SALES_TRAINER_ADMIN_ROUTES.aiCoach,
        ],
    },
    {
        root: "/admin/sales-trainer/articles",
        label: "商务技巧文章",
        items: [
            {
                key: "articleBindings",
                href: "/admin/sales-trainer/articles",
                label: "文章绑定",
                icon: FileText,
            },
            {
                key: "articleImport",
                href: "/admin/sales-trainer/articles/import",
                label: "资料导入",
                icon: UploadCloud,
            },
            {
                key: "articleCapabilities",
                href: "/admin/sales-trainer/articles/capabilities",
                label: "能力点",
                icon: Target,
            },
        ],
    },
    {
        root: "/admin/sales-trainer/papers",
        label: "考卷管理",
        items: [SALES_TRAINER_ADMIN_ROUTES.papers],
    },
    {
        root: "/admin/sales-trainer/materials",
        label: "材料库",
        items: [SALES_TRAINER_ADMIN_ROUTES.materials],
    },
    {
        root: "/admin/sales-trainer/training-records",
        label: "训练记录",
        items: [SALES_TRAINER_ADMIN_ROUTES.trainingRecords],
    },
    {
        root: "/admin/sales-trainer/audio-submissions",
        label: "学员录音",
        items: [
            {
                ...SALES_TRAINER_ADMIN_ROUTES.audioSubmissions,
                label: "录音列表",
                icon: Mic,
            },
        ],
    },
    {
        root: "/admin/sales-trainer/score-results",
        label: "评分结果",
        items: [
            {
                ...SALES_TRAINER_ADMIN_ROUTES.scoreResults,
                icon: Headphones,
            },
        ],
    },
    {
        root: "/admin/sales-trainer/analytics",
        label: "Journey 分析",
        items: [SALES_TRAINER_ADMIN_ROUTES.analytics],
    },
    {
        root: "/admin/sales-trainer/settings",
        label: "配置",
        items: [
            {
                ...SALES_TRAINER_ADMIN_ROUTES.settings,
                label: "配置健康",
            },
        ],
    },
    {
        root: "/admin/sales-trainer/operation-logs",
        label: "操作日志",
        items: [SALES_TRAINER_ADMIN_ROUTES.operationLogs],
    },
    {
        root: "/admin/sales-trainer",
        label: "工作台",
        items: [SALES_TRAINER_ADMIN_ROUTES.workbench],
    },
] as const;

export const SALES_TRAINER_ADMIN_WORKBENCH_LINKS =
    SALES_TRAINER_ADMIN_CONTEXT_NAV_GROUPS
        .filter((group) => group.root !== "/admin/sales-trainer")
        .map((group) => group.items[0]);

export function isSalesTrainerAdminPathInGroup(
    currentPath: string,
    root: string,
): boolean {
    if (root === "/admin/sales-trainer") {
        return currentPath === root;
    }
    return currentPath === root || currentPath.startsWith(`${root}/`);
}

export function getSalesTrainerAdminContextNavGroup(
    currentPath: string,
): SalesTrainerAdminContextNavGroup {
    return SALES_TRAINER_ADMIN_CONTEXT_NAV_GROUPS.find((group) =>
        (group.roots ?? [group.root]).some((root) =>
            isSalesTrainerAdminPathInGroup(currentPath, root),
        ),
    )
        ?? SALES_TRAINER_ADMIN_CONTEXT_NAV_GROUPS[
            SALES_TRAINER_ADMIN_CONTEXT_NAV_GROUPS.length - 1
        ];
}

export function getSalesTrainerAdminContextNavGroupForCapabilities(
    currentPath: string,
    capabilities: SalesTrainerAdminCapabilities | null | undefined,
): SalesTrainerAdminContextNavGroup {
    const group = getSalesTrainerAdminContextNavGroup(currentPath);
    return {
        ...group,
        items: filterSalesTrainerAdminRouteItemsForCapabilities(
            group.items,
            capabilities,
        ),
    };
}
