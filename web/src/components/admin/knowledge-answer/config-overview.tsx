"use client";

import type { AdminKnowledgeAnswerAdminConfig } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { GitBranch, Target, Search, Database, BarChart3, ShieldCheck } from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Props                                                              */
/* ------------------------------------------------------------------ */

interface ConfigOverviewProps {
    config: AdminKnowledgeAnswerAdminConfig | null;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function ConfigOverview({ config }: ConfigOverviewProps) {
    if (!config) {
        return (
            <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">
                暂无配置数据
            </div>
        );
    }

    const { active_version, profile_source, summary, selected_profiles } = config;

    return (
        <div className="space-y-4">
            {/* ── 4 summary cards ── */}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {/* Active version */}
                <GlassCard className="rounded-xl border bg-slate-50 p-4">
                    <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
                        <Database className="h-3.5 w-3.5" />
                        当前版本
                    </div>
                    <p className="mt-2 text-sm font-semibold text-slate-900 truncate">
                        {active_version?.version_name ?? "未配置"}
                    </p>
                </GlassCard>

                {/* Profile source */}
                <GlassCard className="rounded-xl border bg-slate-50 p-4">
                    <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
                        <GitBranch className="h-3.5 w-3.5" />
                        配置来源
                    </div>
                    <p className="mt-2 text-sm font-semibold text-slate-900">
                        {profile_source ?? "—"}
                    </p>
                </GlassCard>

                {/* Intent / Alias counts */}
                <GlassCard className="rounded-xl border bg-slate-50 p-4">
                    <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
                        <Target className="h-3.5 w-3.5" />
                        意图 / 别名
                    </div>
                    <div className="mt-2 flex items-baseline gap-3">
                        <span className="text-lg font-bold text-slate-900">
                            {summary.intent_rule_count}
                        </span>
                        <span className="text-xs text-slate-500">意图规则</span>
                        <span className="text-lg font-bold text-slate-900">
                            {summary.entity_alias_count}
                        </span>
                        <span className="text-xs text-slate-500">实体别名</span>
                    </div>
                </GlassCard>

                {/* Query / Rank / Answer counts */}
                <GlassCard className="rounded-xl border bg-slate-50 p-4">
                    <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
                        <BarChart3 className="h-3.5 w-3.5" />
                        查询 / 排序 / 可回答性
                    </div>
                    <div className="mt-2 flex items-baseline gap-2 text-lg font-bold text-slate-900">
                        {summary.query_profile_count}
                        <span className="text-xs font-normal text-slate-500">/</span>
                        {summary.ranking_profile_count}
                        <span className="text-xs font-normal text-slate-500">/</span>
                        {summary.answerability_profile_count}
                    </div>
                    <div className="mt-0.5 flex gap-2 text-[10px] text-slate-400">
                        <span>查询</span>
                        <span>排序</span>
                        <span>可回答性</span>
                    </div>
                </GlassCard>
            </div>

            {/* ── Selected profile keys ── */}
            <div className="grid gap-3 sm:grid-cols-3">
                <SelectedProfileKeysCard
                    icon={<Search className="h-3.5 w-3.5" />}
                    title="查询配置"
                    keys={selected_profiles.query_profile_keys}
                />
                <SelectedProfileKeysCard
                    icon={<BarChart3 className="h-3.5 w-3.5" />}
                    title="排序权重"
                    keys={selected_profiles.ranking_profile_keys}
                />
                <SelectedProfileKeysCard
                    icon={<ShieldCheck className="h-3.5 w-3.5" />}
                    title="可回答性"
                    keys={selected_profiles.answerability_profile_keys}
                />
            </div>
        </div>
    );
}

/* ------------------------------------------------------------------ */
/*  Internal helpers                                                    */
/* ------------------------------------------------------------------ */

function SelectedProfileKeysCard({
    icon,
    title,
    keys,
}: {
    icon: React.ReactNode;
    title: string;
    keys: string[];
}) {
    return (
        <GlassCard className="rounded-xl border bg-slate-50 p-4">
            <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
                {icon}
                已选 {title}
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
                {keys.length === 0 ? (
                    <span className="text-xs text-slate-400">无</span>
                ) : (
                    keys.map((k) => (
                        <span
                            key={k}
                            className="inline-flex items-center rounded-full bg-white px-2 py-0.5 text-xs font-medium text-slate-700 border border-slate-200"
                        >
                            {k}
                        </span>
                    ))
                )}
            </div>
        </GlassCard>
    );
}
