import { LearnerRouteLoadingState } from "@/components/learner/learner-route-loading-state";

export default function AuthLoading() {
    return (
        <LearnerRouteLoadingState
            label="正在加载登录与密码找回页面"
            hint="正在准备认证页面..."
            className="max-w-md"
        >
            <div className="space-y-4 animate-pulse rounded-[2rem] border border-white/50 bg-white/70 p-8 shadow-card md:p-10">
                <div className="mx-auto h-14 w-14 rounded-2xl bg-slate-100" />
                <div className="space-y-3 text-center">
                    <div className="mx-auto h-8 w-40 rounded bg-slate-100" />
                    <div className="mx-auto h-4 w-64 max-w-full rounded bg-slate-100" />
                </div>
                <div className="space-y-3">
                    <div className="h-12 rounded-full bg-slate-100" />
                    <div className="h-12 rounded-full bg-slate-100" />
                    <div className="h-12 rounded-full bg-slate-100" />
                </div>
            </div>
        </LearnerRouteLoadingState>
    );
}
