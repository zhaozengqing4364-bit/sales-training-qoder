import type { ActivityDetailResponse } from "@/lib/api/types/newcomer-training";
export interface ActivityRunnerProps { detail: ActivityDetailResponse; onRefresh?: (detail: ActivityDetailResponse) => void; }
