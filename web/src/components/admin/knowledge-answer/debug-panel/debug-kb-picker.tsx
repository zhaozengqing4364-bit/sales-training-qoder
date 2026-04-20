"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Search, X, FileText, Loader2 } from "lucide-react";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { useToast } from "@/components/ui/toast";
import type { AdminKnowledgeBase } from "@/lib/api/types";

interface DebugKbPickerProps {
    selectedIds: string[];
    onChange: (ids: string[]) => void;
}

export function DebugKbPicker({ selectedIds, onChange }: DebugKbPickerProps) {
    const toast = useToast();
    const [knowledgeBases, setKnowledgeBases] = useState<AdminKnowledgeBase[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchText, setSearchText] = useState("");
    const [dropdownOpen, setDropdownOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                setLoading(true);
                // Fetch all knowledge bases (large page size to get all)
                const result = await api.admin.getKnowledgeBases({ page: 1, page_size: 200 });
                if (!cancelled) {
                    setKnowledgeBases(result.items);
                }
            } catch (err) {
                if (!cancelled) {
                    toast.error("加载知识库列表失败: " + getApiErrorMessage(err));
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, [toast]);

    // Close dropdown on outside click
    useEffect(() => {
        function handleClickOutside(e: MouseEvent) {
            if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
                setDropdownOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const filteredKBs = useMemo(() => {
        if (!searchText.trim()) return knowledgeBases;
        const lower = searchText.toLowerCase();
        return knowledgeBases.filter((kb) => kb.name.toLowerCase().includes(lower));
    }, [knowledgeBases, searchText]);

    const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);

    function toggleKB(id: string) {
        if (selectedSet.has(id)) {
            onChange(selectedIds.filter((sid) => sid !== id));
        } else {
            onChange([...selectedIds, id]);
        }
    }

    function removeKB(id: string) {
        onChange(selectedIds.filter((sid) => sid !== id));
    }

    const selectedKBs = knowledgeBases.filter((kb) => selectedSet.has(kb.id));

    return (
        <div className="space-y-2" ref={containerRef}>
            <label className="block text-sm font-medium text-slate-700">
                选择知识库
            </label>

            {/* Selected KB badges */}
            {selectedKBs.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                    {selectedKBs.map((kb) => (
                        <Badge
                            key={kb.id}
                            variant="secondary"
                            className="flex items-center gap-1 pr-1 text-xs"
                        >
                            <FileText className="h-3 w-3" />
                            {kb.name}
                            <button
                                type="button"
                                onClick={() => removeKB(kb.id)}
                                className="ml-0.5 rounded-full p-0.5 hover:bg-slate-300/50"
                            >
                                <X className="h-3 w-3" />
                            </button>
                        </Badge>
                    ))}
                </div>
            )}

            {/* Search input */}
            <div className="relative">
                <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <Input
                    value={searchText}
                    onChange={(e) => {
                        setSearchText(e.target.value);
                        setDropdownOpen(true);
                    }}
                    onFocus={() => setDropdownOpen(true)}
                    placeholder="搜索知识库..."
                    className="h-10 pl-9"
                />
            </div>

            {/* Dropdown list */}
            {dropdownOpen && (
                <div className="max-h-60 overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-md">
                    {loading ? (
                        <div className="flex items-center justify-center py-6">
                            <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
                            <span className="ml-2 text-sm text-slate-500">加载中...</span>
                        </div>
                    ) : filteredKBs.length === 0 ? (
                        <div className="py-6 text-center text-sm text-slate-400">
                            {searchText ? "没有匹配的知识库" : "暂无知识库"}
                        </div>
                    ) : (
                        filteredKBs.map((kb) => {
                            const isSelected = selectedSet.has(kb.id);
                            return (
                                <button
                                    key={kb.id}
                                    type="button"
                                    onClick={() => toggleKB(kb.id)}
                                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-slate-50"
                                >
                                    <span
                                        className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                                            isSelected
                                                ? "border-indigo-600 bg-indigo-600 text-white"
                                                : "border-slate-300 bg-white"
                                        }`}
                                    >
                                        {isSelected && (
                                            <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none">
                                                <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                            </svg>
                                        )}
                                    </span>
                                    <div className="min-w-0 flex-1">
                                        <span className="truncate font-medium text-slate-900">{kb.name}</span>
                                        <span className="ml-1 text-xs text-slate-400">
                                            ({kb.document_count ?? kb.doc_count ?? 0} 篇文档)
                                        </span>
                                    </div>
                                </button>
                            );
                        })
                    )}
                </div>
            )}
        </div>
    );
}
