"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AdminAssetRefPicker, type AssetRefPickerOption } from "@/components/admin/asset-ref-picker";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { debug } from "@/lib/debug";

interface PersonaRefPickerProps {
    value: string;
    onChange: (personaId: string) => void;
    error?: string | null;
}

export function PersonaRefPicker({ value, onChange, error }: PersonaRefPickerProps) {
    const [options, setOptions] = useState<AssetRefPickerOption[]>([]);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);

    const loadPersonas = useCallback(async () => {
        setLoading(true);
        setLoadError(null);
        try {
            const response = await api.admin.getPersonas({ page: 1, page_size: 200 });
            setOptions(
                response.items.map((persona) => ({
                    id: persona.id,
                    label: persona.name,
                    subtitle: persona.category,
                    status: persona.status === "active" ? "启用中" : "已停用",
                    editHref: `/admin/personas/${persona.id}`,
                    selectable: persona.status === "active",
                    publishHint: persona.status === "active" ? undefined : "去启用",
                })),
            );
        } catch (err) {
            setLoadError(getApiErrorMessage(err));
            debug.warn("[PersonaRefPicker] failed to load personas", { error: err });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void Promise.resolve().then(loadPersonas);
    }, [loadPersonas]);

    const selectedHref = useMemo(
        () => (value ? `/admin/personas/${value}` : null),
        [value],
    );

    return (
        <div className="space-y-1">
            <AdminAssetRefPicker
                label="关联 Persona（可选）"
                value={value}
                onChange={onChange}
                options={options}
                loading={loading}
                placeholder="搜索 Persona…"
                emptyMessage="暂无 Persona，请先在角色管理中创建"
                error={error ?? loadError}
            />
            {selectedHref ? (
                <Link href={selectedHref} className="text-xs font-medium text-blue-700 hover:text-blue-900">
                    查看 Persona 详情
                </Link>
            ) : (
                <p className="text-xs text-slate-500">
                    用于弱关联实时对练人格；留空则仅使用本角色库的行为规则。
                </p>
            )}
        </div>
    );
}

export function validatePersonaRef(
    personaRef: string,
    options: AssetRefPickerOption[],
): string | null {
    const trimmed = personaRef.trim();
    if (!trimmed) return null;
    const match = options.find((option) => option.id === trimmed);
    if (!match) return "所选 Persona 不存在，请重新选择。";
    if (!match.selectable) return "所选 Persona 未启用，请先在角色管理中启用。";
    return null;
}
