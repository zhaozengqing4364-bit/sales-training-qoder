"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
    BrainCircuit,
    ChevronRight,
    FileClock,
    Flag,
    ListChecks,
    RefreshCw,
    Settings,
    Shield,
} from "lucide-react";

import { AdminPageHeader } from "@/components/admin/admin-layout-shells";
import {
    FoundationAdminCapabilityBoundary,
    useFoundationAdminCapabilities,
} from "@/components/admin/newcomer-training/workspace-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { FoundationAuditItem } from "@/lib/api/types/foundation-admin";

const SETTINGS_AREAS = [
    {
        href: "/admin/prompts",
        title: "提示模板与绑定",
        description: "管理版本、输入输出合同和业务场景绑定；发布前保留人工审核。",
        icon: BrainCircuit,
    },
    {
        href: "/admin/settings",
        title: "模型与 Provider 路由",
        description: "配置模型路由、超时和降级。密钥只显示配置状态，不在此工作区回传。",
        icon: Settings,
    },
    {
        href: "/admin/sales-trainer/settings",
        title: "训练活动与评分策略",
        description: "管理训练阈值、评分修订和活动策略，并保留发布与回滚记录。",
        icon: ListChecks,
    },
    {
        href: "/admin/governance",
        title: "合同与功能开关",
        description: "检查运行合同、治理违规和可降级功能；高风险变更需要审计。",
        icon: Flag,
    },
] as const;

export function FoundationGovernanceSettingsWorkspace() {
    const searchParams = useSearchParams();
    const objectId = searchParams.get("object_id")?.trim() || undefined;
    const capabilities = useFoundationAdminCapabilities();
    const mayViewAudit = capabilities.data?.capabilities.includes("view_sensitive_audit") ?? false;
    const audits = useQuery({
        queryKey: ["foundation-admin", "audits", objectId],
        queryFn: () => api.admin.newcomerTraining.listFoundationAudits({ object_id: objectId, limit: 50 }),
        enabled: mayViewAudit,
    });

    return (
        <FoundationAdminCapabilityBoundary capability={["govern_ai", "view_sensitive_audit"]}>
            <main className="px-4 py-6 md:px-6">
                <div className="mx-auto max-w-7xl space-y-6">
                    <AdminPageHeader
                        title="治理设置"
                        description="从具体治理对象进入现有配置中心；新人训练工作区不复制配置，也不展示敏感密钥或提示模板原文。"
                        icon={<Shield className="h-7 w-7 text-blue-600" />}
                    />

                    <section aria-labelledby="governance-areas-title" className="rounded-2xl border border-slate-200 bg-white p-5">
                        <h2 id="governance-areas-title" className="font-semibold text-slate-950">治理入口</h2>
                        <p className="mt-1 text-sm text-slate-600">每项设置仍由其领域模块维护唯一正式版本；这里仅组织任务入口。</p>
                        <div className="mt-4 divide-y divide-slate-100">
                            {SETTINGS_AREAS.map((area) => {
                                const Icon = area.icon;
                                return <Link key={area.href} href={area.href} prefetch={false} className="flex items-start gap-4 py-4 first:pt-0 last:pb-0"><span className="rounded-xl bg-slate-100 p-2 text-slate-700"><Icon className="h-5 w-5" /></span><span className="min-w-0 flex-1"><span className="font-medium text-slate-950">{area.title}</span><span className="mt-1 block text-sm leading-6 text-slate-600">{area.description}</span></span><ChevronRight className="mt-2 h-4 w-4 shrink-0 text-slate-400" /></Link>;
                            })}
                        </div>
                    </section>

                    <section aria-labelledby="audit-title" className="rounded-2xl border border-slate-200 bg-white p-5">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><div className="flex items-center gap-2"><FileClock className="h-5 w-5 text-slate-500" /><h2 id="audit-title" className="font-semibold text-slate-950">高风险操作记录</h2></div><p className="mt-1 text-sm text-slate-600">按业务对象查看发布、回滚、迁移和复核相关操作；技术追踪信息不在普通工作区展示。</p></div>{mayViewAudit ? <Button type="button" variant="outline" size="sm" onClick={() => void audits.refetch()} disabled={audits.isFetching}><RefreshCw className={`mr-2 h-4 w-4 ${audits.isFetching ? "animate-spin" : ""}`} />刷新记录</Button> : null}</div>
                        {objectId ? <div className="mt-4 flex items-center justify-between gap-3 rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900"><span>当前只显示从业务对象详情进入的相关记录。</span><Link href="/admin/newcomer-training/settings" className="font-semibold underline">清除范围</Link></div> : null}
                        {!mayViewAudit ? <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">当前账号可以管理相应治理设置，但不能查看敏感审计。需要时请联系组织管理员申请审计查看权限。</div> : audits.isPending ? <div className="mt-4 space-y-2">{[0, 1, 2].map((item) => <div key={item} className="h-20 animate-pulse rounded-xl bg-slate-100" />)}</div> : audits.error ? <div role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">{getApiErrorMessage(audits.error)}<button type="button" className="ml-2 font-semibold underline" onClick={() => void audits.refetch()}>重试</button></div> : audits.data?.items.length ? <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="border-b border-slate-200 text-xs text-slate-500"><tr><th className="px-3 py-2">时间</th><th className="px-3 py-2">业务对象</th><th className="px-3 py-2">操作</th><th className="px-3 py-2">结果</th><th className="px-3 py-2">原因</th><th className="px-3 py-2">版本变化</th></tr></thead><tbody className="divide-y divide-slate-100">{audits.data.items.map((item) => <AuditRow key={item.audit_id} item={item} />)}</tbody></table></div> : <div className="mt-4 rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">当前范围没有操作记录。</div>}
                    </section>
                </div>
            </main>
        </FoundationAdminCapabilityBoundary>
    );
}

function AuditRow({ item }: { item: FoundationAuditItem }) {
    return <tr><td className="px-3 py-3 text-slate-500">{new Date(item.occurred_at).toLocaleString("zh-CN")}</td><td className="px-3 py-3 font-medium text-slate-900">{objectTypeLabel(item.object_type)}</td><td className="px-3 py-3 text-slate-700">{actionLabel(item.action)}</td><td className="px-3 py-3"><Badge variant={item.result === "succeeded" || item.result === "previewed" ? "green" : item.result === "failed" ? "red" : "gray"}>{resultLabel(item.result)}</Badge></td><td className="max-w-xs px-3 py-3 text-slate-600">{item.reason || "未单独填写"}</td><td className="px-3 py-3 text-slate-500">{item.before_version !== null || item.after_version !== null ? `${item.before_version ?? "-"} → ${item.after_version ?? "-"}` : "无版本变化"}</td></tr>;
}

function objectTypeLabel(value: string): string { return { release_plan: "路径发布", path: "训练路径", enrollment: "学员分配", cohort: "训练班级", question_candidate: "候选题目", readiness_dossier: "达标档案" }[value] ?? "新人训练对象"; }
function actionLabel(value: string): string { return { preview_release_plan: "预览发布", publish_release_plan: "发布版本", preview_release_rollback: "预览回滚", rollback_release_plan: "恢复历史发布", migrate_enrollment_revision: "迁移冻结版本", import_enrollments: "批量分配学员" }[value] ?? "治理操作"; }
function resultLabel(value: string): string { return { succeeded: "已完成", previewed: "已预览", failed: "未完成", partial: "部分完成", blocked: "已阻止" }[value] ?? "已记录"; }
