"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerAdminCapabilities } from "@/lib/api/types";
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
    const [capabilities, setCapabilities] = useState<SalesTrainerAdminCapabilities | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [reloadToken, setReloadToken] = useState(0);

    const reloadCapabilities = useCallback(() => {
        setIsLoading(true);
        setError(null);
        setReloadToken((current) => current + 1);
    }, []);

    useEffect(() => {
        let isCurrent = true;
        void api.admin.salesTrainer.getCapabilities()
            .then((result) => {
                if (!isCurrent) return;
                setCapabilities(result);
                setError(null);
            })
            .catch((loadError) => {
                if (!isCurrent) return;
                setCapabilities(null);
                setError(getApiErrorMessage(loadError));
            })
            .finally(() => {
                if (!isCurrent) return;
                setIsLoading(false);
            });
        return () => {
            isCurrent = false;
        };
    }, [reloadToken]);

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
        reloadCapabilities,
    };
}
