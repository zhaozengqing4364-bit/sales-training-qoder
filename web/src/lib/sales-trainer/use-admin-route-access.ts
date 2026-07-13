"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerAdminCapabilities } from "@/lib/api/types";
import { salesTrainerAdminCapabilitiesQueryOptions } from "@/lib/query/sales-trainer-admin";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";

export interface SalesTrainerAdminRouteAccess {
    capabilities: SalesTrainerAdminCapabilities | null;
    canAccess: boolean;
    denialMessage: string | null;
    error: string | null;
    isLoading: boolean;
    reloadCapabilities: () => void;
}

const DEFAULT_DENIAL_MESSAGE = "当前账号无权访问该新人训练管理页面。";

export function useSalesTrainerAdminRouteAccess(pathname: string): SalesTrainerAdminRouteAccess {
    const query = useQuery(salesTrainerAdminCapabilitiesQueryOptions());
    const capabilities = query.data ?? null;
    const error = query.error ? getApiErrorMessage(query.error) : null;
    const isLoading = query.isPending;

    const canAccess = useMemo(
        () => isSalesTrainerAdminPathAllowedForCapabilities(pathname, capabilities),
        [capabilities, pathname],
    );

    return {
        capabilities,
        canAccess,
        denialMessage: isLoading || canAccess ? null : error ?? DEFAULT_DENIAL_MESSAGE,
        error,
        isLoading,
        reloadCapabilities: () => {
            void query.refetch();
        },
    };
}
