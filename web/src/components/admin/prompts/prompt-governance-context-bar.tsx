"use client";

import { ShieldAlert } from "lucide-react";
import type { PromptTemplateGovernanceStatus } from "@/lib/api/types";
import { AdminContextBar } from "@/components/admin/admin-layout-shells";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatGovernanceIssue } from "./prompt-labels";

interface PromptGovernanceContextBarProps {
    loadWarnings: string[];
    governanceStatus: PromptTemplateGovernanceStatus | null;
    canOperate: boolean;
    isOperating: boolean;
    onRemediate: () => void;
}

export function PromptGovernanceContextBar({ loadWarnings, governanceStatus, canOperate, isOperating, onRemediate }: PromptGovernanceContextBarProps) {
    return (
        <AdminContextBar>
            {loadWarnings.length > 0 ? (
                <GlassCard className="border-amber-200 bg-amber-50 p-4">
                    <div className="flex items-start gap-3 text-amber-900">
                        <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
                        <div>
                            <p className="font-semibold">部分提示词治理数据加载失败</p>
                            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{loadWarnings.map((w) => <li key={w}>{w}</li>)}</ul>
                            <p className="mt-2 text-xs text-amber-800">页面保留已加载数据；涉及写操作仍需管理员权限，失败项修复后可点击刷新重试。</p>
                        </div>
                    </div>
                </GlassCard>
            ) : null}
            <GlassCard className="space-y-4 p-4">
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">销售场景仅允许绑定评估/报告/实时评分类模板。</div>
                <div className={`rounded-xl border px-3 py-3 text-xs ${governanceStatus?.invalid_count ? "border-red-200 bg-red-50 text-red-700" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
                    <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                        <div>
                            <div className="font-semibold">提示词治理状态</div>
                            <div className="mt-1">{governanceStatus ? `允许类型 ${governanceStatus.allowed_prompt_types.join(" / ")}；非法历史模板 ${governanceStatus.invalid_count} 个；变量规则：${governanceStatus.policy.variables_schema}` : "治理状态暂不可用"}</div>
                        </div>
                        {governanceStatus?.invalid_count ? (
                            <Button variant="outline" size="sm" disabled={!canOperate || isOperating} onClick={onRemediate}>禁用非法历史模板</Button>
                        ) : null}
                    </div>
                </div>
            </GlassCard>
            {governanceStatus && governanceStatus.invalid_count > 0 ? (
                <GlassCard className="border border-red-200 bg-red-50 p-4">
                    <div className="mb-3 font-bold text-red-800">提示词治理发现 {governanceStatus.invalid_count} 条非法历史模板</div>
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div className="flex flex-wrap gap-2">
                        {governanceStatus.issues.slice(0, 4).map((issue) => (
                            <Badge key={issue.template_id} className="border border-red-200 bg-white text-red-700">
                                {issue.name || issue.template_id.slice(0, 8)} · {issue.issue_codes.map(formatGovernanceIssue).join(" / ")}
                            </Badge>
                        ))}
                        </div>
                        <Button variant="outline" className="border-red-200 bg-white text-red-700" disabled={!canOperate || isOperating || governanceStatus.invalid_active_count === 0} onClick={onRemediate}>禁用非法历史模板</Button>
                    </div>
                </GlassCard>
            ) : null}
        </AdminContextBar>
    );
}
