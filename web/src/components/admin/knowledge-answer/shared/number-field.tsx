"use client";

import { Input } from "@/components/ui/input";

interface NumberFieldProps {
    label: string;
    description?: string;
    value: number;
    onChange: (value: number) => void;
    min?: number;
    max?: number;
    step?: number;
    disabled?: boolean;
    placeholder?: string;
}

export function NumberField({
    label,
    description,
    value,
    onChange,
    min,
    max,
    step = 0.1,
    disabled,
    placeholder,
}: NumberFieldProps) {
    return (
        <div className="space-y-1.5">
            <label className="block text-sm font-medium text-slate-700">
                {label}
            </label>
            {description && (
                <p className="text-xs text-slate-500">{description}</p>
            )}
            <Input
                type="number"
                value={value}
                onChange={(e) => {
                    const v = parseFloat(e.target.value);
                    if (!isNaN(v)) onChange(v);
                }}
                min={min}
                max={max}
                step={step}
                disabled={disabled}
                placeholder={placeholder}
                className="h-10"
            />
        </div>
    );
}
