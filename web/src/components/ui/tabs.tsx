"use client";

import React, { createContext, useContext, useMemo, useState } from "react";
import { cn } from "@/lib/utils";

type TabsContextValue = {
    value: string;
    onValueChange: (value: string) => void;
};

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabsContext(): TabsContextValue {
    const context = useContext(TabsContext);
    if (!context) {
        throw new Error("Tabs components must be used within <Tabs>");
    }
    return context;
}

type TabsProps = {
    value?: string;
    defaultValue?: string;
    onValueChange?: (value: string) => void;
    className?: string;
    children: React.ReactNode;
};

export function Tabs({
    value,
    defaultValue = "",
    onValueChange,
    className,
    children,
}: TabsProps) {
    const [internalValue, setInternalValue] = useState(defaultValue);
    const currentValue = value ?? internalValue;

    const context = useMemo<TabsContextValue>(() => ({
        value: currentValue,
        onValueChange: (nextValue: string) => {
            if (value === undefined) {
                setInternalValue(nextValue);
            }
            onValueChange?.(nextValue);
        },
    }), [currentValue, onValueChange, value]);

    return (
        <TabsContext.Provider value={context}>
            <div className={cn("w-full", className)}>{children}</div>
        </TabsContext.Provider>
    );
}

type TabsListProps = React.HTMLAttributes<HTMLDivElement>;

export function TabsList({ className, children, ...props }: TabsListProps) {
    return (
        <div className={cn("inline-flex items-center gap-1", className)} {...props}>
            {children}
        </div>
    );
}

type TabsTriggerProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
    value: string;
};

export function TabsTrigger({ value, className, children, ...props }: TabsTriggerProps) {
    const { value: activeValue, onValueChange } = useTabsContext();
    const isActive = activeValue === value;

    return (
        <button
            type="button"
            aria-selected={isActive}
            data-state={isActive ? "active" : "inactive"}
            onClick={() => onValueChange(value)}
            className={cn(
                "inline-flex items-center justify-center text-sm font-medium transition-colors",
                "px-3 py-1.5 text-slate-600 hover:text-slate-900",
                "data-[state=active]:bg-white data-[state=active]:text-slate-900",
                className
            )}
            {...props}
        >
            {children}
        </button>
    );
}

type TabsContentProps = React.HTMLAttributes<HTMLDivElement> & {
    value: string;
};

export function TabsContent({ value, className, children, ...props }: TabsContentProps) {
    const { value: activeValue } = useTabsContext();
    if (activeValue !== value) {
        return null;
    }

    return (
        <div className={cn("w-full", className)} {...props}>
            {children}
        </div>
    );
}
