import { cn } from "@/lib/utils";

function Skeleton({
    className,
    ...props
}: React.HTMLAttributes<HTMLDivElement>) {
    return (
        <div
            className={cn("animate-pulse rounded-2xl bg-slate-200/50", className)}
            {...props}
        />
    );
}

export { Skeleton };
