
import { cn } from "@/lib/utils";

interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
    children?: React.ReactNode;
    className?: string;
    hoverEffect?: boolean;
}

export function GlassCard({ children, className, hoverEffect = false, ...props }: GlassCardProps) {
    return (
        <div
            className={cn(
                "rounded-[2rem] bg-white/70 backdrop-blur-xl border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] relative overflow-hidden transition-all duration-300",
                hoverEffect && "hover:bg-white/90 hover:border-white/80 hover:shadow-[0_20px_40px_rgba(0,0,0,0.06)] hover:-translate-y-1 cursor-pointer",
                className
            )}
            {...props}
        >
            {/* Subtle top shine for 3D feel */}
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/60 to-transparent opacity-70" />

            {children}
        </div>
    );
}
