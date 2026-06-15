"use client";

import { useEffect, useMemo, useState } from "react";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { PromptTemplate, PromptTemplateOptions, PromptType, ScenarioPrompt } from "@/lib/api/types";
import { formatPromptType, formatTemplateName, PROMPT_TYPE_LABELS } from "./prompt-labels";

type ScenarioType = "sales" | "presentation";

const SCENARIO_OPTIONS: Array<{ value: ScenarioType; label: string; description: string }> = [
  { value: "sales", label: "销售训练", description: "销售对练、评分、报告等运行时" },
  { value: "presentation", label: "PPT 演练", description: "PPT 要点提取、打断、跟踪等运行时" },
];

function templateTitle(template?: PromptTemplate | null): string {
  if (!template) return "未设置";
  return formatTemplateName(template.name, template.display_name);
}

export function ScenarioBindingsPanel() {
  const toast = useToast();
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [scenarioPrompts, setScenarioPrompts] = useState<ScenarioPrompt[]>([]);
  const [promptOptions, setPromptOptions] = useState<PromptTemplateOptions | null>(null);
  const [currentEffectiveTemplate, setCurrentEffectiveTemplate] = useState<PromptTemplate | null>(null);
  const [loading, setLoading] = useState(true);
  const [isOperating, setIsOperating] = useState(false);
  const [bindingTemplateId, setBindingTemplateId] = useState("");
  const [bindingScenarioType, setBindingScenarioType] = useState<ScenarioType>("presentation");
  const [bindingPromptType, setBindingPromptType] = useState<PromptType>("interruption");
  const [bindingScenarioId, setBindingScenarioId] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<ScenarioPrompt | null>(null);

  const salesAllowedPromptTypes = useMemo(
    () => new Set((promptOptions?.sales_allowed_prompt_types || []) as PromptType[]),
    [promptOptions],
  );
  const templateMap = useMemo(() => new Map(templates.map((item) => [item.id, item])), [templates]);
  const defaultTemplateForPromptType = useMemo(
    () => templates.find((template) => template.is_active && template.is_default && template.prompt_type === bindingPromptType) || null,
    [bindingPromptType, templates],
  );
  const selectablePromptTypes = useMemo(() => {
    const entries = Object.entries(PROMPT_TYPE_LABELS) as [PromptType, string][];
    if (bindingScenarioType !== "sales" || salesAllowedPromptTypes.size === 0) return entries;
    return entries.filter(([type]) => salesAllowedPromptTypes.has(type));
  }, [bindingScenarioType, salesAllowedPromptTypes]);
  const selectableTemplates = useMemo(
    () => templates.filter((template) => template.is_active && template.prompt_type === bindingPromptType),
    [bindingPromptType, templates],
  );
  const selectedTemplate = templateMap.get(bindingTemplateId) || null;

  const loadData = async () => {
    setLoading(true);
    try {
      const [templatesResult, scenarioPromptsResult, optionsResult] = await Promise.all([
        api.admin.getPromptTemplates({ is_active: true }),
        api.admin.getScenarioPrompts(),
        api.admin.getPromptTemplateOptions(),
      ]);
      setTemplates(templatesResult);
      setScenarioPrompts(scenarioPromptsResult);
      setPromptOptions(optionsResult);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadData(); }, 0);
    return () => window.clearTimeout(timer);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectablePromptTypes.some(([type]) => type === bindingPromptType)) {
      const timer = window.setTimeout(() => {
        setBindingPromptType(selectablePromptTypes[0]?.[0] || "evaluation");
        setBindingTemplateId("");
      }, 0);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [bindingPromptType, selectablePromptTypes]);

  useEffect(() => {
    let ignore = false;
    void api.admin.getPromptTemplateForScenario(
      bindingScenarioType,
      bindingPromptType,
      bindingScenarioId.trim() || undefined,
    ).then((template) => {
      if (!ignore) setCurrentEffectiveTemplate(template);
    }).catch(() => {
      if (!ignore) setCurrentEffectiveTemplate(null);
    });
    return () => { ignore = true; };
  }, [bindingPromptType, bindingScenarioId, bindingScenarioType]);

  useEffect(() => {
    if (selectedTemplate?.prompt_type !== bindingPromptType) {
      const timer = window.setTimeout(() => setBindingTemplateId(""), 0);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [bindingPromptType, selectedTemplate]);

  const handleCreate = async () => {
    if (!bindingTemplateId) { toast.error("请先选择要生效的模板"); return; }
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
      setBindingTemplateId("");
      await loadData();
      toast.success("生效场景已保存");
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setIsOperating(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setIsOperating(true);
    try {
      await api.admin.deleteScenarioPrompt(deleteTarget.id);
      setDeleteTarget(null);
      await loadData();
      toast.success("场景绑定已删除");
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setIsOperating(false);
    }
  };

  const fallbackForDelete = deleteTarget
    ? templates.find((template) => template.is_active && template.is_default && template.prompt_type === deleteTarget.prompt_type)
    : null;

  return (
    <AdminFormShell
      backHref="/admin/prompts"
      backLabel="返回提示词治理台"
      title="配置生效场景"
      description="按业务域、用途和模板配置运行时实际使用的提示词。未配置场景绑定时会回退到对应用途的默认模板。"
    >
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="删除场景绑定"
        description={`删除后会回退到默认模板：${templateTitle(fallbackForDelete)}。`}
        confirmText="确认删除"
        variant="warning"
        onConfirm={() => void handleDelete()}
        isLoading={isOperating}
      />

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <GlassCard className="space-y-5 p-5">
          <div>
            <h3 className="text-lg font-bold">生效场景向导</h3>
            <p className="mt-1 text-sm text-slate-500">保存后只影响后续运行时解析，不会回写历史评分或报告。</p>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">1. 选择业务域</label>
              <div className="grid grid-cols-1 gap-2">
                {SCENARIO_OPTIONS.map((option) => (
                  <button
                    type="button"
                    key={option.value}
                    onClick={() => {
                      setBindingScenarioType(option.value);
                      setBindingTemplateId("");
                    }}
                    className={`rounded-xl border px-3 py-3 text-left text-sm ${bindingScenarioType === option.value ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white text-slate-700"}`}
                  >
                    <div className="font-semibold">{option.label}</div>
                    <div className={bindingScenarioType === option.value ? "text-slate-200" : "text-slate-500"}>{option.description}</div>
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">2. 选择用途</label>
                <select
                  value={bindingPromptType}
                  onChange={(event) => {
                    setBindingPromptType(event.target.value as PromptType);
                    setBindingTemplateId("");
                  }}
                  className="w-full rounded-lg border px-3 py-2 text-sm"
                >
                  {selectablePromptTypes.map(([type, label]) => <option key={type} value={type}>{formatPromptType(type, label)}</option>)}
                </select>
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">3. 具体场景编号（可选，高级）</label>
                <Input value={bindingScenarioId} onChange={(event) => setBindingScenarioId(event.target.value)} placeholder="不填表示该业务域全局生效" />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">4. 选择模板</label>
                <select value={bindingTemplateId} onChange={(event) => setBindingTemplateId(event.target.value)} className="w-full rounded-lg border px-3 py-2 text-sm">
                  <option value="">选择模板</option>
                  {selectableTemplates.map((template) => <option key={template.id} value={template.id}>{templateTitle(template)}</option>)}
                </select>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
              <div className="font-semibold text-slate-800">当前实际生效</div>
              <div className="mt-2 text-slate-600">{templateTitle(currentEffectiveTemplate || defaultTemplateForPromptType)}</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
              <div className="font-semibold text-slate-800">保存后生效</div>
              <div className="mt-2 text-slate-600">{templateTitle(selectedTemplate || currentEffectiveTemplate || defaultTemplateForPromptType)}</div>
            </div>
          </div>

          <div className="flex justify-end">
            <Button disabled={isOperating || loading || !bindingTemplateId} onClick={() => void handleCreate()}>保存绑定</Button>
          </div>
        </GlassCard>

        <GlassCard className="p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold">当前绑定</h3>
            <Badge className="bg-slate-100 text-slate-700">{scenarioPrompts.length} 条</Badge>
          </div>
          <div className="mt-4 space-y-3">
            {loading ? (
              <div className="py-4 text-sm text-slate-500">正在加载...</div>
            ) : scenarioPrompts.length === 0 ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">当前没有场景绑定，运行时全部回退到默认模板。</div>
            ) : scenarioPrompts.map((item) => {
              const linked = templateMap.get(item.template_id);
              return (
                <div key={item.id} className="rounded-xl border bg-white px-3 py-3 text-sm">
                  <div className="font-semibold text-slate-900">{item.template_display_name || templateTitle(linked)}</div>
                  <div className="mt-1 text-slate-600">{item.display_scenario_type || (item.scenario_type === "sales" ? "销售训练" : "PPT 演练")} · {item.display_prompt_type || formatPromptType(item.prompt_type)} · {item.scenario_id || "全局"}</div>
                  <div className="mt-3 flex items-center justify-between">
                    <Badge className={item.is_active ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-700"}>{item.is_active ? "启用" : "停用"}</Badge>
                    <Button variant="outline" size="sm" disabled={isOperating} onClick={() => setDeleteTarget(item)}>删除</Button>
                  </div>
                </div>
              );
            })}
          </div>
        </GlassCard>
      </div>
    </AdminFormShell>
  );
}
