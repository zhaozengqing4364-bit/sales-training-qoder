"use client";
import { debug } from "@/lib/debug";

import { useEffect, useMemo, useState } from "react";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api/client";
import type {
  PresentationAIPolicy,
  PresentationAIPolicyEffectiveResponse,
  PresentationAIPolicyPreviewResponse,
  PresentationAIScopeType,
  PromptTemplate,
} from "@/lib/api/types";
import { FlaskConical, Loader2, RefreshCw, Save } from "lucide-react";

const DEFAULT_POLICY: PresentationAIPolicy = {
  enabled: true,
  prompt_config: {
    enable_prompt_first: true,
    interruption_template_id: null,
  },
  rule_config: {
    similarity_threshold: 0.75,
    point_tracker_cooldown_seconds: 30,
    feedback_cooldown_seconds: 30,
    allow_critical_forbidden_interrupt: true,
    allow_regular_forbidden_interrupt: true,
    missing_points_interrupt_ratio_threshold: 0.3,
    missing_points_min_count: 1,
    missing_points_preview_count: 2,
  },
  fallback_config: {
    enable_interruption_detector_fallback: true,
    allow_scenario_prompt_fallback: true,
    fallback_when_template_missing: true,
    fallback_when_render_error: true,
  },
};

function parseTextList(raw: string): string[] {
  return raw
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function clampNumber(value: number, fallback: number, min: number, max: number): number {
  if (Number.isNaN(value)) {
    return fallback;
  }
  return Math.max(min, Math.min(max, value));
}

export default function PresentationAIPolicyPage() {
  const toast = useToast();

  const [scopeType, setScopeType] = useState<PresentationAIScopeType>("global");
  const [scopeId, setScopeId] = useState("");
  const [policy, setPolicy] = useState<PresentationAIPolicy>(DEFAULT_POLICY);
  const [exists, setExists] = useState(false);
  const [policyMeta, setPolicyMeta] = useState<{ id?: string | null; updated_at?: string | null }>({});

  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(true);

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const [previewTranscript, setPreviewTranscript] = useState("");
  const [previewRequiredPoints, setPreviewRequiredPoints] = useState("");
  const [previewForbiddenWords, setPreviewForbiddenWords] = useState("");
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [previewResult, setPreviewResult] = useState<PresentationAIPolicyPreviewResponse | null>(null);

  const [effectiveSessionId, setEffectiveSessionId] = useState("");
  const [effectivePolicy, setEffectivePolicy] = useState<PresentationAIPolicyEffectiveResponse | null>(null);
  const [isLoadingEffective, setIsLoadingEffective] = useState(false);

  const normalizedScopeId = useMemo(() => scopeId.trim(), [scopeId]);

  const loadTemplateOptions = async () => {
    setIsLoadingTemplates(true);
    try {
      const data = await api.admin.getPromptTemplates({
        prompt_type: "interruption",
        is_active: true,
      });
      setTemplates(data);
    } catch (error) {
      debug.error("Failed to load interruption templates", error);
      setTemplates([]);
      toast.error("中断模板加载失败");
    } finally {
      setIsLoadingTemplates(false);
    }
  };

  const loadPolicy = async () => {
    if (scopeType !== "global" && !normalizedScopeId) {
      toast.error("请先填写作用域 ID");
      return;
    }

    setIsLoading(true);
    try {
      const response = await api.admin.getPresentationAIPolicy({
        scope_type: scopeType,
        scope_id: scopeType === "global" ? undefined : normalizedScopeId,
      });
      setPolicy(response.policy);
      setExists(Boolean(response.exists));
      setPolicyMeta(response.meta || {});
    } catch (error) {
      debug.error("Failed to load presentation AI policy", error);
      toast.error("加载策略失败");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void Promise.all([loadPolicy(), loadTemplateOptions()]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const savePolicy = async () => {
    if (scopeType !== "global" && !normalizedScopeId) {
      toast.error("请先填写作用域 ID");
      return;
    }

    setIsSaving(true);
    try {
      const response = await api.admin.updatePresentationAIPolicy({
        scope_type: scopeType,
        scope_id: scopeType === "global" ? undefined : normalizedScopeId,
        enabled: policy.enabled,
        prompt_config: policy.prompt_config,
        rule_config: policy.rule_config,
        fallback_config: policy.fallback_config,
      });
      setPolicy(response.policy);
      setExists(Boolean(response.exists));
      setPolicyMeta(response.meta || {});
      toast.success("策略保存成功");
    } catch (error) {
      debug.error("Failed to save presentation AI policy", error);
      toast.error("保存失败");
    } finally {
      setIsSaving(false);
    }
  };

  const runPreview = async () => {
    if (!previewTranscript.trim()) {
      toast.error("请填写预览转写文本");
      return;
    }

    if (scopeType !== "global" && !normalizedScopeId) {
      toast.error("请先填写作用域 ID");
      return;
    }

    setIsPreviewing(true);
    try {
      const response = await api.admin.previewPresentationAIPolicy({
        scope_type: scopeType,
        scope_id: scopeType === "global" ? undefined : normalizedScopeId,
        transcript: previewTranscript,
        required_points: parseTextList(previewRequiredPoints),
        forbidden_words: parseTextList(previewForbiddenWords),
      });
      setPreviewResult(response);
      toast.success("预览完成");
    } catch (error) {
      debug.error("Failed to preview presentation AI policy", error);
      toast.error("预览失败");
    } finally {
      setIsPreviewing(false);
    }
  };

  const loadEffectivePolicy = async () => {
    if (!effectiveSessionId.trim()) {
      toast.error("请填写会话 ID");
      return;
    }

    setIsLoadingEffective(true);
    try {
      const response = await api.admin.getEffectivePresentationAIPolicy({
        session_id: effectiveSessionId.trim(),
      });
      setEffectivePolicy(response);
      toast.success("已加载生效策略");
    } catch (error) {
      debug.error("Failed to load effective presentation AI policy", error);
      toast.error("加载生效策略失败");
    } finally {
      setIsLoadingEffective(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h1 className="text-3xl font-black text-slate-900 tracking-tight">PPT AI 策略</h1>
          <p className="text-slate-500 mt-1">默认只保留关键开关。高级参数在下方折叠面板中配置。</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="rounded-full" onClick={() => void loadPolicy()} disabled={isLoading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
            刷新
          </Button>
          <Button
            className="rounded-full bg-slate-900 text-white"
            onClick={() => void savePolicy()}
            disabled={isSaving || isLoading}
          >
            {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
            保存策略
          </Button>
        </div>
      </div>

      <GlassCard className="p-6 space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-500 uppercase">作用域</label>
            <select
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              value={scopeType}
              onChange={(event) => setScopeType(event.target.value as PresentationAIScopeType)}
            >
              <option value="global">全局</option>
              <option value="scenario">场景</option>
              <option value="presentation">PPT</option>
            </select>
          </div>
          <div className="space-y-2 md:col-span-2">
            <label className="text-xs font-bold text-slate-500 uppercase">作用域 ID</label>
            <Input
              name="presentation_ai_scope_id"
              autoComplete="off"
              placeholder={scopeType === "global" ? "全局无需填写" : "输入 scenario_id 或 presentation_id"}
              value={scopeId}
              disabled={scopeType === "global"}
              onChange={(event) => setScopeId(event.target.value)}
            />
          </div>
        </div>

        <div className="text-xs text-slate-500">
          当前状态：{exists ? "已存在策略" : "使用默认策略"}
          {policyMeta.updated_at ? ` · 最近更新 ${new Date(policyMeta.updated_at).toLocaleString("zh-CN")}` : ""}
        </div>

        {isLoading ? (
          <div className="py-16 flex items-center justify-center text-slate-400">
            <Loader2 className="w-5 h-5 animate-spin" />
          </div>
        ) : (
          <div className="space-y-5">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-4">
              <h3 className="text-base font-bold text-slate-900">最简模式（推荐）</h3>

              <label className="flex items-center gap-3 text-sm text-slate-700">
                <Checkbox
                  checked={policy.enabled}
                  onCheckedChange={(checked) => setPolicy((prev) => ({ ...prev, enabled: Boolean(checked) }))}
                />
                启用该作用域策略
              </label>

              <div className="space-y-2">
                <label className="text-xs font-bold text-slate-500 uppercase">中断提示词模板</label>
                <select
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  value={policy.prompt_config.interruption_template_id || ""}
                  onChange={(event) => {
                    const value = event.target.value.trim();
                    setPolicy((prev) => ({
                      ...prev,
                      prompt_config: {
                        ...prev.prompt_config,
                        interruption_template_id: value || null,
                      },
                    }));
                  }}
                >
                  <option value="">自动选择（按场景默认）</option>
                  {templates.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.name} · {template.category}
                    </option>
                  ))}
                </select>
                {isLoadingTemplates ? (
                  <div className="text-xs text-slate-500">正在加载模板...</div>
                ) : templates.length === 0 ? (
                  <div className="text-xs text-amber-600">暂无可选中断模板，将使用系统兜底策略。</div>
                ) : null}
              </div>

              <div className="space-y-2">
                <label className="text-xs font-bold text-slate-500 uppercase">语义相似度阈值</label>
                <Input
                  type="number"
                  min={0.1}
                  max={0.99}
                  step={0.01}
                  value={policy.rule_config.similarity_threshold}
                  onChange={(event) => {
                    const next = clampNumber(Number(event.target.value), 0.75, 0.1, 0.99);
                    setPolicy((prev) => ({
                      ...prev,
                      rule_config: { ...prev.rule_config, similarity_threshold: next },
                    }));
                  }}
                />
              </div>

              <label className="flex items-center gap-3 text-sm text-slate-700">
                <Checkbox
                  checked={policy.fallback_config.enable_interruption_detector_fallback}
                  onCheckedChange={(checked) =>
                    setPolicy((prev) => ({
                      ...prev,
                      fallback_config: {
                        ...prev.fallback_config,
                        enable_interruption_detector_fallback: Boolean(checked),
                      },
                    }))
                  }
                />
                开启规则兜底（模板异常或不可用时）
              </label>
            </div>

            <details className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <summary className="cursor-pointer text-sm font-bold text-slate-800">高级设置（开发者）</summary>
              <div className="mt-4 space-y-4">
                <label className="flex items-center gap-3 text-sm text-slate-700">
                  <Checkbox
                    checked={policy.prompt_config.enable_prompt_first}
                    onCheckedChange={(checked) =>
                      setPolicy((prev) => ({
                        ...prev,
                        prompt_config: { ...prev.prompt_config, enable_prompt_first: Boolean(checked) },
                      }))
                    }
                  />
                  提示词优先于规则
                </label>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-500 uppercase">反馈冷却（秒）</label>
                    <Input
                      type="number"
                      min={0}
                      max={600}
                      step={1}
                      value={policy.rule_config.feedback_cooldown_seconds}
                      onChange={(event) => {
                        const next = clampNumber(Number(event.target.value), 30, 0, 600);
                        setPolicy((prev) => ({
                          ...prev,
                          rule_config: { ...prev.rule_config, feedback_cooldown_seconds: next },
                        }));
                      }}
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-500 uppercase">要点检测冷却（秒）</label>
                    <Input
                      type="number"
                      min={0}
                      max={600}
                      step={1}
                      value={policy.rule_config.point_tracker_cooldown_seconds}
                      onChange={(event) => {
                        const next = clampNumber(Number(event.target.value), 30, 0, 600);
                        setPolicy((prev) => ({
                          ...prev,
                          rule_config: { ...prev.rule_config, point_tracker_cooldown_seconds: next },
                        }));
                      }}
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-500 uppercase">缺失要点占比阈值</label>
                    <Input
                      type="number"
                      min={0}
                      max={1}
                      step={0.05}
                      value={policy.rule_config.missing_points_interrupt_ratio_threshold}
                      onChange={(event) => {
                        const next = clampNumber(Number(event.target.value), 0.3, 0, 1);
                        setPolicy((prev) => ({
                          ...prev,
                          rule_config: {
                            ...prev.rule_config,
                            missing_points_interrupt_ratio_threshold: next,
                          },
                        }));
                      }}
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-500 uppercase">缺失要点最小数量</label>
                    <Input
                      type="number"
                      min={1}
                      max={50}
                      step={1}
                      value={policy.rule_config.missing_points_min_count}
                      onChange={(event) => {
                        const next = clampNumber(Number(event.target.value), 1, 1, 50);
                        setPolicy((prev) => ({
                          ...prev,
                          rule_config: { ...prev.rule_config, missing_points_min_count: next },
                        }));
                      }}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <label className="flex items-center gap-3 text-sm text-slate-700">
                    <Checkbox
                      checked={policy.rule_config.allow_critical_forbidden_interrupt}
                      onCheckedChange={(checked) =>
                        setPolicy((prev) => ({
                          ...prev,
                          rule_config: {
                            ...prev.rule_config,
                            allow_critical_forbidden_interrupt: Boolean(checked),
                          },
                        }))
                      }
                    />
                    允许严重禁忌词触发中断
                  </label>

                  <label className="flex items-center gap-3 text-sm text-slate-700">
                    <Checkbox
                      checked={policy.rule_config.allow_regular_forbidden_interrupt}
                      onCheckedChange={(checked) =>
                        setPolicy((prev) => ({
                          ...prev,
                          rule_config: {
                            ...prev.rule_config,
                            allow_regular_forbidden_interrupt: Boolean(checked),
                          },
                        }))
                      }
                    />
                    允许普通禁忌词触发中断
                  </label>

                  <label className="flex items-center gap-3 text-sm text-slate-700">
                    <Checkbox
                      checked={policy.fallback_config.allow_scenario_prompt_fallback}
                      onCheckedChange={(checked) =>
                        setPolicy((prev) => ({
                          ...prev,
                          fallback_config: {
                            ...prev.fallback_config,
                            allow_scenario_prompt_fallback: Boolean(checked),
                          },
                        }))
                      }
                    />
                    模板缺失时允许场景模板兜底
                  </label>

                  <label className="flex items-center gap-3 text-sm text-slate-700">
                    <Checkbox
                      checked={policy.fallback_config.fallback_when_render_error}
                      onCheckedChange={(checked) =>
                        setPolicy((prev) => ({
                          ...prev,
                          fallback_config: {
                            ...prev.fallback_config,
                            fallback_when_render_error: Boolean(checked),
                          },
                        }))
                      }
                    />
                    渲染失败时自动降级兜底
                  </label>
                </div>
              </div>
            </details>
          </div>
        )}
      </GlassCard>

      <details className="rounded-xl border border-slate-200 bg-slate-50 p-4">
        <summary className="cursor-pointer text-sm font-bold text-slate-800">调试工具（预览 / 生效策略）</summary>
        <div className="mt-4 grid grid-cols-1 xl:grid-cols-2 gap-6">
          <GlassCard className="p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">策略预览</h3>
              <Button
                variant="outline"
                className="rounded-full"
                onClick={() => void runPreview()}
                disabled={isPreviewing}
              >
                {isPreviewing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <FlaskConical className="w-4 h-4 mr-2" />}
                运行预览
              </Button>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-500 uppercase">转写文本</label>
              <textarea
                className="w-full min-h-[120px] rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-200"
                value={previewTranscript}
                onChange={(event) => setPreviewTranscript(event.target.value)}
                placeholder="输入一段演讲文本用于模拟检测"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-500 uppercase">要点列表（逗号或换行）</label>
              <textarea
                className="w-full min-h-[72px] rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-200"
                value={previewRequiredPoints}
                onChange={(event) => setPreviewRequiredPoints(event.target.value)}
                placeholder="例如：客户痛点, 方案价值, ROI"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-500 uppercase">禁忌词（逗号或换行）</label>
              <textarea
                className="w-full min-h-[72px] rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-200"
                value={previewForbiddenWords}
                onChange={(event) => setPreviewForbiddenWords(event.target.value)}
                placeholder="例如：大概, 可能"
              />
            </div>

            {previewResult && (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm space-y-1">
                <div>
                  是否中断：
                  <span className="font-bold text-slate-900">{previewResult.result.should_interrupt ? "是" : "否"}</span>
                </div>
                <div>原因：{previewResult.result.reason || "-"}</div>
                <div>消息：{previewResult.result.message || "-"}</div>
                <div>
                  要点覆盖：{previewResult.result.point_coverage.covered}/{previewResult.result.point_coverage.total}
                </div>
                <div>
                  命中禁忌词：{previewResult.result.forbidden_matches.map((item) => item.word).join("、") || "无"}
                </div>
              </div>
            )}
          </GlassCard>

          <GlassCard className="p-5 space-y-4">
            <h3 className="text-base font-bold text-slate-900">会话生效策略查询</h3>
            <div className="flex gap-2">
              <Input
                value={effectiveSessionId}
                onChange={(event) => setEffectiveSessionId(event.target.value)}
                placeholder="输入 session_id"
              />
              <Button
                variant="outline"
                className="rounded-full"
                onClick={() => void loadEffectivePolicy()}
                disabled={isLoadingEffective}
              >
                {isLoadingEffective ? <Loader2 className="w-4 h-4 animate-spin" /> : "查询"}
              </Button>
            </div>

            {effectivePolicy ? (
              <pre className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs leading-relaxed overflow-auto max-h-[340px]">
                {JSON.stringify(effectivePolicy, null, 2)}
              </pre>
            ) : (
              <div className="text-sm text-slate-500">输入会话 ID 查看运行时最终生效策略。</div>
            )}
          </GlassCard>
        </div>
      </details>
    </div>
  );
}
