import { cn } from "@/lib/utils";
import { ReactNode, HTMLAttributes } from "react";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
    children: ReactNode;
    variant?: "blue" | "purple" | "green" | "orange" | "gray" | "red" | "neutral" | "secondary";
    className?: string;
}

export function Badge({ children, variant = "blue", className, ...props }: BadgeProps) {
    const variants = {
        blue: "bg-blue-50 text-blue-700 border-blue-100",
        purple: "bg-purple-50 text-purple-700 border-purple-100",
        green: "bg-emerald-50 text-emerald-700 border-emerald-100",
        orange: "bg-orange-50 text-orange-700 border-orange-100",
        gray: "bg-slate-100 text-slate-700 border-slate-200",
        red: "bg-red-50 text-red-700 border-red-100",
        neutral: "bg-white border-gray-200 text-gray-900",
        secondary: "bg-slate-100 text-slate-600 border-slate-200",
    };

    return (
        <span 
            className={cn("inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border", variants[variant], className)}
            {...props}
        >
            {children}
        </span>
    );
}