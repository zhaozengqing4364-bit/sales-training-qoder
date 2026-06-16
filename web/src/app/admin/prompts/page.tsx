"use client";

import { debug } from "@/lib/debug";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Copy, Eye, Plus, RefreshCw, Search, ShieldCheck, Wrench } from "lucide-react";
import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { PromptGovernanceContextBar } from "@/components/admin/prompts/prompt-governance-context-bar";
import {
  formatBusinessPurpose,
  formatCategoryLabel,
  formatGovernanceIssue,
  formatPromptType,
  formatTemplateName,
  PROMPT_BUSINESS_PURPOSE,
  PROMPT_TYPE_COLORS,
  PROMPT_TYPE_LABELS,
} from "@/components/admin/prompts/prompt-labels";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
  PromptTemplate,
  PromptTemplateGovernanceStatus,
  PromptTemplateImpactResponse,
  PromptTemplateRepairDefaultsResponse,
  PromptType,
  ScenarioPrompt,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

type ConfirmAction =
  | { type: "toggle"; template: PromptTemplate }
  | { type: "default"; template: PromptTemplate }
  | { type: "executeRepair" }
  | null;

function getRoleLabel(role: string): string {
  if (role === "admin") return "管理员";
  if (role === "support") return "运营（只读）";
  return "只读";
}

function templateTitle(template: PromptTemplate): string {
  return formatTemplateName(template.name, template.display_name);
}

function templateType(template: PromptTemplate): string {
  return formatPromptType(template.prompt_type, template.display_type);
}

function templateCategory(template: PromptTemplate): string {
  return template.display_category || formatCategoryLabel(template.category);
}

const AI_COACH_PROMPT_CATEGORY = "sales_trainer_ai_coach";
const BUSINESS_ETIQUETTE_PROMPT_CATEGORY = "business_etiquette";
const QUESTION_TEMPLATE_KEYWORDS = ["题目生成", "题目草稿", "试题生成", "question"] as const;
const QUESTION_TEMPLATE_EXCLUDE_KEYWORDS = ["对话教练", "互动卡片", "chatbot"] as const;
const AI_COACH_CONVERSATION_KEYWORDS = ["对话教练", "互动卡片", "chatbot", "教练回复"] as const;
const QUESTION_PROMPT_TEMPLATE_NAME = "商务礼仪题目草稿生成 v1";
const AI_COACH_SYSTEM_PROMPT_TEMPLATE_NAME = "新人训练路径商务技巧 AI 对话教练生成 v1";

const CATEGORY_FILTER_OPTIONS = [
  { value: "all", label: "全部分类" },
  { value: AI_COACH_PROMPT_CATEGORY, label: "新人训练 AI 教练" },
  { value: BUSINESS_ETIQUETTE_PROMPT_CATEGORY, label: "商务礼仪" },
  { value: "sales", label: "销售训练" },
  { value: "sales_bot", label: "销售实时对练" },
  { value: "presentation", label: "PPT 演练" },
  { value: "system", label: "系统报告" },
  { value: "common", label: "通用" },
] as const;

const MATRIX_GROUPS: Array<{ key: string; title: string; categories: string[] }> = [
  { key: "sales", title: "销售训练", categories: ["sales", "sales_bot"] },
  { key: "presentation", title: "PPT 演练", categories: ["presentation"] },
  { key: "coach", title: "AI 教练", categories: [AI_COACH_PROMPT_CATEGORY] },
  { key: "system", title: "系统报告", categories: ["system", "common"] },
];

const AI_COACH_PROMPT_SLOTS = [
  {
    key: "coach_conversation",
    title: "AI 教练对话系统提示词",
    description: "控制新人训练路径商务技巧 AI 教练如何生成对话、卡片和下一步动作。",
    createName: AI_COACH_SYSTEM_PROMPT_TEMPLATE_NAME,
    businessPurpose: PROMPT_BUSINESS_PURPOSE.AI_COACH_CONVERSATION,
    listKeyword: "对话教练",
    managementCopy: "绑定入口：新人训练路径 → AI 教练配置",
    managementHref: "/admin/sales-trainer/ai-coach",
    match: isAiCoachConversationTemplate,
  },
  {
    key: "question_generation",
    title: "商务礼仪题目生成提示词",
    description: "控制学习内容详情页如何按章节生成单选、多选、简答题草稿。",
    createName: QUESTION_PROMPT_TEMPLATE_NAME,
    businessPurpose: PROMPT_BUSINESS_PURPOSE.BUSINESS_ETIQUETTE_QUESTION,
    listKeyword: "题目生成",
    managementCopy: "使用入口：学习内容详情页 → 商务礼仪 AI 出题",
    managementHref: "/admin/learning-contents",
    match: isBusinessEtiquetteQuestionTemplate,
  },
] as const;

function normalizedTemplateText(template: PromptTemplate): string {
  return [
    template.name,
    template.display_name,
    template.category,
    template.display_category,
    template.prompt_type,
    template.display_type,
    template.business_purpose,
    template.display_business_purpose,
    template.template,
  ].filter(Boolean).join(" ").toLowerCase();
}

function textHasAny(text: string, keywords: readonly string[]): boolean {
  return keywords.some((keyword) => text.includes(keyword.toLowerCase()));
}

function isBusinessEtiquetteQuestionTemplate(template: PromptTemplate): boolean {
  if (template.business_purpose) {
    return template.business_purpose === PROMPT_BUSINESS_PURPOSE.BUSINESS_ETIQUETTE_QUESTION;
  }
  const text = normalizedTemplateText(template);
  return (
    [AI_COACH_PROMPT_CATEGORY, BUSINESS_ETIQUETTE_PROMPT_CATEGORY, "sales_trainer"].includes(template.category)
    && textHasAny(text, QUESTION_TEMPLATE_KEYWORDS)
    && !textHasAny(text, QUESTION_TEMPLATE_EXCLUDE_KEYWORDS)
  );
}

function isAiCoachConversationTemplate(template: PromptTemplate): boolean {
  if (template.business_purpose) {
    return template.business_purpose === PROMPT_BUSINESS_PURPOSE.AI_COACH_CONVERSATION;
  }
  const text = normalizedTemplateText(template);
  return (
    template.category === AI_COACH_PROMPT_CATEGORY
    && textHasAny(text, AI_COACH_CONVERSATION_KEYWORDS)
    && !isBusinessEtiquetteQuestionTemplate(template)
  );
}

function promptTemplateCreateHref(name: string, businessPurpose: string): string {
  const category = (
    businessPurpose === PROMPT_BUSINESS_PURPOSE.BUSINESS_ETIQUETTE_QUESTION
      ? BUSINESS_ETIQUETTE_PROMPT_CATEGORY
      : AI_COACH_PROMPT_CATEGORY
  );
  const promptType = (
    businessPurpose === PROMPT_BUSINESS_PURPOSE.BUSINESS_ETIQUETTE_QUESTION
      ? "scoring"
      : "stage"
  );
  return (
    `/admin/prompts/new?category=${category}`
    + `&prompt_type=${promptType}&business_purpose=${businessPurpose}&name=${encodeURIComponent(name)}`
  );
}

export default function AdminPromptsPage() {
  const router = useRouter();
  const toast = useToast();
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [scenarioPrompts, setScenarioPrompts] = useState<ScenarioPrompt[]>([]);
  const [governanceStatus, setGovernanceStatus] = useState<PromptTemplateGovernanceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadWarnings, setLoadWarnings] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<PromptType | "all">("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [showInactive, setShowInactive] = useState(false);
  const [userRole, setUserRole] = useState("user");
  const [isOperating, setIsOperating] = useState(false);
  const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null);
  const [impact, setImpact] = useState<PromptTemplateImpactResponse | null>(null);
  const [repairPreview, setRepairPreview] = useState<PromptTemplateRepairDefaultsResponse | null>(null);
  const isAdmin = userRole === "admin";
  const canOperate = isAdmin;

  const loadData = async () => {
    setLoading(true);
    setLoadWarnings([]);
    try {
      const [templatesResult, scenarioPromptsResult, userResult, governanceResult] = await Promise.allSettled([
        api.admin.getPromptTemplates({ is_active: showInactive ? undefined : true }),
        api.admin.getScenarioPrompts(),
        api.user.getMe(),
        api.admin.getPromptTemplateGovernanceStatus(),
      ]);
      const warnings: string[] = [];
      if (templatesResult.status === "fulfilled") setTemplates(templatesResult.value);
      else { setTemplates([]); warnings.push(`模板列表加载失败：${getApiErrorMessage(templatesResult.reason)}`); }
      if (scenarioPromptsResult.status === "fulfilled") setScenarioPrompts(scenarioPromptsResult.value);
      else { setScenarioPrompts([]); warnings.push(`场景绑定加载失败：${getApiErrorMessage(scenarioPromptsResult.reason)}`); }
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
    const timer = window.setTimeout(() => { void loadData(); }, 0);
    return () => window.clearTimeout(timer);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showInactive]);

  const filteredTemplates = useMemo(() => templates.filter((template) => {
    const haystack = [
      templateTitle(template),
      template.name,
      templateType(template),
      templateCategory(template),
      formatBusinessPurpose(template.business_purpose, template.display_business_purpose),
      template.business_purpose || "",
    ].join(" ").toLowerCase();
    const matchesSearch = haystack.includes(searchQuery.toLowerCase());
    const matchesType = typeFilter === "all" || template.prompt_type === typeFilter;
    const matchesCategory = categoryFilter === "all" || template.category === categoryFilter;
    return matchesSearch && matchesType && matchesCategory;
  }), [categoryFilter, searchQuery, templates, typeFilter]);

  const aiCoachSlots = useMemo(() => AI_COACH_PROMPT_SLOTS.map((slot) => ({
    ...slot,
    templates: templates.filter((template) => template.is_active && slot.match(template)),
  })), [templates]);

  const healthCards = useMemo(() => {
    const defaultConflictCount = governanceStatus?.default_conflict_count || 0;
    const invalidCount = governanceStatus?.invalid_count || 0;
    const bindingCount = scenarioPrompts.filter((item) => item.is_active).length;
    const runtimeCount = templates.filter((item) => item.is_runtime_effective).length;
    return [
      { label: "治理健康", value: defaultConflictCount + invalidCount === 0 ? "正常" : "需处理", tone: defaultConflictCount + invalidCount === 0 ? "good" : "bad" },
      { label: "默认冲突", value: `${defaultConflictCount} 个`, tone: defaultConflictCount ? "bad" : "good" },
      { label: "非法变量", value: `${invalidCount} 个`, tone: invalidCount ? "bad" : "good" },
      { label: "场景绑定", value: `${bindingCount} 条`, tone: bindingCount ? "good" : "muted" },
      { label: "运行时生效", value: `${runtimeCount} 个`, tone: runtimeCount ? "good" : "muted" },
    ];
  }, [governanceStatus, scenarioPrompts, templates]);

  const refreshAfterMutation = async (message: string) => {
    await loadData();
    toast.success(message);
  };

  const handleToggleActive = async (template: PromptTemplate) => {
    if (!canOperate) return;
    setIsOperating(true);
    try {
      if (template.is_active) await api.admin.deletePromptTemplate(template.id);
      else await api.admin.updatePromptTemplate(template.id, { is_active: true });
      await refreshAfterMutation(template.is_active ? "模板已停用" : "模板已启用");
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    } finally {
      setIsOperating(false);
    }
  };

  const handleSetDefault = async (template: PromptTemplate) => {
    if (!canOperate) return;
    setIsOperating(true);
    try {
      await api.admin.setDefaultPromptTemplate(template.id, template.prompt_type);
      await refreshAfterMutation("已设为该用途默认模板");
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    } finally {
      setIsOperating(false);
    }
  };

  const handlePreviewRepair = async () => {
    if (!canOperate) return;
    setIsOperating(true);
    try {
      const result = await api.admin.repairPromptTemplateDefaults({
        reason: "运营后台预览提示词治理修复",
        dry_run: true,
      });
      setRepairPreview(result);
      toast.success(`已生成修复预览：${result.repaired} 项`);
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    } finally {
      setIsOperating(false);
    }
  };

  const handleExecuteRepair = async () => {
    if (!canOperate) return;
    setIsOperating(true);
    try {
      const result = await api.admin.repairPromptTemplateDefaults({
        reason: "运营后台执行提示词治理修复",
        dry_run: false,
      });
      setRepairPreview(null);
      await loadData();
      toast.success(`治理修复完成：${result.repaired} 项`);
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    } finally {
      setIsOperating(false);
    }
  };

  const handleClone = async (template: PromptTemplate) => {
    if (!canOperate) return;
    setIsOperating(true);
    try {
      const cloned = await api.admin.clonePromptTemplate(template.id, {
        reason: "运营复制系统模板后编辑",
      });
      toast.success("已复制为自定义模板");
      router.push(`/admin/prompts/${cloned.id}/edit`);
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    } finally {
      setIsOperating(false);
    }
  };

  const handleShowImpact = async (template: PromptTemplate) => {
    try {
      setImpact(await api.admin.getPromptTemplateImpact(template.id));
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    }
  };

  const handleConfirmAction = () => {
    const action = confirmAction;
    setConfirmAction(null);
    if (!action) return;
    if (action.type === "toggle") void handleToggleActive(action.template);
    if (action.type === "default") void handleSetDefault(action.template);
    if (action.type === "executeRepair") void handleExecuteRepair();
  };

  const confirmCopy = (() => {
    if (!confirmAction) return { title: "确认操作", description: "", confirmText: "确认", variant: "warning" as const };
    if (confirmAction.type === "toggle") {
      const title = confirmAction.template.is_active ? "停用模板" : "启用模板";
      const description = `${templateTitle(confirmAction.template)}。停用前系统会检查默认与场景绑定影响。`;
      return { title, description, confirmText: "确认", variant: "warning" as const };
    }
    if (confirmAction.type === "default") {
      return { title: "设为该用途默认", description: templateTitle(confirmAction.template), confirmText: "设为默认", variant: "warning" as const };
    }
    return { title: "执行治理修复", description: "将修复默认冲突、非法变量对象和系统模板中文名，并记录审计。", confirmText: "执行修复", variant: "danger" as const };
  })();

  return (
    <AdminIndexShell
      header={(
        <AdminPageHeader
          title="提示词治理台"
          description="管理提示词模板、默认兜底和场景绑定；系统模板只读，运营需复制为自定义模板后再调整。"
          primaryAction={isAdmin ? (
            <Button className="rounded-full bg-slate-900 text-white" onClick={() => router.push("/admin/prompts/new")}>
              <Plus className="mr-2 h-4 w-4" />新建自定义模板
            </Button>
          ) : undefined}
          secondaryActions={(
            <>
              <Badge className="bg-slate-100 text-slate-700">当前角色：{getRoleLabel(userRole)}</Badge>
              <Button variant="outline" className="rounded-full" onClick={() => router.push("/admin/prompts/bindings")}>配置生效场景</Button>
              <Button variant="outline" className="rounded-full" onClick={() => void loadData()} disabled={loading}>
                <RefreshCw className={cn("mr-2 h-4 w-4", loading && "animate-spin")} />刷新
              </Button>
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
          onRemediate={() => void handlePreviewRepair()}
        />
      )}
    >
      <ConfirmDialog
        open={!!confirmAction}
        onOpenChange={(open) => !open && setConfirmAction(null)}
        title={confirmCopy.title}
        description={confirmCopy.description}
        confirmText={confirmCopy.confirmText}
        variant={confirmCopy.variant}
        onConfirm={handleConfirmAction}
        isLoading={isOperating}
      />

      <div className="space-y-5">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
          {healthCards.map((card) => (
            <GlassCard key={card.label} className="p-4">
              <div className="text-xs text-slate-500">{card.label}</div>
              <div className={cn(
                "mt-2 text-xl font-bold",
                card.tone === "good" && "text-emerald-700",
                card.tone === "bad" && "text-red-700",
                card.tone === "muted" && "text-slate-700",
              )}>{card.value}</div>
            </GlassCard>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-5">
            <GlassCard className="p-5">
              <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">新人训练 AI 教练提示词</h2>
                  <p className="text-sm text-slate-500">
                    这里集中显示商务礼仪 AI 教练对话与题目生成模板；对话模板归入「新人训练 AI 教练」，题目草稿模板归入「商务礼仪」。
                  </p>
                </div>
                <Badge className="bg-indigo-100 text-indigo-700">分类：AI 教练 / 商务礼仪</Badge>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {aiCoachSlots.map((slot) => {
                  const primaryTemplate = slot.templates[0];
                  return (
                    <div key={slot.key} className="rounded-xl border border-slate-200 bg-white/70 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="font-semibold text-slate-900">{slot.title}</h3>
                          <p className="mt-1 text-sm leading-5 text-slate-500">{slot.description}</p>
                        </div>
                        <Badge className={slot.templates.length ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}>
                          {slot.templates.length ? `${slot.templates.length} 个模板` : "未配置"}
                        </Badge>
                      </div>
                      <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm">
                        <div className="text-xs font-medium text-slate-500">当前模板</div>
                        {primaryTemplate ? (
                          <div className="mt-1">
                            <button
                              type="button"
                              className="text-left font-semibold text-slate-900 hover:underline"
                              onClick={() => router.push(`/admin/prompts/${primaryTemplate.id}/edit`)}
                            >
                              {templateTitle(primaryTemplate)}
                            </button>
                            <div className="mt-2 flex flex-wrap gap-1">
                              <Badge className="bg-indigo-100 text-indigo-700">
                                业务用途：{formatBusinessPurpose(primaryTemplate.business_purpose, primaryTemplate.display_business_purpose)}
                              </Badge>
                              {primaryTemplate.is_system ? <Badge className="bg-slate-100 text-slate-700">系统只读</Badge> : <Badge className="bg-blue-100 text-blue-700">自定义</Badge>}
                              {primaryTemplate.is_runtime_effective ? <Badge className="bg-teal-100 text-teal-700">运行时生效</Badge> : null}
                              {primaryTemplate.is_default ? <Badge className="bg-amber-100 text-amber-700">默认</Badge> : null}
                            </div>
                          </div>
                        ) : (
                          <p className="mt-1 text-amber-700">未找到对应模板，请先新建或检查模板分类。</p>
                        )}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {primaryTemplate ? (
                          <Button variant="outline" size="sm" onClick={() => router.push(`/admin/prompts/${primaryTemplate.id}/edit`)}>
                            查看/编辑
                          </Button>
                        ) : null}
                        <Button variant="outline" size="sm" onClick={() => router.push(promptTemplateCreateHref(slot.createName, slot.businessPurpose))}>
                          新建模板
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setCategoryFilter(AI_COACH_PROMPT_CATEGORY);
                            setTypeFilter("all");
                            setSearchQuery(slot.listKeyword);
                          }}
                        >
                          在列表中筛选
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => router.push(slot.managementHref)}>
                          {slot.managementCopy}
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </GlassCard>

            <GlassCard className="p-5">
              <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">运行时生效矩阵</h2>
                  <p className="text-sm text-slate-500">显示各业务域当前默认模板与场景绑定数量；分类与用途会分开显示，避免把不同业务模板混在一起。</p>
                </div>
                <Button variant="outline" size="sm" onClick={() => router.push("/admin/prompts/bindings")}>配置生效场景</Button>
              </div>
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                {MATRIX_GROUPS.map((group) => {
                  const groupTemplates = templates.filter((template) => group.categories.includes(template.category));
                  const rows = Array.from(
                    groupTemplates.reduce((map, template) => {
                      const key = `${template.category}:${template.prompt_type}`;
                      const existing = map.get(key);
                      if (existing) {
                        existing.templates.push(template);
                      } else {
                        map.set(key, {
                          key,
                          category: template.category,
                          prompt_type: template.prompt_type,
                          templates: [template],
                        });
                      }
                      return map;
                    }, new Map<string, { key: string; category: string; prompt_type: PromptType; templates: PromptTemplate[] }>()),
                  ).map(([, value]) => value);
                  return (
                    <div key={group.key} className="rounded-xl border border-slate-200 bg-white/70 p-4">
                      <div className="mb-3 flex items-center justify-between">
                        <h3 className="font-semibold text-slate-900">{group.title}</h3>
                        <Badge className="bg-slate-100 text-slate-700">{groupTemplates.filter((item) => item.is_runtime_effective).length} 个生效</Badge>
                      </div>
                      {rows.length === 0 ? (
                        <p className="text-sm text-slate-500">暂无模板</p>
                      ) : (
                        <div className="space-y-2">
                          {rows.map((row) => {
                            const defaultTemplate = row.templates.find((template) => template.is_active && template.is_default);
                            const bindingCount = scenarioPrompts.filter((item) => item.is_active && item.prompt_type === row.prompt_type).length;
                            return (
                              <div key={row.key} className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
                                <div className="font-medium text-slate-800">
                                  {formatCategoryLabel(row.category)} · {PROMPT_TYPE_LABELS[row.prompt_type]}
                                </div>
                                <div className="mt-1 text-slate-600">默认：{defaultTemplate ? templateTitle(defaultTemplate) : "未设置"}</div>
                                <div className="mt-1 text-xs text-slate-500">
                                  模板：{row.templates.length} 个 · 场景绑定：{bindingCount} 条
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </GlassCard>

            <GlassCard className="p-4">
              <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-5">
                <div className="relative md:col-span-2">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
                  <Input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="搜索中文模板名、用途或分类" className="pl-9" />
                </div>
                <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value as PromptType | "all")} className="rounded-lg border px-3 py-2 text-sm">
                  <option value="all">全部用途</option>
                  {Object.entries(PROMPT_TYPE_LABELS).map(([type, label]) => (<option key={type} value={type}>{label}</option>))}
                </select>
                <select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)} className="rounded-lg border px-3 py-2 text-sm">
                  {CATEGORY_FILTER_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={showInactive} onChange={(event) => setShowInactive(event.target.checked)} />显示停用模板
                </label>
              </div>
              <div className="overflow-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-slate-500">
                      <th className="py-2 pr-3">模板</th>
                      <th className="py-2 pr-3">用途</th>
                      <th className="py-2 pr-3">分类</th>
                      <th className="py-2 pr-3">生效状态</th>
                      <th className="py-2">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {loading ? (
                      <tr><td colSpan={5} className="py-8 text-center text-slate-500">正在加载...</td></tr>
                    ) : filteredTemplates.length === 0 ? (
                      <tr><td colSpan={5} className="py-10 text-center text-slate-500">没有匹配的模板</td></tr>
                    ) : filteredTemplates.map((template) => (
                      <tr key={template.id} className="border-b border-slate-100 hover:bg-slate-50/60">
                        <td className="py-3 pr-3">
                          <button type="button" className="text-left font-semibold text-zinc-900 hover:underline" onClick={() => router.push(`/admin/prompts/${template.id}/edit`)}>
                            {templateTitle(template)}
                          </button>
                          <div className="mt-1 flex flex-wrap gap-1">
                            {template.is_system ? <Badge className="bg-slate-100 text-slate-700">系统只读</Badge> : <Badge className="bg-blue-100 text-blue-700">自定义</Badge>}
                            {template.business_purpose ? (
                              <Badge className="bg-indigo-100 text-indigo-700">
                                {formatBusinessPurpose(template.business_purpose, template.display_business_purpose)}
                              </Badge>
                            ) : null}
                            {template.governance_issues?.length ? <Badge className="bg-red-100 text-red-700">需治理</Badge> : null}
                          </div>
                        </td>
                        <td className="py-3 pr-3"><Badge className={PROMPT_TYPE_COLORS[template.prompt_type]}>{templateType(template)}</Badge></td>
                        <td className="py-3 pr-3 text-slate-600">{templateCategory(template)}</td>
                        <td className="py-3 pr-3">
                          <div className="flex flex-wrap gap-1">
                            <Badge className={template.is_active ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-700"}>{template.is_active ? "启用" : "停用"}</Badge>
                            {template.is_default ? <Badge className="bg-amber-100 text-amber-700">默认</Badge> : null}
                            {template.binding_count ? <Badge className="bg-indigo-100 text-indigo-700">绑定 {template.binding_count}</Badge> : null}
                            {template.is_runtime_effective ? <Badge className="bg-teal-100 text-teal-700">运行时生效</Badge> : null}
                          </div>
                        </td>
                        <td className="py-3">
                          <div className="flex flex-wrap gap-2">
                            <Button variant="outline" size="sm" onClick={() => void handleShowImpact(template)}><Eye className="mr-1 h-3.5 w-3.5" />影响</Button>
                            {template.is_system ? (
                              <Button variant="outline" size="sm" disabled={!canOperate || isOperating} onClick={() => void handleClone(template)}><Copy className="mr-1 h-3.5 w-3.5" />复制</Button>
                            ) : (
                              <Button variant="outline" size="sm" onClick={() => router.push(`/admin/prompts/${template.id}/edit`)}>编辑</Button>
                            )}
                            <Button variant="outline" size="sm" disabled={!canOperate || template.is_default || template.is_system || isOperating} onClick={() => setConfirmAction({ type: "default", template })}>设为默认</Button>
                            <Button variant="outline" size="sm" disabled={!canOperate || template.is_system || isOperating} onClick={() => setConfirmAction({ type: "toggle", template })}>{template.is_active ? "停用" : "启用"}</Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </GlassCard>
          </div>

          <div className="space-y-5">
            <GlassCard className="p-5">
              <div className="flex items-center gap-2">
                <Wrench className="h-5 w-5 text-slate-700" />
                <h2 className="font-bold text-slate-900">治理操作</h2>
              </div>
              <p className="mt-2 text-sm text-slate-500">先预览修复项，再执行；执行会写入操作记录。</p>
              <div className="mt-4 flex flex-col gap-2">
                <Button variant="outline" disabled={!canOperate || isOperating} onClick={() => void handlePreviewRepair()}>检查并预览修复</Button>
                <Button disabled={!canOperate || isOperating || !repairPreview || repairPreview.repaired === 0} onClick={() => setConfirmAction({ type: "executeRepair" })}>
                  <ShieldCheck className="mr-2 h-4 w-4" />执行修复
                </Button>
              </div>
              {repairPreview ? (
                <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                  <div className="font-semibold">修复预览：{repairPreview.repaired} 项</div>
                  <ul className="mt-2 list-disc space-y-1 pl-5">
                    {repairPreview.items.slice(0, 5).map((item, index) => (
                      <li key={`${String(item.template_id || index)}`}>
                        {String(item.name || item.template_id || "模板")}：{Array.isArray(item.actions) ? item.actions.join(" / ") : "待修复"}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </GlassCard>

            <GlassCard className="p-5">
              <h2 className="font-bold text-slate-900">影响范围</h2>
              {impact ? (
                <div className="mt-3 space-y-3 text-sm">
                  <div>
                    <div className="font-semibold text-slate-900">{impact.display_name}</div>
                    <div className="mt-1 text-slate-500">
                      {impact.display_category} · {impact.display_type} · {impact.display_business_purpose}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    <Badge className={impact.is_runtime_effective ? "bg-teal-100 text-teal-700" : "bg-slate-100 text-slate-700"}>{impact.is_runtime_effective ? "运行时生效" : "当前未生效"}</Badge>
                    {impact.is_default ? <Badge className="bg-amber-100 text-amber-700">默认兜底</Badge> : null}
                    {impact.binding_count ? <Badge className="bg-indigo-100 text-indigo-700">绑定 {impact.binding_count}</Badge> : null}
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="font-medium text-slate-700">运行时消费者</div>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-600">
                      {impact.runtime_consumers.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="font-medium text-slate-700">建议下一步</div>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-600">
                      {impact.recommended_next_steps.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </div>
                </div>
              ) : (
                <p className="mt-3 text-sm text-slate-500">点击列表中的“影响”查看默认、绑定和运行时消费者。</p>
              )}
            </GlassCard>
          </div>
        </div>

        {governanceStatus && governanceStatus.issues.length > 0 ? (
          <GlassCard className="border-red-200 bg-red-50 p-4">
            <div className="font-bold text-red-800">治理问题</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {governanceStatus.issues.slice(0, 8).map((issue, index) => (
                <Badge key={`${issue.template_id}-${index}`} className="border border-red-200 bg-white text-red-700">
                  {issue.name || issue.template_id} · {issue.issue_codes.map(formatGovernanceIssue).join(" / ")}
                </Badge>
              ))}
            </div>
          </GlassCard>
        ) : null}
      </div>
    </AdminIndexShell>
  );
}
