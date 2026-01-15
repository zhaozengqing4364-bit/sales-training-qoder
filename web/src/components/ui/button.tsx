"use client";

import { ButtonHTMLAttributes, forwardRef } from "react";
import { Slot } from "@radix-ui/react-slot";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: "primary" | "secondary" | "outline" | "ghost" | "danger" | "destructive";
    size?: "sm" | "md" | "lg" | "icon";
    isLoading?: boolean;
    asChild?: boolean;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
    ({ className, variant = "primary", size = "md", isLoading, asChild = false, children, disabled, ...props }, ref) => {
        const Comp = asChild ? Slot : "button";
        return (
            <Comp
                ref={ref}
                disabled={disabled || isLoading}
                className={cn(
                    "inline-flex items-center justify-center rounded-full font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:opacity-50 disabled:pointer-events-none active:scale-[0.98]",
                    {
                        // Primary: Dark Slate (The Anchor)
                        "bg-slate-900 text-white hover:bg-slate-800 shadow-md hover:shadow-xl hover:shadow-slate-900/20": variant === "primary",

                        // Secondary: White Card-like
                        "bg-white text-slate-700 border border-gray-200 hover:bg-gray-50 hover:border-gray-300 shadow-sm hover:shadow-md": variant === "secondary",

                        // Outline
                        "border border-slate-200 bg-transparent hover:bg-slate-50 text-slate-900": variant === "outline",

                        // Ghost
                        "hover:bg-slate-100 text-slate-600 hover:text-slate-900": variant === "ghost",

                        // Danger / Destructive
                        "bg-red-50 text-red-600 hover:bg-red-100": variant === "danger" || variant === "destructive",

                        // Sizes
                        "h-8 px-3 text-xs": size === "sm",
                        "h-11 px-6 text-sm": size === "md",
                        "h-14 px-8 text-base": size === "lg",
                        "h-10 w-10 p-0 rounded-full": size === "icon",
                    },
                    className
                )}
                {...props}
            >
                {asChild ? children : (
                    <>
                        {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        {children}
                    </>
                )}
            </Comp>
        );
    }
);
Button.displayName = "Button";

export { Button };
