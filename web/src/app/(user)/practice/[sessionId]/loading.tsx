import { LearnerRouteLoadingState } from "@/components/learner/learner-route-loading-state";

export default function PracticeSessionLoading() {
    return (
        <LearnerRouteLoadingState
            label="正在加载训练会话"
            hint="正在准备训练会话..."
            className="max-w-6xl"
        >
            <div className="grid min-h-[70vh] gap-6 md:grid-cols-[minmax(0,1fr)_22rem]">
                <div className="space-y-4">
                    <div className="animate-pulse rounded-3xl border border-slate-200 bg-white/70 p-4 md:p-6">
                        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                            <div className="space-y-2">
                                <div className="h-6 w-36 rounded bg-slate-100" />
                                <div className="h-4 w-56 max-w-full rounded bg-slate-100" />
                            </div>
                            <div className="flex gap-2">
                                <div className="h-9 w-24 rounded-full bg-slate-100" />
                                <div className="h-9 w-24 rounded-full bg-slate-100" />
                            </div>
                        </div>
                    </div>
                    <div className="animate-pulse space-y-4 rounded-3xl border border-slate-200 bg-white/70 p-4 md:p-6">
                        <div className="grid gap-3 md:grid-cols-3">
                            <div className="h-24 rounded-2xl bg-slate-100" />
                            <div className="h-24 rounded-2xl bg-slate-100" />
                            <div className="h-24 rounded-2xl bg-slate-100" />
                        </div>
                        <div className="h-64 rounded-3xl bg-slate-100" />
                        <div className="mx-auto h-16 w-16 rounded-full bg-slate-100 md:h-20 md:w-20" />
                    </div>
                </div>
                <div className="hidden animate-pulse rounded-3xl border border-slate-200 bg-white/60 p-6 md:block">
                    <div className="space-y-4">
                        <div className="h-6 w-32 rounded bg-slate-100" />
                        <div className="h-28 rounded-2xl bg-slate-100" />
                        <div className="h-40 rounded-2xl bg-slate-100" />
                        <div className="h-32 rounded-2xl bg-slate-100" />
                    </div>
                </div>
            </div>
        </LearnerRouteLoadingState>
    );
}
