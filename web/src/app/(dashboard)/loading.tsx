import { DashboardSkeleton } from "@/components/dashboard-skeleton";
import { LearnerRouteLoadingState } from "@/components/learner/learner-route-loading-state";

export default function DashboardLoading() {
    return (
        <LearnerRouteLoadingState
            label="正在加载训练与复盘页面"
            hint="正在准备训练与复盘页面..."
            className="max-w-none px-0 py-0"
        >
            <DashboardSkeleton />
        </LearnerRouteLoadingState>
    );
}
