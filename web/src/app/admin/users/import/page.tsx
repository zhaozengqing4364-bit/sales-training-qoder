"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, CheckCircle2, Copy, Download, FileUp, Loader2, RefreshCw } from "lucide-react";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { ProvisioningBatchResult, ProvisioningCredential } from "@/lib/api/types";
import { generateClientToken } from "@/lib/sales-trainer/idempotency";

type TeamOverride = { name?: string; primary_leader_email?: string };

function downloadCredentials(credentials: ProvisioningCredential[]) {
    const quote = (value: string | number) => `"${String(value).replaceAll('"', '""')}"`;
    const rows = [
        ["姓名", "公司邮箱", "临时密码", "有效期至"],
        ...credentials.map((item) => [item.name, item.email, item.temporary_password, item.temporary_password_expires_at]),
    ];
    const blob = new Blob([`\uFEFF${rows.map((row) => row.map(quote).join(",")).join("\n")}`], { type: "text/csv;charset=utf-8" });
    const href = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = href;
    link.download = `开户结果-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(href);
}

function downloadTemplate() {
    const content = "\uFEFFname,email,role,team_code,team_name,primary_leader_email,employee_number\n张三,zhangsan@company.com,user,east-sales,华东销售一组,leader@company.com,E001";
    const href = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = href;
    link.download = "批量开户模板.csv";
    link.click();
    URL.revokeObjectURL(href);
}

export default function UserProvisioningPage() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const batchId = searchParams.get("batchId");
    const [batch, setBatch] = useState<ProvisioningBatchResult | null>(null);
    const [file, setFile] = useState<File | null>(null);
    const [overrides, setOverrides] = useState<Record<string, TeamOverride>>({});
    const [credentials, setCredentials] = useState<ProvisioningCredential[]>([]);
    const [busy, setBusy] = useState<"preview" | "confirm" | "reset" | null>(null);
    const [error, setError] = useState<string | null>(null);

    const loadBatch = useCallback(async (id: string) => {
        setError(null);
        try {
            setBatch(await api.admin.getUserProvisioningBatch(id));
        } catch (reason) {
            setError(getApiErrorMessage(reason));
        }
    }, []);

    useEffect(() => {
        if (batchId) void loadBatch(batchId);
    }, [batchId, loadBatch]);

    useEffect(() => {
        if (!batchId) return;
        const saved = window.localStorage.getItem(`provisioning-overrides:${batchId}`);
        if (saved) {
            try { setOverrides(JSON.parse(saved) as Record<string, TeamOverride>); } catch { window.localStorage.removeItem(`provisioning-overrides:${batchId}`); }
        }
    }, [batchId]);

    useEffect(() => {
        if (batch?.batch_id) window.localStorage.setItem(`provisioning-overrides:${batch.batch_id}`, JSON.stringify(overrides));
    }, [batch?.batch_id, overrides]);

    const invalidRows = batch?.rows.filter((row) => row.status === "invalid") ?? [];
    const failedTeams = batch?.teams.filter((team) => team.status === "failed") ?? [];
    const canConfirm = Boolean(batch && invalidRows.length === 0 && batch.teams.some((team) => team.status !== "completed"));
    const teamRows = useMemo(() => new Map((batch?.teams ?? []).map((team) => [team.team_code, batch?.rows.filter((row) => row.team_code === team.team_code) ?? []])), [batch]);

    const handlePreview = async () => {
        if (!file) return;
        setBusy("preview");
        setError(null);
        setCredentials([]);
        try {
            const result = await api.admin.previewUserProvisioning({
                csv_text: await file.text(),
                source_name: file.name,
                idempotency_key: generateClientToken(),
            });
            setBatch(result);
            router.replace(`/admin/users/import?batchId=${encodeURIComponent(result.batch_id)}`);
        } catch (reason) {
            setError(getApiErrorMessage(reason));
        } finally {
            setBusy(null);
        }
    };

    const handleConfirm = async (retryOnly = false) => {
        if (!batch) return;
        setBusy("confirm");
        setError(null);
        try {
            const result = await api.admin.confirmUserProvisioning(batch.batch_id, {
                team_overrides: overrides,
                retry_team_codes: retryOnly ? failedTeams.map((team) => team.team_code) : undefined,
            });
            setBatch(result);
            setCredentials(result.credentials ?? []);
            if (result.status === "completed") window.localStorage.removeItem(`provisioning-overrides:${result.batch_id}`);
        } catch (reason) {
            setError(getApiErrorMessage(reason));
        } finally {
            setBusy(null);
        }
    };

    const handleReset = async () => {
        if (!batch || !window.confirm("将立即使本批次账号此前尚未使用的临时密码失效。确认重新生成？")) return;
        setBusy("reset");
        setError(null);
        try {
            const result = await api.admin.resetUserProvisioningCredentials(batch.batch_id);
            setCredentials(result.credentials);
        } catch (reason) {
            setError(getApiErrorMessage(reason));
        } finally {
            setBusy(null);
        }
    };

    return (
        <AdminFormShell
            backHref="/admin/users"
            backLabel="返回账号管理"
            title="批量开户"
            description="先预览校验，再按团队开户。单个团队全成全败，不同团队互不影响。"
        >
            <section className="rounded-2xl border border-slate-200 bg-white p-5" aria-labelledby="upload-title">
                <h2 id="upload-title" className="text-lg font-semibold text-slate-900">1. 选择开户文件</h2>
                <p className="mt-1 text-sm text-slate-600">CSV 必填列：name、email、role、team_code；可选 team_name、primary_leader_email、employee_number。团队是唯一组织归属，单次最多 500 人。</p>
                <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
                    <label className="flex-1 text-sm font-medium text-slate-700">
                        CSV 文件
                        <Input className="mt-2" type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
                    </label>
                    <Button type="button" variant="outline" onClick={downloadTemplate}><Download className="mr-2 h-4 w-4" />下载模板</Button>
                    <Button disabled={!file || busy !== null} onClick={() => void handlePreview()}>
                        {busy === "preview" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileUp className="mr-2 h-4 w-4" />}预览并校验
                    </Button>
                </div>
            </section>

            {error ? <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">开户流程未完成：{error}。已填写内容和批次不会丢失，请修正后重试。</div> : null}

            {batch ? (
                <section className="space-y-4" aria-labelledby="preview-title">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                        <div><h2 id="preview-title" className="text-lg font-semibold text-slate-900">2. 按团队确认</h2><p className="text-sm text-slate-600">文件：{batch.source_name} · {batch.rows.length} 个账号 · {batch.teams.length} 个团队</p></div>
                        <Button variant="outline" onClick={() => void loadBatch(batch.batch_id)} disabled={busy !== null}><RefreshCw className="mr-2 h-4 w-4" />刷新批次</Button>
                    </div>
                    {batch.teams.map((team) => {
                        const rows = teamRows.get(team.team_code) ?? [];
                        const suggestedName = rows.find((row) => row.team_name)?.team_name ?? "";
                        const suggestedLeader = rows.find((row) => row.primary_leader_email)?.primary_leader_email ?? "";
                        return <article key={team.team_code} className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-5 py-4">
                                <div><h3 className="font-semibold text-slate-900">{team.team_code}</h3><p className="text-xs text-slate-500">{team.row_count} 人 · {team.exists ? "已有团队" : "将新建团队"}</p></div>
                                <span className={`rounded-full px-3 py-1 text-xs font-medium ${team.status === "completed" ? "bg-emerald-50 text-emerald-700" : team.status === "failed" ? "bg-red-50 text-red-700" : "bg-slate-100 text-slate-700"}`}>{team.status === "completed" ? "开户成功" : team.status === "failed" ? "开户失败，可重试" : "待确认"}</span>
                            </div>
                            {!team.exists && team.status !== "completed" ? <div className="grid gap-3 border-b border-slate-100 bg-slate-50/60 p-4 md:grid-cols-2">
                                <label className="text-sm font-medium text-slate-700">团队名称<Input className="mt-1 bg-white" defaultValue={suggestedName} onChange={(event) => setOverrides((state) => ({ ...state, [team.team_code]: { ...state[team.team_code], name: event.target.value } }))} /></label>
                                <label className="text-sm font-medium text-slate-700">主组长公司邮箱<Input className="mt-1 bg-white" type="email" defaultValue={suggestedLeader ?? ""} onChange={(event) => setOverrides((state) => ({ ...state, [team.team_code]: { ...state[team.team_code], primary_leader_email: event.target.value } }))} /></label>
                            </div> : null}
                            <div className="overflow-x-auto"><table className="min-w-full text-left text-sm"><thead className="bg-slate-50 text-xs text-slate-500"><tr><th className="px-4 py-2">姓名</th><th className="px-4 py-2">公司邮箱</th><th className="px-4 py-2">角色</th><th className="px-4 py-2">校验结果</th></tr></thead><tbody className="divide-y divide-slate-100">{rows.map((row) => <tr key={row.row_number}><td className="px-4 py-3 text-slate-900">{row.name}</td><td className="px-4 py-3 text-slate-600">{row.email}</td><td className="px-4 py-3 text-slate-600">{row.role === "training_manager" ? "销售组长" : "销售学员"}</td><td className="px-4 py-3">{row.status === "invalid" || row.status === "failed" ? <span className="text-red-700"><AlertTriangle className="mr-1 inline h-4 w-4" />{row.error_message ?? "未通过"}</span> : <span className="text-emerald-700"><CheckCircle2 className="mr-1 inline h-4 w-4" />{row.status === "created" ? "已创建" : "可开户"}</span>}</td></tr>)}</tbody></table></div>
                        </article>;
                    })}
                    <div className="flex flex-wrap justify-end gap-2">
                        {failedTeams.length > 0 ? <Button variant="outline" disabled={busy !== null} onClick={() => void handleConfirm(true)}>只重试失败团队</Button> : null}
                        <Button disabled={!canConfirm || busy !== null} onClick={() => void handleConfirm(false)}>{busy === "confirm" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}确认开户</Button>
                    </div>
                </section>
            ) : null}

            {batch?.status === "completed" || batch?.status === "partially_completed" ? <section className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-5" aria-labelledby="result-title"><div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><h2 id="result-title" className="text-lg font-semibold text-slate-900">3. 交付登录凭证</h2><p className="mt-1 text-sm text-slate-700">临时密码只在本次开户或重置后显示。请立即复制或导出，并通过安全渠道分别交付。</p></div><div className="flex flex-wrap gap-2">{credentials.length > 0 ? <><Button variant="outline" onClick={() => void navigator.clipboard.writeText(credentials.map((item) => `${item.name}\t${item.email}\t${item.temporary_password}`).join("\n"))}><Copy className="mr-2 h-4 w-4" />复制</Button><Button onClick={() => downloadCredentials(credentials)}><Download className="mr-2 h-4 w-4" />导出凭证</Button></> : <Button variant="outline" disabled={busy !== null} onClick={() => void handleReset()}>{busy === "reset" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}重新生成本批次密码</Button>}</div></div>{credentials.length > 0 ? <div className="mt-4 overflow-x-auto"><table className="min-w-full text-left text-sm"><thead><tr className="text-xs text-slate-500"><th className="py-2 pr-4">姓名</th><th className="py-2 pr-4">公司邮箱</th><th className="py-2 pr-4">临时密码</th><th className="py-2">有效期至</th></tr></thead><tbody>{credentials.map((item) => <tr key={item.email} className="border-t border-emerald-100"><td className="py-3 pr-4">{item.name}</td><td className="py-3 pr-4">{item.email}</td><td className="py-3 pr-4 font-mono font-semibold">{item.temporary_password}</td><td className="py-3">{new Date(item.temporary_password_expires_at).toLocaleString("zh-CN")}</td></tr>)}</tbody></table></div> : <p className="mt-4 text-sm text-amber-800"><AlertTriangle className="mr-1 inline h-4 w-4" />页面刷新后无法恢复原临时密码；如未保存，请重新生成。</p>}</section> : null}
        </AdminFormShell>
    );
}
