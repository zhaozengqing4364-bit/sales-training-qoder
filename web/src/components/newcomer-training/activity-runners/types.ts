import type { FoundationActivityWorkspace } from "@/lib/api/types/newcomer-training";
import type { FoundationActivityViewModel } from "@/lib/newcomer-training/view-models";

export interface ActivityRunnerProps {
    detail: FoundationActivityViewModel;
    onRefresh?: (detail: FoundationActivityWorkspace) => void;
}
