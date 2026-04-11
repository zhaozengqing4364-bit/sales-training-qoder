"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Menu, Shield } from "lucide-react";

import { AdminSidebar, AdminSidebarContent } from "@/components/layout/admin-sidebar";
import { GlassSheet } from "@/components/ui/glass-sheet";
import { Button } from "@/components/ui/button";
import { useSidebarStore } from "@/hooks/use-sidebar";
import { useCurrentUser } from "@/hooks/use-current-user";
import { isAuthenticationError } from "@/lib/api/client";
import { authHandler } from "@/lib/auth-handler";
import { cn } from "@/lib/utils";
import type { CurrentUser } from "@/lib/auth/current-user";

export function AdminShell({
    children,
    currentUser,
}: {
    children: React.ReactNode;
    currentUser: CurrentUser;
}) {
    const router = useRouter();
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

        if (effectiveUser.role !== "admin") {
            router.replace("/");
        }
    }, [authError, effectiveUser.role, router]);

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
        <div className="flex bg-[#FAFAF9] min-h-screen text-slate-900 selection:bg-blue-100 selection:text-blue-900 relative overflow-hidden">
            <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
                <div className="absolute top-[-10%] left-[-10%] w-[800px] h-[800px] bg-blue-100/40 rounded-full blur-[120px] opacity-60" />
                <div className="absolute bottom-[-10%] right-[-10%] w-[800px] h-[800px] bg-purple-100/40 rounded-full blur-[120px] opacity-60" />
            </div>

            <AdminSidebar currentUser={effectiveUser} />

            <div className="md:hidden fixed top-0 left-0 right-0 z-40 p-4 flex items-center justify-between bg-white/70 backdrop-blur-xl border-b border-white/50 shadow-sm">
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
                    "flex-1 p-4 md:p-8 relative z-10 overflow-y-auto h-screen scroll-smooth mt-16 md:mt-0 transition-all duration-300 ease-in-out",
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
