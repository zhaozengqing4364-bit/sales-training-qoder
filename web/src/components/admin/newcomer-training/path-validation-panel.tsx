import type { PathIssue, PathValidationResponse } from "@/lib/api/types/newcomer-training";

export function PathValidationPanel({ validation, onFocusIssue }: { validation: PathValidationResponse | null; onFocusIssue: (issue: PathIssue) => void }) {
    if (!validation) return <section aria-label="路径检查" className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">点击“检查并预览”查看发布条件。</section>;
    if (validation.issues.length === 0) return <section aria-label="路径检查" className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">路径配置完整，可以发布。</section>;
    return <section aria-label="路径检查" className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
        <h3 className="font-semibold text-amber-900">还有 {validation.issues.length} 项需要处理</h3>
        <ul className="mt-2 space-y-2">{validation.issues.map((issue, index) => <li key={`${issue.object_id}-${issue.field_path}-${index}`}><button type="button" className="text-left text-sm text-amber-900 underline decoration-amber-400 underline-offset-2" onClick={() => onFocusIssue(issue)}>{issue.message}</button></li>)}</ul>
    </section>;
}
