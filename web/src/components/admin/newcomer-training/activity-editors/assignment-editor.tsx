"use client";
import type { AssignmentActivity } from "@/lib/api/types/newcomer-training";
import { AdvancedSettings, NumberField, controlClass } from "./editor-fields";
import type { ActivityEditorProps } from "./types";

export function AssignmentEditor({ value, disabled, onChange }: ActivityEditorProps<AssignmentActivity>) {
    const patch = (config: Partial<AssignmentActivity["config"]>) => onChange({ ...value, config: { ...value.config, ...config } });
    return <div className="space-y-4"><label className="block text-sm font-medium text-slate-700">提交形式<select aria-label="提交形式" className={controlClass} value={value.config.submission_type} disabled={disabled} onChange={(event) => patch({ submission_type: event.target.value as AssignmentActivity["config"]["submission_type"] })}><option value="text">文字</option><option value="file">文件</option><option value="text_or_file">文字或文件</option></select></label><label className="block text-sm font-medium text-slate-700">审核方式<select className={controlClass} value={value.config.review_mode} disabled={disabled} onChange={(event) => patch({ review_mode: event.target.value as AssignmentActivity["config"]["review_mode"] })}><option value="automatic_complete">提交即完成</option><option value="manual_review">人工审核</option></select></label><AdvancedSettings><NumberField label="文件大小上限（MB）" value={Math.round(value.config.max_file_size_bytes / 1_048_576)} min={1} max={100} disabled={disabled} onChange={(size) => patch({ max_file_size_bytes: (size ?? 10) * 1_048_576 })} /></AdvancedSettings></div>;
}
