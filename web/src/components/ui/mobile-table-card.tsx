"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

interface MobileTableCardProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
    title: React.ReactNode;
    icon?: React.ReactNode;
    status?: {
        label: string;
        state: "default" | "success" | "warning" | "error" | "secondary";
    };
    columns?: {
        label: string;
        value: React.ReactNode;
    }[];
    actions?: React.ReactNode;
    children?: React.ReactNode;
}

export function MobileTableCard({
    title,
    icon,
    status,
    columns,
    actions,
    children,
    className,
    ...props
}: MobileTableCardProps) {
    return (
        <div
            className={cn(
                "bg-white rounded-2xl p-4 border border-slate-100 shadow-sm flex flex-col gap-4",
                className
            )}
            {...props}
        >
            {/* Header */}
            <div className="flex justify-between items-start">
                <div className="flex items-center gap-3">
                    {icon && (
                        <div className="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600 shrink-0">
                            {icon}
                        </div>
                    )}
                    <div>
                        <div className="font-semibold text-slate-800 text-lg flex items-center gap-2">
                            {title}
                            {status && (
                                <Badge variant={status.state === 'success' ? 'green' : 'secondary'}>
                                    {status.label}
                                </Badge>
                            )}
                        </div>
                        {children && <div className="mt-1">{children}</div>}
                    </div>
                </div>
            </div>

            {/* Columns (Grid) */}
            {columns && columns.length > 0 && (
                <div className="grid grid-cols-2 gap-4 text-sm mt-2 pt-4 border-t border-slate-50">
                    {columns.map((col, idx) => (
                        <div key={idx}>
                            <span className="text-slate-400 text-[10px] uppercase font-bold block mb-1 tracking-wider">{col.label}</span>
                            <div className="font-medium text-slate-700">{col.value}</div>
                        </div>
                    ))}
                </div>
            )}

            {/* Actions */}
            {actions && (
                <div className="pt-2">
                    {actions}
                </div>
            )}
        </div>
    );
}
