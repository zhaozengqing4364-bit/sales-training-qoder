"use client";
import { debug } from "@/lib/debug";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, RefreshCw, Search, ShieldAlert, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { PromptTemplate, PromptTemplateGovernanceStatus, PromptType, ScenarioPrompt } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const PROMPT_TYPE_LABELS: Record<PromptType, string> = {
  summary: "总结",
  system: "系统",
  system_prompt: "系统提示词",
  extraction: "信息提取",
  scoring: "评分",
  realtime_scoring: "实时评分",
  stage: "阶段",
  realtime_scoring: "实时评分",
  fuzzy_detection: "模糊检测",
  realtime_scoring: "实时评分",
  interruption: "打断检测",
  tracking: "跟踪",
  welcome: "欢迎词",
  evaluation: "实时评价",
  report: "综合报告",
  realtime_scoring: "实时评分",
};

const PROMPT_TYPE_COLORS: Record<PromptType, string> = {
  summary: "bg-blue-100 text-blue-700",
  system: "bg-slate-200 text-slate-700",
  system_prompt: "bg-slate-200 text-slate-700",
  extraction: "bg-green-100 text-green-700",
  scoring: "bg-amber-100 text-amber-700",
  realtime_scoring: "bg-violet-100 text-violet-700",
  stage: "bg-orange-100 text-orange-700",
  realtime_scoring: "bg-lime-100 text-lime-700",
  fuzzy_detection: "bg-rose-100 text-rose-700",
  realtime_scoring: "bg-violet-100 text-violet-700",
  interruption: "bg-pink-100 text-pink-700",
  tracking: "bg-cyan-100 text-cyan-700",
  welcome: "bg-indigo-100 text-indigo-700",
  evaluation: "bg-teal-100 text-teal-700",
  report: "bg-zinc-200 text-zinc-700",
  realtime_scoring: "bg-violet-100 text-violet-700",
};
const SALES_ALLOWED_PROMPT_TYPES: PromptType[] = ["evaluation", "report", "stage", "scoring", "realtime_scoring"];

function getRoleLabel(role: string): string {
  if (role === "admin") {
    return "管理员";
  }
  if (role === "support") {
    return "运营（只读）";
  }
  return "只读";
}

function formatGovernanceIssue(issue: string): string {
  switch (issue) {
    case "variables_object_migratable":
      return "历史变量对象已标记待迁移";
    case "variables_string_not_json_array":
    case "variables_json_not_array":
    case "variables_not_array":
      return "变量字段不是字符串数组";
    case "prompt_type_not_allowed":
      return "提示词类型不在允许列表";
    default:
      return issue;
  }
}

export default function AdminPromptsPage() {
  const router = useRouter();
  const toast = useToast();

  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [scenarioPrompts, setScenarioPrompts] = useState<ScenarioPrompt[]>([]);
  const [governanceStatus, setGovernanceStatus] = useState<PromptTemplateGovernanceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<PromptType | "all">("all");
  const [showInactive, setShowInactive] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);

  const [userRole, setUserRole] = useState("user");
  const [isOperating, setIsOperating] = useState(false);

  const [bindingTemplateId, setBindingTemplateId] = useState("");
  const [bindingScenarioType, setBindingScenarioType] = useState<"sales" | "presentation">("presentation");
  const [bindingPromptType, setBindingPromptType] = useState<PromptType>("interruption");
  const [bindingScenarioId, setBindingScenarioId] = useState("");

  const isAdmin = userRole === "admin";
  const canOperate = isAdmin;

  const loadData = async () => {
    setLoading(true);
    try {
      const [templatesResult, scenarioPromptsResult, userResult, governanceResult] = await Promise.allSettled([
        api.admin.getPromptTemplates({ is_active: showInactive ? undefined : true }),
        api.admin.getScenarioPrompts(),
        api.admin.getPromptTemplateGovernanceStatus(),
        api.user.getMe(),
        api.admin.getPromptTemplateGovernanceStatus(),
      ]);

      if (templatesResult.status === "fulfilled") {
        setTemplates(templatesResult.value);
      } else {
        setTemplates([]);
      }

      if (scenarioPromptsResult.status === "fulfilled") {
        setScenarioPrompts(scenarioPromptsResult.value);
      } else {
        setScenarioPrompts([]);
      }

      if (governanceResult.status === "fulfilled") {
        setGovernanceStatus(governanceResult.value);
      } else {
        setGovernanceStatus(null);
      }

      if (userResult.status === "fulfilled") {
        setUserRole(String(userResult.value.role || "user"));
      } else {
        setUserRole("user");
      }

      if (governanceResult.status === "fulfilled") {
        setGovernanceStatus(governanceResult.value);
      } else {
        setGovernanceStatus(null);
      }
    } catch (error) {
      debug.error("Failed to load prompt admin data", error);
      toast.error("提示词数据加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showInactive]);

  const filteredTemplates = useMemo(() => {
    return templates.filter((template) => {
      const matchesSearch =
        template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        template.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
        template.template.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesType = typeFilter === "all" || template.prompt_type === typeFilter;
      return matchesSearch && matchesType;
    });
  }, [searchQuery, templates, typeFilter]);

  const templateMap = useMemo(() => {
    return new Map(templates.map((item) => [item.id, item]));
  }, [templates]);

  const selectedTemplate = useMemo(() => {
    if (!selectedTemplateId) {
      return null;
    }
    return templateMap.get(selectedTemplateId) || null;
  }, [selectedTemplateId, templateMap]);

  const selectedTemplateBindings = useMemo(() => {
    if (!selectedTemplateId) {
      return scenarioPrompts;
    }
    return scenarioPrompts.filter((item) => item.template_id === selectedTemplateId);
  }, [scenarioPrompts, selectedTemplateId]);

  const refreshAfterMutation = async (successMessage: string) => {
    await loadData();
    toast.success(successMessage);
  };

  const handleToggleActive = async (template: PromptTemplate) => {
    if (!canOperate) {
      toast.error("当前角色无操作权限");
      return;
    }

    setIsOperating(true);
    try {
      await api.admin.updatePromptTemplate(template.id, {
        is_active: !template.is_active,
      });
      await refreshAfterMutation(template.is_active ? "模板已停用" : "模板已启用");
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    } finally {
      setIsOperating(false);
    }
  };

  const handleSetDefault = async (template: PromptTemplate) => {
    if (!canOperate) {
      toast.error("当前角色无操作权限");
      return;
    }

    setIsOperating(true);
    try {
      await api.admin.setDefaultPromptTemplate(template.id, template.prompt_type);
      await refreshAfterMutation("已设为默认模板");
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    } finally {
      setIsOperating(false);
    }
  };


  const handleMigrateInvalidTemplates = async () => {
    if (!canOperate) {
      toast.error("当前角色无操作权限");
      return;
    }

    setIsOperating(true);
    try {
      const result = await api.admin.migrateInvalidPromptTemplates({
        reason: "Admin prompt governance migration",
        dry_run: false,
      });
      await loadData();
      toast.success(`治理迁移完成：${result.data.remediated} 条`);
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    } finally {
      setIsOperating(false);
    }
  };

  const handleRollbackGovernance = async (template: PromptTemplate) => {
    if (!canOperate) {
      toast.error("当前角色无操作权限");
      return;
    }

    setIsOperating(true);
    try {
      await api.admin.rollbackPromptTemplateGovernance(template.id, {
        reason: "Admin prompt governance rollback",
      });
      await refreshAfterMutation("提示词治理变更已回滚");
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    } finally {
      setIsOperating(false);
    }
  };

  const handleCreateScenarioBinding = async () => {
    if (!canOperate) {
      toast.error("当前角色无操作权限");
      return;
    }

    if (!bindingTemplateId) {
      toast.error("请先选择模板");
      return;
    }

    setIsOperating(true);
    try {
      await api.admin.createScenarioPrompt({
        scenario_type: bindingScenarioType,
        scenario_id: bindingScenarioId.trim() || undefined,
        prompt_type: bindingPromptType,
        template_id: bindingTemplateId,
        is_active: true,
      });
      setBindingScenarioId("");
      await refreshAfterMutation("场景绑定已创建");
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    } finally {
      setIsOperating(false);
    }
  };

  const handleDeleteScenarioBinding = async (assignmentId: string) => {
    if (!canOperate) {
      toast.error("当前角色无操作权限");
      return;
    }

    setIsOperating(true);
    try {
      await api.admin.deleteScenarioPrompt(assignmentId);
      await refreshAfterMutation("场景绑定已删除");
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    } finally {
      setIsOperating(false);
    }
  };

  const handleRemediateInvalidTemplates = async () => {
    if (!canOperate) {
      toast.error("当前角色无操作权限");
      return;
    }

    setIsOperating(true);
    try {
      const result = await api.admin.remediateInvalidPromptTemplates("A-009 prompt template governance remediation");
      await refreshAfterMutation(`已停用 ${result.remediated_count} 个非法历史模板`);
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    } finally {
      setIsOperating(false);
    }
  };

  useEffect(() => {
    if (!selectedTemplate) {
      return;
    }

    setBindingTemplateId(selectedTemplate.id);
    setBindingPromptType(selectedTemplate.prompt_type);
    setBindingScenarioType(selectedTemplate.category === "sales" ? "sales" : "presentation");
  }, [selectedTemplate]);

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h1 className="text-3xl font-black text-slate-900 tracking-tight">评估/报告提示词管理</h1>
          <p className="text-slate-500 mt-1">销售实时角色提示词已迁移到角色中心；本页仅用于评估与报告模板治理。</p>
        </div>
        <div className="flex gap-2 items-center">
          <Badge className="bg-slate-100 text-slate-700">当前角色：{getRoleLabel(userRole)}</Badge>
          <Button variant="outline" className="rounded-full" onClick={() => void loadData()} disabled={loading}>
            <RefreshCw className={cn("w-4 h-4 mr-2", loading && "animate-spin")} />
            刷新
          </Button>
          {isAdmin ? (
            <>
              <Button
                variant="outline"
                className="rounded-full"
                onClick={() => void handleMigrateInvalidTemplates()}
                disabled={isOperating}
              >
                治理扫描/迁移
              </Button>
              <Button
                className="rounded-full bg-slate-900 text-white"
                onClick={() => router.push("/admin/prompts/new")}
              >
                <Plus className="w-4 h-4 mr-2" />
                新建模板
              </Button>
            </>
          ) : null}
        </div>
      </div>

      <GlassCard className="p-4 space-y-4">
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
          销售场景仅允许绑定评估/报告/实时评分类模板。业务角色提示词与知识库策略请在角色中心配置。
        </div>
        <div className={cn(
          "rounded-xl border px-3 py-3 text-xs",
          governanceStatus?.invalid_count
            ? "border-red-200 bg-red-50 text-red-700"
            : "border-emerald-200 bg-emerald-50 text-emerald-700"
        )}>
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="font-semibold">提示词治理状态</div>
              <div className="mt-1">
                {governanceStatus
                  ? `允许类型 ${governanceStatus.allowed_prompt_types.join(" / ")}；非法历史模板 ${governanceStatus.invalid_count} 个；变量 schema：${governanceStatus.policy.variables_schema}`
                  : "治理状态暂不可用，请刷新或查看后端日志。"}
              </div>
            </div>
            {governanceStatus?.invalid_count ? (
              <Button
                variant="outline"
                size="sm"
                disabled={!canOperate || isOperating}
                onClick={() => void handleRemediateInvalidTemplates()}
              >
                停用非法历史模板
              </Button>
            ) : null}
          </div>
        </div>
        {governanceAudit ? (
          <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs text-slate-700">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
              <div>
                <span className="font-semibold">历史模板治理：</span>
                共 {governanceAudit.total} 条，待处理 {governanceAudit.invalid_count} 条。
                {governanceAudit.invalid_count > 0 ? (
                  <span className="ml-1 text-amber-700">
                    管理员可迁移 variables 字典并禁用无法信任的历史模板，审计日志可回滚。
                  </span>
                ) : (
                  <span className="ml-1 text-emerald-700">当前无非法历史模板。</span>
                )}
              </div>
              <Button
                variant="outline"
                size="sm"
                disabled={!canOperate || isOperating || governanceAudit.invalid_count === 0}
                onClick={() => void handleRemediateGovernance()}
              >
                治理历史模板
              </Button>
            </div>
            {governanceAudit.items.length ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {governanceAudit.items.slice(0, 4).map((item) => (
                  <Badge key={item.template_id} className="bg-amber-100 text-amber-800">
                    {item.name || item.template_id.slice(0, 8)}：{item.issues.join(" / ")}
                  </Badge>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="md:col-span-2 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
            <Input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="搜索模板名称/分类/内容"
              className="pl-9"
            />
          </div>
          <select
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value as PromptType | "all")}
            className="rounded-lg border border-zinc-200 bg-stone-50 px-3 py-2 text-sm"
          >
            <option value="all">全部类型</option>
            {Object.entries(PROMPT_TYPE_LABELS).map(([type, label]) => (
              <option key={type} value={type}>
                {label}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-sm text-zinc-600">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(event) => setShowInactive(event.target.checked)}
            />
            显示停用模板
          </label>
        </div>
      </GlassCard>

      {governanceStatus && governanceStatus.invalid_count > 0 ? (
        <GlassCard className="border border-red-200 bg-red-50 p-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-2 font-bold text-red-800">
                <ShieldAlert className="h-4 w-4" />
                提示词治理发现 {governanceStatus.invalid_count} 条非法历史模板
              </div>
              <p className="text-sm text-red-700">
                {governanceStatus.invalid_active_count} 条仍处于启用/默认状态；运行时会跳过非法模板并记录状态，请先禁用后修正。
              </p>
              <p className="text-xs text-red-700 text-pretty">
                回滚：修正 prompt_type/variables 后重新启用或设为默认；所有操作写入 {governanceStatus.audit_log_action} 审计。
              </p>
              <div className="flex flex-wrap gap-2">
                {governanceStatus.issues.slice(0, 4).map((issue) => (
                  <Badge key={issue.template_id} className="bg-white text-red-700 border border-red-200">
                    {issue.name || issue.template_id.slice(0, 8)} · {issue.issue_codes.join("/")}
                  </Badge>
                ))}
              </div>
            </div>
            <Button
              variant="outline"
              className="border-red-200 bg-white text-red-700"
              disabled={!canOperate || isOperating || governanceStatus.invalid_active_count === 0}
              onClick={() => void handleQuarantineInvalidTemplates()}
            >
              禁用非法历史模板
            </Button>
          </div>
        </GlassCard>
      ) : null}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <GlassCard className="p-4 xl:col-span-2">
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500 border-b border-slate-200">
                  <th className="py-2 pr-3">模板</th>
                  <th className="py-2 pr-3">类型</th>
                  <th className="py-2 pr-3">业务分类</th>
                  <th className="py-2 pr-3">状态</th>
                  <th className="py-2 pr-3">默认</th>
                  <th className="py-2">操作</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-500">
                      正在加载模板...
                    </td>
                  </tr>
                ) : filteredTemplates.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-10 text-center text-slate-500">
                      未找到符合条件的模板
                    </td>
                  </tr>
                ) : (
                  filteredTemplates.map((template) => {
                    const isSelected = selectedTemplateId === template.id;
                    return (
                      <tr
                        key={template.id}
                        className={cn(
                          "border-b border-slate-100 hover:bg-slate-50/60",
                          isSelected && "bg-slate-100/70"
                        )}
                      >
                        <td className="py-3 pr-3">
                          <button
                            type="button"
                            className="text-left"
                            onClick={() => setSelectedTemplateId(template.id)}
                          >
                            <div className="font-semibold text-zinc-900">{template.name}</div>
                            <div className="text-xs text-slate-500">ID: {template.id.slice(0, 8)}...</div>
                          </button>
                        </td>
                        <td className="py-3 pr-3">
                          <Badge className={PROMPT_TYPE_COLORS[template.prompt_type]}>
                            {PROMPT_TYPE_LABELS[template.prompt_type]}
                          </Badge>
                        </td>
                        <td className="py-3 pr-3 text-slate-600">{template.category}</td>
                        <td className="py-3 pr-3">
                          <div className="flex flex-col gap-1">
                            <Badge className={template.is_active ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-700"}>
                              {template.is_active ? "启用" : "停用"}
                            </Badge>
                            {template.governance_status === "needs_review" ? (
                              <Badge className="bg-red-100 text-red-700">需治理</Badge>
                            ) : null}
                          </div>
                        </td>
                        <td className="py-3 pr-3">
                          {template.is_default ? <Badge className="bg-amber-100 text-amber-700">默认</Badge> : "-"}
                        </td>
                        <td className="py-3">
                          <div className="flex flex-wrap gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={!canOperate || isOperating}
                              onClick={() => void handleToggleActive(template)}
                            >
                              {template.is_active ? "停用" : "启用"}
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={!canOperate || template.is_default || isOperating}
                              onClick={() => void handleSetDefault(template)}
                            >
                              设为默认
                            </Button>
                            {isAdmin ? (
                              <>
                                {template.governance_status === "needs_review" ? (
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    disabled={isOperating}
                                    onClick={() => void handleMigrateInvalidTemplates()}
                                  >
                                    迁移
                                  </Button>
                                ) : null}
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => router.push(`/admin/prompts/${template.id}/edit`)}
                                >
                                  编辑
                                </Button>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  disabled={isOperating}
                                  onClick={() => void handleRollbackGovernance(template)}
                                >
                                  回滚治理
                                </Button>
                              </>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </GlassCard>

        <GlassCard className="p-4 space-y-4">
          <h3 className="text-lg font-bold text-slate-900">模板详情</h3>
          {!selectedTemplate ? (
            <div className="text-sm text-slate-500">点击左侧模板查看详情与场景绑定。</div>
          ) : (
            <div className="space-y-3">
              <div>
                <div className="text-sm font-semibold text-zinc-900">{selectedTemplate.name}</div>
                <div className="text-xs text-slate-500 mt-1">类型：{PROMPT_TYPE_LABELS[selectedTemplate.prompt_type]} · 分类：{selectedTemplate.category}</div>
              </div>

              <div className="text-xs text-slate-500">变量：{selectedTemplate.variables.length ? selectedTemplate.variables.join("、") : "无"}</div>

              {selectedTemplate.governance_status === "needs_review" ? (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                  <div className="font-semibold">治理状态：需要处理后才能作为可信运行时模板。</div>
                  <ul className="mt-1 list-disc pl-4">
                    {(selectedTemplate.governance_issues || []).map((issue) => (
                      <li key={issue}>{formatGovernanceIssue(issue)}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <details className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <summary className="cursor-pointer text-sm font-semibold text-slate-800">开发者模式：查看模板正文</summary>
                <pre className="mt-3 whitespace-pre-wrap text-xs text-slate-700 leading-relaxed max-h-60 overflow-auto">
                  {selectedTemplate.template}
                </pre>
              </details>
            </div>
          )}
        </GlassCard>
      </div>

      <GlassCard className="p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold text-slate-900">场景绑定</h3>
            <p className="text-sm text-slate-500">将模板绑定到销售/演讲场景，避免运行时使用错误模板。</p>
          </div>
          <Badge className="bg-slate-100 text-slate-700">当前 {selectedTemplateBindings.length} 条</Badge>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <select
            value={bindingTemplateId}
            onChange={(event) => {
              const nextId = event.target.value;
              setBindingTemplateId(nextId);
              const selected = templateMap.get(nextId);
              if (selected) {
                setBindingPromptType(selected.prompt_type);
              }
            }}
            className="rounded-lg border border-zinc-200 bg-stone-50 px-3 py-2 text-sm"
          >
            <option value="">选择模板</option>
            {templates.filter((item) => item.is_active).map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>

          <select
            value={bindingScenarioType}
            onChange={(event) => setBindingScenarioType(event.target.value as "sales" | "presentation")}
            className="rounded-lg border border-zinc-200 bg-stone-50 px-3 py-2 text-sm"
          >
            <option value="sales">销售场景</option>
            <option value="presentation">演讲场景</option>
          </select>

          <select
            value={bindingPromptType}
            onChange={(event) => setBindingPromptType(event.target.value as PromptType)}
            className="rounded-lg border border-zinc-200 bg-stone-50 px-3 py-2 text-sm"
          >
            {Object.entries(PROMPT_TYPE_LABELS)
              .filter(([type]) => {
                if (bindingScenarioType !== "sales") {
                  return true;
                }
                return SALES_ALLOWED_PROMPT_TYPES.includes(type as PromptType);
              })
              .map(([type, label]) => (
              <option key={type} value={type}>
                {label}
              </option>
            ))}
          </select>

          <Input
            value={bindingScenarioId}
            onChange={(event) => setBindingScenarioId(event.target.value)}
            placeholder="可选：具体 scenario_id"
          />

          <Button
            className="rounded-lg bg-slate-900 text-white"
            disabled={!canOperate || isOperating}
            onClick={() => void handleCreateScenarioBinding()}
          >
            新建绑定
          </Button>
        </div>

        <div className="space-y-2">
          {selectedTemplateBindings.length === 0 ? (
            <div className="text-sm text-slate-500 py-4">暂无绑定记录</div>
          ) : (
            selectedTemplateBindings.map((item) => {
              const linkedTemplate = templateMap.get(item.template_id);
              return (
                <div key={item.id} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                  <div className="text-sm text-slate-700">
                    <span className="font-semibold text-zinc-900">{linkedTemplate?.name || item.template_id}</span>
                    <span className="mx-2 text-slate-400">·</span>
                    <span>{item.scenario_type === "sales" ? "销售" : "演讲"}</span>
                    <span className="mx-2 text-slate-400">·</span>
                    <span>{PROMPT_TYPE_LABELS[item.prompt_type as PromptType] || item.prompt_type}</span>
                    <span className="mx-2 text-slate-400">·</span>
                    <span>{item.scenario_id || "全场景"}</span>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!canOperate || isOperating}
                    onClick={() => void handleDeleteScenarioBinding(item.id)}
                  >
                    删除绑定
                  </Button>
                </div>
              );
            })
          )}
        </div>
      </GlassCard>

      {!loading && filteredTemplates.length === 0 ? (
        <GlassCard className="p-12 text-center">
          <Sparkles className="w-10 h-10 mx-auto mb-3 text-zinc-300" />
          <p className="text-zinc-500">当前条件下没有可显示的模板。</p>
        </GlassCard>
      ) : null}
    </div>
  );
}
