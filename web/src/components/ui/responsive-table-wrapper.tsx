import * as React from "react";
import { cn } from "@/lib/utils";

interface ResponsiveTableWrapperProps {
    children: React.ReactNode; // Desktop Table
    mobileCards: React.ReactNode; // Mobile Card List
    className?: string;
}

export function ResponsiveTableWrapper({
    children,
    mobileCards,
    className,
}: ResponsiveTableWrapperProps) {
    return (
        <div className={cn("w-full transition-all duration-300", className)}>
            <div className="hidden md:block w-full">{children}</div>
            <div className="md:hidden w-full space-y-4">{mobileCards}</div>
        </div>
    );
}
