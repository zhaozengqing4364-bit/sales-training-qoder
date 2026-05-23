"use client";
import { debug } from "@/lib/debug";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, RefreshCw, Search } from "lucide-react";
import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { PromptGovernanceContextBar } from "@/components/admin/prompts/prompt-governance-context-bar";
import { formatCategoryLabel, PROMPT_TYPE_COLORS, PROMPT_TYPE_LABELS } from "@/components/admin/prompts/prompt-labels";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { PromptTemplate, PromptTemplateGovernanceStatus, PromptType } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type ConfirmAction =
  | { type: "toggle"; template: PromptTemplate }
  | { type: "default"; template: PromptTemplate }
  | { type: "migrate" }
  | { type: "rollback"; template: PromptTemplate }
  | { type: "remediate" }
  | null;

function getRoleLabel(role: string): string {
  if (role === "admin") return "管理员";
  if (role === "support") return "运营（只读）";
  return "只读";
}

export default function AdminPromptsPage() {
  const router = useRouter();
  const toast = useToast();
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [governanceStatus, setGovernanceStatus] = useState<PromptTemplateGovernanceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadWarnings, setLoadWarnings] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<PromptType | "all">("all");
  const [showInactive, setShowInactive] = useState(false);
  const [userRole, setUserRole] = useState("user");
  const [isOperating, setIsOperating] = useState(false);
  const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null);
  const isAdmin = userRole === "admin";
  const canOperate = isAdmin;

  const loadData = async () => {
    setLoading(true);
    setLoadWarnings([]);
    try {
      const [templatesResult, userResult, governanceResult] = await Promise.allSettled([
        api.admin.getPromptTemplates({ is_active: showInactive ? undefined : true }),
        api.user.getMe(),
        api.admin.getPromptTemplateGovernanceStatus(),
      ]);
      const warnings: string[] = [];
      if (templatesResult.status === "fulfilled") setTemplates(templatesResult.value);
      else { setTemplates([]); warnings.push(`模板列表加载失败：${getApiErrorMessage(templatesResult.reason)}`); }
      if (userResult.status === "fulfilled") setUserRole(String(userResult.value.role || "user"));
      else { setUserRole("user"); warnings.push("当前用户权限加载失败"); }
      if (governanceResult.status === "fulfilled") setGovernanceStatus(governanceResult.value);
      else { setGovernanceStatus(null); warnings.push(`治理状态加载失败：${getApiErrorMessage(governanceResult.reason)}`); }
      setLoadWarnings(warnings);
    } catch (error) {
      debug.error("Failed to load prompt admin data", error);
      toast.error("提示词数据加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const t = window.setTimeout(() => { void loadData(); }, 0);
    return () => window.clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showInactive]);

  const filteredTemplates = useMemo(() => templates.filter((template) => {
    const matchesSearch = template.name.toLowerCase().includes(searchQuery.toLowerCase()) || template.category.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = typeFilter === "all" || template.prompt_type === typeFilter;
    return matchesSearch && matchesType;
  }), [searchQuery, templates, typeFilter]);

  const refreshAfterMutation = async (msg: string) => { await loadData(); toast.success(msg); };

  const handleToggleActive = async (template: PromptTemplate) => {
    if (!canOperate) return;
    setIsOperating(true);
    try {
      await api.admin.updatePromptTemplate(template.id, { is_active: !template.is_active });
      await refreshAfterMutation(template.is_active ? "模板已停用" : "模板已启用");
    } catch (error) { toast.error(getApiErrorMessage(error)); } finally { setIsOperating(false); }
  };

  const handleSetDefault = async (template: PromptTemplate) => {
    if (!canOperate) return;
    setIsOperating(true);
    try {
      await api.admin.setDefaultPromptTemplate(template.id, template.prompt_type);
      await refreshAfterMutation("已设为默认模板");
    } catch (error) { toast.error(getApiErrorMessage(error)); } finally { setIsOperating(false); }
  };

  const handleMigrate = async () => {
    if (!canOperate) return;
    setIsOperating(true);
    try {
      const result = await api.admin.migrateInvalidPromptTemplates({ reason: "Admin prompt governance migration", dry_run: false });
      await loadData();
      toast.success(`治理迁移完成：${result.data.remediated} 条`);
    } catch (error) { toast.error(getApiErrorMessage(error)); } finally { setIsOperating(false); }
  };

  const handleRollback = async (template: PromptTemplate) => {
    if (!canOperate) return;
    setIsOperating(true);
    try {
      await api.admin.rollbackPromptTemplateGovernance(template.id, { reason: "Admin prompt governance rollback" });
      await refreshAfterMutation("提示词治理变更已回滚");
    } catch (error) { toast.error(getApiErrorMessage(error)); } finally { setIsOperating(false); }
  };

  const handleRemediate = async () => {
    if (!canOperate) return;
    setIsOperating(true);
    try {
      const result = await api.admin.remediateInvalidPromptTemplates("A-009 prompt template governance remediation");
      await refreshAfterMutation(`已停用 ${result.remediated_count} 个非法历史模板`);
    } catch (error) { toast.error(getApiErrorMessage(error)); } finally { setIsOperating(false); }
  };

  const handleConfirmAction = () => {
    const action = confirmAction;
    setConfirmAction(null);
    if (!action) return;
    if (action.type === "toggle") void handleToggleActive(action.template);
    else if (action.type === "default") void handleSetDefault(action.template);
    else if (action.type === "migrate") void handleMigrate();
    else if (action.type === "rollback") void handleRollback(action.template);
    else if (action.type === "remediate") void handleRemediate();
  };

  const confirmCopy = (() => {
    if (!confirmAction) return { title: "确认操作", description: "", confirmText: "确认", variant: "warning" as const };
    if (confirmAction.type === "toggle") return { title: confirmAction.template.is_active ? "停用模板" : "启用模板", description: confirmAction.template.name, confirmText: "确认", variant: "warning" as const };
    if (confirmAction.type === "default") return { title: "设为默认", description: confirmAction.template.name, confirmText: "确认", variant: "warning" as const };
    if (confirmAction.type === "migrate") return { title: "执行治理迁移", description: "批量修复历史变量格式", confirmText: "确认迁移", variant: "danger" as const };
    if (confirmAction.type === "rollback") return { title: "回滚治理变更", description: confirmAction.template.name, confirmText: "确认回滚", variant: "warning" as const };
    return { title: "停用非法历史模板", description: "批量停用非法活跃模板", confirmText: "确认停用", variant: "danger" as const };
  })();

  return (
    <AdminIndexShell
      header={(
        <AdminPageHeader
          title="评估/报告提示词管理"
          description="列表页仅用于浏览与行操作；编辑请进入模板详情，场景绑定请使用独立入口。"
          primaryAction={isAdmin ? <Button className="rounded-full bg-slate-900 text-white" onClick={() => router.push("/admin/prompts/new")}><Plus className="mr-2 h-4 w-4" />新建模板</Button> : undefined}
          secondaryActions={(
            <>
              <Badge className="bg-slate-100 text-slate-700">当前角色：{getRoleLabel(userRole)}</Badge>
              <Button variant="outline" className="rounded-full" onClick={() => router.push("/admin/prompts/bindings")}>场景绑定</Button>
              {isAdmin ? <Button variant="outline" className="rounded-full" onClick={() => setConfirmAction({ type: "migrate" })} disabled={isOperating}>治理扫描/迁移</Button> : null}
              <Button variant="outline" className="rounded-full" onClick={() => void loadData()} disabled={loading}><RefreshCw className={cn("mr-2 h-4 w-4", loading && "animate-spin")} />刷新</Button>
            </>
          )}
        />
      )}
      contextBar={(
        <PromptGovernanceContextBar
          loadWarnings={loadWarnings}
          governanceStatus={governanceStatus}
          canOperate={canOperate}
          isOperating={isOperating}
          onRemediate={() => setConfirmAction({ type: "remediate" })}
        />
      )}
    >
      <ConfirmDialog open={!!confirmAction} onOpenChange={(open) => !open && setConfirmAction(null)} title={confirmCopy.title} description={confirmCopy.description} confirmText={confirmCopy.confirmText} variant={confirmCopy.variant} onConfirm={handleConfirmAction} isLoading={isOperating} />
      <GlassCard className="p-4">
        <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-4">
          <div className="relative md:col-span-2"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" /><Input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="搜索模板名称/分类" className="pl-9" /></div>
          <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as PromptType | "all")} className="rounded-lg border px-3 py-2 text-sm"><option value="all">全部类型</option>{Object.entries(PROMPT_TYPE_LABELS).map(([type, label]) => (<option key={type} value={type}>{label}</option>))}</select>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />显示停用模板</label>
        </div>
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-slate-200 text-left text-slate-500"><th className="py-2 pr-3">模板</th><th className="py-2 pr-3">类型</th><th className="py-2 pr-3">分类</th><th className="py-2 pr-3">状态</th><th className="py-2 pr-3">默认</th><th className="py-2">操作</th></tr></thead>
            <tbody>
              {loading ? <tr><td colSpan={6} className="py-8 text-center text-slate-500">正在加载...</td></tr> : filteredTemplates.length === 0 ? <tr><td colSpan={6} className="py-10 text-center text-slate-500">未找到模板</td></tr> : filteredTemplates.map((template) => (
                <tr key={template.id} className="border-b border-slate-100 hover:bg-slate-50/60">
                  <td className="py-3 pr-3"><button type="button" className="text-left font-semibold text-zinc-900 hover:underline" onClick={() => router.push(`/admin/prompts/${template.id}/edit`)}>{template.name}</button></td>
                  <td className="py-3 pr-3"><Badge className={PROMPT_TYPE_COLORS[template.prompt_type]}>{PROMPT_TYPE_LABELS[template.prompt_type]}</Badge></td>
                  <td className="py-3 pr-3 text-slate-600">{formatCategoryLabel(template.category)}</td>
                  <td className="py-3 pr-3"><Badge className={template.is_active ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-700"}>{template.is_active ? "启用" : "停用"}</Badge></td>
                  <td className="py-3 pr-3">{template.is_default ? <Badge className="bg-amber-100 text-amber-700">默认</Badge> : "-"}</td>
                  <td className="py-3">
                    <div className="flex flex-wrap gap-2">
                      <Button variant="outline" size="sm" disabled={!canOperate || isOperating} onClick={() => setConfirmAction({ type: "toggle", template })}>{template.is_active ? "停用" : "启用"}</Button>
                      <Button variant="outline" size="sm" disabled={!canOperate || template.is_default || isOperating} onClick={() => setConfirmAction({ type: "default", template })}>设为默认</Button>
                      {isAdmin ? <Button variant="outline" size="sm" onClick={() => router.push(`/admin/prompts/${template.id}/edit`)}>编辑</Button> : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>
    </AdminIndexShell>
  );
}
