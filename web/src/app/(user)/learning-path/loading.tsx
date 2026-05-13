import { LearnerRouteLoadingState } from "@/components/learner/learner-route-loading-state";

export default function LearningPathLoading() {
    return (
        <LearnerRouteLoadingState
            label="正在加载学习路径"
            hint="正在准备你的下一步训练路径..."
            className="max-w-6xl"
        >
            <div className="space-y-6">
                <div className="animate-pulse rounded-3xl border border-slate-200 bg-white/70 p-6">
                    <div className="h-5 w-28 rounded-full bg-slate-100" />
                    <div className="mt-4 h-10 w-56 rounded bg-slate-100" />
                    <div className="mt-3 h-4 w-full max-w-xl rounded bg-slate-100" />
                </div>
                <div className="animate-pulse rounded-3xl border border-slate-200 bg-white/70 p-6">
                    <div className="h-5 w-28 rounded bg-slate-100" />
                    <div className="mt-4 h-8 w-64 rounded bg-slate-100" />
                    <div className="mt-3 h-4 w-72 rounded bg-slate-100" />
                </div>
                <div className="grid gap-4">
                    <div className="h-28 animate-pulse rounded-3xl border border-slate-200 bg-white/70" />
                    <div className="h-28 animate-pulse rounded-3xl border border-slate-200 bg-white/70" />
                    <div className="h-28 animate-pulse rounded-3xl border border-slate-200 bg-white/70" />
                </div>
            </div>
        </LearnerRouteLoadingState>
    );
}
