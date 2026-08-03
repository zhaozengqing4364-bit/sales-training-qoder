import Link from "next/link";
import { CheckCircle2, Clock3, TriangleAlert } from "lucide-react";

import type { FoundationActivityViewModel } from "@/lib/newcomer-training/view-models";

export function ActivityResultPanel({ detail }: { detail: FoundationActivityViewModel }) {
    const outcome = detail.outcome;
    const completed = outcome?.lifecycle_result === "completed" || detail.runner.status === "completed";
    const failed = outcome?.passed === false;
    const processing = detail.display.is_processing;
    const title = completed && !failed
        ? "活动已完成"
        : failed
          ? "这次还未通过"
          : processing
            ? "已提交，正在处理"
            : "结果等待复核";
    const description = completed && !failed
        ? "结果已记录，返回训练路径继续下一项任务。"
        : failed
          ? "查看反馈后可按照训练路径安排重新练习。"
          : processing
            ? "评分完成后会自动更新训练进度，当前答案已经保留。"
            : "复核完成后会更新训练进度。";
    const Icon = completed && !failed ? CheckCircle2 : failed ? TriangleAlert : Clock3;

    return <section aria-live="polite" data-motion-kind="spatial" className={`motion-result-reveal rounded-2xl border p-5 ${completed && !failed ? "border-emerald-200 bg-emerald-50" : failed ? "border-amber-200 bg-amber-50" : "border-blue-200 bg-blue-50"}`}>
        <div className="flex items-start gap-3">
            <Icon className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
                <h2 className="font-semibold text-slate-900">{title}</h2>
                <p className="mt-1 text-sm text-slate-600">{description}</p>
                {typeof outcome?.score === "number" ? <p className="mt-3 text-2xl font-semibold text-slate-900">{outcome.score} / {outcome.max_score ?? 100}</p> : null}
            </div>
        </div>
        <div className="mt-4"><Link className="inline-flex h-10 items-center rounded-full bg-slate-900 px-4 text-sm font-medium text-white" href="/newcomer-training">返回训练路径</Link></div>
    </section>;
}
