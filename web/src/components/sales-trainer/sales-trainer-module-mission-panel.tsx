"use client";

import { MODULE_SUGGESTED_ORDER_HINT } from "@/lib/sales-trainer/module-path";

export function SalesTrainerModuleMissionPanel() {
    return (
        <div className="rounded-lg bg-slate-900 p-5 text-white">
            <p className="text-xs font-semibold text-slate-300">开始训练</p>
            <h3 className="mt-2 text-xl font-black">选择下方模块开始训练</h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
                三个模块均可随时进入，无强制解锁。{MODULE_SUGGESTED_ORDER_HINT}
            </p>
        </div>
    );
}
