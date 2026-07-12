"use client";

import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";

export function StringListField({
    label,
    itemLabel,
    values,
    onChange,
    maxItems = 10,
}: {
    label: string;
    itemLabel: string;
    values: string[];
    onChange: (values: string[]) => void;
    maxItems?: number;
}) {
    return <fieldset className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
        <legend className="sr-only">{label}</legend>
        <div className="flex items-center justify-between gap-3"><p className="text-sm font-semibold text-slate-800">{label}</p><Button type="button" size="sm" variant="ghost" disabled={values.length >= maxItems} onClick={() => onChange([...values, ""])}><Plus className="mr-1.5 h-4 w-4" />添加{itemLabel}</Button></div>
        <div className="mt-3 space-y-2">
            {values.length === 0 ? <p className="rounded-xl border border-dashed border-slate-300 bg-white px-3 py-3 text-sm text-slate-500">还没有{itemLabel}，添加后学员会更容易理解任务。</p> : null}
            {values.map((value, index) => <div key={index} className="flex items-center gap-2">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white">{index + 1}</span>
                <label className="min-w-0 flex-1"><span className="sr-only">{itemLabel} {index + 1}</span><input aria-label={`${itemLabel} ${index + 1}`} value={value} maxLength={240} onChange={(event) => onChange(values.map((item, itemIndex) => itemIndex === index ? event.target.value : item))} className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100" /></label>
                <Button type="button" size="icon" variant="ghost" className="h-10 w-10 text-red-600" aria-label={`删除${itemLabel} ${index + 1}`} onClick={() => onChange(values.filter((_, itemIndex) => itemIndex !== index))}><Trash2 className="h-4 w-4" /></Button>
            </div>)}
        </div>
    </fieldset>;
}
