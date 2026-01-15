import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Search } from "lucide-react";

interface EmptyStateProps {
    title: string;
    description: string;
    actionLabel?: string;
    onAction?: () => void;
    icon?: React.ReactNode;
}

export function EmptyState({ title, description, actionLabel, onAction, icon }: EmptyStateProps) {
    return (
        <GlassCard className="flex flex-col items-center justify-center py-16 px-4 text-center">
            <div className="w-24 h-24 bg-slate-50 rounded-full flex items-center justify-center mb-6 animate-pulse">
                {icon || <Search className="w-10 h-10 text-slate-300" />}
            </div>
            <h3 className="text-xl font-bold text-slate-900 mb-2">{title}</h3>
            <p className="text-slate-500 max-w-md mb-8">{description}</p>
            {actionLabel && onAction && (
                <Button onClick={onAction} className="rounded-full px-8">
                    {actionLabel}
                </Button>
            )}
        </GlassCard>
    );
}
