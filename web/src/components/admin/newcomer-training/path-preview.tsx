import type { TrainingPathPayload } from "@/lib/api/types/newcomer-training";
import { LearnerMissionCard } from "@/components/newcomer-training/learner-mission-card";
import { missionFromCandidate } from "@/lib/newcomer-training/learner-mission";

export function PathPreview({ path }: { path: TrainingPathPayload }) {
    const modules = path.phases.flatMap((phase) => phase.modules);
    const activities = modules.flatMap((module) => module.activities);
    const mission = missionFromCandidate(path);
    return <section role="region" aria-label="学员预览" className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"><div><p className="font-semibold text-slate-900">新学员初始视角</p><p className="mt-0.5 text-slate-500">使用与正式学员页面相同的任务组件</p></div><span className="rounded-full bg-slate-100 px-3 py-1 text-slate-600">{path.phases.length} 阶段 · {modules.length} 模块 · {activities.length} 活动</span></div>
        {mission ? <LearnerMissionCard mission={mission} preview /> : <div className="rounded-3xl border border-dashed border-slate-300 bg-white p-10 text-center"><p className="font-semibold text-slate-900">还没有可预览的任务</p><p className="mt-2 text-sm text-slate-500">请先在阶段中添加至少一个模块和活动。</p></div>}
    </section>;
}
