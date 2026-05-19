"use client";

interface JsonEditorWithValidationProps {
    label: string;
    value: string;
    onChange: (value: string) => void;
    validationMessage: string;
    isValid: boolean;
    rows?: number;
    className?: string;
    helpText?: string;
}

export function JsonEditorWithValidation({
    label,
    value,
    onChange,
    validationMessage,
    isValid,
    rows = 8,
    className = "",
    helpText,
}: JsonEditorWithValidationProps) {
    return (
        <label className={`block space-y-2 text-sm font-medium text-slate-700 ${className}`}>
            <span>{label}</span>
            {helpText ? <span className="block text-xs font-normal text-slate-500">{helpText}</span> : null}
            <textarea
                aria-label={label}
                value={value}
                onChange={(event) => onChange(event.target.value)}
                className="w-full rounded-2xl border border-slate-200 bg-slate-950 p-4 font-mono text-xs leading-5 text-slate-100 outline-none focus:ring-2 focus:ring-slate-400"
                rows={rows}
                spellCheck={false}
            />
            <span className={`block rounded-2xl border p-3 text-sm ${isValid ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-red-200 bg-red-50 text-red-800"}`}>
                {validationMessage}
            </span>
        </label>
    );
}
