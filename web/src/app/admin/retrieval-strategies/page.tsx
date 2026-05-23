"use client";

import { Settings2 } from "lucide-react";

import { AdminContextBar, AdminPageHeader, PolicyPageShell } from "@/components/admin/admin-layout-shells";
import { KnowledgeAnswerConsole } from "@/components/admin/knowledge-answer/knowledge-answer-console";

export default function RetrievalStrategiesPage() {
    return (
        <PolicyPageShell
            header={(
                <AdminPageHeader
                    icon={<Settings2 className="h-6 w-6 text-slate-700" />}
                    title="检索策略"
                    description="统一管理检索管线的意图识别、分块预设、排序权重和可回答性配置"
                />
            )}
            contextBar={(
                <AdminContextBar>
                    <div className="rounded-2xl border border-amber-200 bg-amber-50/90 px-4 py-3 text-sm text-amber-900">
                        <p className="font-semibold">影响范围：全部知识库</p>
                        <p className="mt-1 text-amber-800">
                            此页配置的是全局知识检索引擎（意图、排序、可回答性等），激活后对所有知识库生效。
                            单个知识库详情中的 RAG Profile 仅控制该库的分块预设与缓存参数，不能替代本页的全局策略。
                        </p>
                    </div>
                </AdminContextBar>
            )}
        >
            <KnowledgeAnswerConsole />
        </PolicyPageShell>
    );
}
