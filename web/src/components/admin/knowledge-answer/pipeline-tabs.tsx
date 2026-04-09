"use client";

import {
    GitBranch,
    Target,
    Search,
    BarChart3,
    ShieldCheck,
    Layers,
    Scissors,
    Settings2,
} from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

import { EntityAliasesTab } from "./tabs/entity-aliases-tab";
import { IntentRulesTab } from "./tabs/intent-rules-tab";
import { QueryProfilesTab } from "./tabs/query-profiles-tab";
import { ChunkingPresetsTab } from "./tabs/chunking-presets-tab";
import { RankingProfilesTab } from "./tabs/ranking-profiles-tab";
import { AnswerabilityTab } from "./tabs/answerability-tab";
import { AssemblerOverviewTab } from "./tabs/assembler-overview-tab";

/* ------------------------------------------------------------------ */
/*  Props                                                              */
/* ------------------------------------------------------------------ */

interface PipelineTabsProps {
    versionId: string | null;
}

/* ------------------------------------------------------------------ */
/*  Pipeline step definitions                                           */
/* ------------------------------------------------------------------ */

const PIPELINE_STEPS = [
    { key: "entity", label: "实体别名", icon: GitBranch, step: 1 },
    { key: "intent", label: "意图规则", icon: Target, step: 2 },
    { key: "query", label: "查询配置", icon: Search, step: 3 },
    { key: "chunking", label: "分块预设", icon: Scissors, step: 4 },
    { key: "ranking", label: "排序权重", icon: BarChart3, step: 5 },
    { key: "answerability", label: "可回答性", icon: ShieldCheck, step: 6 },
    { key: "assemble", label: "输出组装", icon: Layers, step: 7 },
] as const;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function PipelineTabs({ versionId }: PipelineTabsProps) {
    if (!versionId) {
        return (
            <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center">
                <Settings2 className="mx-auto h-8 w-8 text-slate-300" />
                <p className="mt-3 text-sm text-slate-500">请先选择一个配置版本</p>
            </div>
        );
    }

    return (
        <Tabs defaultValue="entity" className="w-full">
            {/* ── Tab bar ── */}
            <div className="overflow-x-auto pb-1">
                <TabsList className="inline-flex h-auto w-max gap-1 rounded-xl bg-slate-100/80 p-1.5">
                    {PIPELINE_STEPS.map(({ key, label, icon: Icon, step }) => (
                        <TabsTrigger
                            key={key}
                            value={key}
                            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium data-[state=active]:bg-white data-[state=active]:shadow-sm whitespace-nowrap"
                        >
                            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-200 text-[10px] font-bold text-slate-600 data-[state=active]:bg-slate-700 data-[state=active]:text-white">
                                {step}
                            </span>
                            <Icon className="h-3.5 w-3.5" />
                            {label}
                        </TabsTrigger>
                    ))}
                </TabsList>
            </div>

            {/* ── Tab panels ── */}
            <div className="mt-4">
                <TabsContent value="entity">
                    <EntityAliasesTab versionId={versionId} />
                </TabsContent>
                <TabsContent value="intent">
                    <IntentRulesTab versionId={versionId} />
                </TabsContent>
                <TabsContent value="query">
                    <QueryProfilesTab versionId={versionId} />
                </TabsContent>
                <TabsContent value="chunking">
                    <ChunkingPresetsTab versionId={versionId} />
                </TabsContent>
                <TabsContent value="ranking">
                    <RankingProfilesTab versionId={versionId} />
                </TabsContent>
                <TabsContent value="answerability">
                    <AnswerabilityTab versionId={versionId} />
                </TabsContent>
                <TabsContent value="assemble">
                    <AssemblerOverviewTab />
                </TabsContent>
            </div>
        </Tabs>
    );
}
