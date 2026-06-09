"use client";

import type { SalesTrainerPath, SalesTrainerUnit } from "@/lib/api/types";
import { buildModuleViews } from "@/lib/sales-trainer/module-path";

interface SalesTrainerModuleMissionPanelProps {
    readonly path: SalesTrainerPath;
    readonly unitsById: ReadonlyMap<string, SalesTrainerUnit>;
}

function buildModuleHint(path: SalesTrainerPath, unitsById: ReadonlyMap<string, SalesTrainerUnit>): string {
    const modules = buildModuleViews(path, new Map(unitsById));
    const enabledModules = modules.filter((module) => !module.disabled);
    if (enabledModules.length === 0) {
        return "当前没有开放模块，请联系管理员补齐模块配置。";
    }
    if (enabledModules.length === 1) {
        return `当前开放模块：${enabledModules[0]?.title ?? "未命名模块"}。`;
    }
    return `当前开放顺序：${enabledModules.map((module) => module.title).join(" → ")}。`;
}

export function SalesTrainerModuleMissionPanel({
    path,
    unitsById,
}: SalesTrainerModuleMissionPanelProps) {
    return (
        <div className="rounded-lg bg-slate-900 p-5 text-white">
            <p className="text-xs font-semibold text-slate-300">开始训练</p>
            <h3 className="mt-2 text-xl font-black">选择下方模块开始训练</h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
                已开放模块可随时进入，无强制解锁。{buildModuleHint(path, unitsById)}
            </p>
        </div>
    );
}
