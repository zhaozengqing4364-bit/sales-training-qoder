"use client";

import { useState, useCallback } from "react";
import { X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

interface SlotEditorProps {
    label: string;
    description?: string;
    slots: string[];
    onChange: (slots: string[]) => void;
    placeholder?: string;
    disabled?: boolean;
}

export function SlotEditor({
    label,
    description,
    slots,
    onChange,
    placeholder = "输入名称后按 Enter 添加",
    disabled,
}: SlotEditorProps) {
    const [inputValue, setInputValue] = useState("");

    const addSlot = useCallback(() => {
        const trimmed = inputValue.trim();
        if (trimmed && !slots.includes(trimmed)) {
            onChange([...slots, trimmed]);
            setInputValue("");
        }
    }, [inputValue, slots, onChange]);

    const removeSlot = useCallback(
        (slot: string) => {
            onChange(slots.filter((s) => s !== slot));
        },
        [slots, onChange],
    );

    return (
        <div className="space-y-1.5">
            <label className="block text-sm font-medium text-slate-700">
                {label}
            </label>
            {description && (
                <p className="text-xs text-slate-500">{description}</p>
            )}
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-2">
                {slots.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                        {slots.map((slot) => (
                            <Badge
                                key={slot}
                                variant="secondary"
                                className="gap-1 bg-white text-slate-700 border border-slate-200 pr-1"
                            >
                                {slot}
                                {!disabled && (
                                    <button
                                        type="button"
                                        onClick={() => removeSlot(slot)}
                                        className="ml-0.5 rounded-full p-0.5 hover:bg-slate-200"
                                    >
                                        <X className="h-3 w-3" />
                                    </button>
                                )}
                            </Badge>
                        ))}
                    </div>
                )}
                {!disabled && (
                    <Input
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === "Enter") {
                                e.preventDefault();
                                addSlot();
                            }
                        }}
                        placeholder={placeholder}
                        className="h-9 text-xs"
                    />
                )}
            </div>
        </div>
    );
}
