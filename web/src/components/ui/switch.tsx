"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

const Switch = React.forwardRef<
    HTMLInputElement,
    Omit<React.InputHTMLAttributes<HTMLInputElement>, "type" | "onChange" | "checked"> & {
        checked?: boolean;
        onCheckedChange?: (checked: boolean) => void;
    }
>(({ className, checked, onCheckedChange, disabled, ...props }, ref) => (
    <label
        className={cn(
            "relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
            checked ? "bg-indigo-600" : "bg-slate-200",
            className
        )}
    >
        <input
            type="checkbox"
            className="sr-only"
            checked={checked}
            onChange={(e) => onCheckedChange?.(e.target.checked)}
            disabled={disabled}
            ref={ref}
            {...props}
        />
        <span
            className={cn(
                "pointer-events-none block h-5 w-5 rounded-full bg-white shadow-lg ring-0 transition-transform",
                checked ? "translate-x-5" : "translate-x-0"
            )}
        />
    </label>
));
Switch.displayName = "Switch";

export { Switch };
