"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
    BookOpen,
    Boxes,
    ClipboardCheck,
    FileQuestion,
    Gauge,
    Rocket,
    Settings,
    Users,
} from "lucide-react";

import { api, getApiErrorMessage } from "@/lib/api/client";
import type { FoundationAdminCapability } from "@/lib/api/types/foundation-admin";
import { cn } from "@/lib/utils";

const WORKSPACES: Array<{
    href: string;
    label: string;
    capability: FoundationAdminCapability;
    icon: typeof Gauge;
}> = [
    { href: "/admin/newcomer-training", label: "总览与待办", capability: "view_overview", icon: Gauge },
    { href: "/admin/newcomer-training/paths", label: "路径与版本", capability: "edit_paths", icon: Boxes },
    { href: "/admin/newcomer-training/content", label: "内容", capability: "edit_content", icon: BookOpen },
    { href: "/admin/newcomer-training/questions", label: "题库审核", capability: "review_questions", icon: FileQuestion },
    { href: "/admin/newcomer-training/cohorts", label: "学员与班级", capability: "manage_cohorts", icon: Users },
    { href: "/admin/newcomer-training/assessments", label: "评测任务", capability: "retry_assessments", icon: ClipboardCheck },
    { href: "/admin/newcomer-training/reviews", label: "达标复核", capability: "review_readiness", icon: ClipboardCheck },
    { href: "/admin/newcomer-training/releases", label: "发布记录", capability: "publish_releases", icon: Rocket },
    { href: "/admin/newcomer-training/settings", label: "治理设置", capability: "govern_ai", icon: Settings },
];

export function useFoundationAdminCapabilities() {
    return useQuery({
        queryKey: ["foundation-admin", "capabilities"],
        queryFn: () => api.admin.newcomerTraining.getCapabilities(),
        staleTime: 60_000,
        retry: 1,
    });
}

export function FoundationAdminWorkspaceNav() {
    const pathname = usePathname();
    const query = useFoundationAdminCapabilities();
    if (query.isPending) {
        return <div className="h-12 animate-pulse rounded-2xl bg-slate-100" aria-label="正在加载工作区权限" />;
    }
    if (query.error || !query.data) {
        return (
            <div role="alert" className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                工作区权限加载失败：{getApiErrorMessage(query.error)}
                <button type="button" className="ml-3 font-semibold underline" onClick={() => void query.refetch()}>
                    重新加载
                </button>
            </div>
        );
    }
    const allowed = new Set(query.data.capabilities);
    const items = WORKSPACES.filter((item) => allowed.has(item.capability));
    const active = items
        .filter((item) => pathname === item.href || (item.href !== "/admin/newcomer-training" && pathname.startsWith(`${item.href}/`)))
        .sort((left, right) => right.href.length - left.href.length)[0]?.href;
    return (
        <nav aria-label="新人训练管理工作区" className="overflow-x-auto rounded-2xl border border-slate-200 bg-white p-1 shadow-sm">
            <div className="flex min-w-max gap-1">
                {items.map((item) => {
                    const Icon = item.icon;
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            prefetch={false}
                            className={cn(
                                "inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium",
                                active === item.href ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100 hover:text-slate-950",
                            )}
                        >
                            <Icon className="h-4 w-4" aria-hidden />
                            {item.label}
                        </Link>
                    );
                })}
            </div>
        </nav>
    );
}

export function FoundationAdminPermissionState({ capability }: { capability: FoundationAdminCapability }) {
    const query = useFoundationAdminCapabilities();
    if (query.isPending) return <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">正在确认工作区权限…</div>;
    if (query.error || !query.data?.capabilities.includes(capability)) {
        return (
            <div role="alert" className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-950">
                <h2 className="font-semibold">当前账号不能访问此工作区</h2>
                <p className="mt-2 text-sm">{query.data?.permission_help ?? getApiErrorMessage(query.error)}</p>
            </div>
        );
    }
    return null;
}

export function FoundationAdminCapabilityBoundary({
    capability,
    children,
}: {
    capability: FoundationAdminCapability | FoundationAdminCapability[];
    children: ReactNode;
}) {
    const query = useFoundationAdminCapabilities();
    const requested = Array.isArray(capability) ? capability : [capability];
    if (query.isPending) {
        return (
            <div
                aria-busy="true"
                aria-label="正在确认工作区权限"
                className="space-y-3 rounded-2xl border border-slate-200 bg-white p-6"
            >
                <div className="h-5 w-40 animate-pulse rounded bg-slate-100" />
                <div className="h-16 animate-pulse rounded-xl bg-slate-100" />
            </div>
        );
    }
    if (query.error || !query.data) {
        return (
            <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-950">
                <h2 className="font-semibold">工作区权限暂时无法确认</h2>
                <p className="mt-2 text-sm">{getApiErrorMessage(query.error)}</p>
                <button type="button" className="mt-4 text-sm font-semibold underline" onClick={() => void query.refetch()}>
                    重新确认权限
                </button>
            </div>
        );
    }
    if (!requested.some((item) => query.data.capabilities.includes(item))) {
        return (
            <div role="alert" className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-950">
                <h2 className="font-semibold">当前账号不能访问此工作区</h2>
                <p className="mt-2 text-sm">{query.data.permission_help}</p>
            </div>
        );
    }
    return children;
}
