"use client";

import Link from "next/link";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerAdminCapabilities } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { getSalesTrainerAdminContextNavGroupForCapabilities } from "@/lib/sales-trainer/routes";

export {
    SALES_TRAINER_ADMIN_WORKBENCH_LINKS,
    filterSalesTrainerAdminRouteItemsForCapabilities,
} from "@/lib/sales-trainer/routes";

interface SalesTrainerAdminModuleNavProps {
    currentPath: string;
    capabilities?: SalesTrainerAdminCapabilities | null;
}

export function SalesTrainerAdminModuleNav({
    currentPath,
    capabilities: providedCapabilities,
}: SalesTrainerAdminModuleNavProps) {
    const [loadedCapabilities, setLoadedCapabilities] =
        useState<SalesTrainerAdminCapabilities | null>(null);
    const [capabilityError, setCapabilityError] = useState<string | null>(null);
    const capabilities = providedCapabilities !== undefined
        ? providedCapabilities
        : loadedCapabilities;

    const loadCapabilities = useCallback(async () => {
        if (providedCapabilities !== undefined) {
            return;
        }
        setCapabilityError(null);
        try {
            const result = await api.admin.salesTrainer.getCapabilities();
            setLoadedCapabilities(result);
        } catch (error) {
            setLoadedCapabilities(null);
            setCapabilityError(getApiErrorMessage(error));
        }
    }, [providedCapabilities]);

    useEffect(() => {
        if (providedCapabilities !== undefined) {
            return;
        }
        let cancelled = false;
        api.admin.salesTrainer.getCapabilities()
            .then((result) => {
                if (!cancelled) {
                    setLoadedCapabilities(result);
                    setCapabilityError(null);
                }
            })
            .catch((error) => {
                if (!cancelled) {
                    setLoadedCapabilities(null);
                    setCapabilityError(getApiErrorMessage(error));
                }
            });
        return () => {
            cancelled = true;
        };
    }, [providedCapabilities]);

    if (capabilityError && providedCapabilities === undefined) {
        return (
            <div
                role="alert"
                className="flex flex-wrap items-center gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
            >
                <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
                <span className="font-semibold text-amber-950">销售训练导航权限加载失败</span>
                <span className="min-w-0 flex-1">{capabilityError}</span>
                <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="bg-white"
                    onClick={() => void loadCapabilities()}
                >
                    <RefreshCw className="mr-2 h-4 w-4" />
                    重新加载导航
                </Button>
            </div>
        );
    }

    const group = getSalesTrainerAdminContextNavGroupForCapabilities(
        currentPath,
        capabilities,
    );

    if (group.items.length < 2) {
        return null;
    }

    return (
        <nav
            aria-label={`${group.label}模块内导航`}
            className="w-full overflow-x-auto rounded-2xl border border-slate-200/70 bg-white/80 p-1 shadow-sm"
        >
            <div className="flex min-w-max items-center gap-1">
                <span className="px-3 text-xs font-semibold text-slate-400">
                    {group.label}
                </span>
                {group.items.map((item) => {
                    const Icon = item.icon;
                    const isActive = currentPath === item.href;
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={cn(
                                "inline-flex items-center gap-2 whitespace-nowrap rounded-xl px-3 py-2 text-sm font-medium transition-colors",
                                isActive
                                    ? "bg-slate-900 text-white"
                                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
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
