"use client";
import { debug } from "@/lib/debug";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiRequestError, api, getApiErrorMessage } from "@/lib/api/client";
import { AdminUser, CreatedAdminUser } from "@/lib/api/types";
import type { PracticeTemplateRecord, BatchAssignResponse, AdminTeam } from "@/lib/api/types";
import {
    EMPTY_ADMIN_MANAGER_LITE_LISTS,
    buildOperatingPackReadModel,
    formatAdminRelativeTime,
    formatAdminUserRoleLabel,
    formatAdminUserStatusLabel,
} from "@/lib/admin/read-models";
import { buildAdminUserDrillInHref } from "@/lib/admin/drill-in";
import { formatIssueTypeLabel } from "@/lib/session-evidence";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Search, Filter, MoreHorizontal, UserPlus, Download, Mail, Shield, Ban, Calendar, CheckCircle, Loader2, Eye, RefreshCw, Send, CheckSquare, AlertTriangle, FileUp, Network } from "lucide-react";
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

// Form state type
interface CreateUserForm {
    name: string;
    email: string;
    teamId: string;
    role: "user" | "training_manager" | "support" | "admin";
}

interface EditUserForm {
    name: string;
    email: string | undefined;
    teamId: string;
    role: string;
}

type AccountActionKind = "suspend" | "activate" | "reset_password";

interface AccountActionLoading {
    userId: string;
    kind: AccountActionKind;
}

interface AccountActionDialogState {
    user: AdminUser;
    action: AccountActionKind;
}

const initialCreateForm: CreateUserForm = {
    name: "",
    email: "",
    teamId: "",
    role: "user"
};

export default function UsersPage() {
    const router = useRouter();
    const [users, setUsers] = useState<AdminUser[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [weeklyManagerLists, setWeeklyManagerLists] = useState(EMPTY_ADMIN_MANAGER_LITE_LISTS);
    const [weeklyBucketsError, setWeeklyBucketsError] = useState<string | null>(null);
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

    const [accountActionDialog, setAccountActionDialog] = useState<AccountActionDialogState | null>(null);
    const [accountActionReason, setAccountActionReason] = useState("");
    const [accountActionError, setAccountActionError] = useState<string | null>(null);
    const [accountActionNotice, setAccountActionNotice] = useState<{ tone: "success" | "warning" | "error"; message: string } | null>(null);

    // Create user form
    const [createForm, setCreateForm] = useState<CreateUserForm>(initialCreateForm);
    const [isCreating, setIsCreating] = useState(false);
    const [createError, setCreateError] = useState("");
    const [createdCredential, setCreatedCredential] = useState<CreatedAdminUser | null>(null);

    // Edit user state
    const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
    const [editForm, setEditForm] = useState<EditUserForm>({ name: "", email: "", teamId: "", role: "" });
    const [isEditing, setIsEditing] = useState(false);

    // Action states
    const [actionLoading, setActionLoading] = useState<AccountActionLoading | null>(null);

    // Team filter & multi-select
    const [teamFilter, setTeamFilter] = useState("all");
    const [selectedUserIds, setSelectedUserIds] = useState<Set<string>>(new Set());
    const [teams, setTeams] = useState<AdminTeam[]>([]);

    // Batch assign state
    const [isBatchAssignOpen, setIsBatchAssignOpen] = useState(false);
    const [batchTemplates, setBatchTemplates] = useState<PracticeTemplateRecord[]>([]);
    const [selectedTemplateId, setSelectedTemplateId] = useState("");
    const [batchTitle, setBatchTitle] = useState("");
    const [batchGoal, setBatchGoal] = useState("");
    const [batchScenarioType, setBatchScenarioType] = useState<"sales" | "presentation">("sales");
    const [isBatchAssigning, setIsBatchAssigning] = useState(false);
    const [isLoadingTemplates, setIsLoadingTemplates] = useState(false);

    // Batch result state
    const [batchResults, setBatchResults] = useState<BatchAssignResponse | null>(null);
    const [isResultsOpen, setIsResultsOpen] = useState(false);

    const loadData = useCallback(async () => {
        setIsLoading(true);
        try {
            const data = await api.admin.getUsers({
                search: searchQuery,
                status: statusFilter === "all" ? undefined : statusFilter,
                role: roleFilter === "all" ? undefined : roleFilter,
                team_id: teamFilter === "all" ? undefined : teamFilter,
                page: page,
                page_size: 10
            });
            setUsers(data.items || []);
        } catch (err) {
            debug.error("Failed to load users:", err);
        } finally {
            setIsLoading(false);
        }
    }, [page, roleFilter, searchQuery, statusFilter, teamFilter]);

    const loadWeeklyBuckets = useCallback(async () => {
        setWeeklyBucketsError(null);
        try {
            const operatingPack = await api.analytics.getOperatingPack({
                time_range: "7d",
                limit: 10,
                inactive_days: 7,
            });
            setWeeklyManagerLists(buildOperatingPackReadModel(operatingPack).managerLite);
        } catch (err) {
            debug.error("Failed to load weekly operating buckets:", err);
            setWeeklyManagerLists(EMPTY_ADMIN_MANAGER_LITE_LISTS);
            setWeeklyBucketsError("本周经营名单暂时不可用，请稍后重试。");
        }
    }, []);

    const loadTeams = useCallback(async () => {
        try {
            const data = await api.admin.getTeams();
            setTeams(data.items || []);
        } catch (err) {
            debug.error("Failed to load team relationships:", err);
            setTeams([]);
        }
    }, []);

    // Create user handler
    const handleCreateUser = async () => {
        setCreateError("");

        // Validation
        if (!createForm.name.trim()) {
            setCreateError("请输入姓名");
            return;
        }
        if (!createForm.email.trim()) {
            setCreateError("请输入邮箱地址");
            return;
        }
        setIsCreating(true);
        try {
            const created = await api.admin.createUser({
                name: createForm.name.trim(),
                email: createForm.email.trim(),
                role: createForm.role,
                team_id: createForm.role === "user" && createForm.teamId
                    ? createForm.teamId
                    : undefined,
            });
            setIsCreateOpen(false);
            setCreatedCredential(created);
            setCreateForm(initialCreateForm);
            loadData();
        } catch (err) {
            debug.error("Failed to create user:", err);
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
            });
        } catch (err) {
            debug.error("Failed to update user:", err);
            toast.error("更新失败");
            setIsEditing(false);
            return;
        }

        // Profile updated — role change is independent
        let roleFailed = false;
        if (editForm.role && editForm.role !== editingUser.role) {
            try {
                await api.admin.updateUserRole(editingUser.id, { role: editForm.role });
            } catch (err) {
                debug.error("Failed to update user role:", err);
                roleFailed = true;
            }
        }

        let teamFailed = false;
        if (
            !roleFailed
            && editForm.role === "user"
            && editForm.teamId
            && editForm.teamId !== editingUser.team?.team_id
        ) {
            try {
                await api.admin.assignTeamMember(editForm.teamId, editingUser.id);
            } catch (err) {
                debug.error("Failed to update user team:", err);
                teamFailed = true;
            }
        }

        setEditingUser(null);
        setIsEditing(false);
        if (roleFailed) {
            toast.success("资料已更新，但角色更新失败，请重试");
        } else if (teamFailed) {
            toast.error("资料已更新，但团队分配失败，请重试");
        } else {
            toast.success("用户信息已更新");
        }
        void Promise.all([loadData(), loadTeams()]);
    };

    const applyAuthoritativeUserState = (authoritativeUser: AdminUser) => {
        setUsers((previous) => previous.map((user) => user.id === authoritativeUser.id
            ? {
                ...user,
                status: authoritativeUser.status,
                is_active: authoritativeUser.status === "active",
                credential_version: authoritativeUser.credential_version,
            }
            : user));
    };

    const reconcileAccountStatus = async (userId: string) => {
        const authoritativeUser = await api.admin.getUser(userId);
        applyAuthoritativeUserState(authoritativeUser);
        return authoritativeUser;
    };

    const executeAccountStatusChange = async () => {
        if (!accountActionDialog || !accountActionReason.trim()) return;

        const { user, action } = accountActionDialog;
        const expectedStatus = action === "suspend" ? "inactive" : "active";
        setActionLoading({ userId: user.id, kind: action });
        setAccountActionError(null);
        setAccountActionNotice(null);
        try {
            const payload = {
                audit_reason: accountActionReason.trim(),
                expected_credential_version: user.credential_version,
            };
            if (action === "reset_password") {
                const credential = await api.admin.resetTemporaryPassword(user.id, payload);
                setCreatedCredential(credential);
                applyAuthoritativeUserState(credential);
                setAccountActionNotice({ tone: "success", message: "临时密码已重置；新密码只在当前凭证窗口显示一次。" });
                setAccountActionDialog(null);
                setAccountActionReason("");
                return;
            }

            const result = action === "suspend"
                ? await api.admin.suspendUser(user.id, payload)
                : await api.admin.activateUser(user.id, payload);
            setUsers((previous) => previous.map((item) => item.id === user.id
                ? {
                    ...item,
                    status: result.status,
                    is_active: result.status === "active",
                    credential_version: result.credential_version,
                }
                : item));
            const successMessage = action === "suspend" ? "账户已停用，可由管理员重新激活。" : "账户已激活。";
            setAccountActionNotice({ tone: "success", message: successMessage });
            setAccountActionDialog(null);
            setAccountActionReason("");
            toast.success(action === "suspend" ? "账户已停用" : "账户已激活");
        } catch (err) {
            debug.error("Failed to change account status:", err);
            if (err instanceof ApiRequestError && ["[REQUEST_TIMEOUT]", "[ACCOUNT_STATUS_CONFLICT]"].includes(err.errorCode)) {
                try {
                    const authoritativeUser = await reconcileAccountStatus(user.id);
                    const resetWasApplied = action === "reset_password"
                        && Number(authoritativeUser.credential_version || 0) > Number(user.credential_version || 0);
                    if (resetWasApplied) {
                        setAccountActionNotice({
                            tone: "warning",
                            message: "临时密码可能已重置，但响应中断，密码未被展示。请再次执行重置，以生成一组新的可交付密码。",
                        });
                        setAccountActionDialog(null);
                        setAccountActionReason("");
                    } else if (authoritativeUser.status === expectedStatus && action !== "reset_password") {
                        setAccountActionNotice({
                            tone: "success",
                            message: `${action === "suspend" ? "停用" : "激活"}响应超时，但已核对：账号状态已经生效。`,
                        });
                        setAccountActionDialog(null);
                        setAccountActionReason("");
                    } else {
                        setAccountActionError("账号状态已被刷新，本次操作尚未生效。请确认最新状态后重试。");
                        setAccountActionDialog({ user: authoritativeUser, action });
                    }
                    return;
                } catch (reconcileError) {
                    debug.error("Failed to reconcile account status:", reconcileError);
                    setAccountActionError("请求结果暂时无法确认。已保留操作原因，请刷新账号列表后核对，避免重复操作。");
                    return;
                }
            }
            const message = getApiErrorMessage(err);
            setAccountActionError(message);
            toast.error(message);
        } finally {
            setActionLoading(null);
        }
    };

    const openAccountActionDialog = (user: AdminUser, action: AccountActionKind) => {
        if (actionLoading?.userId === user.id) return;
        setAccountActionReason("");
        setAccountActionError(null);
        setAccountActionDialog({ user, action });
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
            debug.error("Failed to export users:", err);
            toast.error("导出失败");
        } finally {
            setIsExporting(false);
        }
    };

    const handleApplyFilter = () => {
        setIsFilterOpen(false);
        setPage(1);
    };

    const activeTeams = teams.filter((team) => team.is_active);
    const filteredUsers = users;

    const selectableLearners = filteredUsers.filter((user) => user.role === "user");
    const allFilteredSelected = selectableLearners.length > 0
        && selectableLearners.every((user) => selectedUserIds.has(user.id));
    const teamLeaderUserIds = new Set(teams.flatMap((team) => team.leader_user_ids));
    const teamByLeaderUserId = new Map(
        teams.flatMap((team) => team.leader_user_ids.map((userId) => [userId, team] as const)),
    );
    const teamByMemberUserId = new Map(
        teams.flatMap((team) => team.members.map((member) => [member.user_id, team] as const)),
    );

    const toggleSelectAll = () => {
        if (allFilteredSelected) {
            setSelectedUserIds((prev) => {
                const next = new Set(prev);
                selectableLearners.forEach((user) => next.delete(user.id));
                return next;
            });
        } else {
            setSelectedUserIds((prev) => {
                const next = new Set(prev);
                selectableLearners.forEach((user) => next.add(user.id));
                return next;
            });
        }
    };

    const toggleUserSelection = (userId: string) => {
        setSelectedUserIds((prev) => {
            const next = new Set(prev);
            if (next.has(userId)) {
                next.delete(userId);
            } else {
                next.add(userId);
            }
            return next;
        });
    };

    const loadTemplates = async () => {
        setIsLoadingTemplates(true);
        try {
            const data = await api.admin.listPracticeTemplates();
            const published = (data.items || []).filter(
                (t) => t.status === "published" && t.curriculum_plan,
            );
            setBatchTemplates(published);
            if (published.length > 0 && !selectedTemplateId) {
                setSelectedTemplateId(published[0].template_id);
            }
        } catch (err) {
            debug.error("Failed to load templates:", err);
            toast.error("加载模板失败");
        } finally {
            setIsLoadingTemplates(false);
        }
    };

    const handleBatchAssign = async () => {
        if (selectedUserIds.size === 0 || !selectedTemplateId) return;

        const template = batchTemplates.find((t) => t.template_id === selectedTemplateId);
        if (!template) return;

        setIsBatchAssigning(true);
        try {
            const result = await api.trainingTasks.batchAssign({
                user_ids: Array.from(selectedUserIds),
                template_id: selectedTemplateId,
                curriculum_plan_id: selectedTemplateId,
                title: batchTitle || template.name,
                scenario_type: batchScenarioType,
                goal: batchGoal || template.description || "完成训练任务",
            });
            setBatchResults(result);
            setIsBatchAssignOpen(false);
            setIsResultsOpen(true);
            setSelectedUserIds(new Set());
            if (result.assigned_count > 0) {
                toast.success(`成功分配 ${result.assigned_count} 个训练任务`);
            }
            if (result.skipped_count > 0 || result.failed_count > 0) {
                toast.error(`${result.skipped_count} 跳过, ${result.failed_count} 失败`);
            }
        } catch (err) {
            debug.error("Failed to batch assign:", err);
            toast.error("批量分配失败");
        } finally {
            setIsBatchAssigning(false);
        }
    };

    // Open edit dialog
    const openEditDialog = (user: AdminUser) => {
        setEditingUser(user);
        setEditForm({
            name: user.display_name,
            email: user.email,
            teamId: user.team?.team_id || "",
            role: user.role
        });
    };

    useEffect(() => {
        loadData();
    }, [loadData]);

    useEffect(() => {
        void loadWeeklyBuckets();
    }, [loadWeeklyBuckets]);

    useEffect(() => {
        void loadTeams();
    }, [loadTeams]);

    if (isLoading) {
        return <div className="p-8 text-center text-slate-500">加载中...</div>;
    }

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Account status confirmation */}
            <ConfirmDialog
                open={accountActionDialog !== null}
                onOpenChange={(open) => {
                    if (!open && !actionLoading) {
                        setAccountActionDialog(null);
                        setAccountActionError(null);
                    }
                }}
                title={accountActionDialog?.action === "activate" ? "激活账户" : accountActionDialog?.action === "reset_password" ? "重置临时密码" : "停用账户"}
                description={accountActionDialog?.action === "activate"
                    ? `激活后，${accountActionDialog?.user.display_name ?? "该用户"}可以重新登录系统。`
                    : accountActionDialog?.action === "reset_password"
                        ? `重置后，${accountActionDialog?.user.display_name ?? "该用户"}的现有登录态和旧密码将失效；新临时密码只显示一次。`
                        : `停用后，${accountActionDialog?.user.display_name ?? "该用户"}将无法登录；训练、团队和审计记录会保留，并可重新激活。`}
                confirmText={accountActionDialog?.action === "activate" ? "确认激活" : accountActionDialog?.action === "reset_password" ? "确认重置" : "确认停用"}
                variant={accountActionDialog?.action === "activate" ? "default" : "warning"}
                onConfirm={() => void executeAccountStatusChange()}
                isLoading={Boolean(accountActionDialog && actionLoading?.userId === accountActionDialog.user.id && actionLoading.kind === accountActionDialog.action)}
                confirmDisabled={!accountActionReason.trim()}
            >
                <div className="mt-4 space-y-2">
                    <label htmlFor="account-action-reason" className="text-sm font-medium text-slate-700">操作原因</label>
                    <textarea
                        id="account-action-reason"
                        value={accountActionReason}
                        onChange={(event) => setAccountActionReason(event.target.value)}
                        maxLength={500}
                        rows={3}
                        placeholder="例如：员工离职、账号恢复使用"
                        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
                    />
                    {accountActionError ? <p role="alert" className="text-sm text-red-600">{accountActionError}</p> : null}
                </div>
            </ConfirmDialog>

            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight">用户管理</h1>
                    <p className="text-slate-500 mt-1">管理系统访问权限，并在用户详情里设置主管重点与提醒。</p>
                </div>
                <div className="flex gap-3">
                    <Button asChild variant="outline" className="rounded-full border-slate-200 text-slate-700">
                        <Link href="/admin/teams"><Network className="mr-2 h-4 w-4" />团队与成员</Link>
                    </Button>
                    <Button asChild variant="outline" className="rounded-full border-slate-200 text-slate-700">
                        <Link href="/admin/users/import"><FileUp className="mr-2 h-4 w-4" />批量开户</Link>
                    </Button>
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
                                    className={`flex-1 p-4 rounded-xl border cursor-pointer transition-all text-center ${exportFormat === "csv"
                                            ? "border-blue-500 bg-blue-50"
                                            : "border-slate-200 bg-slate-50 hover:border-blue-500 hover:bg-blue-50"
                                        }`}
                                    onClick={() => setExportFormat("csv")}
                                >
                                    <div className="font-bold text-slate-900">CSV</div>
                                    <div className="text-xs text-slate-500 mt-1">电子表格</div>
                                </div>
                                <div
                                    className={`flex-1 p-4 rounded-xl border cursor-pointer transition-all text-center ${exportFormat === "json"
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
                                <div className="space-y-2">
                                        <label className="text-xs font-bold text-slate-500 uppercase">姓名 *</label>
                                        <input
                                            className="w-full h-10 px-3 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                            placeholder="张三"
                                            value={createForm.name}
                                            onChange={(e) => setCreateForm(prev => ({ ...prev, name: e.target.value }))}
                                        />
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
                                {createForm.role === "user" ? (
                                    <div className="space-y-2">
                                        <label className="text-xs font-bold text-slate-500 uppercase">所属团队</label>
                                        <select
                                            className="w-full h-10 px-3 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                            value={createForm.teamId}
                                            onChange={(e) => setCreateForm(prev => ({ ...prev, teamId: e.target.value }))}
                                        >
                                            <option value="">暂不分配团队</option>
                                            {activeTeams.map((team) => (
                                                <option key={team.team_id} value={team.team_id}>{team.name}</option>
                                            ))}
                                        </select>
                                        <p className="text-xs text-slate-500">创建账号与团队归属在同一事务中完成。</p>
                                    </div>
                                ) : null}
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">角色 *</label>
                                    <div className="grid grid-cols-2 gap-2">
                                        <div
                                            className={`border py-2.5 rounded-xl text-center cursor-pointer transition-all ${createForm.role === "user"
                                                    ? "border-blue-500 bg-blue-50 text-blue-700"
                                                    : "border-slate-200 text-slate-600 hover:bg-slate-50"
                                                }`}
                                            onClick={() => setCreateForm(prev => ({ ...prev, role: "user" }))}
                                        >
                                            <div className="font-bold text-sm">学员</div>
                                            <div className="text-xs opacity-70">参与训练</div>
                                        </div>
                                        <div
                                            className={`border py-2.5 rounded-xl text-center cursor-pointer transition-all ${createForm.role === "training_manager"
                                                    ? "border-blue-500 bg-blue-50 text-blue-700"
                                                    : "border-slate-200 text-slate-600 hover:bg-slate-50"
                                                }`}
                                            onClick={() => setCreateForm(prev => ({ ...prev, role: "training_manager", teamId: "" }))}
                                        >
                                            <div className="font-bold text-sm">培训管理员</div>
                                            <div className="text-xs opacity-70">可配置为销售组长</div>
                                        </div>
                                        <div
                                            className={`border py-2.5 rounded-xl text-center cursor-pointer transition-all ${createForm.role === "support"
                                                    ? "border-blue-500 bg-blue-50 text-blue-700"
                                                    : "border-slate-200 text-slate-600 hover:bg-slate-50"
                                                }`}
                                            onClick={() => setCreateForm(prev => ({ ...prev, role: "support", teamId: "" }))}
                                        >
                                            <div className="font-bold text-sm">技术支持</div>
                                            <div className="text-xs opacity-70">只读运行状态</div>
                                        </div>
                                        <div
                                            className={`border py-2.5 rounded-xl text-center cursor-pointer transition-all ${createForm.role === "admin"
                                                    ? "border-blue-500 bg-blue-50 text-blue-700"
                                                    : "border-slate-200 text-slate-600 hover:bg-slate-50"
                                                }`}
                                            onClick={() => setCreateForm(prev => ({ ...prev, role: "admin", teamId: "" }))}
                                        >
                                            <div className="font-bold text-sm">平台管理员</div>
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

                    <Dialog open={createdCredential !== null} onOpenChange={(open) => !open && setCreatedCredential(null)}>
                        <DialogContent className="max-w-md">
                            <DialogHeader>
                                <DialogTitle>账号已创建</DialogTitle>
                                <DialogDescription>临时密码只显示这一次，请立即安全交付给本人。</DialogDescription>
                            </DialogHeader>
                            {createdCredential && (
                                <div className="space-y-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm">
                                    <p><span className="text-slate-500">邮箱：</span>{createdCredential.email}</p>
                                    <p className="break-all font-mono text-base font-semibold text-slate-900">{createdCredential.temporary_password}</p>
                                    <p className="text-amber-800">首次登录必须修改密码；临时密码有效期至 {createdCredential.temporary_password_expires_at ? new Date(createdCredential.temporary_password_expires_at).toLocaleString("zh-CN") : "系统配置时间"}。</p>
                                </div>
                            )}
                            <DialogFooter>
                                <Button onClick={() => setCreatedCredential(null)}>我已安全保存</Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>
            </div>

            {accountActionNotice ? (
                <div
                    role="status"
                    className={`rounded-xl border px-4 py-3 text-sm ${accountActionNotice.tone === "success"
                        ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                        : accountActionNotice.tone === "warning"
                            ? "border-amber-200 bg-amber-50 text-amber-800"
                            : "border-red-200 bg-red-50 text-red-700"
                        }`}
                >
                    {accountActionNotice.message}
                </div>
            ) : null}

            <GlassCard className="p-6 border border-slate-200 bg-white/95">
                <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                    <div>
                        <h2 className="text-lg font-bold text-slate-900">本周经营名单 drill-in</h2>
                        <p className="mt-1 text-sm text-slate-500 text-pretty">
                            把当前用户页和本周经营节奏包放在同一套风险 / 回升词汇上，点进详情后会自动带上对应的主管重点上下文。
                        </p>
                    </div>
                    <Button variant="outline" size="sm" className="rounded-full" onClick={() => void loadWeeklyBuckets()}>
                        <RefreshCw className="w-4 h-4 mr-2" />
                        刷新名单
                    </Button>
                </div>

                {weeklyBucketsError ? (
                    <div role="alert" className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                        {weeklyBucketsError}
                    </div>
                ) : (
                    <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-3">
                        <div className="rounded-2xl border border-rose-100 bg-rose-50/70 p-4">
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <h3 className="text-sm font-bold text-slate-900">本周风险成员</h3>
                                    <p className="mt-1 text-xs text-slate-500">统一训练证据里最近一条可评估训练仍未通过。</p>
                                </div>
                                <span className="text-xs font-medium text-rose-700">{weeklyManagerLists.not_passed.length} 人</span>
                            </div>
                            <div className="mt-4 space-y-3">
                                {weeklyManagerLists.not_passed.length > 0 ? weeklyManagerLists.not_passed.map((item) => (
                                    <div key={`${item.user_id}-${item.session_id}`} className="rounded-2xl border border-white/80 bg-white px-4 py-3">
                                        <p className="text-sm font-semibold text-slate-900">{item.user_name}</p>
                                        <p className="mt-1 text-xs text-slate-500">{item.team?.name || "未分配团队"}</p>
                                        <p className="mt-2 text-xs text-rose-700 text-pretty">
                                            问题家族 · {formatIssueTypeLabel(item.issue_family) || item.issue_family || "证据支撑"}
                                        </p>
                                        <div className="mt-3 flex flex-wrap gap-2">
                                            <Button asChild size="sm" variant="outline" className="h-8 rounded-full">
                                                <Link
                                                    href={buildAdminUserDrillInHref({
                                                        kind: "not_passed",
                                                        userId: item.user_id,
                                                        issueFamily: item.issue_family,
                                                    })}
                                                    prefetch={false}
                                                >
                                                    查看并设重点
                                                </Link>
                                            </Button>
                                        </div>
                                    </div>
                                )) : (
                                    <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-5 text-sm text-slate-500">
                                        当前没有风险成员。
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="rounded-2xl border border-amber-100 bg-amber-50/70 p-4">
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <h3 className="text-sm font-bold text-slate-900">本周连续未练</h3>
                                    <p className="mt-1 text-xs text-slate-500">按最后一次已完成训练计算连续未练天数。</p>
                                </div>
                                <span className="text-xs font-medium text-amber-700">{weeklyManagerLists.inactive_streak.length} 人</span>
                            </div>
                            <div className="mt-4 space-y-3">
                                {weeklyManagerLists.inactive_streak.length > 0 ? weeklyManagerLists.inactive_streak.map((item) => (
                                    <div key={item.user_id} className="rounded-2xl border border-white/80 bg-white px-4 py-3">
                                        <p className="text-sm font-semibold text-slate-900">{item.user_name}</p>
                                        <p className="mt-1 text-xs text-slate-500">{item.team?.name || "未分配团队"}</p>
                                        <p className="mt-2 text-xs text-amber-700">连续未练：{item.inactive_days} 天</p>
                                        <div className="mt-3 flex flex-wrap gap-2">
                                            <Button asChild size="sm" variant="outline" className="h-8 rounded-full">
                                                <Link href={buildAdminUserDrillInHref({ kind: "inactive_streak", userId: item.user_id })} prefetch={false}>
                                                    查看详情
                                                </Link>
                                            </Button>
                                        </div>
                                    </div>
                                )) : (
                                    <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-5 text-sm text-slate-500">
                                        当前没有连续未练成员。
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="rounded-2xl border border-emerald-100 bg-emerald-50/70 p-4">
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <h3 className="text-sm font-bold text-slate-900">本周显著回升</h3>
                                    <p className="mt-1 text-xs text-slate-500">通过率改善只按可评估的已完成训练计算。</p>
                                </div>
                                <span className="text-xs font-medium text-emerald-700">{weeklyManagerLists.improving.length} 人</span>
                            </div>
                            <div className="mt-4 space-y-3">
                                {weeklyManagerLists.improving.length > 0 ? weeklyManagerLists.improving.map((item) => (
                                    <div key={item.user_id} className="rounded-2xl border border-white/80 bg-white px-4 py-3">
                                        <p className="text-sm font-semibold text-slate-900">{item.user_name}</p>
                                        <p className="mt-1 text-xs text-slate-500">{item.team?.name || "未分配团队"}</p>
                                        <p className="mt-2 text-xs text-emerald-700">可评估通过率提升：+{item.pass_gain}%</p>
                                        <p className="mt-1 text-[11px] text-slate-500">基线 {item.baseline_pass_rate}% → 当前 {item.current_pass_rate}%</p>
                                        <div className="mt-3 flex flex-wrap gap-2">
                                            <Button asChild size="sm" variant="outline" className="h-8 rounded-full">
                                                <Link href={buildAdminUserDrillInHref({ kind: "improving", userId: item.user_id })} prefetch={false}>
                                                    查看详情
                                                </Link>
                                            </Button>
                                        </div>
                                    </div>
                                )) : (
                                    <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-5 text-sm text-slate-500">
                                        当前没有显著回升成员。
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )}
            </GlassCard>

            {/* Edit User Dialog */}
            <Dialog open={!!editingUser} onOpenChange={(open) => !open && setEditingUser(null)}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle>编辑用户权限</DialogTitle>
                        <DialogDescription>修改用户 {editingUser?.display_name} 的信息</DialogDescription>
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
                        {editForm.role === "user" ? (
                            <div className="space-y-2">
                                <label className="text-xs font-bold text-slate-500 uppercase">所属团队</label>
                                <select
                                    className="w-full h-10 px-3 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                    value={editForm.teamId}
                                    onChange={(e) => setEditForm(prev => ({ ...prev, teamId: e.target.value }))}
                                >
                                    <option value="">保持未分配</option>
                                    {activeTeams.map((team) => (
                                        <option key={team.team_id} value={team.team_id}>{team.name}</option>
                                    ))}
                                </select>
                                <p className="text-xs text-slate-500">选择其他团队会结束原主团队关系并建立新关系。</p>
                            </div>
                        ) : null}
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">角色</label>
                            <div className="grid grid-cols-2 gap-2">
                                <div
                                    className={`border py-2.5 rounded-xl text-center cursor-pointer transition-all ${editForm.role === "user"
                                            ? "border-blue-500 bg-blue-50 text-blue-700"
                                            : "border-slate-200 text-slate-600 hover:bg-slate-50"
                                        }`}
                                    onClick={() => setEditForm(prev => ({ ...prev, role: "user" }))}
                                >
                                    <div className="font-bold text-sm">学员</div>
                                </div>
                                <div
                                    className={`border py-2.5 rounded-xl text-center cursor-pointer transition-all ${editForm.role === "training_manager"
                                            ? "border-blue-500 bg-blue-50 text-blue-700"
                                            : "border-slate-200 text-slate-600 hover:bg-slate-50"
                                        }`}
                                    onClick={() => setEditForm(prev => ({ ...prev, role: "training_manager", teamId: "" }))}
                                >
                                    <div className="font-bold text-sm">培训管理员</div>
                                </div>
                                <div
                                    className={`border py-2.5 rounded-xl text-center cursor-pointer transition-all ${editForm.role === "support"
                                            ? "border-blue-500 bg-blue-50 text-blue-700"
                                            : "border-slate-200 text-slate-600 hover:bg-slate-50"
                                        }`}
                                    onClick={() => setEditForm(prev => ({ ...prev, role: "support", teamId: "" }))}
                                >
                                    <div className="font-bold text-sm">技术支持</div>
                                </div>
                                <div
                                    className={`border py-2.5 rounded-xl text-center cursor-pointer transition-all ${editForm.role === "admin"
                                            ? "border-blue-500 bg-blue-50 text-blue-700"
                                            : "border-slate-200 text-slate-600 hover:bg-slate-50"
                                        }`}
                                    onClick={() => setEditForm(prev => ({ ...prev, role: "admin", teamId: "" }))}
                                >
                                    <div className="font-bold text-sm">平台管理员</div>
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
                    <select
                        aria-label="团队筛选"
                        className="h-10 px-3 rounded-full border border-slate-200 bg-slate-50 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/10 focus:border-blue-500 transition-all text-slate-600"
                        value={teamFilter}
                        onChange={(e) => {
                            setTeamFilter(e.target.value);
                            setPage(1);
                            setSelectedUserIds(new Set());
                        }}
                    >
                        <option value="all">全部团队</option>
                        {activeTeams.map((team) => (
                            <option key={team.team_id} value={team.team_id}>{team.name}</option>
                        ))}
                    </select>
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
                                                {s === "all" ? "全部" : formatAdminUserStatusLabel(s)}
                                            </Badge>
                                        ))}
                                    </div>
                                </div>
                                <div>
                                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 block">角色</label>
                                    <div className="flex flex-wrap gap-2">
                                        {["all", "admin", "training_manager", "support", "user"].map((r) => (
                                            <Badge
                                                key={r}
                                                variant={roleFilter === r ? 'blue' : 'secondary'}
                                                className="cursor-pointer"
                                                onClick={() => setRoleFilter(r)}
                                            >
                                                {r === "all" ? "全部" : formatAdminUserRoleLabel(r)}
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

            {/* Batch Assign Action Bar */}
            {selectedUserIds.size > 0 && (
                <div className="flex items-center gap-4 px-4 py-3 rounded-2xl border border-blue-200 bg-blue-50/80">
                    <CheckSquare className="w-5 h-5 text-blue-600" />
                    <span className="text-sm font-semibold text-blue-800">
                        已选择 {selectedUserIds.size} 位学员
                    </span>
                    <Button
                        className="ml-auto rounded-full bg-blue-600 hover:bg-blue-700 text-white"
                        onClick={() => {
                            setIsBatchAssignOpen(true);
                            loadTemplates();
                        }}
                    >
                        <Send className="w-4 h-4 mr-2" /> 批量分配训练任务
                    </Button>
                </div>
            )}

            {/* Batch Assign Dialog */}
            <Dialog open={isBatchAssignOpen} onOpenChange={setIsBatchAssignOpen}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle>批量分配训练任务</DialogTitle>
                        <DialogDescription>
                            为 {selectedUserIds.size} 位学员分配训练任务
                        </DialogDescription>
                    </DialogHeader>
                    <div className="py-4 space-y-4">
                        {isLoadingTemplates ? (
                            <div className="flex items-center justify-center py-4">
                                <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
                                <span className="ml-2 text-sm text-slate-500">加载模板中...</span>
                            </div>
                        ) : batchTemplates.length === 0 ? (
                            <div className="rounded-xl border border-dashed border-slate-200 px-4 py-6 text-center text-sm text-slate-500">
                                没有可用的已发布模板，请先在模板管理中发布模板。
                            </div>
                        ) : (
                            <>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">训练模板</label>
                                    <select
                                        className="w-full h-10 px-3 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                        value={selectedTemplateId}
                                        onChange={(e) => setSelectedTemplateId(e.target.value)}
                                    >
                                        {batchTemplates.map((t) => (
                                            <option key={t.template_id} value={t.template_id}>
                                                {t.name} ({t.scenario_type === "sales" ? "销售" : "演讲"})
                                                {t.curriculum_plan ? " ◆" : ""}
                                            </option>
                                        ))}
                                    </select>
                                    {(() => {
                                        const t = batchTemplates.find((tmpl) => tmpl.template_id === selectedTemplateId);
                                        return t?.curriculum_plan ? (
                                            <p className="text-xs text-emerald-600">包含课程计划（{t.curriculum_plan.stages.length} 阶段）</p>
                                        ) : null;
                                    })()}
                                </div>

                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">场景类型</label>
                                    <div className="grid grid-cols-2 gap-2">
                                        {(["sales", "presentation"] as const).map((s) => (
                                            <div
                                                key={s}
                                                className={`border py-2.5 rounded-xl text-center cursor-pointer transition-all ${
                                                    batchScenarioType === s
                                                        ? "border-blue-500 bg-blue-50 text-blue-700"
                                                        : "border-slate-200 text-slate-600 hover:bg-slate-50"
                                                }`}
                                                onClick={() => setBatchScenarioType(s)}
                                            >
                                                <div className="font-bold text-sm">{s === "sales" ? "销售" : "演讲"}</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">任务标题（可选，默认使用模板名）</label>
                                    <input
                                        className="w-full h-10 px-3 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                        placeholder={selectedTemplateId ? batchTemplates.find((t) => t.template_id === selectedTemplateId)?.name || "" : ""}
                                        value={batchTitle}
                                        onChange={(e) => setBatchTitle(e.target.value)}
                                    />
                                </div>

                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">训练目标</label>
                                    <input
                                        className="w-full h-10 px-3 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                        placeholder="例如：完成销售话术实战训练"
                                        value={batchGoal}
                                        onChange={(e) => setBatchGoal(e.target.value)}
                                    />
                                </div>
                            </>
                        )}
                    </div>
                    <DialogFooter className="gap-2">
                        <Button variant="ghost" className="rounded-full" onClick={() => setIsBatchAssignOpen(false)}>取消</Button>
                        <Button
                            className="rounded-full bg-slate-900 text-white px-6"
                            onClick={handleBatchAssign}
                            disabled={isBatchAssigning || batchTemplates.length === 0}
                        >
                            {isBatchAssigning ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                            确认分配
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Batch Result Dialog */}
            <Dialog open={isResultsOpen} onOpenChange={setIsResultsOpen}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle>分配结果</DialogTitle>
                        <DialogDescription>
                            共处理 {(batchResults?.assigned_count ?? 0) + (batchResults?.skipped_count ?? 0) + (batchResults?.failed_count ?? 0)} 位学员
                        </DialogDescription>
                    </DialogHeader>
                    <div className="py-4 space-y-4">
                        {batchResults && (
                            <>
                                <div className="grid grid-cols-3 gap-3">
                                    <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-center">
                                        <div className="text-2xl font-bold text-emerald-700">{batchResults.assigned_count}</div>
                                        <div className="text-xs text-emerald-600 mt-1">已分配</div>
                                    </div>
                                    <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-center">
                                        <div className="text-2xl font-bold text-amber-700">{batchResults.skipped_count}</div>
                                        <div className="text-xs text-amber-600 mt-1">已跳过</div>
                                    </div>
                                    <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-center">
                                        <div className="text-2xl font-bold text-red-700">{batchResults.failed_count}</div>
                                        <div className="text-xs text-red-600 mt-1">失败</div>
                                    </div>
                                </div>
                                <div className="max-h-64 overflow-y-auto space-y-2">
                                    {batchResults.assigned.map((r) => (
                                        <div key={`a-${r.user_id}`} className="flex items-start gap-3 rounded-lg border border-emerald-100 bg-emerald-50/50 px-3 py-2 text-sm">
                                            <CheckCircle className="w-4 h-4 text-emerald-500 mt-0.5 shrink-0" />
                                            <div className="flex-1 min-w-0">
                                                <span className="font-semibold text-slate-900">{users.find((u) => u.id === r.user_id)?.display_name ?? r.user_id}</span>
                                                <p className="text-xs text-slate-500 mt-0.5">任务ID: {r.task_id}</p>
                                            </div>
                                        </div>
                                    ))}
                                    {batchResults.skipped.map((r) => (
                                        <div key={`s-${r.user_id}`} className="flex items-start gap-3 rounded-lg border border-amber-100 bg-amber-50/50 px-3 py-2 text-sm">
                                            <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
                                            <div className="flex-1 min-w-0">
                                                <span className="font-semibold text-slate-900">{users.find((u) => u.id === r.user_id)?.display_name ?? r.user_id}</span>
                                                {r.reason && (
                                                    <p className="text-xs text-slate-500 mt-0.5">{r.reason}</p>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                    {batchResults.failed.map((r) => (
                                        <div key={`f-${r.user_id}`} className="flex items-start gap-3 rounded-lg border border-red-100 bg-red-50/50 px-3 py-2 text-sm">
                                            <AlertTriangle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
                                            <div className="flex-1 min-w-0">
                                                <span className="font-semibold text-slate-900">{users.find((u) => u.id === r.user_id)?.display_name ?? r.user_id}</span>
                                                {r.reason && (
                                                    <p className="text-xs text-slate-500 mt-0.5">{r.reason}</p>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </>
                        )}
                    </div>
                    <DialogFooter>
                        <Button className="w-full rounded-full bg-slate-900 text-white" onClick={() => setIsResultsOpen(false)}>关闭</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Users Table */}
            <GlassCard className="overflow-hidden">
                {/* Mobile Card View */}
                <div className="md:hidden space-y-4 p-4">
                    {filteredUsers.map((user) => (
                        <MobileTableCard
                            key={user.id}
                            title={
                                <div>
                                    <div className="flex items-start gap-3">
                                        <Checkbox
                                            checked={selectedUserIds.has(user.id)}
                                            onCheckedChange={() => toggleUserSelection(user.id)}
                                            disabled={user.role !== "user"}
                                            aria-label={`选择 ${user.display_name}`}
                                        />
                                        <div>
                                            <div className="font-bold text-slate-900">{user.display_name || user.email || "未知用户"}</div>
                                            <div className="text-slate-400 text-xs">{user.email}</div>
                                        </div>
                                    </div>
                                </div>
                            }
                            icon={
                                <div className="w-10 h-10 rounded-full bg-slate-200 flex items-center justify-center text-slate-500 text-sm font-bold">
                                    {(user.display_name || user.email || "U").charAt(0).toUpperCase()}
                                </div>
                            }
                            columns={[
                                {
                                    label: "角色",
                                    value: <Badge variant="secondary" className="bg-slate-100 text-slate-600 border-slate-200 font-medium">{formatAdminUserRoleLabel(user.role, { isTeamLeader: teamLeaderUserIds.has(user.id) })}</Badge>
                                },
                                {
                                    label: "所属团队",
                                    value: user.team?.name || teamByMemberUserId.get(user.id)?.name || teamByLeaderUserId.get(user.id)?.name || "未分配"
                                },
                                {
                                    label: "状态",
                                    value: (
                                        <div className="flex items-center gap-2">
                                            <div className={`w-1.5 h-1.5 rounded-full ${user.status === 'active' ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]' : (['suspended', 'inactive'].includes(user.status) ? 'bg-red-500' : 'bg-slate-400')}`} />
                                            <span className={`font-medium ${user.status === 'active' ? 'text-emerald-600' : (['suspended', 'inactive'].includes(user.status) ? 'text-red-600' : 'text-slate-500')}`}>
                                                {formatAdminUserStatusLabel(user.status)}
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
                                        onSuspend={() => openAccountActionDialog(user, "suspend")}
                                        onActivate={() => openAccountActionDialog(user, "activate")}
                                        onResetPassword={() => openAccountActionDialog(user, "reset_password")}
                                        onViewDetail={() => router.push(`/admin/users/${user.id}`)}
                                        isLoading={actionLoading?.userId === user.id}
                                    />
                                </div>
                            }
                            className="relative"
                        >
                            <div className="flex items-center gap-2 text-xs text-slate-400 pt-2">
                                <Calendar className="w-3 h-3" /> 上次活跃: {formatAdminRelativeTime(user.last_active_at || user.last_login)}
                            </div>
                        </MobileTableCard>
                    ))}
                </div>

                {/* Desktop Table View */}
                <div className="hidden md:block overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-slate-50/50 border-b border-slate-100 text-xs uppercase font-bold text-slate-400 tracking-wider">
                            <tr>
                                <th className="px-6 py-4 w-10">
                                    <Checkbox
                                        checked={allFilteredSelected}
                                        onCheckedChange={toggleSelectAll}
                                        aria-label="全选"
                                    />
                                </th>
                                <th className="px-6 py-4">用户</th>
                                <th className="px-6 py-4">角色</th>
                                <th className="px-6 py-4">团队</th>
                                <th className="px-6 py-4">状态</th>
                                <th className="px-6 py-4">上次活跃</th>
                                <th className="px-6 py-4 text-right">操作</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {filteredUsers.map((user) => (
                                <tr key={user.id} className="hover:bg-slate-50/50 transition-colors group">
                                    <td className="px-6 py-4">
                                        <Checkbox
                                            checked={selectedUserIds.has(user.id)}
                                            onCheckedChange={() => toggleUserSelection(user.id)}
                                            disabled={user.role !== "user"}
                                            aria-label={`选择 ${user.display_name}`}
                                        />
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-3">
                                            <div className="w-9 h-9 rounded-full bg-slate-200 flex items-center justify-center text-slate-500 text-xs font-bold group-hover:bg-blue-100 group-hover:text-blue-600 transition-colors">
                                                {(user.display_name || user.email || "U").charAt(0).toUpperCase()}
                                            </div>
                                            <div>
                                                <div className="font-bold text-slate-900">{user.display_name || user.email || "未知用户"}</div>
                                                <div className="text-slate-400 text-xs">{user.email}</div>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <Badge variant="secondary" className="bg-slate-100 text-slate-600 border-slate-200 font-medium">{formatAdminUserRoleLabel(user.role, { isTeamLeader: teamLeaderUserIds.has(user.id) })}</Badge>
                                    </td>
                                    <td className="px-6 py-4 text-slate-500 font-medium">
                                        {user.team?.name || teamByMemberUserId.get(user.id)?.name || teamByLeaderUserId.get(user.id)?.name || "未分配"}
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-2">
                                            <div className={`w-1.5 h-1.5 rounded-full ${user.status === 'active' ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]' : (['suspended', 'inactive'].includes(user.status) ? 'bg-red-500' : 'bg-slate-400')}`} />
                                            <span className={`font-medium ${user.status === 'active' ? 'text-emerald-600' : (['suspended', 'inactive'].includes(user.status) ? 'text-red-600' : 'text-slate-500')}`}>
                                                {formatAdminUserStatusLabel(user.status)}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 text-slate-500 font-medium">
                                        {formatAdminRelativeTime(user.last_active_at || user.last_login)}
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <UserActionMenu
                                            user={user}
                                            onEdit={() => openEditDialog(user)}
                                            onSuspend={() => openAccountActionDialog(user, "suspend")}
                                            onActivate={() => openAccountActionDialog(user, "activate")}
                                            onResetPassword={() => openAccountActionDialog(user, "reset_password")}
                                            onViewDetail={() => router.push(`/admin/users/${user.id}`)}
                                            isLoading={actionLoading?.userId === user.id}
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
    onResetPassword,
    onViewDetail,
    isLoading
}: {
    user: AdminUser;
    onEdit: () => void;
    onSuspend: () => void;
    onActivate: () => void;
    onResetPassword: () => void;
    onViewDetail: () => void;
    isLoading: boolean;
}) {
    const [isOpen, setIsOpen] = useState(false);
    const closeThenRun = (action: () => void) => {
        setIsOpen(false);
        action();
    };

    return (
        <TooltipProvider>
            <Dialog open={isOpen} onOpenChange={setIsOpen}>
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
                        <DialogTitle>管理用户: {user.display_name}</DialogTitle>
                        <DialogDescription>{user.email}</DialogDescription>
                    </DialogHeader>
                    <div className="py-4 space-y-2">
                        <Button disabled={isLoading} onClick={() => closeThenRun(onViewDetail)} variant="ghost" className="w-full justify-start text-slate-700 hover:bg-slate-50 hover:text-blue-600">
                            <Eye className="w-4 h-4 mr-3" /> 详情 / 主管重点
                        </Button>
                        <Button disabled={isLoading} onClick={() => closeThenRun(onEdit)} variant="ghost" className="w-full justify-start text-slate-700 hover:bg-slate-50 hover:text-blue-600">
                            <Shield className="w-4 h-4 mr-3" /> 编辑权限
                        </Button>
                        <Button disabled={isLoading} onClick={() => closeThenRun(onResetPassword)} variant="ghost" className="w-full justify-start text-slate-700 hover:bg-slate-50 hover:text-blue-600">
                            <RefreshCw className="w-4 h-4 mr-3" /> 重置临时密码
                        </Button>
                        {user.status === "active" ? (
                            <Button disabled={isLoading} onClick={() => closeThenRun(onSuspend)} variant="ghost" className="w-full justify-start text-slate-700 hover:bg-slate-50 hover:text-amber-600">
                                <Ban className="w-4 h-4 mr-3" /> 停用账户
                            </Button>
                        ) : (
                            <Button disabled={isLoading} onClick={() => closeThenRun(onActivate)} variant="ghost" className="w-full justify-start text-slate-700 hover:bg-slate-50 hover:text-emerald-600">
                                <CheckCircle className="w-4 h-4 mr-3" /> 激活账户
                            </Button>
                        )}
                    </div>
                </DialogContent>
            </Dialog>
        </TooltipProvider>
    );
}
