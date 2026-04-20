"use client";

const PRIORITY_PAYLOAD_FIELDS: Record<string, string> = {
    query: "查询文本",
    canonical_entity: "标准化实体",
    rewritten_queries: "改写查询",
    hit_count: "命中片段数",
    executed_query_count: "执行查询数",
    candidate_count: "候选数",
    top_k: "Top K",
    score: "相关性分数",
    chunk_index: "分块索引",
    document_id: "文档 ID",
    document_title: "文档标题",
    snippet: "片段内容",
    reason: "原因",
    profile_key: "配置键",
    threshold: "阈值",
    coverage_slots: "覆盖槽位",
    slot_hits: "槽位命中",
};

function renderPayloadValue(value: unknown): React.ReactNode {
    if (value === null || value === undefined) return "\u2014";
    if (typeof value === "string") return value;
    if (typeof value === "number") return String(value);
    if (typeof value === "boolean") return value ? "\u662f" : "\u5426";
    if (Array.isArray(value)) {
        if (value.length === 0) return "[]";
        if (value.every((v) => typeof v === "string"))
            return value.join("\u3001");
        return value.map((v, i) => (
            <div key={i} className="ml-2">
                {typeof v === "string" ? v : JSON.stringify(v)}
            </div>
        ));
    }
    return JSON.stringify(value);
}

export function StructuredPayloadViewer({
    data,
}: {
    data: Record<string, unknown> | null | undefined;
}) {
    if (!data || typeof data !== "object") {
        return <span className="text-slate-400">{"\u2014"}</span>;
    }

    const entries = Object.entries(data);
    if (entries.length === 0) {
        return <span className="text-slate-400">空</span>;
    }

    const priorityEntries = entries.filter(([key]) => key in PRIORITY_PAYLOAD_FIELDS);
    const remainingEntries = entries.filter(
        ([key]) => !(key in PRIORITY_PAYLOAD_FIELDS),
    );

    return (
        <div className="space-y-2">
            {priorityEntries.length > 0 && (
                <div className="grid gap-x-4 gap-y-1.5 sm:grid-cols-2">
                    {priorityEntries.map(([key, value]) => (
                        <div key={key} className="text-xs">
                            <span className="text-slate-500">
                                {PRIORITY_PAYLOAD_FIELDS[key]}
                            </span>
                            <div className="mt-0.5 font-medium text-slate-900 break-all">
                                {renderPayloadValue(value)}
                            </div>
                        </div>
                    ))}
                </div>
            )}
            {remainingEntries.length > 0 && (
                <details className="rounded-lg border border-slate-100 bg-slate-50 p-2">
                    <summary className="cursor-pointer list-none text-xs font-medium text-slate-500">
                        {priorityEntries.length > 0
                            ? "\u5176\u4ed6\u5b57\u6bb5"
                            : "\u5c55\u5f00\u539f\u59cb\u6570\u636e"}
                    </summary>
                    <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all text-xs text-slate-700">
                        {JSON.stringify(
                            Object.fromEntries(remainingEntries),
                            null,
                            2,
                        )}
                    </pre>
                </details>
            )}
        </div>
    );
}
