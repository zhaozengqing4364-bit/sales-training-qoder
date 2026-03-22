"use client";

import { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { ArrowLeft, Save, Trash2, Loader2, Plus, User, GripVertical, Star, X, Database } from "lucide-react";
import { api } from "@/lib/api/client";
import { AdminAgent, AdminPersona } from "@/lib/api/types";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/glass-modal";

interface LinkedPersona extends AdminPersona {
    persona_id: string;
    is_default: boolean;
}

interface ModelConfigListItem {
    id: string;
    name: string;
    model_type: string;
    provider: string;
    model_name: string;
    is_default: boolean;
    is_active: boolean;
    last_test_status: string | null;
}

interface ModelConfigListResponse {
    llm: ModelConfigListItem[];
    embedding: ModelConfigListItem[];
    asr: ModelConfigListItem[];
    tts: ModelConfigListItem[];
    total: number;
}

interface RuntimeProfileItem {
    id: string;
    name: string;
    voice_mode: "legacy" | "stepfun_realtime";
    model_name: string;
    voice_name: string;
    is_default: boolean;
    is_active: boolean;
}

interface AgentVoicePolicyConfig {
    enabled: boolean;
    runtime_profile_id?: string | null;
    voice_mode_override?: "legacy" | "stepfun_realtime" | null;
}

const DIFFICULTY_MAP: Record<string, { label: string; color: string }> = {
    easy: { label: "简单", color: "text-emerald-600 bg-emerald-50" },
    medium: { label: "中等", color: "text-blue-600 bg-blue-50" },
    hard: { label: "困难", color: "text-orange-600 bg-orange-50" },
};

// 能力配置定义
interface CapabilityConfig {
    enabled: boolean;
    [key: string]: unknown;
}

interface CapabilitiesConfig {
    fuzzy_detection?: CapabilityConfig;
    sales_stage?: CapabilityConfig;
    realtime_scoring?: CapabilityConfig;
    knowledge_retrieval?: CapabilityConfig;
    llm?: CapabilityConfig;
    [key: string]: CapabilityConfig | undefined;
}

// 能力模块元数据
const CAPABILITY_METADATA: Record<string, { name: string; description: string; icon: string }> = {
    fuzzy_detection: {
        name: "模糊词检测",
        description: "检测用户话语中的模糊词汇并给出提示",
        icon: "🔍",
    },
    sales_stage: {
        name: "销售阶段追踪",
        description: "自动识别和追踪当前销售对话阶段",
        icon: "📊",
    },
    realtime_scoring: {
        name: "实时评分",
        description: "对话过程中展示实时维度评分",
        icon: "⭐",
    },
    knowledge_retrieval: {
        name: "知识库检索",
        description: "对话时自动检索关联知识库的相关内容",
        icon: "📚",
    },
};

export default function AgentEditPage({ params }: { params: Promise<{ id: string }> }) {
    const router = useRouter();
    const toast = useToast();
    const { id } = use(params);

    const [agent, setAgent] = useState<AdminAgent | null>(null);
    const [linkedPersonas, setLinkedPersonas] = useState<LinkedPersona[]>([]);
    const [availablePersonas, setAvailablePersonas] = useState<AdminPersona[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);

    // Add Persona Dialog
    const [isAddPersonaOpen, setIsAddPersonaOpen] = useState(false);
    const [selectedPersonaId, setSelectedPersonaId] = useState<string>("");
    const [isAddingPersona, setIsAddingPersona] = useState(false);

    // Remove Persona Confirm
    const [removeTarget, setRemoveTarget] = useState<LinkedPersona | null>(null);
    const [isRemoving, setIsRemoving] = useState(false);

    const [llmConfigs, setLlmConfigs] = useState<ModelConfigListItem[]>([]);
    const [runtimeProfiles, setRuntimeProfiles] = useState<RuntimeProfileItem[]>([]);
    const [agentVoicePolicy, setAgentVoicePolicy] = useState<AgentVoicePolicyConfig>({
        enabled: true,
        runtime_profile_id: null,
        voice_mode_override: null,
    });
    const [isSavingVoicePolicy, setIsSavingVoicePolicy] = useState(false);

    useEffect(() => {
        const loadData = async () => {
            try {
                const [agentData, personasData, allPersonas, modelConfigsData, voiceProfiles, voicePolicy] = await Promise.all([
                    api.admin.getAgent(id),
                    api.admin.getAgentPersonas(id),
                    api.admin.getPersonas({ page_size: 100 }),
                    api.admin.getModelConfigs(),
                    api.admin.getVoiceRuntimeProfiles({ only_active: true }),
                    api.admin.getAgentVoicePolicy(id),
                ]);
                setAgent(agentData);
                setLinkedPersonas(personasData as LinkedPersona[]);
                setAvailablePersonas(allPersonas.items || []);
                setRuntimeProfiles((voiceProfiles.items || []) as RuntimeProfileItem[]);
                setAgentVoicePolicy({
                    enabled: (voicePolicy as AgentVoicePolicyConfig).enabled ?? true,
                    runtime_profile_id: (voicePolicy as AgentVoicePolicyConfig).runtime_profile_id || null,
                    voice_mode_override: (voicePolicy as AgentVoicePolicyConfig).voice_mode_override || null,
                });

                const modelConfigs = modelConfigsData as ModelConfigListResponse | ModelConfigListItem[];
                const llmModelList = Array.isArray(modelConfigs)
                    ? modelConfigs.filter((item) => item.model_type === "llm")
                    : modelConfigs.llm;
                setLlmConfigs(llmModelList.filter((item) => item.is_active));
            } catch (err) {
                console.error("Failed to load agent:", err);
                toast.error("加载失败");
            } finally {
                setIsLoading(false);
            }
        };
        loadData();
    }, [id, toast]);

    const handleSave = async () => {
        if (!agent) return;
        setIsSaving(true);
        try {
            await api.admin.updateAgent(id, {
                name: agent.name,
                description: agent.description,
                icon: agent.icon,
                category: agent.category,
                welcome_message: agent.welcome_message,
                capabilities_config: agent.capabilities_config,
            });
            toast.success("保存成功");
        } catch (err) {
            console.error("Failed to update agent:", err);
            toast.error("保存失败");
        } finally {
            setIsSaving(false);
        }
    };

    const handleSaveVoicePolicy = async () => {
        setIsSavingVoicePolicy(true);
        try {
            await api.admin.updateAgentVoicePolicy(id, {
                enabled: agentVoicePolicy.enabled,
                runtime_profile_id: agentVoicePolicy.runtime_profile_id || null,
                voice_mode_override: agentVoicePolicy.voice_mode_override || null,
            });
            toast.success("语音策略已保存");
        } catch (err) {
            console.error("Failed to update voice policy:", err);
            toast.error("语音策略保存失败");
        } finally {
            setIsSavingVoicePolicy(false);
        }
    };

    const handleAddPersona = async () => {
        if (!selectedPersonaId) {
            toast.error("请选择一个角色");
            return;
        }

        setIsAddingPersona(true);
        try {
            await api.admin.addPersonaToAgent(id, {
                persona_id: selectedPersonaId,
                is_default: linkedPersonas.length === 0,
            });

            // Reload linked personas
            const updated = await api.admin.getAgentPersonas(id);
            setLinkedPersonas(updated as LinkedPersona[]);

            setIsAddPersonaOpen(false);
            setSelectedPersonaId("");
            toast.success("角色关联成功");
        } catch (err) {
            console.error("Failed to add persona:", err);
            toast.error("关联失败");
        } finally {
            setIsAddingPersona(false);
        }
    };

    const handleRemovePersona = async () => {
        if (!removeTarget) return;

        setIsRemoving(true);
        try {
            await api.admin.removePersonaFromAgent(id, removeTarget.persona_id);
            setLinkedPersonas(prev => prev.filter(p => p.persona_id !== removeTarget.persona_id));
            setRemoveTarget(null);
            toast.success("已移除角色");
        } catch (err) {
            console.error("Failed to remove persona:", err);
            toast.error("移除失败");
        } finally {
            setIsRemoving(false);
        }
    };

    const handleSetDefault = async (persona: LinkedPersona) => {
        try {
            await api.admin.updateAgentPersona(id, persona.persona_id, {
                is_default: true,
            });

            // Update local state
            setLinkedPersonas(prev => prev.map(p => ({
                ...p,
                is_default: p.persona_id === persona.persona_id,
            })));
            toast.success("已设为默认角色");
        } catch (err) {
            console.error("Failed to set default:", err);
            toast.error("设置失败");
        }
    };

    // Filter out already linked personas
    const unlinkedPersonas = availablePersonas.filter(
        p => !linkedPersonas.some(lp => lp.persona_id === p.id)
    );

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
            </div>
        );
    }

    if (!agent) {
        return <div className="p-8 text-center text-red-500">未找到智能体</div>;
    }

    const llmSettings = (
        ((agent.capabilities_config as CapabilitiesConfig)?.llm as CapabilityConfig | undefined) ?? {}
    ) as CapabilityConfig;
    const selectedModelConfigId = typeof llmSettings["model_config_id"] === "string"
        ? (llmSettings["model_config_id"] as string)
        : "";

    return (
        <div className="space-y-6 max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Remove Persona Confirm */}
            <ConfirmDialog
                open={!!removeTarget}
                onOpenChange={(open) => !open && setRemoveTarget(null)}
                title="移除角色"
                description={`确定要从该智能体移除「${removeTarget?.name}」吗？`}
                confirmText="移除"
                variant="danger"
                onConfirm={handleRemovePersona}
                isLoading={isRemoving}
            />

            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Button variant="ghost" size="icon" onClick={() => router.back()} className="rounded-full">
                        <ArrowLeft className="w-5 h-5" />
                    </Button>
                    <h1 className="text-2xl font-bold text-slate-800">编辑智能体</h1>
                </div>
                <div className="flex gap-2">
                    <Button variant="ghost" className="text-red-500 hover:text-red-600 hover:bg-red-50 rounded-full">
                        <Trash2 className="w-4 h-4 mr-2" />
                        删除
                    </Button>
                    <Button
                        onClick={handleSave}
                        disabled={isSaving}
                        className="bg-slate-900 hover:bg-slate-800 text-white shadow-lg shadow-slate-900/20 rounded-full px-6"
                    >
                        {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                        保存修改
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Main Info */}
                <GlassCard className="md:col-span-2 p-8 space-y-6">
                    <div className="space-y-2">
                        <label className="text-xs font-bold text-slate-400 uppercase tracking-widest">智能体名称</label>
                        <Input
                            value={agent.name}
                            onChange={(e) => setAgent({ ...agent, name: e.target.value })}
                            className="bg-slate-50 border-slate-200"
                        />
                    </div>
                    <div className="space-y-2">
                        <label className="text-xs font-bold text-slate-400 uppercase tracking-widest">描述</label>
                        <textarea
                            className="flex min-h-[120px] w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                            value={agent.description ?? ""}
                            onChange={(e) => setAgent({ ...agent, description: e.target.value })}
                        />
                    </div>

                    {/* Linked Personas Section */}
                    <div className="pt-4">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-sm font-bold text-slate-800">关联角色</h3>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-full"
                                onClick={() => setIsAddPersonaOpen(true)}
                            >
                                <Plus className="w-4 h-4 mr-1" />
                                添加角色
                            </Button>
                        </div>

                        {linkedPersonas.length === 0 ? (
                            <div
                                className="text-center py-12 border-2 border-dashed border-slate-200 rounded-2xl cursor-pointer hover:border-blue-300 hover:bg-blue-50/30 transition-all"
                                onClick={() => setIsAddPersonaOpen(true)}
                            >
                                <User className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                                <p className="text-sm text-slate-400">暂无关联角色</p>
                                <p className="text-xs text-slate-400 mt-1">点击添加角色，用户可在练习时选择</p>
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {linkedPersonas.map((lp) => {
                                    const diffConfig = DIFFICULTY_MAP[lp.difficulty] || DIFFICULTY_MAP.medium;
                                    return (
                                        <div
                                            key={lp.id}
                                            className="flex items-center gap-3 p-4 rounded-2xl border border-slate-100 bg-slate-50/50 group hover:bg-white hover:border-slate-200 transition-all"
                                        >
                                            <GripVertical className="w-4 h-4 text-slate-300 cursor-grab" />
                                            <span className="text-2xl">{lp.icon || "👤"}</span>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-bold text-slate-800">{lp.name}</span>
                                                    {lp.is_default && (
                                                        <Badge variant="blue" className="text-[10px]">默认</Badge>
                                                    )}
                                                </div>
                                                <span className={`text-xs px-2 py-0.5 rounded-full ${diffConfig.color}`}>
                                                    {diffConfig.label}
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                {!lp.is_default && (
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-8 w-8 text-slate-400 hover:text-amber-500 hover:bg-amber-50 rounded-full"
                                                        onClick={() => handleSetDefault(lp)}
                                                        title="设为默认"
                                                    >
                                                        <Star className="w-4 h-4" />
                                                    </Button>
                                                )}
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-8 w-8 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-full"
                                                    onClick={() => setRemoveTarget(lp)}
                                                >
                                                    <X className="w-4 h-4" />
                                                </Button>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>

                    {/* Capabilities */}
                    <div className="pt-4">
                        <h3 className="text-sm font-bold text-slate-800 mb-4">能力配置</h3>
                        <p className="text-xs text-slate-500 mb-4">启用的能力将在对话过程中自动执行</p>
                        <div className="grid grid-cols-1 gap-3">
                            {Object.entries(CAPABILITY_METADATA).map(([capId, meta]) => {
                                const capConfig = (agent.capabilities_config as CapabilitiesConfig)?.[capId];
                                const isEnabled = capConfig?.enabled ?? false;

                                return (
                                    <div
                                        key={capId}
                                        className={`flex items-center justify-between p-4 rounded-2xl border transition-all ${isEnabled
                                            ? "border-blue-200 bg-blue-50/30"
                                            : "border-slate-100 bg-slate-50/50"
                                            }`}
                                    >
                                        <div className="flex items-center gap-3">
                                            <span className="text-xl">{meta.icon}</span>
                                            <div>
                                                <div className="text-sm font-bold text-slate-800">{meta.name}</div>
                                                <div className="text-xs text-slate-500">{meta.description}</div>
                                            </div>
                                        </div>
                                        <label className="relative inline-flex items-center cursor-pointer">
                                            <input
                                                type="checkbox"
                                                className="sr-only peer"
                                                checked={isEnabled}
                                                onChange={(e) => {
                                                    const newConfig = {
                                                        ...(agent.capabilities_config as CapabilitiesConfig || {}),
                                                        [capId]: {
                                                            ...capConfig,
                                                            enabled: e.target.checked,
                                                        },
                                                    };
                                                    setAgent({ ...agent, capabilities_config: newConfig });
                                                }}
                                            />
                                            <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                                        </label>
                                    </div>
                                );
                            })}
                        </div>

                        <div className="mt-3 p-3 rounded-xl bg-amber-50 border border-amber-200">
                            <p className="text-xs text-amber-700">
                                角色与知识库策略已收敛到「角色中心」。智能体页仅负责能力开关与运行时技术参数。
                            </p>
                        </div>
                    </div>
                </GlassCard>

                {/* Side Settings */}
                <div className="space-y-6">
                    <GlassCard className="p-6">
                        <h3 className="text-sm font-bold text-slate-800 mb-4">模型设置</h3>
                        <div className="space-y-4">
                            <div className="space-y-2">
                                <label className="text-[10px] font-bold text-slate-400 uppercase">LLM 配置</label>
                                <select
                                    className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none"
                                    value={selectedModelConfigId}
                                    onChange={(e) => {
                                        const configId = e.target.value;
                                        const capabilities = { ...(agent.capabilities_config as CapabilitiesConfig || {}) };
                                        capabilities.llm = {
                                            ...(capabilities.llm || {}),
                                            enabled: true,
                                        };

                                        if (configId) {
                                            capabilities.llm.model_config_id = configId;
                                        } else {
                                            delete capabilities.llm.model_config_id;
                                        }

                                        setAgent({ ...agent, capabilities_config: capabilities });
                                    }}
                                >
                                    <option value="">系统默认模型（按全局默认）</option>
                                    {llmConfigs.map((config) => (
                                        <option key={config.id} value={config.id}>
                                            {config.name} · {config.provider}/{config.model_name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="space-y-2">
                                <label className="text-[10px] font-bold text-slate-400 uppercase">说明</label>
                                <p className="text-xs text-slate-500 leading-relaxed">
                                    当前智能体可指定专属 LLM 配置；留空则使用系统默认。温度、超时等参数请在「系统设置 → 模型配置」中配置到对应模型。
                                </p>
                            </div>
                        </div>
                    </GlassCard>

                    <GlassCard className="p-6">
                        <h3 className="text-sm font-bold text-slate-800 mb-4">语音策略（Realtime）</h3>
                        <div className="space-y-4">
                            <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                                <span className="text-sm text-slate-700">启用 Agent 语音策略</span>
                                <label className="relative inline-flex items-center cursor-pointer">
                                    <input
                                        type="checkbox"
                                        className="sr-only peer"
                                        checked={agentVoicePolicy.enabled}
                                        onChange={(e) =>
                                            setAgentVoicePolicy((prev) => ({
                                                ...prev,
                                                enabled: e.target.checked,
                                            }))
                                        }
                                    />
                                    <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                                </label>
                            </div>

                            <div className="space-y-2">
                                <label className="text-[10px] font-bold text-slate-400 uppercase">运行时配置档</label>
                                <select
                                    className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none"
                                    value={agentVoicePolicy.runtime_profile_id || ""}
                                    onChange={(e) =>
                                        setAgentVoicePolicy((prev) => ({
                                            ...prev,
                                            runtime_profile_id: e.target.value || null,
                                        }))
                                    }
                                >
                                    <option value="">跟随系统默认</option>
                                    {runtimeProfiles.map((profile) => (
                                        <option key={profile.id} value={profile.id}>
                                            {profile.name} · {profile.voice_mode === "stepfun_realtime" ? "Realtime" : "经典"}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div className="space-y-2">
                                <label className="text-[10px] font-bold text-slate-400 uppercase">模式覆盖</label>
                                <select
                                    className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none"
                                    value={agentVoicePolicy.voice_mode_override || ""}
                                    onChange={(e) =>
                                        setAgentVoicePolicy((prev) => ({
                                            ...prev,
                                            voice_mode_override: (e.target.value as "legacy" | "stepfun_realtime" | "") || null,
                                        }))
                                    }
                                >
                                    <option value="">不覆盖（跟随配置档）</option>
                                    <option value="stepfun_realtime">强制 Realtime</option>
                                    <option value="legacy">强制经典链路</option>
                                </select>
                            </div>
                            <div className="rounded-xl border border-blue-200 bg-blue-50 p-3">
                                <p className="text-xs text-blue-700 leading-relaxed">
                                    业务提示词、知识库策略和检索规则已迁移到角色中心。此处仅保留运行时配置档与模式覆盖，不再支持业务策略覆盖。
                                </p>
                            </div>

                            <Button
                                className="rounded-full bg-slate-900 text-white"
                                onClick={handleSaveVoicePolicy}
                                disabled={isSavingVoicePolicy}
                            >
                                {isSavingVoicePolicy ? (
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                ) : (
                                    <Save className="w-4 h-4 mr-2" />
                                )}
                                保存语音策略
                            </Button>
                        </div>
                    </GlassCard>

                    <GlassCard className="p-6">
                        <div className="flex items-start gap-3">
                            <Database className="w-5 h-5 text-blue-500 mt-0.5" />
                            <div>
                                <h3 className="text-sm font-bold text-slate-800">知识库归属</h3>
                                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                                    智能体级知识库入口已关闭。请在「角色管理」中为具体角色绑定知识库，运行时将按角色策略强制生效。
                                </p>
                            </div>
                        </div>
                    </GlassCard>
                </div>
            </div>

            {/* Add Persona Dialog */}
            <Dialog open={isAddPersonaOpen} onOpenChange={setIsAddPersonaOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>添加角色</DialogTitle>
                        <DialogDescription>选择一个角色关联到该智能体，用户练习时可以选择。</DialogDescription>
                    </DialogHeader>
                    <div className="py-6">
                        {unlinkedPersonas.length === 0 ? (
                            <div className="text-center py-8 text-slate-400">
                                <p>没有可添加的角色</p>
                                <p className="text-xs mt-1">请先在角色管理中创建角色</p>
                            </div>
                        ) : (
                            <div className="space-y-2 max-h-[300px] overflow-y-auto">
                                {unlinkedPersonas.map((persona) => {
                                    const diffConfig = DIFFICULTY_MAP[persona.difficulty || "medium"] || DIFFICULTY_MAP.medium;
                                    const isSelected = selectedPersonaId === persona.id;
                                    return (
                                        <div
                                            key={persona.id}
                                            onClick={() => setSelectedPersonaId(persona.id)}
                                            className={`flex items-center gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all ${isSelected
                                                ? "border-blue-500 bg-blue-50/50"
                                                : "border-slate-100 hover:border-slate-200 hover:bg-slate-50"
                                                }`}
                                        >
                                            <span className="text-2xl">{persona.icon || "👤"}</span>
                                            <div className="flex-1">
                                                <div className="font-bold text-slate-800">{persona.name}</div>
                                                <div className="flex items-center gap-2 mt-1">
                                                    <span className={`text-xs px-2 py-0.5 rounded-full ${diffConfig.color}`}>
                                                        {diffConfig.label}
                                                    </span>
                                                    {persona.description && (
                                                        <span className="text-xs text-slate-400 truncate max-w-[150px]">
                                                            {persona.description}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                            <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${isSelected ? "border-blue-500 bg-blue-500" : "border-slate-300"
                                                }`}>
                                                {isSelected && <div className="w-2 h-2 rounded-full bg-white" />}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                    <DialogFooter>
                        <Button
                            variant="ghost"
                            className="rounded-full"
                            onClick={() => setIsAddPersonaOpen(false)}
                        >
                            取消
                        </Button>
                        <Button
                            className="rounded-full bg-slate-900 text-white"
                            onClick={handleAddPersona}
                            disabled={!selectedPersonaId || isAddingPersona}
                        >
                            {isAddingPersona ? "添加中..." : "添加"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

        </div>
    );
}
