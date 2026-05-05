"use client";

import { Settings2 } from "lucide-react";
import { KnowledgeAnswerConsole } from "@/components/admin/knowledge-answer/knowledge-answer-console";

export default function RetrievalStrategiesPage() {
    return (
        <div className="p-6 max-w-6xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <div className="flex items-center gap-2">
                        <Settings2 className="h-6 w-6 text-slate-700" />
                        <h1 className="text-2xl font-bold text-zinc-950">检索策略</h1>
                    </div>
                    <p className="text-sm text-slate-500 mt-1">
                        统一管理检索管线的意图识别、分块预设、排序权重和可回答性配置
                    </p>
                </div>
            </div>

            {/* Content */}
            <KnowledgeAnswerConsole />
        </div>
    );
}
