import { queryOptions } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

const defaults = { staleTime: 5 * 60_000, gcTime: 10 * 60_000, retry: false } as const;
export const teamQueryKeys = { all: ["team", "newcomer-training"] as const, journeys: (limit: number, offset: number) => ["team", "newcomer-training", "journeys", limit, offset] as const };
export function teamJourneysQueryOptions(limit = 50, offset = 0) { return queryOptions({ queryKey: teamQueryKeys.journeys(limit, offset), queryFn: () => api.admin.newcomerTraining.listLearners({ limit, offset }), ...defaults }); }
