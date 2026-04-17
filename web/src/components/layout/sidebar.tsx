"use client";

import { type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    Home,
    BarChart2,
    Activity,
    Settings,
    User,
    Sparkles,
    PanelLeftClose,
    PanelLeftOpen,
    LayoutGrid,
    LogOut,
    History,
    type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/glass-modal";
import { Button } from "@/components/ui/button";
import { useSidebarStore } from "@/hooks/use-sidebar";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/glass-tooltip";
import { api } from "@/lib/api/client";
import { authHandler } from "@/lib/auth-handler";
import type { CurrentUser } from "@/lib/auth/current-user";

interface UserInfo {
    id: string;
    name?: string;
    display_name?: string;
    email?: string;
    role: string;
    department?: string;
}

type SidebarFooterSlot = ReactNode | ((options: { isCollapsed: boolean }) => ReactNode);

export const navItems = [
    { label: "首页", icon: Home, href: "/" },
    { label: "训练模式", icon: LayoutGrid, href: "/training" },
    { label: "排行榜", icon: BarChart2, href: "/leaderboard" },
    { label: "历史记录", icon: History, href: "/history" },
];

function resolveSidebarFooterSlot(
    footerSlot: SidebarFooterSlot | undefined,
    isCollapsed: boolean,
): ReactNode {
    if (typeof footerSlot === "function") {
        return footerSlot({ isCollapsed });
    }
    return footerSlot ?? null;
}

export function Sidebar({
    currentUser,
    footerSlot,
}: {
    currentUser: CurrentUser;
    footerSlot?: SidebarFooterSlot;
}) {
    const { isCollapsed, toggleSidebar } = useSidebarStore();

    return (
        <aside
            className={cn(
                "hidden md:flex fixed left-4 top-4 h-[calc(100vh-2rem)] rounded-[2.5rem] bg-white/50 backdrop-blur-2xl border border-white/60 shadow-[0_8px_32px_rgba(0,0,0,0.04)] z-50 flex-col pt-8 pb-6 transition-all duration-300 ease-in-out",
                isCollapsed ? "w-20 px-3" : "w-72 px-5",
            )}
        >
            <SidebarContent
                currentUser={currentUser}
                isCollapsed={isCollapsed}
                toggleSidebar={toggleSidebar}
                showToggle={true}
                footerSlot={resolveSidebarFooterSlot(footerSlot, isCollapsed)}
            />
        </aside>
    );
}

interface SidebarContentProps {
    currentUser: UserInfo | null;
    isCollapsed?: boolean;
    toggleSidebar?: () => void;
    showToggle?: boolean;
    footerSlot?: ReactNode;
}

export function SidebarContent({
    currentUser,
    isCollapsed = false,
    toggleSidebar,
    showToggle = false,
    footerSlot,
}: SidebarContentProps) {
    const pathname = usePathname();
    const isAdmin = currentUser?.role === "admin";
    const isSupport = currentUser?.role === "support";
    const canViewRuntime = isAdmin || isSupport;

    return (
        <div className="flex flex-col h-full w-full overflow-hidden">
            <div
                className={cn(
                    "mb-8 flex items-center group cursor-default transition-all duration-300 shrink-0",
                    isCollapsed ? "justify-center px-0" : "gap-4 px-2",
                )}
            >
                <div className="w-12 h-12 rounded-2xl bg-slate-900 text-white flex items-center justify-center shadow-lg shadow-slate-900/20 group-hover:scale-105 transition-transform duration-300 shrink-0">
                    <Sparkles className="w-6 h-6 text-yellow-300" strokeWidth={1.5} />
                </div>
                <div
                    className={cn(
                        "flex flex-col overflow-hidden transition-all duration-300",
                        isCollapsed ? "w-0 opacity-0 hidden" : "w-auto opacity-100",
                    )}
                >
                    <span className="font-bold text-xl text-slate-900 tracking-tight leading-none whitespace-nowrap">AI 销售教练</span>
                    <span className="text-xs uppercase tracking-[0.2em] text-slate-500 font-semibold mt-1.5 ml-0.5 whitespace-nowrap">平台</span>
                </div>
            </div>

            <TooltipProvider delayDuration={0}>
                <nav aria-label="主导航" className="flex-1 flex flex-col w-full overflow-y-auto scrollbar-hide min-h-0 pb-4">
                    {!isCollapsed ? (
                        <div className="px-4 mb-3 text-xs font-bold text-slate-500 uppercase tracking-widest whitespace-nowrap transition-opacity duration-300 shrink-0">
                            菜单
                        </div>
                    ) : null}

                    <ul role="menubar" className="space-y-2 px-1">
                        {navItems.map((item) => (
                            <li key={item.href} role="none">
                                <NavLink item={item} pathname={pathname} isCollapsed={isCollapsed} />
                            </li>
                        ))}
                    </ul>

                    {canViewRuntime ? (
                        <>
                            <div className="my-6 px-3 shrink-0">
                                <div className="h-px w-full bg-gradient-to-r from-transparent via-slate-200 to-transparent" />
                            </div>

                            {!isCollapsed ? (
                                <div className="px-4 mb-3 text-xs font-bold text-slate-500 uppercase tracking-widest whitespace-nowrap transition-opacity duration-300 shrink-0">
                                    系统
                                </div>
                            ) : null}
                            <ul role="menubar" className="space-y-2 px-1">
                                <li role="none">
                                    <NavLink
                                        item={{ label: "运行状态", icon: Activity, href: "/support/runtime" }}
                                        pathname={pathname}
                                        isCollapsed={isCollapsed}
                                    />
                                </li>
                                {isAdmin ? (
                                    <li role="none">
                                        <NavLink
                                            item={{ label: "管理后台", icon: Settings, href: "/admin" }}
                                            pathname={pathname}
                                            isCollapsed={isCollapsed}
                                        />
                                    </li>
                                ) : null}
                            </ul>
                        </>
                    ) : null}
                </nav>
            </TooltipProvider>

            <div className="mt-auto flex flex-col gap-4 pt-4 shrink-0">
                {footerSlot ? <div className="px-1">{footerSlot}</div> : null}
                <SidebarUser isCollapsed={isCollapsed} userInfo={currentUser} />

                {showToggle && toggleSidebar ? (
                    <Button
                        variant="ghost"
                        size="icon"
                        aria-label={isCollapsed ? "展开侧边栏" : "折叠侧边栏"}
                        onClick={toggleSidebar}
                        className={cn(
                            "mx-auto text-slate-500 hover:text-slate-600 hover:bg-black/5 rounded-full transition-all duration-300",
                            isCollapsed ? "w-10 h-10" : "w-full flex gap-2 items-center justify-center h-10 px-4",
                        )}
                    >
                        {isCollapsed ? (
                            <PanelLeftOpen className="w-5 h-5" />
                        ) : (
                            <>
                                <PanelLeftClose className="w-4 h-4" />
                                <span className="text-sm font-medium">折叠侧边栏</span>
                            </>
                        )}
                    </Button>
                ) : null}
            </div>
        </div>
    );
}

function SidebarUser({ isCollapsed, userInfo }: { isCollapsed: boolean; userInfo: UserInfo | null }) {
    const [mounted, setMounted] = useState(false);
    useEffect(() => {
        const timeoutId = window.setTimeout(() => {
            setMounted(true);
        }, 0);
        return () => window.clearTimeout(timeoutId);
    }, []);

    const displayName = userInfo?.display_name || userInfo?.name || "用户";
    const department = userInfo?.department || "未设置部门";

    if (isCollapsed) {
        return (
            <Dialog>
                <TooltipProvider>
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <DialogTrigger asChild>
                                <div className="mx-auto w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 cursor-pointer hover:bg-blue-50 hover:text-blue-600 transition-colors shadow-sm border border-slate-200">
                                    <User className="w-5 h-5" />
                                </div>
                            </DialogTrigger>
                        </TooltipTrigger>
                        <TooltipContent side="right">
                            <p>{displayName}</p>
                        </TooltipContent>
                    </Tooltip>
                </TooltipProvider>
                <UserProfileModal userInfo={userInfo} />
            </Dialog>
        );
    }

    return (
        <Dialog>
            <DialogTrigger asChild>
                <div className="bg-white/60 p-1.5 rounded-[1.2rem] border border-white/50 shadow-sm flex items-center gap-3 cursor-pointer hover:bg-white/80 transition-colors group overflow-hidden whitespace-nowrap">
                    <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 group-hover:bg-blue-50 group-hover:text-blue-600 transition-colors shrink-0">
                        <User className="w-5 h-5" />
                    </div>
                    <div className="flex flex-col min-w-0">
                        <span className="text-sm font-bold text-slate-800 truncate">{displayName}</span>
                        <span className="text-[10px] text-slate-400 font-medium bg-slate-100 px-1.5 py-0.5 rounded-full w-fit truncate">{department}</span>
                    </div>
                    <div className="ml-auto mr-2 text-slate-300 group-hover:text-red-400 transition-colors shrink-0">
                        <LogOut className="w-4 h-4" />
                    </div>
                </div>
            </DialogTrigger>
            <UserProfileModal userInfo={userInfo} />
        </Dialog>
    );
}

function UserProfileModal({ userInfo }: { userInfo: UserInfo | null }) {
    const handleLogout = async () => {
        try {
            await api.auth.logout();
        } catch {
            // Ignore logout API failures and still leave the current session shell.
        } finally {
            authHandler.logout("已退出登录", {
                redirectTo: "/login",
                notify: false,
            });
        }
    };

    const displayName = userInfo?.display_name || userInfo?.name || "用户";
    const email = userInfo?.email || "未设置邮箱";
    const roleMap: Record<string, string> = {
        admin: "管理员",
        support: "支持角色",
        user: "普通用户",
    };
    const role = roleMap[userInfo?.role || "user"] || (userInfo?.role || "普通用户");
    const department = userInfo?.department || "未设置部门";

    return (
        <DialogContent>
            <DialogHeader>
                <DialogTitle>个人资料</DialogTitle>
                <DialogDescription>管理您的账户设置和偏好。</DialogDescription>
            </DialogHeader>
            <div className="py-6 flex flex-col items-center gap-4">
                <div className="w-20 h-20 rounded-full bg-slate-100 flex items-center justify-center text-slate-400">
                    <User className="w-10 h-10" />
                </div>
                <div className="text-center space-y-1">
                    <div className="text-xl font-bold text-slate-900">{displayName}</div>
                    <div className="text-sm text-slate-500">{email}</div>
                </div>
                <div className="w-full space-y-2 mt-4">
                    <div className="flex justify-between items-center p-3 rounded-xl bg-slate-50 border border-slate-100">
                        <span className="text-sm font-medium text-slate-700">角色</span>
                        <span className="text-xs font-bold bg-blue-100 text-blue-600 px-2 py-1 rounded-full">{role}</span>
                    </div>
                    <div className="flex justify-between items-center p-3 rounded-xl bg-slate-50 border border-slate-100">
                        <span className="text-sm font-medium text-slate-700">部门</span>
                        <span className="text-sm text-slate-900">{department}</span>
                    </div>
                </div>
            </div>
            <DialogFooter>
                <Button
                    variant="outline"
                    onClick={handleLogout}
                    className="rounded-full text-red-500 border-slate-200 hover:bg-red-50 hover:text-red-600 hover:border-red-100"
                >
                    退出登录
                </Button>
                <Button asChild className="rounded-full bg-slate-900 text-white">
                    <Link href="/profile">编辑资料</Link>
                </Button>
            </DialogFooter>
        </DialogContent>
    );
}

interface SidebarNavItem {
    label: string;
    href: string;
    icon: LucideIcon;
}

export function NavLink({
    item,
    pathname,
    isCollapsed,
}: {
    item: SidebarNavItem;
    pathname: string;
    isCollapsed: boolean;
}) {
    let isActive = false;
    if (item.href === "/") {
        isActive = pathname === "/" || pathname === "/dashboard";
    } else {
        isActive = pathname.startsWith(item.href);
    }

    const linkContent = (
        <Link
            href={item.href}
            role="menuitem"
            aria-current={isActive ? "page" : undefined}
            className={cn(
                "flex items-center gap-4 py-3.5 rounded-2xl transition-all duration-300 group relative",
                isCollapsed ? "justify-center px-0 w-12 h-12 mx-auto" : "px-5 w-full",
                isActive
                    ? "text-slate-900 bg-white shadow-[0_2px_20px_rgba(0,0,0,0.04)]"
                    : "text-slate-500 hover:text-slate-900 hover:bg-white/40",
            )}
        >
            {isActive && !isCollapsed ? (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-slate-900 rounded-r-full" />
            ) : null}
            <item.icon
                strokeWidth={isActive ? 2.5 : 2}
                className={cn(
                    "transition-all duration-300 shrink-0",
                    isCollapsed ? "w-6 h-6" : "w-5 h-5",
                    isActive ? "text-slate-900 scale-110" : "text-slate-500 group-hover:text-slate-600 group-hover:scale-105",
                )}
            />
            <span
                className={cn(
                    "text-base font-medium tracking-wide whitespace-nowrap overflow-hidden transition-all duration-300",
                    isActive ? "font-bold" : "",
                    isCollapsed ? "w-0 opacity-0 hidden" : "w-auto opacity-100",
                )}
            >
                {item.label}
            </span>
        </Link>
    );

    if (isCollapsed) {
        return (
            <Tooltip>
                <TooltipTrigger asChild>{linkContent}</TooltipTrigger>
                <TooltipContent side="right">
                    <p>{item.label}</p>
                </TooltipContent>
            </Tooltip>
        );
    }

    return linkContent;
}
