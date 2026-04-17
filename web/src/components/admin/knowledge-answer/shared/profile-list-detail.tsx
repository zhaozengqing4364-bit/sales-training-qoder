"use client";

import { useState, useCallback } from "react";
import { Loader2, Plus, Search } from "lucide-react";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";

export interface ProfileItem {
    id: string;
    enabled: boolean;
}

interface ProfileListDetailProps<T extends ProfileItem> {
    items: T[];
    loading: boolean;
    searchPlaceholder?: string;
    newItemLabel?: string;
    renderItemLabel: (item: T) => string;
    renderItemMeta?: (item: T) => React.ReactNode;
    renderDetail: (props: {
        item: T | null;
        isCreating: boolean;
        onSave: (data: Partial<T>) => void;
        onDelete: (id: string) => void;
        onCancel: () => void;
        onChange: (field: string, value: unknown) => void;
    }) => React.ReactNode;
    onCreateNew: () => T;
    onSave: (data: Partial<T>, isCreating: boolean) => Promise<T | void>;
    onDelete: (id: string) => Promise<void>;
    onToggleEnabled?: (item: T, enabled: boolean) => Promise<void>;
    reloadItems: () => Promise<void>;
}

export function ProfileListDetail<T extends ProfileItem>({
    items,
    loading,
    searchPlaceholder = "搜索...",
    newItemLabel = "新增",
    renderItemLabel,
    renderItemMeta,
    renderDetail,
    onCreateNew,
    onSave,
    onDelete,
    onToggleEnabled,
    reloadItems,
}: ProfileListDetailProps<T>) {
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [isCreating, setIsCreating] = useState(false);
    const [draftItem, setDraftItem] = useState<T | null>(null);
    const [saving, setSaving] = useState(false);

    const filteredItems = items.filter((item) =>
        renderItemLabel(item).toLowerCase().includes(searchQuery.toLowerCase()),
    );

    const selectedItem = isCreating
        ? null
        : items.find((i) => i.id === selectedId) ?? null;

    const activeItem = isCreating ? draftItem : draftItem ?? selectedItem;

    const handleSelect = useCallback(
        (id: string) => {
            setIsCreating(false);
            if (id === selectedId) {
                setSelectedId(null);
                setDraftItem(null);
            } else {
                setSelectedId(id);
                // Clone the selected item into draft so handleChange can mutate it
                const found = items.find((i) => i.id === id);
                setDraftItem(found ? { ...found } : null);
            }
        },
        [selectedId, items],
    );

    const handleNew = useCallback(() => {
        const draft = onCreateNew();
        setDraftItem(draft);
        setIsCreating(true);
        setSelectedId(null);
    }, [onCreateNew]);

    const handleCancel = useCallback(() => {
        setIsCreating(false);
        setDraftItem(null);
        setSelectedId(null);
    }, []);

    const handleChange = useCallback((field: string, value: unknown) => {
        setDraftItem((prev) => {
            if (!prev) return prev;
            return { ...prev, [field]: value };
        });
    }, []);

    const handleSave = useCallback(
        (data: Partial<T>) => {
            setSaving(true);
            void onSave(data, isCreating)
                .then(() => reloadItems())
                .then(() => handleCancel())
                .finally(() => setSaving(false));
        },
        [isCreating, onSave, reloadItems, handleCancel],
    );

    const handleDelete = useCallback(
        (id: string) => {
            setSaving(true);
            void onDelete(id)
                .then(() => reloadItems())
                .then(() => {
                    if (selectedId === id) setSelectedId(null);
                })
                .finally(() => setSaving(false));
        },
        [onDelete, reloadItems, selectedId],
    );

    return (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            {/* Left: List */}
            <div className="lg:col-span-1 space-y-2">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <Input
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder={searchPlaceholder}
                        className="h-10 pl-9 text-xs"
                    />
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    className="w-full text-xs rounded-full"
                    onClick={handleNew}
                >
                    <Plus className="mr-1 h-3.5 w-3.5" /> {newItemLabel}
                </Button>
                <div className="max-h-[500px] space-y-1.5 overflow-y-auto">
                    {loading ? (
                        <div className="flex items-center gap-2 py-4 text-xs text-slate-500">
                            <Loader2 className="h-4 w-4 animate-spin" /> 加载中
                        </div>
                    ) : filteredItems.length === 0 ? (
                        <p className="py-4 text-center text-xs text-slate-400">
                            {searchQuery ? "无匹配结果" : "暂无数据"}
                        </p>
                    ) : (
                        filteredItems.map((item) => {
                            const isSelected = !isCreating && selectedId === item.id;
                            return (
                                <button
                                    key={item.id}
                                    type="button"
                                    onClick={() => handleSelect(item.id)}
                                    className={`w-full rounded-xl border p-3 text-left transition ${
                                        isSelected
                                            ? "border-blue-300 bg-blue-50"
                                            : "border-slate-200 bg-white hover:bg-slate-50"
                                    }`}
                                >
                                    <div className="flex items-center justify-between gap-2">
                                        <span className="text-sm font-medium text-slate-900 truncate">
                                            {renderItemLabel(item)}
                                        </span>
                                        {onToggleEnabled && (
                                            <Switch
                                                checked={item.enabled}
                                                onCheckedChange={(checked) =>
                                                    void onToggleEnabled(item, checked)
                                                }
                                                onClick={(e) => e.stopPropagation()}
                                                className="scale-75"
                                            />
                                        )}
                                    </div>
                                    {renderItemMeta && (
                                        <div className="mt-1 flex flex-wrap gap-1">
                                            {renderItemMeta(item)}
                                        </div>
                                    )}
                                </button>
                            );
                        })
                    )}
                </div>
            </div>

            {/* Right: Detail */}
            <div className="lg:col-span-2">
                {activeItem || isCreating ? (
                    <GlassCard className="p-4 space-y-4">
                        {saving && (
                            <div className="flex items-center gap-2 text-xs text-slate-500">
                                <Loader2 className="h-3.5 w-3.5 animate-spin" /> 保存中...
                            </div>
                        )}
                        {renderDetail({
                            item: activeItem as T | null,
                            isCreating,
                            onSave: handleSave,
                            onDelete: handleDelete,
                            onCancel: handleCancel,
                            onChange: handleChange,
                        })}
                    </GlassCard>
                ) : (
                    <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 p-8">
                        <p className="text-sm text-slate-400">
                            从左侧选择一项进行编辑，或点击&quot;{newItemLabel}&quot;创建
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
