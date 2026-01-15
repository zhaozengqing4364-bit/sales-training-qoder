"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { AdminUser } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Search, Filter, MoreHorizontal, UserPlus, Download, Mail, Shield, Ban, Trash2, Calendar, CheckCircle, Loader2 } from "lucide-react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/glass-modal";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/glass-tooltip";
import {
    MobileTableCard
} from "@/components/ui/mobile-table-card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";

// Helper to format relative time
function formatRelativeTime(dateString: string) {
    if (!dateString) return "从未";
    const date = new Date(dateString);
    const now = new Date();
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
    
    if (diffInSeconds < 60) return "刚刚";
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}分钟前`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}小时前`;
    if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)}天前`;
    return date.toLocaleDateString();
}

function getStatusLabel(status: string) {
    const map: Record<string, string> = {
        active: "活跃",
        inactive: "停用",
        offline: "离线",
        suspended: "已停用"
    };
    return map[status] || status;
}

function getRoleLabel(role: string) {
    const map: Record<string, string> = {
        admin: "管理员",
        user: "普通用户",
        manager: "经理",
        editor: "编辑",
        viewer: "访客"
    };
    return map[role] || role;
}

// Form state type
interface CreateUserForm {
    username: string;
    name: string;
    email: string;
    password: string;
    department: string;
    role: "user" | "admin";
}

interface EditUserForm {
    name: string;
    email: string;
    department: string;
    role: string;
}

const initialCreateForm: CreateUserForm = {
    username: "",
    name: "",
    email: "",
    password: "",
    department: "",
    role: "user"
};

export default function UsersPage() {
    const [users, setUsers] = useState<AdminUser[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const toast = useToast();

    // Filter & Search States
    const [searchQuery, setSearchQuery] = useState("");
    const [statusFilter, setStatusFilter] = useState("all");
    const [roleFilter, setRoleFilter] = useState("all");
    const [page, setPage] = useState(1);
    const [isFilterOpen, setIsFilterOpen] = useState(false);

    // Dialog states
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [isExportOpen, setIsExportOpen] = useState(false);
    const [exportFormat, setExportFormat] = useState<"csv" | "json">("csv");
    const [isExporting, setIsExporting] = useState(false);

    // Confirm dialog states
    const [confirmDialog, setConfirmDialog] = useState<{
        open: boolean;
        title: string;
        description: string;
        variant: "danger" | "warning" | "default";
        onConfirm: () => void;
    }>({ open: false, title: "", description: "", variant: "default", onConfirm: () => {} });

    // Create user form
    const [createForm, setCreateForm] = useState<CreateUserForm>(initialCreateForm);
    const [isCreating, setIsCreating] = useState(false);
    const [createError, setCreateError] = useState("");

    // Edit user state
    const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
    const [editForm, setEditForm] = useState<EditUserForm>({ name: "", email: "", department: "", role: "" });
    const [isEditing, setIsEditing] = useState(false);

    // Action states
    const [actionLoading, setActionLoading] = useState<string | null>(null);

    const loadData = async () => {
        setIsLoading(true);
        try {
            const data = await api.admin.getUsers({
                search: searchQuery,
                status: statusFilter === "all" ? undefined : statusFilter,
                role: roleFilter === "all" ? undefined : roleFilter,
                page: page,
                page_size: 10
            });
            setUsers(data);
        } catch (err) {
            console.error("Failed to load users:", err);
        } finally {
            setIsLoading(false);
        }
    };

    // Create user handler
    const handleCreateUser = async () => {
        setCreateError("");
        
        // Validation
        if (!createForm.username.trim()) {
            setCreateError("请输入用户名");
            return;
        }
        if (!createForm.email.trim()) {
            setCreateError("请输入邮箱地址");
            return;
        }
        if (!createForm.password || createForm.password.length < 8) {
            setCreateError("密码至少需要8位");
            return;
        }
        
        setIsCreating(true);
        try {
            await api.admin.createUser({
                username: createForm.username,
                email: createForm.email,
                password: createForm.password,
                name: createForm.name || undefined,
                department: createForm.department || undefined,
                role: createForm.role
            });
            setIsCreateOpen(false);
            setCreateForm(initialCreateForm);
            loadData();
        } catch (err) {
            console.error("Failed to create user:", err);
            setCreateError(err instanceof Error ? err.message : "创建失败");
        } finally {
            setIsCreating(false);
        }
    };

    // Update user handler
    const handleUpdateUser = async () => {
        if (!editingUser) return;
        
        setIsEditing(true);
        try {
            await api.admin.updateUser(editingUser.id, {
                name: editForm.name || undefined,
                email: editForm.email || undefined,
                department: editForm.department || undefined,
                role: editForm.role || undefined
            });
            setEditingUser(null);
            toast.success("用户信息已更新");
            loadData();
        } catch (err) {
            console.error("Failed to update user:", err);
            toast.error("更新失败");
        } finally {
            setIsEditing(false);
        }
    };

    // Suspend user handler - actual execution
    const executeSuspend = async (userId: string) => {
        setConfirmDialog(prev => ({ ...prev, open: false }));
        setActionLoading(userId);
        try {
            await api.admin.suspendUser(userId);
            setUsers(prev => prev.map(u => 
                u.id === userId ? { ...u, status: "suspended" as const } : u
            ));
            toast.success("账户已停用");
        } catch (err) {
            console.error("Failed to suspend user:", err);
            toast.error("停用失败");
        } finally {
            setActionLoading(null);
        }
    };

    // Suspend user handler - show confirm
    const handleSuspend = (userId: string) => {
        setConfirmDialog({
            open: true,
            title: "停用账户",
            description: "确定要停用该用户账户吗？停用后用户将无法登录系统。",
            variant: "warning",
            onConfirm: () => executeSuspend(userId)
        });
    };

    // Activate user handler
    const handleActivate = async (userId: string) => {
        setActionLoading(userId);
        try {
            await api.admin.activateUser(userId);
            setUsers(prev => prev.map(u => 
                u.id === userId ? { ...u, status: "active" as const } : u
            ));
            toast.success("账户已激活");
        } catch (err) {
            console.error("Failed to activate user:", err);
            toast.error("激活失败");
        } finally {
            setActionLoading(null);
        }
    };

    // Delete user handler - actual execution
    const executeDelete = async (id: string) => {
        setConfirmDialog(prev => ({ ...prev, open: false }));
        setActionLoading(id);
        try {
            await api.admin.deleteUser(id);
            setUsers(prev => prev.filter(u => u.id !== id));
            toast.success("用户已删除");
        } catch (err) {
            console.error("Failed to delete user:", err);
            toast.error("删除失败");
        } finally {
            setActionLoading(null);
        }
    };

    // Delete user handler - show confirm
    const handleDelete = (id: string) => {
        setConfirmDialog({
            open: true,
            title: "删除用户",
            description: "确定要删除该用户吗？此操作无法撤销。",
            variant: "danger",
            onConfirm: () => executeDelete(id)
        });
    };

    // Export handler
    const handleExport = async () => {
        setIsExporting(true);
        try {
            await api.admin.exportUsers(exportFormat, {
                search: searchQuery || undefined,
                status: statusFilter === "all" ? undefined : statusFilter
            });
            setIsExportOpen(false);
            toast.success("导出成功");
        } catch (err) {
            console.error("Failed to export users:", err);
            toast.error("导出失败");
        } finally {
            setIsExporting(false);
        }
    };

    const handleApplyFilter = () => {
        setIsFilterOpen(false);
        setPage(1);
    };

    // Open edit dialog
    const openEditDialog = (user: AdminUser) => {
        setEditingUser(user);
        setEditForm({
            name: user.username,
            email: user.email,
            department: "",
            role: user.role
        });
    };

    useEffect(() => {
        loadData();
    }, [page, statusFilter, roleFilter, searchQuery]);

    if (isLoading) {
        return <div className="p-8 text-center text-slate-500">加载中...</div>;
    }

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Confirm Dialog */}
            <ConfirmDialog
                open={confirmDialog.open}
                onOpenChange={(open) => setConfirmDialog(prev => ({ ...prev, open }))}
                title={confirmDialog.title}
                description={confirmDialog.description}
                variant={confirmDialog.variant}
                onConfirm={confirmDialog.onConfirm}
                isLoading={!!actionLoading}
            />

            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight">用户管理</h1>
                    <p className="text-slate-500 mt-1">管理系统访问权限</p>
                </div>
                <div className="flex gap-3">
                    {/* Export Dialog */}
                    <Dialog open={isExportOpen} onOpenChange={setIsExportOpen}>
                        <DialogTrigger asChild>
                            <Button variant="outline" className="rounded-full border-slate-200 text-slate-600 hover:bg-slate-50">
                                <Download className="w-4 h-4 mr-2" /> 导出
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>导出用户数据</DialogTitle>
                                <DialogDescription>选择导出格式。</DialogDescription>
                            </DialogHeader>
                            <div className="py-6 flex gap-4">
                                <div 
                                    className={`flex-1 p-4 rounded-xl border cursor-pointer transition-all text-center ${
                                        exportFormat === "csv" 
                                            ? "border-blue-500 bg-blue-50" 
                                            : "border-slate-200 bg-slate-50 hover:border-blue-500 hover:bg-blue-50"
                                    }`}
                                    onClick={() => setExportFormat("csv")}
                                >
                                    <div className="font-bold text-slate-900">CSV</div>
                                    <div className="text-xs text-slate-500 mt-1">电子表格</div>
                                </div>
                                <div 
                                    className={`flex-1 p-4 rounded-xl border cursor-pointer transition-all text-center ${
                                        exportFormat === "json" 
                                            ? "border-blue-500 bg-blue-50" 
                                            : "border-slate-200 bg-slate-50 hover:border-blue-500 hover:bg-blue-50"
                                    }`}
                                    onClick={() => setExportFormat("json")}
                                >
                                    <div className="font-bold text-slate-900">JSON</div>
                                    <div className="text-xs text-slate-500 mt-1">原始数据</div>
                                </div>
                            </div>
                            <DialogFooter>
                                <Button 
                                    className="w-full rounded-full bg-slate-900 text-white"
                                    onClick={handleExport}
                                    disabled={isExporting}
                                >
                                    {isExporting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                                    下载
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>

                    {/* Create User Dialog */}
                    <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                        <DialogTrigger asChild>
                            <Button className="rounded-full bg-slate-900 hover:bg-slate-800 text-white shadow-lg shadow-slate-900/20">
                                <UserPlus className="w-4 h-4 mr-2" /> 添加用户
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-md">
                            <DialogHeader>
                                <DialogTitle>添加新用户</DialogTitle>
                                <DialogDescription>创建新的系统用户账号</DialogDescription>
                            </DialogHeader>
                            <div className="py-4 space-y-4">
                                {createError && (
                                    <div className="p-3 rounded-lg bg-red-50 text-red-600 text-sm">
                                        {createError}
                                    </div>
                                )}
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <label className="text-xs font-bold text-slate-500 uppercase">用户名 *</label>
                                        <input 
                                            className="w-full h-10 px-3 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none text-sm" 
                                            placeholder="zhangsan"
                                            value={createForm.username}
                                            onChange={(e) => setCreateForm(prev => ({ ...prev, username: e.target.value }))}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-xs font-bold text-slate-500 uppercase">姓名</label>
                                        <input 
                                            className="w-full h-10 px-3 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none text-sm" 
                                            placeholder="张三"
                                            value={createForm.name}
                                            onChange={(e) => setCreateForm(prev => ({ ...prev, name: e.target.value }))}
                                        />
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">邮箱地址 *</label>
                                    <div className="relative">
                                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                        <input 
                                            type="email"
                                            className="w-full h-10 pl-10 pr-3 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none text-sm" 
                                            placeholder="zhangsan@company.com"
                                            value={createForm.email}
                                            onChange={(e) => setCreateForm(prev => ({ ...prev, email: e.target.value }))}
                                        />
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">初始密码 *</label>
                                    <input 
                                        type="password"
                                        className="w-full h-10 px-3 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none text-sm" 
                                        placeholder="••••••••"
                                        value={createForm.password}
                                        onChange={(e) => setCreateForm(prev => ({ ...prev, password: e.target.value }))}
                                    />
                                    <p className="text-xs text-slate-400">至少 8 位，包含字母和数字</p>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">部门</label>
                                    <select 
                                        className="w-full h-10 px-3 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                        value={createForm.department}
                                        onChange={(e) => setCreateForm(prev => ({ ...prev, department: e.target.value }))}
                                    >
                                        <option value="">选择部门</option>
                                        <option value="销售部">销售部</option>
                                        <option value="市场部">市场部</option>
                                        <option value="客服部">客服部</option>
                                        <option value="技术部">技术部</option>
                                        <option value="人力资源">人力资源</option>
                                    </select>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">角色 *</label>
                                    <div className="grid grid-cols-2 gap-2">
                                        <div 
                                            className={`border py-2.5 rounded-xl text-center cursor-pointer transition-all ${
                                                createForm.role === "user" 
                                                    ? "border-blue-500 bg-blue-50 text-blue-700" 
                                                    : "border-slate-200 text-slate-600 hover:bg-slate-50"
                                            }`}
                                            onClick={() => setCreateForm(prev => ({ ...prev, role: "user" }))}
                                        >
                                            <div className="font-bold text-sm">普通用户</div>
                                            <div className="text-xs opacity-70">基础访问权限</div>
                                        </div>
                                        <div 
                                            className={`border py-2.5 rounded-xl text-center cursor-pointer transition-all ${
                                                createForm.role === "admin" 
                                                    ? "border-blue-500 bg-blue-50 text-blue-700" 
                                                    : "border-slate-200 text-slate-600 hover:bg-slate-50"
                                            }`}
                                            onClick={() => setCreateForm(prev => ({ ...prev, role: "admin" }))}
                                        >
                                            <div className="font-bold text-sm">管理员</div>
                                            <div className="text-xs opacity-70">完整管理权限</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <DialogFooter className="gap-2">
                                <Button variant="ghost" className="rounded-full" onClick={() => setIsCreateOpen(false)}>取消</Button>
                                <Button 
                                    className="rounded-full bg-slate-900 text-white px-6"
                                    onClick={handleCreateUser}
                                    disabled={isCreating}
                                >
                                    {isCreating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                                    创建用户
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>
            </div>

            {/* Edit User Dialog */}
            <Dialog open={!!editingUser} onOpenChange={(open) => !open && setEditingUser(null)}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle>编辑用户权限</DialogTitle>
                        <DialogDescription>修改用户 {editingUser?.username} 的信息</DialogDescription>
                    </DialogHeader>
                    <div className="py-4 space-y-4">
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">姓名</label>
                            <input 
                                className="w-full h-10 px-3 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none text-sm" 
                                value={editForm.name}
                                onChange={(e) => setEditForm(prev => ({ ...prev, name: e.target.value }))}
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">邮箱</label>
                            <input 
                                type="email"
                                className="w-full h-10 px-3 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none text-sm" 
                                value={editForm.email}
                                onChange={(e) => setEditForm(prev => ({ ...prev, email: e.target.value }))}
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">部门</label>
                            <select 
                                className="w-full h-10 px-3 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                value={editForm.department}
                                onChange={(e) => setEditForm(prev => ({ ...prev, department: e.target.value }))}
                            >
                                <option value="">选择部门</option>
                                <option value="销售部">销售部</option>
                                <option value="市场部">市场部</option>
                                <option value="客服部">客服部</option>
                                <option value="技术部">技术部</option>
                                <option value="人力资源">人力资源</option>
                            </select>
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">角色</label>
                            <div className="grid grid-cols-2 gap-2">
                                <div 
                                    className={`border py-2.5 rounded-xl text-center cursor-pointer transition-all ${
                                        editForm.role === "user" 
                                            ? "border-blue-500 bg-blue-50 text-blue-700" 
                                            : "border-slate-200 text-slate-600 hover:bg-slate-50"
                                    }`}
                                    onClick={() => setEditForm(prev => ({ ...prev, role: "user" }))}
                                >
                                    <div className="font-bold text-sm">普通用户</div>
                                </div>
                                <div 
                                    className={`border py-2.5 rounded-xl text-center cursor-pointer transition-all ${
                                        editForm.role === "admin" 
                                            ? "border-blue-500 bg-blue-50 text-blue-700" 
                                            : "border-slate-200 text-slate-600 hover:bg-slate-50"
                                    }`}
                                    onClick={() => setEditForm(prev => ({ ...prev, role: "admin" }))}
                                >
                                    <div className="font-bold text-sm">管理员</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <DialogFooter className="gap-2">
                        <Button variant="ghost" className="rounded-full" onClick={() => setEditingUser(null)}>取消</Button>
                        <Button 
                            className="rounded-full bg-slate-900 text-white px-6"
                            onClick={handleUpdateUser}
                            disabled={isEditing}
                        >
                            {isEditing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                            保存修改
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Filters Section */}
            <GlassCard className="p-4 flex flex-col md:flex-row gap-4 items-center justify-between">
                <div className="relative w-full md:w-96 group">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-blue-500 transition-colors" />
                    <input
                        type="text"
                        placeholder="搜索用户..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full h-10 pl-10 pr-4 bg-slate-50 border border-slate-200 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/10 focus:border-blue-500 transition-all"
                    />
                </div>
                <div className="flex gap-2">
                    <Dialog open={isFilterOpen} onOpenChange={setIsFilterOpen}>
                        <DialogTrigger asChild>
                            <Button variant="ghost" size="sm" className="text-slate-500 hover:text-slate-900">
                                <Filter className="w-4 h-4 mr-2" /> 筛选
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>筛选用户</DialogTitle>
                            </DialogHeader>
                            <div className="py-6 space-y-4">
                                <div>
                                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 block">状态</label>
                                    <div className="flex flex-wrap gap-2">
                                        {["all", "active", "inactive", "suspended"].map((s) => (
                                            <Badge 
                                                key={s}
                                                variant={statusFilter === s ? 'blue' : 'secondary'} 
                                                className="cursor-pointer"
                                                onClick={() => setStatusFilter(s)}
                                            >
                                                {s === "all" ? "全部" : getStatusLabel(s)}
                                            </Badge>
                                        ))}
                                    </div>
                                </div>
                                <div>
                                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 block">角色</label>
                                    <div className="flex flex-wrap gap-2">
                                        {["all", "admin", "user"].map((r) => (
                                            <Badge 
                                                key={r}
                                                variant={roleFilter === r ? 'blue' : 'secondary'} 
                                                className="cursor-pointer"
                                                onClick={() => setRoleFilter(r)}
                                            >
                                                {r === "all" ? "全部" : getRoleLabel(r)}
                                            </Badge>
                                        ))}
                                    </div>
                                </div>
                            </div>
                            <DialogFooter>
                                <Button className="w-full rounded-full bg-slate-900 text-white" onClick={handleApplyFilter}>应用筛选</Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>
            </GlassCard>

            {/* Users Table */}
            <GlassCard className="overflow-hidden">
                {/* Mobile Card View */}
                <div className="md:hidden space-y-4 p-4">
                    {users.map((user) => (
                        <MobileTableCard
                            key={user.id}
                            title={
                                <div>
                                    <div className="font-bold text-slate-900">{user.username}</div>
                                    <div className="text-slate-400 text-xs">{user.email}</div>
                                </div>
                            }
                            icon={
                                <div className="w-10 h-10 rounded-full bg-slate-200 flex items-center justify-center text-slate-500 text-sm font-bold">
                                    {user.username.charAt(0).toUpperCase()}
                                </div>
                            }
                            columns={[
                                {
                                    label: "角色",
                                    value: <Badge variant="secondary" className="bg-slate-100 text-slate-600 border-slate-200 font-medium">{getRoleLabel(user.role)}</Badge>
                                },
                                {
                                    label: "状态",
                                    value: (
                                        <div className="flex items-center gap-2">
                                            <div className={`w-1.5 h-1.5 rounded-full ${user.status === 'active' ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]' : (['suspended', 'inactive'].includes(user.status) ? 'bg-red-500' : 'bg-slate-400')}`} />
                                            <span className={`font-medium ${user.status === 'active' ? 'text-emerald-600' : (['suspended', 'inactive'].includes(user.status) ? 'text-red-600' : 'text-slate-500')}`}>
                                                {getStatusLabel(user.status)}
                                            </span>
                                        </div>
                                    )
                                }
                            ]}
                            actions={
                                <div className="absolute top-4 right-4">
                                    <UserActionMenu 
                                        user={user}
                                        onEdit={() => openEditDialog(user)}
                                        onSuspend={() => handleSuspend(user.id)}
                                        onActivate={() => handleActivate(user.id)}
                                        onDelete={() => handleDelete(user.id)}
                                        isLoading={actionLoading === user.id}
                                    />
                                </div>
                            }
                            className="relative"
                        >
                            <div className="flex items-center gap-2 text-xs text-slate-400 pt-2">
                                <Calendar className="w-3 h-3" /> 上次活跃: {formatRelativeTime(user.last_active_at)}
                            </div>
                        </MobileTableCard>
                    ))}
                </div>

                {/* Desktop Table View */}
                <div className="hidden md:block overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-slate-50/50 border-b border-slate-100 text-xs uppercase font-bold text-slate-400 tracking-wider">
                            <tr>
                                <th className="px-6 py-4">用户</th>
                                <th className="px-6 py-4">角色</th>
                                <th className="px-6 py-4">状态</th>
                                <th className="px-6 py-4">上次活跃</th>
                                <th className="px-6 py-4 text-right">操作</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {users.map((user) => (
                                <tr key={user.id} className="hover:bg-slate-50/50 transition-colors group">
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-3">
                                            <div className="w-9 h-9 rounded-full bg-slate-200 flex items-center justify-center text-slate-500 text-xs font-bold group-hover:bg-blue-100 group-hover:text-blue-600 transition-colors">
                                                {user.username.charAt(0).toUpperCase()}
                                            </div>
                                            <div>
                                                <div className="font-bold text-slate-900">{user.username}</div>
                                                <div className="text-slate-400 text-xs">{user.email}</div>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <Badge variant="secondary" className="bg-slate-100 text-slate-600 border-slate-200 font-medium">{getRoleLabel(user.role)}</Badge>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-2">
                                            <div className={`w-1.5 h-1.5 rounded-full ${user.status === 'active' ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]' : (['suspended', 'inactive'].includes(user.status) ? 'bg-red-500' : 'bg-slate-400')}`} />
                                            <span className={`font-medium ${user.status === 'active' ? 'text-emerald-600' : (['suspended', 'inactive'].includes(user.status) ? 'text-red-600' : 'text-slate-500')}`}>
                                                {getStatusLabel(user.status)}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 text-slate-500 font-medium">
                                        {formatRelativeTime(user.last_active_at)}
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <UserActionMenu 
                                            user={user}
                                            onEdit={() => openEditDialog(user)}
                                            onSuspend={() => handleSuspend(user.id)}
                                            onActivate={() => handleActivate(user.id)}
                                            onDelete={() => handleDelete(user.id)}
                                            isLoading={actionLoading === user.id}
                                        />
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
                {/* Pagination */}
                <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between">
                    <span className="text-xs text-slate-400 font-medium">显示 {users.length} 位用户</span>
                    <div className="flex gap-2">
                        <Button 
                            variant="outline" 
                            size="sm" 
                            className="h-8 text-xs rounded-full" 
                            disabled={page === 1}
                            onClick={() => setPage(p => p - 1)}
                        >
                            上一页
                        </Button>
                        <Button 
                            variant="outline" 
                            size="sm" 
                            className="h-8 text-xs rounded-full"
                            onClick={() => setPage(p => p + 1)}
                            disabled={users.length < 10}
                        >
                            下一页
                        </Button>
                    </div>
                </div>
            </GlassCard>
        </div>
    );
}

// User Action Menu Component
function UserActionMenu({ 
    user, 
    onEdit, 
    onSuspend, 
    onActivate, 
    onDelete,
    isLoading 
}: { 
    user: AdminUser;
    onEdit: () => void;
    onSuspend: () => void;
    onActivate: () => void;
    onDelete: () => void;
    isLoading: boolean;
}) {
    return (
        <TooltipProvider>
            <Dialog>
                <Tooltip>
                    <TooltipTrigger asChild>
                        <DialogTrigger asChild>
                            <Button variant="ghost" size="icon" className="text-slate-400 hover:text-slate-900 rounded-full hover:bg-slate-200/50">
                                {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <MoreHorizontal className="w-4 h-4" />}
                            </Button>
                        </DialogTrigger>
                    </TooltipTrigger>
                    <TooltipContent>管理用户</TooltipContent>
                </Tooltip>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>管理用户: {user.username}</DialogTitle>
                        <DialogDescription>{user.email}</DialogDescription>
                    </DialogHeader>
                    <div className="py-4 space-y-2">
                        <Button onClick={onEdit} variant="ghost" className="w-full justify-start text-slate-700 hover:bg-slate-50 hover:text-blue-600">
                            <Shield className="w-4 h-4 mr-3" /> 编辑权限
                        </Button>
                        {user.status === "active" ? (
                            <Button onClick={onSuspend} variant="ghost" className="w-full justify-start text-slate-700 hover:bg-slate-50 hover:text-amber-600">
                                <Ban className="w-4 h-4 mr-3" /> 停用账户
                            </Button>
                        ) : (
                            <Button onClick={onActivate} variant="ghost" className="w-full justify-start text-slate-700 hover:bg-slate-50 hover:text-emerald-600">
                                <CheckCircle className="w-4 h-4 mr-3" /> 激活账户
                            </Button>
                        )}
                        <div className="h-px bg-slate-100 my-1"></div>
                        <Button onClick={onDelete} variant="ghost" className="w-full justify-start text-red-600 hover:bg-red-50 hover:text-red-700">
                            <Trash2 className="w-4 h-4 mr-3" /> 删除用户
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>
        </TooltipProvider>
    );
}
