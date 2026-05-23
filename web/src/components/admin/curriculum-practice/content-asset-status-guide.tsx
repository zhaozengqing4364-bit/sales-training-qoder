"use client";

import { Badge } from "@/components/ui/badge";

import { formatAssetStatus } from "./content-asset-utils";

const PUBLISHED_GUIDE =
    "已发布内容不可修改，以保证开练快照一致；如需变更请复制为新草稿并更新模板绑定。";
const ARCHIVED_GUIDE =
    "已归档，不可绑定；历史模板若仍引用需手动换绑。";
const DRAFT_GUIDE = "草稿可编辑、可发布。";

export function assetCardClassName(status: string): string {
    const base = "rounded-2xl border p-4";
    if (status === "published") {
        return `${base} border-green-100 bg-green-50/30`;
    }
    if (status === "archived") {
        return `${base} border-slate-200 bg-white/60 opacity-70`;
    }
    return `${base} border-slate-100 bg-white/80`;
}

export interface ContentAssetStatusGuideProps {
    status: string;
    compact?: boolean;
}

export function ContentAssetStatusGuide({ status, compact = false }: ContentAssetStatusGuideProps) {
    if (status === "draft") {
        if (compact) return null;
        return (
            <p className="rounded-xl border border-orange-100 bg-orange-50/70 px-3 py-2 text-xs text-orange-800">
                {DRAFT_GUIDE}
            </p>
        );
    }

    if (status === "published") {
        return (
            <div className="space-y-2">
                <div className="rounded-xl border border-emerald-100 bg-emerald-50/80 px-3 py-2 text-xs text-emerald-900">
                    {PUBLISHED_GUIDE}
                </div>
                {!compact ? (
                    <Badge variant="green">{formatAssetStatus(status)}</Badge>
                ) : null}
            </div>
        );
    }

    if (status === "archived") {
        return (
            <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                {ARCHIVED_GUIDE}
            </p>
        );
    }

    return null;
}

export const publishedAssetGuideText = PUBLISHED_GUIDE;
