"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronUp, Loader2, Settings2 } from "lucide-react";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    AdminKnowledgeAnswerAdminConfig,
    AdminKnowledgeAnswerConfigOptions,
} from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

import { ConfigOverview } from "./config-overview";
import { VersionManager } from "./version-manager";
import { PipelineTabs } from "./pipeline-tabs";
import { DebugPanel } from "./debug-panel/debug-panel";
import { RunHistory } from "./run-history/run-history";

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function KnowledgeAnswerConsole() {
    const toast = useToast();

    /* ── State ── */
    const [config, setConfig] = useState<AdminKnowledgeAnswerAdminConfig | null>(null);
    const [configOptions, setConfigOptions] = useState<AdminKnowledgeAnswerConfigOptions | null>(null);
    const [selectedVersionId, setSelectedVersionId] = useState("");
    const [isSaving, setIsSaving] = useState(false);
    const [showVersionManager, setShowVersionManager] = useState(false);
    const [debugOpen, setDebugOpen] = useState(false);
    const [historyOpen, setHistoryOpen] = useState(false);

    /* ── Load config + options ── */
    const loadData = useCallback(async () => {
        try {
            const [configData, optionsData] = await Promise.all([
                api.admin.getKnowledgeAnswerAdminConfig(),
                api.admin.getKnowledgeAnswerAdminConfigOptions(),
            ]);
            setConfig(configData);
            if (configData.active_version) {
                setSelectedVersionId(configData.active_version.id);
            }
            setConfigOptions(optionsData);
        } catch (e) {
            toast.error(`加载配置失败：${getApiErrorMessage(e)}`);
        }
    }, [toast]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    /* ── Save global config ── */
    const handleSave = async () => {
        if (!selectedVersionId) {
            toast.error("请先选择一个版本");
            return;
        }
        setIsSaving(true);
        try {
            const result = await api.admin.updateKnowledgeAnswerAdminConfig({
                config_version_id: selectedVersionId,
            });
            toast.success("全局配置已保存");
            setConfig(result);
        } catch (e) {
            toast.error(`保存失败：${getApiErrorMessage(e)}`);
        } finally {
            setIsSaving(false);
        }
    };

    /* ── Render ── */
    return (
        <div className="space-y-6">
            {/* 1. Overview */}
            <ConfigOverview config={config} />

            {/* 2. Version selector row */}
            <div className="flex flex-wrap items-center gap-3">
                <select
                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300"
                    value={selectedVersionId}
                    onChange={(e) => setSelectedVersionId(e.target.value)}
                >
                    <option value="">选择版本…</option>
                    {(configOptions?.versions ?? []).map((v) => (
                        <option key={v.id} value={v.id}>
                            {v.version_name}
                            {v.status === "active" ? " (活跃)" : ""}
                        </option>
                    ))}
                </select>

                <Button
                    variant="outline"
                    size="sm"
                    className="rounded-full"
                    onClick={() => setShowVersionManager(true)}
                >
                    <Settings2 className="mr-1.5 h-3.5 w-3.5" />
                    管理版本
                </Button>

                <Button
                    size="sm"
                    className="rounded-full"
                    disabled={isSaving || !selectedVersionId}
                    onClick={handleSave}
                >
                    {isSaving && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                    保存全局配置
                </Button>
            </div>

            {/* 3. Pipeline tabs */}
            <PipelineTabs versionId={selectedVersionId || null} />

            {/* 4. Collapsible: Debug panel */}
            <CollapsibleSection title="调试面板" open={debugOpen} onToggle={() => setDebugOpen(!debugOpen)}>
                <DebugPanel />
            </CollapsibleSection>

            {/* 5. Collapsible: Run history */}
            <CollapsibleSection title="运行记录" open={historyOpen} onToggle={() => setHistoryOpen(!historyOpen)}>
                <RunHistory />
            </CollapsibleSection>

            {/* Version manager modal */}
            <VersionManager
                open={showVersionManager}
                onOpenChange={setShowVersionManager}
                onVersionChange={loadData}
            />
        </div>
    );
}

/* ------------------------------------------------------------------ */
/*  Internal: Collapsible section                                       */
/* ------------------------------------------------------------------ */

function CollapsibleSection({
    title,
    open,
    onToggle,
    children,
}: {
    title: string;
    open: boolean;
    onToggle: () => void;
    children: React.ReactNode;
}) {
    return (
        <div className="rounded-xl border border-slate-200 bg-white">
            <button
                type="button"
                className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-slate-900 hover:bg-slate-50 rounded-xl transition-colors"
                onClick={onToggle}
            >
                {title}
                {open ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
            </button>
            {open && <div className="border-t border-slate-100 px-4 py-4">{children}</div>}
        </div>
    );
}
