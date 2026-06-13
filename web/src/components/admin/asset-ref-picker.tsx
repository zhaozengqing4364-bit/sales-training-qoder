"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { ExternalLink, Loader2, Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import type { AssetRefPickerOption } from "@/lib/admin/asset-ref-types";

export type { AssetRefPickerOption } from "@/lib/admin/asset-ref-types";

interface AdminAssetRefPickerProps {
    label: string;
    value: string;
    onChange: (id: string) => void;
    options: AssetRefPickerOption[];
    loading?: boolean;
    placeholder?: string;
    emptyMessage?: string;
    error?: string | null;
}

export function AdminAssetRefPicker({
    label,
    value,
    onChange,
    options,
    loading = false,
    placeholder = "搜索并选择…",
    emptyMessage = "暂无可用资产",
    error,
}: AdminAssetRefPickerProps) {
    const [searchText, setSearchText] = useState("");
    const [dropdownOpen, setDropdownOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    const selected = useMemo(
        () => options.find((option) => option.id === value) ?? null,
        [options, value],
    );

    const filtered = useMemo(() => {
        const query = searchText.trim().toLowerCase();
        if (!query) return options;
        return options.filter((option) => {
            const haystack = [option.label, option.subtitle ?? "", option.id].join(" ").toLowerCase();
            return haystack.includes(query);
        });
    }, [options, searchText]);

    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setDropdownOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    return (
        <div className="space-y-1" ref={containerRef}>
            <label className="text-sm font-medium text-slate-700">
                <span>{label}</span>
            </label>
            {selected ? (
                <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm">
                    <span className="font-medium text-slate-900">{selected.label}</span>
                    <span className="font-mono text-xs text-slate-400">{selected.id}</span>
                    {selected.subtitle ? (
                        <span className="text-xs text-slate-500">{selected.subtitle}</span>
                    ) : null}
                    {!selected.selectable ? (
                        <Link
                            href={selected.editHref}
                            className="text-xs font-medium text-amber-700 hover:text-amber-900"
                        >
                            去发布
                        </Link>
                    ) : null}
                    <button
                        type="button"
                        className="ml-auto text-xs text-slate-500 hover:text-slate-800"
                        onClick={() => onChange("")}
                    >
                        清除
                    </button>
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
                    placeholder={placeholder}
                    className="h-10 pl-9"
                    aria-label={label}
                />
            </div>
            {error ? <p className="text-xs text-red-600">{error}</p> : null}
            {dropdownOpen ? (
                <div className="max-h-60 overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-md">
                    {loading ? (
                        <div className="flex items-center justify-center py-6 text-sm text-slate-500">
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            加载中…
                        </div>
                    ) : filtered.length === 0 ? (
                        <div className="py-6 text-center text-sm text-slate-400">{emptyMessage}</div>
                    ) : (
                        filtered.map((option) => (
                            <button
                                key={option.id}
                                type="button"
                                disabled={!option.selectable}
                                onClick={() => {
                                    if (!option.selectable) return;
                                    onChange(option.id);
                                    setSearchText("");
                                    setDropdownOpen(false);
                                }}
                                className={`flex w-full items-start gap-2 px-3 py-2 text-left text-sm transition-colors ${
                                    option.selectable
                                        ? "hover:bg-slate-50 text-slate-900"
                                        : "cursor-not-allowed bg-slate-50/80 text-slate-400"
                                }`}
                            >
                                <div className="min-w-0 flex-1">
                                    <div className="font-medium">{option.label}</div>
                                    <div className="truncate font-mono text-xs text-slate-400">{option.id}</div>
                                    {option.subtitle ? (
                                        <div className="text-xs text-slate-500">{option.subtitle}</div>
                                    ) : null}
                                    <div className="text-xs text-slate-400">{option.status}</div>
                                </div>
                                {!option.selectable ? (
                                    <Link
                                        href={option.editHref}
                                        className="shrink-0 inline-flex items-center gap-1 text-xs font-medium text-amber-700 hover:text-amber-900"
                                        onClick={(event) => event.stopPropagation()}
                                    >
                                        去发布
                                        <ExternalLink className="h-3 w-3" />
                                    </Link>
                                ) : null}
                            </button>
                        ))
                    )}
                </div>
            ) : null}
        </div>
    );
}
