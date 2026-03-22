"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Check } from "lucide-react";

const Checkbox = React.forwardRef<
    HTMLInputElement,
    Omit<React.InputHTMLAttributes<HTMLInputElement>, "type" | "onChange" | "checked"> & {
        checked?: boolean;
        onCheckedChange?: (checked: boolean) => void;
    }
>(({ className, checked, onCheckedChange, disabled, ...props }, ref) => (
    <label
        className={cn(
            "relative flex h-5 w-5 shrink-0 cursor-pointer items-center justify-center rounded-md border-2 transition-all",
            checked
                ? "border-indigo-600 bg-indigo-600"
                : "border-slate-300 bg-white hover:border-slate-400",
            disabled && "cursor-not-allowed opacity-50",
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
        <Check
            className={cn(
                "h-3.5 w-3.5 text-white transition-opacity",
                checked ? "opacity-100" : "opacity-0"
            )}
            strokeWidth={3}
        />
    </label>
));
Checkbox.displayName = "Checkbox";

export { Checkbox };
