import Link from "next/link";
import { CheckCircle2, Clock3, RotateCcw, TriangleAlert } from "lucide-react";

export function ActivityResultPanel({
    status,
    completed,
    passed,
    score,
    maxScore,
    moduleId,
}: {
    status: string;
    completed: boolean;
    passed?: boolean | null;
    score?: number | null;
    maxScore?: number | null;
    moduleId: string;
}) {
    const failed = status === "failed" || passed === false;
    const title = completed ? "活动已完成" : failed ? "这次还未通过" : "已提交，正在处理";
    const description = completed
        ? "结果已记录，返回模块继续下一项训练。"
        : failed
          ? "查看反馈后可以在当前页面重新练习。"
          : "评分完成后会自动更新训练进度，你可以先返回模块。";
    const Icon = completed ? CheckCircle2 : failed ? TriangleAlert : Clock3;
    return <section aria-live="polite" data-motion-kind="spatial" className={`motion-result-reveal rounded-2xl border p-5 ${completed ? "border-emerald-200 bg-emerald-50" : failed ? "border-amber-200 bg-amber-50" : "border-blue-200 bg-blue-50"}`}>
        <div className="flex items-start gap-3"><Icon className="mt-0.5 h-5 w-5 shrink-0" /><div><h2 className="font-semibold text-slate-900">{title}</h2><p className="mt-1 text-sm text-slate-600">{description}</p>{typeof score === "number" ? <p className="mt-3 text-2xl font-semibold text-slate-900">{score} / {maxScore ?? 100}</p> : null}</div></div>
        <div className="mt-4 flex flex-wrap gap-2"><Link className="inline-flex h-10 items-center rounded-full bg-slate-900 px-4 text-sm font-medium text-white" href={`/newcomer-training/modules/${encodeURIComponent(moduleId)}`}>返回模块</Link>{failed ? <span className="inline-flex items-center gap-1 text-sm text-amber-800"><RotateCcw className="h-4 w-4" />可在下方重试</span> : null}</div>
    </section>;
}
