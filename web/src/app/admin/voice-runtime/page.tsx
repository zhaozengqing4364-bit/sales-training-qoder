"use client";

import { useEffect, useMemo, useState } from "react";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api/client";
import { Loader2, Plus, Save, Trash2, RefreshCw, Sparkles } from "lucide-react";

type VoiceMode = "legacy" | "stepfun_realtime";

interface RuntimeProfile {
    id: string;
    name: string;
    description?: string | null;
    is_default: boolean;
    is_active: boolean;
    voice_mode: VoiceMode;
    model_name: string;
    voice_name: string;
    temperature: number;
    input_audio_format: string;
    output_audio_format: string;
    output_sample_rate: number;
    turn_detection?: string | null;
    tool_policy: {
        web_search_top_k?: number;
        web_search_timeout_seconds?: number;
        retrieval_top_k?: number;
        retrieval_similarity_threshold?: number;
        retrieval_enable_hybrid?: boolean;
        retrieval_keyword_candidate_limit?: number;
    };
}

const ALLOWED_RUNTIME_TOOL_POLICY_KEYS = [
    "web_search_top_k",
    "web_search_timeout_seconds",
    "retrieval_top_k",
    "retrieval_similarity_threshold",
    "retrieval_enable_hybrid",
    "retrieval_keyword_candidate_limit",
] as const;

const DEFAULT_RUNTIME_TOOL_POLICY: RuntimeProfile["tool_policy"] = {
    web_search_top_k: 5,
    web_search_timeout_seconds: 3,
    retrieval_top_k: 5,
    retrieval_similarity_threshold: 0.65,
    retrieval_enable_hybrid: true,
    retrieval_keyword_candidate_limit: 32,
};

function sanitizeRuntimeToolPolicy(input: Record<string, unknown> | undefined) {
    const output: RuntimeProfile["tool_policy"] = { ...DEFAULT_RUNTIME_TOOL_POLICY };
    if (!input || typeof input !== "object") {
        return output;
    }
    for (const key of ALLOWED_RUNTIME_TOOL_POLICY_KEYS) {
        if (key in input) {
            (output as Record<string, unknown>)[key] = input[key];
        }
    }
    return output;
}

const EMPTY_FORM: Omit<RuntimeProfile, "id"> = {
    name: "",
    description: "",
    is_default: false,
    is_active: true,
    voice_mode: "stepfun_realtime",
    model_name: "step-audio-2",
    voice_name: "qingchunshaonv",
    temperature: 0.7,
    input_audio_format: "pcm16",
    output_audio_format: "pcm16",
    output_sample_rate: 24000,
    turn_detection: null,
    tool_policy: { ...DEFAULT_RUNTIME_TOOL_POLICY },
};

export default function VoiceRuntimePage() {
    const toast = useToast();
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [profiles, setProfiles] = useState<RuntimeProfile[]>([]);
    const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
    const [form, setForm] = useState<Omit<RuntimeProfile, "id">>(EMPTY_FORM);

    const selectedProfile = useMemo(
        () => profiles.find((profile) => profile.id === selectedProfileId) || null,
        [profiles, selectedProfileId],
    );

    const loadProfiles = async () => {
        setIsLoading(true);
        try {
            const response = await api.admin.getVoiceRuntimeProfiles();
            setProfiles(response.items as RuntimeProfile[]);
            if (response.items.length > 0) {
                const defaultProfile = (response.items as RuntimeProfile[]).find((profile) => profile.is_default);
                const initial = defaultProfile || (response.items as RuntimeProfile[])[0];
                setSelectedProfileId(initial.id);
                setForm({
                    ...EMPTY_FORM,
                    ...initial,
                    tool_policy: sanitizeRuntimeToolPolicy(initial.tool_policy as Record<string, unknown>),
                });
            } else {
                setSelectedProfileId(null);
                setForm(EMPTY_FORM);
            }
        } catch (error) {
            console.error("Failed to load runtime profiles", error);
            toast.error("加载语音策略失败");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        void loadProfiles();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const selectProfile = (profile: RuntimeProfile) => {
        setSelectedProfileId(profile.id);
        setForm({
            ...EMPTY_FORM,
            ...profile,
            tool_policy: sanitizeRuntimeToolPolicy(profile.tool_policy as Record<string, unknown>),
        });
    };

    const handleCreateNew = () => {
        setSelectedProfileId(null);
        setForm({
            ...EMPTY_FORM,
            name: `新配置-${new Date().toLocaleDateString("zh-CN")}`,
        });
    };

    const handleSave = async () => {
        if (!form.name.trim()) {
            toast.error("请先填写配置名称");
            return;
        }

        setIsSaving(true);
        try {
            const payload = {
                ...form,
                tool_policy: sanitizeRuntimeToolPolicy(form.tool_policy as Record<string, unknown>),
            };
            if (selectedProfileId) {
                await api.admin.updateVoiceRuntimeProfile(selectedProfileId, payload);
                toast.success("配置已更新");
            } else {
                await api.admin.createVoiceRuntimeProfile(payload);
                toast.success("配置已创建");
            }
            await loadProfiles();
        } catch (error) {
            console.error("Failed to save runtime profile", error);
            toast.error("保存失败");
        } finally {
            setIsSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!selectedProfileId) return;
        setIsSaving(true);
        try {
            await api.admin.deleteVoiceRuntimeProfile(selectedProfileId);
            toast.success("配置已删除");
            await loadProfiles();
        } catch (error) {
            console.error("Failed to delete runtime profile", error);
            toast.error("删除失败");
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight">语音运行时策略</h1>
                    <p className="text-slate-500 mt-1">管理 Realtime / 经典模式与底层运行参数。业务提示词已迁移到角色中心。</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" className="rounded-full" onClick={() => void loadProfiles()} disabled={isLoading}>
                        <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
                        刷新
                    </Button>
                    <Button className="rounded-full bg-slate-900 text-white" onClick={handleCreateNew}>
                        <Plus className="w-4 h-4 mr-2" />
                        新建配置
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <GlassCard className="p-4 lg:col-span-1">
                    <div className="text-sm font-bold text-slate-700 mb-3">配置列表</div>
                    {isLoading ? (
                        <div className="flex items-center justify-center py-16 text-slate-400">
                            <Loader2 className="w-5 h-5 animate-spin" />
                        </div>
                    ) : profiles.length === 0 ? (
                        <div className="text-sm text-slate-400 py-10 text-center">暂无配置，请先创建。</div>
                    ) : (
                        <div className="space-y-2">
                            {profiles.map((profile) => {
                                const active = profile.id === selectedProfileId;
                                return (
                                    <button
                                        key={profile.id}
                                        type="button"
                                        onClick={() => selectProfile(profile)}
                                        className={`w-full text-left rounded-xl border p-3 transition-all ${
                                            active
                                                ? "border-indigo-400 bg-indigo-50/60"
                                                : "border-slate-200 bg-white hover:border-slate-300"
                                        }`}
                                    >
                                        <div className="flex items-center justify-between">
                                            <div className="font-semibold text-slate-800 text-sm truncate">{profile.name}</div>
                                            <div className="flex items-center gap-1">
                                                {profile.is_default && <Badge variant="blue">默认</Badge>}
                                                {profile.voice_mode === "stepfun_realtime" && (
                                                    <Badge variant="green" className="gap-1">
                                                        <Sparkles className="w-3 h-3" />
                                                        Realtime
                                                    </Badge>
                                                )}
                                            </div>
                                        </div>
                                        <div className="text-xs text-slate-500 mt-1 truncate">
                                            {profile.model_name} · {profile.voice_name}
                                        </div>
                                    </button>
                                );
                            })}
                        </div>
                    )}
                </GlassCard>

                <GlassCard className="p-6 lg:col-span-2">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2 md:col-span-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">配置名称</label>
                            <Input
                                name="voice_runtime_profile_name"
                                autoComplete="section-voice-runtime organization-title"
                                value={form.name}
                                onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                                placeholder="例如：销售默认 Realtime"
                            />
                        </div>
                        <div className="space-y-2 md:col-span-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">描述</label>
                            <Input
                                name="voice_runtime_profile_description"
                                autoComplete="section-voice-runtime off"
                                value={form.description || ""}
                                onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
                                placeholder="描述该策略的适用场景"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">语音模式</label>
                            <select
                                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                value={form.voice_mode}
                                onChange={(event) =>
                                    setForm((prev) => ({ ...prev, voice_mode: event.target.value as VoiceMode }))
                                }
                            >
                                <option value="stepfun_realtime">StepFun Realtime</option>
                                <option value="legacy">经典链路</option>
                            </select>
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">温度</label>
                            <Input
                                name="voice_runtime_temperature"
                                autoComplete="section-voice-runtime off"
                                type="number"
                                min={0}
                                max={2}
                                step={0.1}
                                value={form.temperature}
                                onChange={(event) =>
                                    setForm((prev) => ({ ...prev, temperature: Number(event.target.value || 0.7) }))
                                }
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">模型名称</label>
                            <Input
                                name="voice_runtime_model_name"
                                autoComplete="section-voice-runtime off"
                                value={form.model_name}
                                onChange={(event) => setForm((prev) => ({ ...prev, model_name: event.target.value }))}
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">音色</label>
                            <Input
                                name="voice_runtime_voice_name"
                                autoComplete="section-voice-runtime off"
                                value={form.voice_name}
                                onChange={(event) => setForm((prev) => ({ ...prev, voice_name: event.target.value }))}
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">内部检索 TopK</label>
                            <Input
                                name="voice_runtime_retrieval_top_k"
                                autoComplete="section-voice-runtime off"
                                type="number"
                                min={1}
                                step={1}
                                value={form.tool_policy.retrieval_top_k || 5}
                                onChange={(event) =>
                                    setForm((prev) => ({
                                        ...prev,
                                        tool_policy: {
                                            ...prev.tool_policy,
                                            retrieval_top_k: Number(event.target.value || 5),
                                        },
                                    }))
                                }
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">检索相似度阈值</label>
                            <Input
                                name="voice_runtime_retrieval_similarity_threshold"
                                autoComplete="section-voice-runtime off"
                                type="number"
                                min={0}
                                max={1}
                                step={0.01}
                                value={form.tool_policy.retrieval_similarity_threshold || 0.65}
                                onChange={(event) =>
                                    setForm((prev) => ({
                                        ...prev,
                                        tool_policy: {
                                            ...prev.tool_policy,
                                            retrieval_similarity_threshold: Number(event.target.value || 0.65),
                                        },
                                    }))
                                }
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">候选关键词上限</label>
                            <Input
                                name="voice_runtime_retrieval_keyword_candidate_limit"
                                autoComplete="section-voice-runtime off"
                                type="number"
                                min={8}
                                step={1}
                                value={form.tool_policy.retrieval_keyword_candidate_limit || 32}
                                onChange={(event) =>
                                    setForm((prev) => ({
                                        ...prev,
                                        tool_policy: {
                                            ...prev.tool_policy,
                                            retrieval_keyword_candidate_limit: Number(event.target.value || 32),
                                        },
                                    }))
                                }
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">检索混合召回</label>
                            <select
                                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                value={form.tool_policy.retrieval_enable_hybrid ? "true" : "false"}
                                onChange={(event) =>
                                    setForm((prev) => ({
                                        ...prev,
                                        tool_policy: {
                                            ...prev.tool_policy,
                                            retrieval_enable_hybrid: event.target.value === "true",
                                        },
                                    }))
                                }
                            >
                                <option value="true">开启</option>
                                <option value="false">关闭</option>
                            </select>
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">联网搜索 TopK</label>
                            <Input
                                name="voice_runtime_web_search_top_k"
                                autoComplete="section-voice-runtime off"
                                type="number"
                                min={1}
                                step={1}
                                value={form.tool_policy.web_search_top_k || 5}
                                onChange={(event) =>
                                    setForm((prev) => ({
                                        ...prev,
                                        tool_policy: {
                                            ...prev.tool_policy,
                                            web_search_top_k: Number(event.target.value || 5),
                                        },
                                    }))
                                }
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">联网超时秒数</label>
                            <Input
                                name="voice_runtime_web_search_timeout"
                                autoComplete="section-voice-runtime off"
                                type="number"
                                min={1}
                                step={1}
                                value={form.tool_policy.web_search_timeout_seconds || 3}
                                onChange={(event) =>
                                    setForm((prev) => ({
                                        ...prev,
                                        tool_policy: {
                                            ...prev.tool_policy,
                                            web_search_timeout_seconds: Number(event.target.value || 3),
                                        },
                                    }))
                                }
                            />
                        </div>
                        <div className="md:col-span-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
                            角色中心已接管策略锁：联网开关、内部检索开关、检索优先级、知识库强制模式等能力请前往角色中心配置。
                        </div>
                    </div>

                    <div className="mt-6 flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <label className="flex items-center gap-2 text-sm text-slate-600">
                                <input
                                    type="checkbox"
                                    checked={form.is_default}
                                    onChange={(event) => setForm((prev) => ({ ...prev, is_default: event.target.checked }))}
                                />
                                设为默认配置
                            </label>
                            <label className="flex items-center gap-2 text-sm text-slate-600">
                                <input
                                    type="checkbox"
                                    checked={form.is_active}
                                    onChange={(event) => setForm((prev) => ({ ...prev, is_active: event.target.checked }))}
                                />
                                启用
                            </label>
                        </div>
                        <div className="flex gap-2">
                            {selectedProfile && (
                                <Button
                                    variant="outline"
                                    className="rounded-full border-red-200 text-red-600 hover:bg-red-50"
                                    onClick={() => void handleDelete()}
                                    disabled={isSaving}
                                >
                                    <Trash2 className="w-4 h-4 mr-2" />
                                    删除
                                </Button>
                            )}
                            <Button className="rounded-full bg-slate-900 text-white" onClick={() => void handleSave()} disabled={isSaving}>
                                {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                                保存
                            </Button>
                        </div>
                    </div>
                </GlassCard>
            </div>
        </div>
    );
}
