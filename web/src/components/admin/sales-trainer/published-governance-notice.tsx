"use client";

import type { SalesTrainerStatus } from "@/lib/api/types";

interface PublishedGovernanceNoticeProps {
    readonly status: SalesTrainerStatus | undefined;
}

export function PublishedGovernanceNotice({
    status,
}: PublishedGovernanceNoticeProps) {
    if (status === "draft" || status === undefined) {
        return null;
    }

    const isPublished = status === "published";

    return (
        <div className="flex flex-col gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 md:flex-row md:items-center md:justify-between">
            <div className="space-y-1">
                <p className="font-semibold">
                    {isPublished ? "编辑将生成新修订" : "已归档内容只读"}
                </p>
                <p className="text-amber-800">
                    {isPublished
                        ? "保存修改会进入待发布修订；发布后只影响后续学员，已有考试、录音和评分记录继续保留当时快照。"
                        : "归档版本保留用于审计和历史追溯，不能继续编辑；需要恢复使用时请在历史版本中执行回滚。"}
                </p>
            </div>
        </div>
    );
}
