"use client";

import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface WeightEditorProps {
    label: string;
    description?: string;
    weights: Record<string, number>;
    onChange: (weights: Record<string, number>) => void;
    suggestedKeys?: string[];
    keyPlaceholder?: string;
    valueMin?: number;
    valueMax?: number;
    valueStep?: number;
    disabled?: boolean;
}

export function WeightEditor({
    label,
    description,
    weights,
    onChange,
    keyPlaceholder = "键名",
    valueMin = 0,
    valueMax = 2,
    valueStep = 0.05,
    disabled,
}: WeightEditorProps) {
    const entries = Object.entries(weights);

    const addEntry = () => {
        onChange({ ...weights, "": 0 });
    };

    const removeEntry = (key: string) => {
        const next = { ...weights };
        delete next[key];
        onChange(next);
    };

    const updateKey = (oldKey: string, newKey: string) => {
        const next: Record<string, number> = {};
        for (const [k, v] of Object.entries(weights)) {
            next[k === oldKey ? newKey : k] = v;
        }
        onChange(next);
    };

    const updateValue = (key: string, value: number) => {
        onChange({ ...weights, [key]: value });
    };

    return (
        <div className="space-y-1.5">
            <label className="block text-sm font-medium text-slate-700">
                {label}
            </label>
            {description && (
                <p className="text-xs text-slate-500">{description}</p>
            )}
            <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-3">
                {entries.length === 0 && (
                    <p className="text-xs text-slate-400 py-2">暂无权重配置</p>
                )}
                {entries.map(([key, value]) => (
                    <div key={key} className="flex items-center gap-2">
                        <Input
                            value={key}
                            onChange={(e) => updateKey(key, e.target.value)}
                            placeholder={keyPlaceholder}
                            disabled={disabled}
                            className="h-9 flex-1 text-xs"
                        />
                        <Input
                            type="number"
                            value={value}
                            onChange={(e) => {
                                const v = parseFloat(e.target.value);
                                if (!isNaN(v)) updateValue(key, v);
                            }}
                            min={valueMin}
                            max={valueMax}
                            step={valueStep}
                            disabled={disabled}
                            className="h-9 w-24 text-xs"
                        />
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0 text-slate-400 hover:text-red-500"
                            onClick={() => removeEntry(key)}
                            disabled={disabled}
                        >
                            <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                    </div>
                ))}
                <Button
                    variant="outline"
                    size="sm"
                    className="h-8 text-xs rounded-full"
                    onClick={addEntry}
                    disabled={disabled}
                >
                    <Plus className="mr-1 h-3 w-3" /> 添加
                </Button>
            </div>
        </div>
    );
}
