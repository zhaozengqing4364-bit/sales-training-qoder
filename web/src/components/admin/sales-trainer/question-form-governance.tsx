import type { SalesTrainerStatus } from "@/lib/api/types";

export function canEditQuestionRevision(status: SalesTrainerStatus | undefined): boolean {
    return status !== "archived";
}

export function QuestionPublishedRevisionGuidance() {
    return (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
            <p className="font-semibold">编辑将生成题目新修订</p>
            <p className="mt-1 text-emerald-800">
                保存修改会进入待发布修订；发布后只影响后续组卷和后续学员作答，已提交考试记录继续保留当时题目快照。
                正确答案、分值、通过线和 AI 评分 prompt 变化属于高风险评分规则变更。
            </p>
        </div>
    );
}

export function QuestionArchivedReadOnlyGuidance() {
    return (
        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            归档题目仅用于审计和历史追溯，不能继续编辑；需要恢复使用时请在历史版本中执行回滚。
        </div>
    );
}
