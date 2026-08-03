"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Menu, Shield } from "lucide-react";

import { AdminSidebar, AdminSidebarContent } from "@/components/layout/admin-sidebar";
import { GlassSheet } from "@/components/ui/glass-sheet";
import { Button } from "@/components/ui/button";
import { useSidebarStore } from "@/hooks/use-sidebar";
import { useCurrentUser } from "@/hooks/use-current-user";
import { isAuthenticationError } from "@/lib/api/client";
import { authHandler } from "@/lib/auth-handler";
import { cn } from "@/lib/utils";
import {
    canUseAdminConsoleRole,
    shouldStayInSalesTrainerAdmin,
    type CurrentUser,
} from "@/lib/auth/current-user";

const SALES_TRAINER_ADMIN_PREFIX = "/admin/sales-trainer";
const SALES_TRAINER_MANAGER_ENTRY = "/admin/newcomer-training/resources";

function canUseAdminShell(role: string): boolean {
    return canUseAdminConsoleRole(role);
}

function isSalesTrainerManagerRole(role: string): boolean {
    return shouldStayInSalesTrainerAdmin(role);
}

export function AdminShell({
    children,
    currentUser,
}: {
    children: React.ReactNode;
    currentUser: CurrentUser;
}) {
    const router = useRouter();
    const pathname = usePathname();
    const { data: sessionUser, error } = useCurrentUser(currentUser);
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const { isCollapsed } = useSidebarStore();
    const effectiveUser = sessionUser || currentUser;
    const authError = isAuthenticationError(error);

    useEffect(() => {
        if (authError) {
            authHandler.sessionExpired();
            return;
        }

        if (!canUseAdminShell(effectiveUser.role)) {
            router.replace("/");
            return;
        }

        if (
            isSalesTrainerManagerRole(effectiveUser.role)
            && !pathname.startsWith(SALES_TRAINER_ADMIN_PREFIX)
            && !pathname.startsWith("/admin/newcomer-training")
        ) {
            router.replace(SALES_TRAINER_MANAGER_ENTRY);
        }
    }, [authError, effectiveUser.role, pathname, router]);

    useEffect(() => {
        let startX = 0;
        let startY = 0;

        const handleTouchStart = (e: TouchEvent) => {
            if (e.touches.length !== 1) return;
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
        };

        const handleTouchMove = (e: TouchEvent) => {
            if (e.touches.length !== 1) return;
            const currentX = e.touches[0].clientX;
            const currentY = e.touches[0].clientY;

            if (startX > 30) return;

            const diffX = currentX - startX;
            const diffY = Math.abs(currentY - startY);

            if (diffX > 50 && diffX > diffY * 2) {
                setIsMobileMenuOpen(true);
            }
        };

        window.addEventListener("touchstart", handleTouchStart);
        window.addEventListener("touchmove", handleTouchMove);

        return () => {
            window.removeEventListener("touchstart", handleTouchStart);
            window.removeEventListener("touchmove", handleTouchMove);
        };
    }, []);

    return (
        <div className="relative flex min-h-screen overflow-hidden bg-[#FAFAF9] text-slate-900 selection:bg-blue-100 selection:text-blue-900">
            <AdminSidebar currentUser={effectiveUser} />

            <div className="fixed left-0 right-0 top-0 z-40 flex items-center justify-between border-b border-slate-200/80 bg-white/95 p-4 shadow-sm md:hidden">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-slate-900 text-white flex items-center justify-center shadow-md">
                        <Shield className="w-4 h-4 text-yellow-300" strokeWidth={2} />
                    </div>
                    <span className="font-bold text-lg text-slate-900">管理控制台</span>
                </div>
                <Button variant="ghost" size="icon" onClick={() => setIsMobileMenuOpen(true)}>
                    <Menu className="w-6 h-6 text-slate-700" />
                </Button>
            </div>

            <GlassSheet isOpen={isMobileMenuOpen} onClose={() => setIsMobileMenuOpen(false)}>
                <div className="flex flex-col h-full pt-4">
                    <AdminSidebarContent currentUser={effectiveUser} />
                </div>
            </GlassSheet>

            <main
                className={cn(
                    "flex-1 p-4 md:p-8 relative z-10 overflow-y-auto h-screen mt-16 md:mt-0",
                    isCollapsed ? "md:ml-28" : "md:ml-80",
                )}
            >
                <div className="max-w-[1600px] mx-auto space-y-10 pb-20 pt-4">
                    {children}
                </div>
            </main>
        </div>
    );
}
