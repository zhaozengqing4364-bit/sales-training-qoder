"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AlertCircle, ArrowLeft, Copy, Play, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { GlassCard } from "@/components/ui/glass-card";
import { GlassModal } from "@/components/ui/glass-modal";
import { StatusIndicator } from "@/components/ui/status-indicator";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { PromptTemplate, PromptTemplateImpactResponse, PromptTemplateOptions, PromptType } from "@/lib/api/types";
import { formatCategoryLabel, formatPromptType, formatTemplateName, PROMPT_TYPE_LABELS } from "@/components/admin/prompts/prompt-labels";

const PROMPT_CATEGORY_OPTIONS = [
  { value: "common", label: "通用" },
  { value: "sales", label: "销售训练" },
  { value: "sales_bot", label: "销售实时对练" },
  { value: "sales_trainer_ai_coach", label: "新人训练 AI 教练" },
  { value: "presentation", label: "PPT 演练" },
  { value: "system", label: "系统报告" },
] as const;

function extractTemplateVariables(template: string): string[] {
  const matches = template.match(/\{\{\s*([A-Za-z_][A-Za-z0-9_]*)[\s|}]/g);
  if (!matches) return [];
  return [...new Set(matches.map((match) => match.replace(/\{\{\s*|\s*[|}]/g, "").trim()))].filter(Boolean);
}

export default function EditPromptTemplatePage() {
  const params = useParams();
  const router = useRouter();
  const toast = useToast();
  const rawTemplateId = params?.id;
  const templateId = Array.isArray(rawTemplateId) ? rawTemplateId[0] : rawTemplateId;
  const isValidTemplateId = typeof templateId === "string" && templateId.trim().length > 0 && templateId !== "undefined";

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [originalTemplate, setOriginalTemplate] = useState<PromptTemplate | null>(null);
  const [impact, setImpact] = useState<PromptTemplateImpactResponse | null>(null);
  const [promptOptions, setPromptOptions] = useState<PromptTemplateOptions | null>(null);

  const [name, setName] = useState("");
  const [promptType, setPromptType] = useState<PromptType>("summary");
  const [category, setCategory] = useState("common");
  const [template, setTemplate] = useState("");
  const [isActive, setIsActive] = useState(true);

  const [testVariables, setTestVariables] = useState("{}");
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [showTestModal, setShowTestModal] = useState(false);
  const [showSaveConfirm, setShowSaveConfirm] = useState(false);

  const isSystemTemplate = Boolean(originalTemplate?.is_system);
  const canEditDirectly = Boolean(originalTemplate && !isSystemTemplate);
  const normalizedCategory = category.trim().toLowerCase();
  const salesAllowedPromptTypes = useMemo(
    () => new Set((promptOptions?.sales_allowed_prompt_types || []) as PromptType[]),
    [promptOptions],
  );
  const selectablePromptTypes = useMemo(() => {
    const entries = Object.entries(PROMPT_TYPE_LABELS) as [PromptType, string][];
    if (normalizedCategory !== "sales" || salesAllowedPromptTypes.size === 0) return entries;
    return entries.filter(([type]) => salesAllowedPromptTypes.has(type));
  }, [normalizedCategory, salesAllowedPromptTypes]);
  const effectivePromptType = selectablePromptTypes.some(([type]) => type === promptType)
    ? promptType
    : (selectablePromptTypes[0]?.[0] ?? promptType);
  const extractedVars = useMemo(() => extractTemplateVariables(template), [template]);

  useEffect(() => {
    void api.admin.getPromptTemplateOptions().then(setPromptOptions).catch(() => setPromptOptions(null));
  }, []);

  const loadTemplate = useCallback(async () => {
    if (!isValidTemplateId || !templateId) {
      setError("模板编号无效，请返回列表后重试。");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [data, impactData] = await Promise.all([
        api.admin.getPromptTemplate(templateId),
        api.admin.getPromptTemplateImpact(templateId),
      ]);
      setOriginalTemplate(data);
      setImpact(impactData);
      setName(data.name);
      setPromptType(data.prompt_type);
      setCategory(data.category);
      setTemplate(data.template);
      setIsActive(data.is_active);
      const sampleVars: Record<string, string> = {};
      data.variables.forEach((variable) => { sampleVars[variable] = `示例_${variable}`; });
      setTestVariables(JSON.stringify(sampleVars, null, 2));
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [isValidTemplateId, templateId]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadTemplate(); }, 0);
    return () => window.clearTimeout(timer);
  }, [loadTemplate]);

  const saveTemplate = async () => {
    if (!isValidTemplateId || !templateId) return;
    setSaving(true);
    setError(null);
    try {
      if (!canEditDirectly) throw new Error("系统模板不可直接保存，请先复制为自定义模板。");
      await api.admin.updatePromptTemplate(templateId, {
        name,
        prompt_type: effectivePromptType,
        category,
        template,
        variables: extractedVars,
        is_active: isActive,
      });
      toast.success("模板已保存");
      router.push("/admin/prompts");
    } catch (err) {
      setError(getApiErrorMessage(err));
      setSaving(false);
    }
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!canEditDirectly) return;
    setShowSaveConfirm(true);
  };

  const handleClone = async () => {
    if (!isValidTemplateId || !templateId) return;
    setSaving(true);
    setError(null);
    try {
      const cloned = await api.admin.clonePromptTemplate(templateId, {
        reason: "提示词详情页复制系统模板",
      });
      toast.success("已复制为自定义模板");
      router.push(`/admin/prompts/${cloned.id}/edit`);
    } catch (err) {
      setError(getApiErrorMessage(err));
      setSaving(false);
    }
  };

  const handleTestRender = async () => {
    if (!isValidTemplateId || !templateId) return;
    setTesting(true);
    setTestResult(null);
    try {
      const variables = JSON.parse(testVariables);
      const result = await api.admin.renderPromptTemplate(templateId, variables);
      setTestResult(result.rendered);
    } catch (err) {
      setTestResult(`错误：${getApiErrorMessage(err)}`);
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto max-w-4xl px-4 py-12 text-center">
        <StatusIndicator status="loading" />
        <p className="mt-4 text-zinc-500">正在加载模板...</p>
      </div>
    );
  }

  if (error && !originalTemplate) {
    return (
      <div className="container mx-auto max-w-4xl px-4 py-12">
        <div className="flex items-center justify-center gap-2 text-red-500">
          <AlertCircle className="h-6 w-6" />
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto max-w-5xl px-4 py-6">
      <div className="mb-6 flex flex-wrap items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => router.push("/admin/prompts")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          返回
        </Button>
        <h1 className="text-2xl font-semibold text-zinc-900">{isSystemTemplate ? "查看系统模板" : "编辑自定义模板"}</h1>
        {originalTemplate?.is_system ? <Badge className="bg-slate-100 text-slate-800">系统只读</Badge> : <Badge className="bg-blue-100 text-blue-800">自定义模板</Badge>}
        {isSystemTemplate ? (
          <Button variant="outline" disabled={saving} onClick={() => void handleClone()}>
            <Copy className="mr-2 h-4 w-4" />
            复制为自定义模板
          </Button>
        ) : null}
      </div>

      {error ? (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 p-3 text-red-600">
          <AlertCircle className="h-5 w-5" />
          {error}
        </div>
      ) : null}

      <GlassCard className="p-6">
        {isSystemTemplate ? (
          <div className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
            系统模板只能查看，不能直接保存、停用或修改默认状态。需要调整时，请复制为自定义模板，再设置默认或配置生效场景。
          </div>
        ) : null}

        {impact ? (
          <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-4">
            <div className="rounded-xl bg-slate-50 p-3 text-sm">
              <div className="text-slate-500">模板名称</div>
              <div className="mt-1 font-semibold">{formatTemplateName(originalTemplate?.name || "", originalTemplate?.display_name)}</div>
            </div>
            <div className="rounded-xl bg-slate-50 p-3 text-sm">
              <div className="text-slate-500">分类用途</div>
              <div className="mt-1 font-semibold">{impact.display_category} · {impact.display_type}</div>
            </div>
            <div className="rounded-xl bg-slate-50 p-3 text-sm">
              <div className="text-slate-500">生效状态</div>
              <div className="mt-1 font-semibold">{impact.is_runtime_effective ? "运行时生效" : "未生效"}</div>
            </div>
            <div className="rounded-xl bg-slate-50 p-3 text-sm">
              <div className="text-slate-500">场景绑定</div>
              <div className="mt-1 font-semibold">{impact.binding_count} 条</div>
            </div>
          </div>
        ) : null}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div>
              <label className="mb-2 block text-sm font-medium text-zinc-700">模板名称</label>
              <Input value={name} onChange={(event) => setName(event.target.value)} required disabled={!canEditDirectly} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-zinc-700">提示词用途</label>
              <select
                value={effectivePromptType}
                onChange={(event) => setPromptType(event.target.value as PromptType)}
                className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 disabled:bg-slate-100"
                required
                disabled={!canEditDirectly}
              >
                {selectablePromptTypes.map(([type, label]) => <option key={type} value={type}>{formatPromptType(type, label)}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-zinc-700">分类</label>
              <input
                list="prompt-category-options"
                value={category}
                onChange={(event) => {
                  const nextCategory = event.target.value;
                  const nextNormalized = nextCategory.trim().toLowerCase();
                  if (nextNormalized === "sales" && salesAllowedPromptTypes.size > 0 && !salesAllowedPromptTypes.has(promptType)) {
                    setPromptType([...salesAllowedPromptTypes][0]);
                  }
                  setCategory(nextCategory);
                }}
                className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 disabled:bg-slate-100"
                disabled={!canEditDirectly}
                placeholder="选择或输入分类"
              />
              <datalist id="prompt-category-options">
                {PROMPT_CATEGORY_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </datalist>
              <p className="mt-1 text-xs text-slate-500">{formatCategoryLabel(category)}</p>
            </div>
            <div className="flex items-center gap-4">
              <label className="flex cursor-pointer items-center gap-2">
                <input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} disabled={!canEditDirectly} />
                <span className="text-sm text-zinc-700">启用</span>
              </label>
              <Badge className={originalTemplate?.is_default ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-700"}>
                {originalTemplate?.is_default ? "默认模板" : "非默认"}
              </Badge>
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <label className="block text-sm font-medium text-zinc-700">模板内容</label>
              <Button type="button" variant="outline" size="sm" onClick={() => setShowTestModal(true)}>
                <Play className="mr-2 h-4 w-4" />
                渲染预览
              </Button>
            </div>
            <textarea
              value={template}
              onChange={(event) => setTemplate(event.target.value)}
              placeholder="输入 Jinja2 模板，使用 {{ variable }} 语法插入变量"
              className="min-h-[320px] w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 disabled:bg-slate-100"
              required
              disabled={!canEditDirectly}
            />
            <p className="mt-1 text-xs text-zinc-500">变量名、JSON 字段和 Jinja2 占位符保持英文，不要翻译。</p>
          </div>

          <div className="rounded-lg bg-blue-50 p-4">
            <h4 className="mb-2 text-sm font-medium text-blue-900">变量校验</h4>
            {extractedVars.length === 0 ? (
              <p className="text-sm text-blue-700">当前模板未提取到变量。</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {extractedVars.map((variable) => <Badge key={variable} className="bg-blue-100 text-blue-800">{variable}</Badge>)}
              </div>
            )}
          </div>

          <div className="flex justify-end gap-3 border-t pt-4">
            <Button type="button" variant="outline" onClick={() => router.push("/admin/prompts")} disabled={saving}>取消</Button>
            <Button type="submit" className="bg-zinc-900 hover:bg-zinc-800" disabled={saving || !name || !template || !canEditDirectly}>
              {saving ? <><StatusIndicator status="loading" className="mr-2" />保存中...</> : <><Save className="mr-2 h-4 w-4" />保存</>}
            </Button>
          </div>
        </form>
      </GlassCard>

      <ConfirmDialog
        open={showSaveConfirm}
        onOpenChange={setShowSaveConfirm}
        title="保存自定义模板"
        description={impact?.is_runtime_effective ? "该模板当前已在运行时生效，保存会影响后续调用。请确认变量、正文和渲染预览已检查。" : "保存后模板仍需设为默认或配置生效场景才会生效。"}
        confirmText="确认保存"
        variant="warning"
        onConfirm={() => void saveTemplate()}
        isLoading={saving}
      />

      <GlassModal isOpen={showTestModal} onClose={() => setShowTestModal(false)} title="渲染预览" size="lg">
        <div className="space-y-4">
          <div>
            <label className="mb-2 block text-sm font-medium text-zinc-700">变量 JSON</label>
            <textarea
              value={testVariables}
              onChange={(event) => setTestVariables(event.target.value)}
              className="min-h-[150px] w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
              placeholder='{"variable": "value"}'
            />
          </div>
          <Button onClick={() => void handleTestRender()} disabled={testing} className="w-full">
            {testing ? <><StatusIndicator status="loading" className="mr-2" />渲染中...</> : <><Play className="mr-2 h-4 w-4" />渲染</>}
          </Button>
          {testResult !== null ? (
            <div className="max-h-96 overflow-auto rounded-lg bg-zinc-900 p-4 font-mono text-sm text-zinc-100">
              <pre>{testResult}</pre>
            </div>
          ) : null}
        </div>
      </GlassModal>
    </div>
  );
}
