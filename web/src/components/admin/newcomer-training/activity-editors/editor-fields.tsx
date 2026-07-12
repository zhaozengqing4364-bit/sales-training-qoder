import { Button } from "@/components/ui/button";
import type { QuickCreateKind, ResourceOption } from "./types";

export const controlClass = "mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100";

export function ResourceSelect({ label, value, options, disabled, onChange, quickCreate, onQuickCreate }: {
    label: string; value: string | null; options: ResourceOption[]; disabled?: boolean; onChange: (id: string) => void;
    quickCreate?: QuickCreateKind; onQuickCreate?: (kind: QuickCreateKind) => void;
}) {
    return <div><label className="block text-sm font-medium text-slate-700">{label}<select aria-label={label} className={controlClass} value={value ?? ""} disabled={disabled} onChange={(event) => onChange(event.target.value)}><option value="">请选择</option>{options.filter((item) => item.status === "published").map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>{quickCreate && onQuickCreate && <Button type="button" size="sm" variant="ghost" disabled={disabled} className="mt-1" onClick={() => onQuickCreate(quickCreate)}>当前页快速新建</Button>}</div>;
}

export function NumberField({ label, value, min = 0, max, disabled, onChange }: { label: string; value: number | null; min?: number; max?: number; disabled?: boolean; onChange: (value: number | null) => void }) {
    return <label className="block text-sm font-medium text-slate-700">{label}<input aria-label={label} type="number" className={controlClass} min={min} max={max} value={value ?? ""} disabled={disabled} onChange={(event) => onChange(event.target.value === "" ? null : Number(event.target.value))} /></label>;
}

export function AdvancedSettings({ children }: { children: React.ReactNode }) {
    return <details className="rounded-xl border border-slate-200 bg-slate-50 p-3"><summary className="cursor-pointer text-sm font-medium text-slate-700">高级设置</summary><div className="mt-3 space-y-3">{children}</div></details>;
}
