import { queryOptions } from "@tanstack/react-query";

import { api } from "@/lib/api/client";

export const salesTrainerAdminQueryKeys = {
    capabilities: ["admin", "sales-trainer", "capabilities"] as const,
};

export function salesTrainerAdminCapabilitiesQueryOptions() {
    return queryOptions({
        queryKey: salesTrainerAdminQueryKeys.capabilities,
        queryFn: () => api.admin.salesTrainer.getCapabilities(),
        staleTime: 5 * 60_000,
        gcTime: 15 * 60_000,
        retry: false,
    });
}
