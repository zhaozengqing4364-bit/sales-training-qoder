"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { ExternalLink, FileText, Loader2, Search, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { AdminKnowledgeBase } from "@/lib/api/types";
import { debug } from "@/lib/debug";

interface AdminKbMultiRefPickerProps {
    label: string;
    value: string[];
    onChange: (ids: string[]) => void;
    knowledgeBases?: AdminKnowledgeBase[];
    loading?: boolean;
    error?: string | null;
}

function isKbSelectable(kb: AdminKnowledgeBase): boolean {
    return kb.status === "active" || kb.status === "published";
}

export function AdminKbMultiRefPicker({
    label,
    value,
    onChange,
    knowledgeBases: knowledgeBasesProp,
    loading: loadingProp,
    error,
}: AdminKbMultiRefPickerProps) {
    const [loadedKnowledgeBases, setLoadedKnowledgeBases] = useState<AdminKnowledgeBase[]>([]);
    const [internalLoading, setInternalLoading] = useState(knowledgeBasesProp === undefined);
    const [loadError, setLoadError] = useState<string | null>(null);
    const knowledgeBases = knowledgeBasesProp ?? loadedKnowledgeBases;
    const loading = loadingProp ?? internalLoading;
    const [searchText, setSearchText] = useState("");
    const [dropdownOpen, setDropdownOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (knowledgeBasesProp !== undefined) return undefined;
        let cancelled = false;
        (async () => {
            try {
                setInternalLoading(true);
                setLoadError(null);
                const result = await api.admin.getKnowledgeBases({ page: 1, page_size: 200 });
                if (!cancelled) setLoadedKnowledgeBases(result.items);
            } catch (err) {
                if (!cancelled) {
                    setLoadError(getApiErrorMessage(err));
                    debug.warn("[AdminKbMultiRefPicker] failed to load knowledge bases", { error: err });
                }
            } finally {
                if (!cancelled) setInternalLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [knowledgeBasesProp]);

    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setDropdownOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const selectedSet = useMemo(() => new Set(value), [value]);
    const selectedKBs = knowledgeBases.filter((kb) => selectedSet.has(kb.id));

    const filtered = useMemo(() => {
        const query = searchText.trim().toLowerCase();
        if (!query) return knowledgeBases;
        return knowledgeBases.filter((kb) => kb.name.toLowerCase().includes(query));
    }, [knowledgeBases, searchText]);

    function toggleKB(kb: AdminKnowledgeBase) {
        if (!isKbSelectable(kb)) return;
        if (selectedSet.has(kb.id)) {
            onChange(value.filter((id) => id !== kb.id));
            return;
        }
        onChange([...value, kb.id]);
    }

    return (
        <div className="space-y-1 md:col-span-2" ref={containerRef}>
            <label className="text-sm font-medium text-slate-700">{label}</label>
            {selectedKBs.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                    {selectedKBs.map((kb) => (
                        <Badge key={kb.id} variant="secondary" className="flex items-center gap-1 pr-1 text-xs">
                            <FileText className="h-3 w-3" />
                            {kb.name}
                            <span className="font-mono text-[10px] text-slate-500">{kb.id}</span>
                            <button
                                type="button"
                                className="ml-0.5 rounded-full p-0.5 hover:bg-slate-300/50"
                                onClick={() => onChange(value.filter((id) => id !== kb.id))}
                                aria-label={`移除 ${kb.name}`}
                            >
                                <X className="h-3 w-3" />
                            </button>
                        </Badge>
                    ))}
                </div>
            ) : null}
            <div className="relative">
                <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <Input
                    value={searchText}
                    onChange={(event) => {
                        setSearchText(event.target.value);
                        setDropdownOpen(true);
                    }}
                    onFocus={() => setDropdownOpen(true)}
                    placeholder="搜索知识库…"
                    className="h-10 pl-9"
                    aria-label={label}
                />
            </div>
            {loadError ? <p className="text-xs text-red-600">{loadError}</p> : null}
            {error ? <p className="text-xs text-red-600">{error}</p> : null}
            {dropdownOpen ? (
                <div className="max-h-60 overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-md">
                    {loading ? (
                        <div className="flex items-center justify-center py-6 text-sm text-slate-500">
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            加载中…
                        </div>
                    ) : filtered.length === 0 ? (
                        <div className="py-6 text-center text-sm text-slate-400">暂无知识库</div>
                    ) : (
                        filtered.map((kb) => {
                            const selectable = isKbSelectable(kb);
                            const isSelected = selectedSet.has(kb.id);
                            return (
                                <button
                                    key={kb.id}
                                    type="button"
                                    disabled={!selectable}
                                    onClick={() => toggleKB(kb)}
                                    className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm ${
                                        selectable ? "hover:bg-slate-50" : "cursor-not-allowed bg-slate-50/80 text-slate-400"
                                    }`}
                                >
                                    <span
                                        className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                                            isSelected
                                                ? "border-indigo-600 bg-indigo-600 text-white"
                                                : "border-slate-300 bg-white"
                                        }`}
                                    >
                                        {isSelected ? "✓" : ""}
                                    </span>
                                    <div className="min-w-0 flex-1">
                                        <div className="truncate font-medium">{kb.name}</div>
                                        <div className="truncate font-mono text-xs text-slate-400">{kb.id}</div>
                                        <div className="text-xs text-slate-400">
                                            {kb.status} · {kb.document_count ?? kb.doc_count ?? 0} 篇文档
                                        </div>
                                    </div>
                                    {!selectable ? (
                                        <Link
                                            href={`/admin/knowledge/${kb.id}`}
                                            className="shrink-0 text-xs font-medium text-amber-700 hover:text-amber-900"
                                            onClick={(event) => event.stopPropagation()}
                                        >
                                            去发布
                                        </Link>
                                    ) : null}
                                </button>
                            );
                        })
                    )}
                </div>
            ) : null}
        </div>
    );
}
