import type { TrainingPathPayload } from "@/lib/api/types/newcomer-training";

export function PathPreview({ path }: { path: TrainingPathPayload }) {
    const modules = path.phases.flatMap((phase) => phase.modules);
    const activities = modules.flatMap((module) => module.activities);
    const next = activities[0] ?? null;
    return <section role="region" aria-label="学员预览" className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">学员预览</p>
        <h2 className="mt-2 text-lg font-semibold text-slate-900">{path.title || "未命名训练路径"}</h2>
        <p className="mt-1 text-sm text-slate-500">{path.phases.length} 个阶段 · {modules.length} 个模块 · {activities.length} 个活动</p>
        <div className="mt-4 rounded-xl bg-slate-900 p-4 text-white">
            <p className="text-xs text-slate-300">下一步</p>
            <p className="mt-1 font-medium">{next?.title ?? "发布后为学员推荐第一个活动"}</p>
        </div>
        <ol className="mt-4 space-y-2">
            {path.phases.map((phase) => <li key={phase.phase_id} className="rounded-xl bg-slate-50 px-3 py-2 text-sm"><span className="font-medium text-slate-800">{phase.title}</span><span className="ml-2 text-slate-500">{phase.modules.length} 个模块</span></li>)}
        </ol>
    </section>;
}
