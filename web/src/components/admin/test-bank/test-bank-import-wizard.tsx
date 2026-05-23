"use client";

import { useState } from "react";
import { Upload } from "lucide-react";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { api } from "@/lib/api/client";
import type { ImportJob, ImportResult } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { useToast } from "@/components/ui/toast";

export function TestBankImportWizard() {
    const toast = useToast();
    const [importResult, setImportResult] = useState<ImportResult | null>(null);
    const [importError, setImportError] = useState<string | null>(null);
    const [importSubmitting, setImportSubmitting] = useState(false);

    const handleImport = async (file: File) => {
        setImportError(null);
        setImportResult(null);
        const ext = file.name.split(".").pop()?.toLowerCase();
        if (ext !== "csv" && ext !== "jsonl") {
            setImportError("仅支持 .csv 和 .jsonl 格式的文件");
            return;
        }
        if (file.size === 0) {
            setImportError("文件为空，请选择有效的文件");
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            setImportError("文件大小不能超过 10MB");
            return;
        }
        setImportSubmitting(true);
        try {
            let job: ImportJob = await api.testBank.importQuestions(file);
            while (job.status === "pending" || job.status === "processing") {
                await new Promise((r) => setTimeout(r, 800));
                job = await api.testBank.getImportJob(job.task_id);
            }
            if (job.status === "failed") {
                setImportError("导入任务执行失败");
                return;
            }
            setImportResult(job.result);
            toast.success(`成功导入 ${job.result.imported} 道题目`);
        } catch (err) {
            setImportError(err instanceof Error ? err.message : "导入失败");
        } finally {
            setImportSubmitting(false);
        }
    };

    return (
        <AdminFormShell backHref="/admin/test-bank" backLabel="返回题目列表" title="批量导入题目" description="上传 CSV 或 JSONL 文件，系统异步处理导入任务。">
            <GlassCard className="p-6">
                <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-slate-900"><Upload className="h-5 w-5" /> 批量导入</h2>
                <input type="file" accept=".csv,.jsonl" data-testid="import-file-input" disabled={importSubmitting} className="h-10 cursor-pointer rounded-full border border-slate-200 bg-slate-50 px-3 text-sm" onChange={(e) => { const file = e.target.files?.[0]; if (file) void handleImport(file); e.target.value = ""; }} />
                {importSubmitting && <p className="mt-3 text-sm text-slate-500">导入中...</p>}
                {importError && <div className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-600">{importError}</div>}
                {importResult && (
                    <div className="mt-4 space-y-3">
                        <div className="flex gap-4 text-sm">
                            <span className="rounded-full bg-green-50 px-3 py-1 text-green-700">导入完成 · 成功 <strong>{importResult.imported}</strong> 道</span>
                            {importResult.failed > 0 && <span className="rounded-full bg-red-50 px-3 py-1 text-red-700">失败 <strong>{importResult.failed}</strong> 道</span>}
                        </div>
                        {importResult.errors.length > 0 && (
                            <table className="w-full text-left text-sm">
                                <thead><tr><th className="px-4 py-2">行号</th><th className="px-4 py-2">字段</th><th className="px-4 py-2">错误</th></tr></thead>
                                <tbody>{importResult.errors.map((err, idx) => (<tr key={idx}><td className="px-4 py-2">{err.row}</td><td className="px-4 py-2">{err.field}</td><td className="px-4 py-2">{err.message}</td></tr>))}</tbody>
                            </table>
                        )}
                    </div>
                )}
            </GlassCard>
        </AdminFormShell>
    );
}
