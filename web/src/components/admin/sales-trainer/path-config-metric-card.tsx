import { GlassCard } from "@/components/ui/glass-card";

interface PathConfigMetricCardProps {
    readonly label: string;
    readonly value: number;
    readonly tone?: "default" | "danger" | "warning";
}

export function PathConfigMetricCard({
    label,
    value,
    tone = "default",
}: PathConfigMetricCardProps) {
    const valueClass = tone === "danger"
        ? "text-red-700"
        : tone === "warning"
            ? "text-amber-700"
            : "text-slate-900";
    return (
        <GlassCard className="p-4">
            <p className="text-xs font-bold uppercase text-slate-400">{label}</p>
            <p className={`mt-2 text-3xl font-black ${valueClass}`}>{value}</p>
        </GlassCard>
    );
}
