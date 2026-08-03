"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowLeft } from "lucide-react";

import { cn } from "@/lib/utils";

export interface AdminPageHeaderProps {
    title: string;
    description?: string;
    icon?: ReactNode;
    primaryAction?: ReactNode;
    secondaryActions?: ReactNode;
    className?: string;
}

export function AdminPageHeader({
    title,
    description,
    icon,
    primaryAction,
    secondaryActions,
    className,
}: AdminPageHeaderProps) {
    return (
        <header
            className={cn(
                "flex flex-col gap-4 md:flex-row md:items-end md:justify-between",
                className,
            )}
        >
            <div>
                <div className="flex items-center gap-2">
                    {icon}
                    <h1 className="text-3xl font-black tracking-tight text-slate-900">{title}</h1>
                </div>
                {description ? (
                    <p className="mt-1 max-w-3xl text-sm text-slate-500">{description}</p>
                ) : null}
            </div>
            {(primaryAction || secondaryActions) && (
                <div className="flex flex-wrap items-center gap-2">
                    {secondaryActions}
                    {primaryAction}
                </div>
            )}
        </header>
    );
}

export interface AdminContextBarProps {
    children: ReactNode;
    className?: string;
}

export function AdminContextBar({ children, className }: AdminContextBarProps) {
    return (
        <div className={cn("space-y-3", className)}>
            {children}
        </div>
    );
}

export interface AdminIndexShellProps {
    header: ReactNode;
    contextBar?: ReactNode;
    children: ReactNode;
    className?: string;
}

export function AdminIndexShell({
    header,
    contextBar,
    children,
    className,
}: AdminIndexShellProps) {
    return (
        <div
            className={cn(
                "space-y-6 motion-safe:animate-in motion-safe:fade-in motion-safe:duration-[var(--duration-tooltip)]",
                className,
            )}
        >
            {header}
            {contextBar}
            {children}
        </div>
    );
}

export interface AdminDetailTab {
    label: string;
    href: string;
    isActive?: boolean;
}

export interface AdminDetailShellProps {
    backHref: string;
    backLabel?: string;
    title: string;
    description?: string;
    tabs?: AdminDetailTab[];
    actions?: ReactNode;
    children: ReactNode;
    className?: string;
}

export function AdminDetailShell({
    backHref,
    backLabel = "返回",
    title,
    description,
    tabs,
    actions,
    children,
    className,
}: AdminDetailShellProps) {
    return (
        <div className={cn("space-y-6 pb-20", className)}>
            <div className="space-y-4">
                <Link
                    href={backHref}
                    prefetch={false}
                    className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
                >
                    <ArrowLeft className="h-4 w-4" />
                    {backLabel}
                </Link>
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div>
                        <h1 className="text-3xl font-black tracking-tight text-slate-900">{title}</h1>
                        {description ? (
                            <p className="mt-1 max-w-3xl text-sm text-slate-500">{description}</p>
                        ) : null}
                    </div>
                    {actions}
                </div>
                {tabs && tabs.length > 0 ? (
                    <nav className="flex flex-wrap gap-2 border-b border-slate-100 pb-1">
                        {tabs.map((tab) => (
                            <Link
                                key={tab.href}
                                href={tab.href}
                                prefetch={false}
                                className={cn(
                                    "rounded-full px-4 py-2 text-sm font-medium transition-colors",
                                    tab.isActive
                                        ? "bg-slate-900 text-white"
                                        : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                                )}
                            >
                                {tab.label}
                            </Link>
                        ))}
                    </nav>
                ) : null}
            </div>
            {children}
        </div>
    );
}

export interface AdminFormShellProps {
    backHref: string;
    backLabel?: string;
    title: string;
    description?: string;
    actions?: ReactNode;
    children: ReactNode;
    className?: string;
}

export function AdminFormShell({
    backHref,
    backLabel = "返回",
    title,
    description,
    actions,
    children,
    className,
}: AdminFormShellProps) {
    return (
        <div className={cn("space-y-6 pb-20", className)}>
            <div className="space-y-4">
                <Link
                    href={backHref}
                    prefetch={false}
                    className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
                >
                    <ArrowLeft className="h-4 w-4" />
                    {backLabel}
                </Link>
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div>
                        <h1 className="text-3xl font-black tracking-tight text-slate-900">{title}</h1>
                        {description ? (
                            <p className="mt-1 max-w-3xl text-sm text-slate-500">{description}</p>
                        ) : null}
                    </div>
                    {actions}
                </div>
            </div>
            {children}
        </div>
    );
}

export interface PolicyPageShellProps {
    header: ReactNode;
    contextBar?: ReactNode;
    children: ReactNode;
    className?: string;
}

/** Thin wrapper for single-purpose 策略中心 config consoles. */
export function PolicyPageShell({
    header,
    contextBar,
    children,
    className,
}: PolicyPageShellProps) {
    return (
        <div
            className={cn(
                "space-y-6 pb-20 motion-safe:animate-in motion-safe:fade-in motion-safe:duration-[var(--duration-tooltip)]",
                className,
            )}
        >
            {header}
            {contextBar}
            {children}
        </div>
    );
}
