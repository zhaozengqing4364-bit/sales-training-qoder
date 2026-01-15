"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
    LayoutDashboard,
    Users,
    Bot,
    Settings,
    Shield,
    LogOut,
    Activity,
    FileText,
    PanelLeftClose,
    PanelLeftOpen,
    BookOpen,
    ArrowLeft,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/glass-modal";
import { useSidebarStore } from "@/hooks/use-sidebar";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/glass-tooltip";
import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";

interface UserInfo {
    id: string;
    display_name: string;
    avatar_url?: string;
    role: string;
    department?: string;
}

export function AdminSidebar() {
    const { isCollapsed, toggleSidebar } = useSidebarStore();
    // Prevent hydration mismatch
    const [mounted, setMounted] = useState(false);
    useEffect(() => {
        setMounted(true);
    }, []);

    if (!mounted) return null;

    return (
        <aside
            className={cn(
                "hidden md:flex fixed left-4 top-4 h-[calc(100vh-2rem)] rounded-[2.5rem] bg-white/50 backdrop-blur-2xl border border-white/60 shadow-[0_8px_32px_rgba(0,0,0,0.04)] z-50 flex-col pt-8 pb-6 transition-all duration-300 ease-in-out overflow-hidden",
                isCollapsed ? "w-20 px-3" : "w-72 px-5"
            )}
        >
            <AdminSidebarContent isCollapsed={isCollapsed} toggleSidebar={toggleSidebar} showToggle={true} />
        </aside>
    );
}

interface AdminSidebarContentProps {
    isCollapsed?: boolean;
    toggleSidebar?: () => void;
    showToggle?: boolean;
}

export function AdminSidebarContent({ isCollapsed = false, toggleSidebar, showToggle = false }: AdminSidebarContentProps) {
    const pathname = usePathname();

    const navItems = [
        { label: "总览", icon: LayoutDashboard, href: "/admin" },
        { label: "用户管理", icon: Users, href: "/admin/users" },
        { label: "智能体管理", icon: Bot, href: "/admin/agents" },
        { label: "角色管理", icon: Users, href: "/admin/personas" },
        { label: "知识库管理", icon: BookOpen, href: "/admin/knowledge" },
        { label: "训练记录", icon: FileText, href: "/admin/records" },
        { label: "系统设置", icon: Settings, href: "/admin/settings" },
        { label: "操作日志", icon: Activity, href: "/admin/logs" },
    ];

    return (
        <div className="flex flex-col h-full w-full overflow-hidden">
            {/* Brand Identity - Admin */}
            <div className={cn(
                "mb-10 flex items-center group cursor-default transition-all duration-300 shrink-0",
                isCollapsed ? "justify-center px-0" : "gap-4 px-2"
            )}>
                <div className="w-12 h-12 rounded-2xl bg-slate-900 text-white flex items-center justify-center shadow-lg shadow-slate-900/20 group-hover:scale-105 transition-transform duration-300 shrink-0">
                    <Shield className="w-6 h-6 text-yellow-300" strokeWidth={2} />
                </div>
                <div className={cn(
                    "flex flex-col overflow-hidden transition-all duration-300",
                    isCollapsed ? "w-0 opacity-0 hidden" : "w-auto opacity-100"
                )}>
                    <span className="font-bold text-xl text-slate-900 tracking-tight leading-none whitespace-nowrap">管理</span>
                    <span className="text-xs uppercase tracking-[0.2em] text-slate-400 font-semibold mt-1.5 ml-0.5 whitespace-nowrap">控制台</span>
                </div>
            </div>

            {/* Main Navigation */}
            <TooltipProvider delayDuration={0}>
                <nav className="flex-1 space-y-1 flex flex-col w-full overflow-y-auto min-h-0">
                    {navItems.map((item) => (
                        <AdminNavLink key={item.href} item={item} pathname={pathname} isCollapsed={isCollapsed} />
                    ))}
                </nav>
            </TooltipProvider>

            {/* Bottom Actions */}
            <div className="mt-auto flex flex-col gap-3 shrink-0 pt-4">
                {/* Back to User Portal */}
                <BackToUserLink isCollapsed={isCollapsed} />
                {/* Admin User Card */}
                <AdminUserCard isCollapsed={isCollapsed} />

                {/* Collapse Trigger */}
                {showToggle && toggleSidebar && (
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={toggleSidebar}
                        className={cn(
                            "mx-auto text-slate-400 hover:text-slate-600 hover:bg-black/5 rounded-full transition-all duration-300",
                            isCollapsed ? "w-10 h-10" : "w-full flex gap-2 items-center justify-center h-10 px-4"
                        )}
                    >
                        {isCollapsed ? <PanelLeftOpen className="w-5 h-5" /> : (
                            <>
                                <PanelLeftClose className="w-4 h-4" />
                                <span className="text-sm font-medium">折叠侧边栏</span>
                            </>
                        )}
                    </Button>
                )}
            </div>
        </div>
    );
}

function AdminUserCard({ isCollapsed }: { isCollapsed: boolean }) {
    const [userInfo, setUserInfo] = useState<UserInfo | null>(null);

    useEffect(() => {
        // Try to get user info from localStorage first (set during login)
        const storedUser = localStorage.getItem("user");
        if (storedUser) {
            try {
                const parsed = JSON.parse(storedUser);
                setUserInfo({
                    id: parsed.id,
                    display_name: parsed.name || parsed.display_name || "用户",
                    role: parsed.role || "user",
                    department: parsed.department,
                });
            } catch {
                // Ignore parse errors
            }
        }

        // Fetch fresh user info from API
        api.user.getMe().then((data) => {
            setUserInfo(data);
            // Update localStorage
            localStorage.setItem("user", JSON.stringify(data));
        }).catch(() => {
            // Ignore errors, use cached data
        });
    }, []);

    const displayName = userInfo?.display_name || "管理员";
    const roleLabel = userInfo?.role === "admin" ? "超级用户" : "普通用户";

    if (isCollapsed) {
        return (
            <Dialog>
                <TooltipProvider>
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <DialogTrigger asChild>
                                <div className="mx-auto w-10 h-10 rounded-[1.2rem] bg-white/60 border border-white/50 shadow-sm flex items-center justify-center cursor-pointer hover:bg-white/80 transition-colors">
                                    <Shield className="w-5 h-5 text-slate-500" />
                                </div>
                            </DialogTrigger>
                        </TooltipTrigger>
                        <TooltipContent side="right">
                            <p>{displayName}</p>
                        </TooltipContent>
                    </Tooltip>
                </TooltipProvider>
                <AdminProfileModal userInfo={userInfo} />
            </Dialog>
        );
    }

    return (
        <Dialog>
            <DialogTrigger asChild>
                <div className="bg-white/60 p-1.5 rounded-[1.2rem] border border-white/50 shadow-sm flex items-center gap-3 cursor-pointer hover:bg-white/80 transition-colors group overflow-hidden whitespace-nowrap">
                    <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 group-hover:bg-blue-50 group-hover:text-blue-600 transition-colors shrink-0">
                        <Shield className="w-4 h-4" />
                    </div>
                    <div className="flex flex-col min-w-0">
                        <span className="text-sm font-bold text-slate-800 truncate">{displayName}</span>
                        <span className="text-xs text-slate-400 font-medium bg-slate-100 px-1.5 py-0.5 rounded-full w-fit truncate">{roleLabel}</span>
                    </div>
                    <div className="ml-auto mr-3 text-slate-300 group-hover:text-red-400 transition-colors shrink-0">
                        <LogOut className="w-4 h-4" />
                    </div>
                </div>
            </DialogTrigger>
            <AdminProfileModal userInfo={userInfo} />
        </Dialog>
    );
}

function AdminProfileModal({ userInfo }: { userInfo: UserInfo | null }) {
    const router = useRouter();

    const handleLogout = () => {
        // Clear token
        localStorage.removeItem("token");
        // Clear any other user data
        localStorage.removeItem("user");
        
        // Redirect to login
        router.push("/login");
    };

    const displayName = userInfo?.display_name || "管理员";
    const roleLabel = userInfo?.role === "admin" ? "超级管理员" : "普通用户";

    return (
        <DialogContent>
            <DialogHeader>
                <DialogTitle>{displayName}</DialogTitle>
                <DialogDescription>{roleLabel} · {userInfo?.department || "未设置部门"}</DialogDescription>
            </DialogHeader>
            <div className="py-6 space-y-4">
                <div className="p-4 bg-red-50 border border-red-100 rounded-xl flex items-start gap-3">
                    <Shield className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
                    <div>
                        <div className="text-sm font-bold text-red-800">安全提示</div>
                        <div className="text-xs text-red-600 mt-1">
                            您正使用管理员权限登录。所有操作将被记录和审计。
                            不使用时请退出登录。
                        </div>
                    </div>
                </div>
                <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-500 uppercase">用户信息</label>
                    <div className="text-sm font-mono bg-slate-100 p-2 rounded text-slate-600">
                        ID: {userInfo?.id?.slice(0, 8) || "..."}<br />
                        角色: {roleLabel}<br />
                        部门: {userInfo?.department || "未设置"}
                    </div>
                </div>
            </div>
            <DialogFooter>
                <Button variant="ghost" className="rounded-full text-slate-500 hover:text-slate-900">切换用户</Button>
                <Button onClick={handleLogout} className="rounded-full bg-red-600 hover:bg-red-700 text-white">安全退出</Button>
            </DialogFooter>
        </DialogContent>
    );
}

function BackToUserLink({ isCollapsed }: { isCollapsed: boolean }) {
    if (isCollapsed) {
        return (
            <TooltipProvider>
                <Tooltip>
                    <TooltipTrigger asChild>
                        <Link
                            href="/"
                            className="mx-auto w-10 h-10 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center cursor-pointer hover:bg-blue-100 transition-colors group"
                        >
                            <ArrowLeft className="w-4 h-4 text-blue-600 group-hover:text-blue-700" />
                        </Link>
                    </TooltipTrigger>
                    <TooltipContent side="right">
                        <p>回到用户端</p>
                    </TooltipContent>
                </Tooltip>
            </TooltipProvider>
        );
    }

    return (
        <Link
            href="/"
            className="flex items-center gap-2 px-3 py-2 rounded-xl bg-blue-50 border border-blue-100 text-blue-600 hover:bg-blue-100 hover:text-blue-700 transition-colors group"
        >
            <ArrowLeft className="w-4 h-4" />
            <span className="text-sm font-medium">回到用户端</span>
        </Link>
    );
}

function AdminNavLink({ item, pathname, isCollapsed }: { item: any, pathname: string, isCollapsed: boolean }) {
    const isActive = pathname === item.href || (item.href !== '/admin' && pathname.startsWith(item.href) && item.href !== '/admin');

    const LinkContent = (
        <Link
            href={item.href}
            className={cn(
                "flex items-center gap-3 py-2.5 rounded-xl transition-all duration-300 group relative",
                isCollapsed ? "justify-center px-0 w-10 h-10 mx-auto" : "px-4 w-full",
                isActive
                    ? "text-slate-900 bg-white shadow-[0_2px_20px_rgba(0,0,0,0.04)]"
                    : "text-slate-500 hover:text-slate-900 hover:bg-white/40"
            )}
        >
            {isActive && !isCollapsed && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-slate-900 rounded-r-full" />
            )}
            <item.icon
                strokeWidth={isActive ? 2.5 : 2}
                className={cn(
                    "transition-all duration-300 shrink-0",
                    isCollapsed ? "w-5 h-5" : "w-4 h-4",
                    isActive ? "text-slate-900 scale-110" : "text-slate-400 group-hover:text-slate-600 group-hover:scale-105"
                )}
            />
            <span className={cn(
                "text-base font-medium tracking-wide whitespace-nowrap overflow-hidden transition-all duration-300",
                isActive ? "font-bold" : "",
                isCollapsed ? "w-0 opacity-0 hidden" : "w-auto opacity-100"
            )}>
                {item.label}
            </span>
        </Link>
    );

    if (isCollapsed) {
        return (
            <Tooltip>
                <TooltipTrigger asChild>
                    {LinkContent}
                </TooltipTrigger>
                <TooltipContent side="right">
                    <p>{item.label}</p>
                </TooltipContent>
            </Tooltip>
        );
    }

    return LinkContent;
}