"use client";
import { debug } from "@/lib/debug";

import { useEffect, useState, useRef } from "react";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
    Settings,
    Globe,
    Shield,
    Bell,
    Save,
    RefreshCw,
    Lock,
    Key,
    Mail,
    Cpu,
    MessageSquare,
    Mic,
    Volume2,
    Plus,
    Edit2,
    Trash2,
    CheckCircle2,
    XCircle,
    Loader2,
    Star,
    Zap,
    Square,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/glass-modal";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    AdminModelConfigCreateRequest as CreateModelConfigRequest,
    AdminModelConfigDetail as ModelConfigDetail,
    AdminModelConfigGrouped as ModelConfigListResponse,
    AdminModelConfigListItem as ModelConfigItem,
    AdminModelConfigProvider as ModelProvider,
    AdminModelConfigTestResponse,
    AdminModelConfigTestRequest,
    AdminModelConfigType as ModelType,
    AdminModelConfigUpdateRequest as UpdateModelConfigRequest,
} from "@/lib/api/types";

const MODEL_TYPE_CONFIG = {
    llm: {
        label: "LLM 大语言模型",
        icon: MessageSquare,
        color: "text-blue-600",
        bgColor: "bg-blue-50",
        description: "用于对话生成、文本理解等任务",
    },
    embedding: {
        label: "Embedding 向量模型",
        icon: Cpu,
        color: "text-purple-600",
        bgColor: "bg-purple-50",
        description: "用于文本向量化、语义搜索",
    },
    asr: {
        label: "ASR 语音识别",
        icon: Mic,
        color: "text-emerald-600",
        bgColor: "bg-emerald-50",
        description: "将语音转换为文字",
    },
    tts: {
        label: "TTS 语音合成",
        icon: Volume2,
        color: "text-orange-600",
        bgColor: "bg-orange-50",
        description: "将文字转换为语音",
    },
};

const SETTINGS_READ_ONLY_TABS = new Set(["general", "security", "notifications"]);

const READ_ONLY_SETTINGS_NOTICE = "这些配置项当前为只读治理视图；保存入口仅在接入校验、权限、审计与回滚后开放。";

const readOnlyInputClassName = "bg-slate-100 border-slate-200 text-slate-500 cursor-not-allowed";

const readOnlySelectClassName = "w-full p-3 rounded-xl border border-slate-200 bg-slate-100 outline-none font-medium text-slate-500 cursor-not-allowed";

const readOnlyTextareaClassName = "w-full p-3 rounded-xl border border-slate-200 bg-slate-100 outline-none transition-all font-medium text-slate-500 h-24 resize-none cursor-not-allowed";

function ReadOnlySettingsNotice() {
    return (
        <div role="status" className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {READ_ONLY_SETTINGS_NOTICE}
        </div>
    );
}

const PROVIDER_OPTIONS: { value: ModelProvider; label: string }[] = [
    { value: "openai", label: "OpenAI" },
    { value: "azure", label: "Azure OpenAI" },
    { value: "alibaba", label: "阿里云" },
    { value: "anthropic", label: "Anthropic" },
    { value: "local", label: "本地/其他" },
    { value: "local_streaming", label: "本地流式（ASR）" },
];

const MODEL_PROVIDER_MAP: Record<ModelType, ModelProvider[]> = {
    llm: ["openai", "azure", "alibaba", "anthropic"],
    embedding: ["openai", "azure"],
    asr: ["alibaba", "local", "local_streaming"],
    tts: ["alibaba", "local"],
};

function requiresApiKey(modelType: ModelType, provider: ModelProvider) {
    if (modelType === "tts" && provider === "local") return false;
    if (modelType === "asr" && (provider === "local" || provider === "local_streaming")) return false;
    return true;
}

function requiresBaseUrl(modelType: ModelType, provider: ModelProvider) {
    if (modelType === "tts") return false;
    if (modelType === "asr" && (provider === "local" || provider === "local_streaming")) return false;
    return true;
}

function getTestStatusBadge(status: string | null) {
    if (status === "success") {
        return (
            <Badge variant="green" className="gap-1">
                <CheckCircle2 className="w-3 h-3" /> 已验证
            </Badge>
        );
    }
    if (status === "failed") {
        return (
            <Badge variant="red" className="gap-1">
                <XCircle className="w-3 h-3" /> 验证失败
            </Badge>
        );
    }
    return <Badge variant="gray" className="gap-1">未测试</Badge>;
}

export default function SettingsPage() {
    const toast = useToast();
    const [activeTab, setActiveTab] = useState("general");

    // Model config states
    const [configs, setConfigs] = useState<ModelConfigListResponse | null>(null);
    const [isLoadingModels, setIsLoadingModels] = useState(false);
    const [activeModelType, setActiveModelType] = useState<ModelType>("llm");
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [isEditOpen, setIsEditOpen] = useState(false);
    const [editingConfig, setEditingConfig] = useState<ModelConfigDetail | null>(null);
    const [deleteTarget, setDeleteTarget] = useState<ModelConfigItem | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);
    const [formData, setFormData] = useState<CreateModelConfigRequest>({
        name: "",
        model_type: "llm",
        provider: "openai",
        base_url: "",
        api_key: "",
        model_name: "",
        extra_config: {},
        is_default: false,
    });
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isTesting, setIsTesting] = useState(false);
    const [testResult, setTestResult] = useState<AdminModelConfigTestResponse | null>(null);
    const [isPreviewingTTS, setIsPreviewingTTS] = useState(false);
    const previewAudioRef = useRef<HTMLAudioElement | null>(null);

    // TTS 试听功能
    const handlePreviewTTS = async () => {
        setIsPreviewingTTS(true);
        try {
            // 停止之前的播放
            if (previewAudioRef.current) {
                previewAudioRef.current.pause();
                previewAudioRef.current = null;
            }

            const extra = formData.extra_config as { rate?: string; volume?: string; pitch?: string } || {};
            const blob = await api.admin.previewTTSBlob({
                text: "你好，这是一段语音试听测试，用于预览当前的语速、音量和音调设置。",
                voice: formData.model_name || "zh-CN-XiaoxiaoNeural",
                rate: extra.rate || "+0%",
                volume: extra.volume || "+0%",
                pitch: extra.pitch || "+0Hz",
            });

            const audioUrl = URL.createObjectURL(blob);
            const audio = new Audio(audioUrl);
            previewAudioRef.current = audio;
            
            audio.onended = () => {
                setIsPreviewingTTS(false);
                URL.revokeObjectURL(audioUrl);
            };
            audio.onerror = () => {
                setIsPreviewingTTS(false);
                toast.error("音频播放失败");
            };
            
            await audio.play();
        } catch (err) {
            debug.error("TTS preview failed:", err);
            toast.error(getApiErrorMessage(err));
            setIsPreviewingTTS(false);
        }
    };

    const stopPreviewTTS = () => {
        if (previewAudioRef.current) {
            previewAudioRef.current.pause();
            previewAudioRef.current = null;
        }
        setIsPreviewingTTS(false);
    };

    const tabs = [
        { id: "general", label: "常规设置", icon: Globe },
        { id: "security", label: "安全与访问", icon: Shield },
        { id: "notifications", label: "通知设置", icon: Bell },
        { id: "models", label: "模型配置", icon: Cpu },
    ];

    const loadConfigs = async () => {
        setIsLoadingModels(true);
        try {
            const data = await api.admin.getModelConfigs();
            setConfigs(data);
        } catch (err) {
            debug.error("Failed to load model configs:", err);
            toast.error("加载配置失败");
        } finally {
            setIsLoadingModels(false);
        }
    };

    // Load model configs when switching to models tab
    useEffect(() => {
        if (activeTab === "models" && !configs) {
            void Promise.resolve().then(loadConfigs);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeTab]);

    const resetForm = () => {
        const defaultProvider = MODEL_PROVIDER_MAP[activeModelType][0];
        setFormData({
            name: "",
            model_type: activeModelType,
            provider: defaultProvider,
            base_url: "",
            api_key: "",
            model_name: "",
            extra_config: {},
            is_default: false,
        });
        setTestResult(null);
    };

    const handleCreate = async () => {
        const apiKeyRequired = requiresApiKey(formData.model_type, formData.provider);
        const baseUrlRequired = requiresBaseUrl(formData.model_type, formData.provider);

        if (
            !formData.name.trim() ||
            (baseUrlRequired && !formData.base_url.trim()) ||
            (apiKeyRequired && !formData.api_key.trim()) ||
            !formData.model_name.trim()
        ) {
            toast.error("请填写所有必填字段");
            return;
        }
        setIsSubmitting(true);
        try {
            await api.admin.createModelConfig(formData);
            toast.success("配置创建成功");
            setIsCreateOpen(false);
            resetForm();
            loadConfigs();
        } catch (err) {
            debug.error("Failed to create config:", err);
            toast.error(`创建失败: ${err instanceof Error ? err.message : "未知错误"}`);
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleOpenEdit = async (config: ModelConfigItem) => {
        try {
            const detail = await api.admin.getModelConfig(config.id);
            setEditingConfig(detail);
            setFormData({
                name: detail.name,
                model_type: detail.model_type,
                provider: detail.provider,
                base_url: detail.base_url,
                api_key: "",
                model_name: detail.model_name,
                extra_config: detail.extra_config,
                is_default: detail.is_default,
            });
            setIsEditOpen(true);
        } catch (err) {
            debug.error("Failed to load config detail:", err);
            toast.error("加载配置详情失败");
        }
    };

    const handleUpdate = async () => {
        if (!editingConfig) return;
        const modelType = editingConfig.model_type;
        const provider = editingConfig.provider;
        const baseUrlRequired = requiresBaseUrl(modelType, provider);
        const apiKeyRequired = requiresApiKey(modelType, provider);

        if (!formData.name.trim() || !formData.model_name.trim()) {
            toast.error("请填写所有必填字段");
            return;
        }
        if (baseUrlRequired && !formData.base_url.trim()) {
            toast.error("当前提供商需要填写 API 地址");
            return;
        }
        if (apiKeyRequired && editingConfig.api_key_masked === "未设置" && !formData.api_key.trim()) {
            toast.error("当前提供商需要 API Key");
            return;
        }

        setIsSubmitting(true);
        try {
            const updateData: UpdateModelConfigRequest = {
                name: formData.name,
                base_url: formData.base_url,
                model_name: formData.model_name,
                extra_config: formData.extra_config,
                is_default: formData.is_default,
            };
            if (formData.api_key.trim()) {
                updateData.api_key = formData.api_key;
            }
            await api.admin.updateModelConfig(editingConfig.id, updateData);
            toast.success("配置更新成功");
            setIsEditOpen(false);
            setEditingConfig(null);
            resetForm();
            loadConfigs();
        } catch (err) {
            debug.error("Failed to update config:", err);
            toast.error(`更新失败: ${err instanceof Error ? err.message : "未知错误"}`);
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteTarget) return;
        setIsDeleting(true);
        try {
            await api.admin.deleteModelConfig(deleteTarget.id);
            toast.success("配置已删除");
            setDeleteTarget(null);
            loadConfigs();
        } catch (err) {
            debug.error("Failed to delete config:", err);
            toast.error(`删除失败: ${err instanceof Error ? err.message : "未知错误"}`);
        } finally {
            setIsDeleting(false);
        }
    };

    const handleTestConnection = async (configId?: string) => {
        setIsTesting(true);
        setTestResult(null);
        try {
            let result;
            if (configId) {
                result = await api.admin.testModelConfig(configId);
            } else {
                const testPayload: AdminModelConfigTestRequest = {
                    model_type: formData.model_type,
                    provider: formData.provider,
                    base_url: formData.base_url,
                    api_key: formData.api_key,
                    model_name: formData.model_name,
                    extra_config: formData.extra_config || {},
                };
                result = await api.admin.testModelConfigInline(testPayload);
            }
            setTestResult({ success: result.success, message: result.message });
            if (result.success) {
                toast.success("连接测试成功");
                if (configId) loadConfigs();
            } else {
                toast.error(`测试失败: ${result.message}`);
            }
        } catch (err) {
            debug.error("Test failed:", err);
            const message = err instanceof Error ? err.message : "测试失败";
            setTestResult({ success: false, message });
            toast.error(message);
        } finally {
            setIsTesting(false);
        }
    };

    const handleSetDefault = async (config: ModelConfigItem) => {
        if (config.is_default) return;
        try {
            await api.admin.updateModelConfig(config.id, { is_default: true });
            toast.success(`已将「${config.name}」设为默认`);
            loadConfigs();
        } catch (err) {
            debug.error("Failed to set default:", err);
            toast.error("设置默认失败");
        }
    };

    const currentConfigs = configs ? configs[activeModelType] : [];


    const renderContent = () => {
        switch (activeTab) {
            case "general":
                return (
                    <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
                        <ReadOnlySettingsNotice />
                        <GlassCard className="p-8">
                            <h3 className="text-lg font-bold text-slate-900 mb-6 flex items-center gap-2">
                                <Globe className="w-5 h-5 text-blue-500" /> 平台信息
                            </h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">平台名称</label>
                                    <Input value="Intelligent Coach AI" readOnly aria-describedby="settings-readonly-notice" className={readOnlyInputClassName} />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">支持邮箱</label>
                                    <Input value="support@company.com" readOnly aria-describedby="settings-readonly-notice" className={readOnlyInputClassName} />
                                </div>
                                <div className="col-span-2 space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">欢迎语</label>
                                    <textarea value="欢迎使用高级训练平台，开启您的学习之旅！" readOnly aria-describedby="settings-readonly-notice" className={readOnlyTextareaClassName} />
                                </div>
                            </div>
                        </GlassCard>

                        <GlassCard className="p-8">
                            <h3 className="text-lg font-bold text-slate-900 mb-6 flex items-center gap-2">
                                <Settings className="w-5 h-5 text-purple-500" /> 区域设置
                            </h3>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">默认语言</label>
                                    <select disabled aria-describedby="settings-readonly-notice" className={readOnlySelectClassName}>
                                        <option>简体中文</option>
                                        <option>English (US)</option>
                                    </select>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">时区</label>
                                    <select disabled aria-describedby="settings-readonly-notice" className={readOnlySelectClassName}>
                                        <option>Asia/Shanghai (GMT+8)</option>
                                        <option>UTC</option>
                                    </select>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">日期格式</label>
                                    <select disabled aria-describedby="settings-readonly-notice" className={readOnlySelectClassName}>
                                        <option>YYYY-MM-DD</option>
                                        <option>MM/DD/YYYY</option>
                                    </select>
                                </div>
                            </div>
                        </GlassCard>
                    </div>
                );
            case "security":
                return (
                    <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
                        <ReadOnlySettingsNotice />
                        <GlassCard className="p-8">
                            <h3 className="text-lg font-bold text-slate-900 mb-6 flex items-center gap-2">
                                <Lock className="w-5 h-5 text-emerald-500" /> 安全策略
                            </h3>
                            <div className="space-y-6">
                                <div className="flex items-center justify-between p-4 bg-slate-50 rounded-2xl border border-slate-100">
                                    <div className="space-y-1">
                                        <div className="text-sm font-bold text-slate-900">强制双重认证 (2FA)</div>
                                        <div className="text-xs text-slate-500">所有管理员必须启用两步验证才能登录</div>
                                    </div>
                                    <input type="checkbox" className="w-6 h-6 accent-slate-900 rounded-lg" checked readOnly aria-describedby="settings-readonly-notice" />
                                </div>
                                <div className="flex items-center justify-between p-4 bg-slate-50 rounded-2xl border border-slate-100">
                                    <div className="space-y-1">
                                        <div className="text-sm font-bold text-slate-900">新设备登录提醒</div>
                                        <div className="text-xs text-slate-500">检测到未知设备时发送邮件通知</div>
                                    </div>
                                    <input type="checkbox" className="w-6 h-6 accent-slate-900 rounded-lg" checked readOnly aria-describedby="settings-readonly-notice" />
                                </div>
                            </div>
                        </GlassCard>

                        <GlassCard className="p-8">
                            <h3 className="text-lg font-bold text-slate-900 mb-6 flex items-center gap-2">
                                <Key className="w-5 h-5 text-orange-500" /> 密码规则
                            </h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">最小长度</label>
                                    <Input type="number" value="8" readOnly aria-describedby="settings-readonly-notice" className={readOnlyInputClassName} />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">有效期 (天)</label>
                                    <Input type="number" value="90" readOnly aria-describedby="settings-readonly-notice" className={readOnlyInputClassName} />
                                </div>
                            </div>
                        </GlassCard>
                    </div>
                );
            case "notifications":
                return (
                    <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
                        <ReadOnlySettingsNotice />
                        <GlassCard className="p-8">
                            <h3 className="text-lg font-bold text-slate-900 mb-6 flex items-center gap-2">
                                <Mail className="w-5 h-5 text-indigo-500" /> 邮件通知
                            </h3>
                            <div className="space-y-4">
                                {[
                                    "用户注册时通知管理员",
                                    "系统异常报警",
                                    "每周数据报表自动发送",
                                    "知识库更新提醒"
                                ].map((item, i) => (
                                    <div key={i} className="flex items-center justify-between py-3 border-b border-slate-100 last:border-0">
                                        <span className="text-sm font-medium text-slate-700">{item}</span>
                                        <input type="checkbox" className="w-5 h-5 accent-slate-900 rounded" checked={i % 2 === 0} readOnly aria-describedby="settings-readonly-notice" />
                                    </div>
                                ))}
                            </div>
                        </GlassCard>
                    </div>
                );
            case "models":
                return (
                    <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
                        {/* Model Type Tabs */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            {(Object.keys(MODEL_TYPE_CONFIG) as ModelType[]).map((type) => {
                                const config = MODEL_TYPE_CONFIG[type];
                                const count = configs ? configs[type].length : 0;
                                const isActive = activeModelType === type;
                                return (
                                    <div
                                        key={type}
                                        className={`p-3 rounded-xl cursor-pointer transition-all border ${
                                            isActive
                                                ? "ring-2 ring-slate-900 bg-white border-transparent"
                                                : "bg-slate-50 border-slate-100 hover:bg-white"
                                        }`}
                                        onClick={() => setActiveModelType(type)}
                                    >
                                        <div className="flex items-center gap-2">
                                            <div className={`w-8 h-8 rounded-lg ${config.bgColor} flex items-center justify-center`}>
                                                <config.icon className={`w-4 h-4 ${config.color}`} />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="font-bold text-slate-900 text-xs truncate">{config.label.split(' ')[0]}</div>
                                                <div className="text-xs text-slate-500">{count} 个</div>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>

                        {/* Config List */}
                        <GlassCard className="overflow-hidden">
                            <div className="p-4 border-b border-slate-100 flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    {(() => {
                                        const config = MODEL_TYPE_CONFIG[activeModelType];
                                        return (
                                            <>
                                                <div className={`w-8 h-8 rounded-lg ${config.bgColor} flex items-center justify-center`}>
                                                    <config.icon className={`w-4 h-4 ${config.color}`} />
                                                </div>
                                                <div>
                                                    <h3 className="text-sm font-bold text-slate-900">{config.label}</h3>
                                                    <p className="text-xs text-slate-500">{config.description}</p>
                                                </div>
                                            </>
                                        );
                                    })()}
                                </div>
                                <Button
                                    size="sm"
                                    className="rounded-full bg-slate-900 hover:bg-slate-800 text-white text-xs"
                                    onClick={() => {
                                        resetForm();
                                        setFormData((prev) => ({
                                            ...prev,
                                            model_type: activeModelType,
                                            provider: MODEL_PROVIDER_MAP[activeModelType][0],
                                        }));
                                        setIsCreateOpen(true);
                                    }}
                                >
                                    <Plus className="w-3 h-3 mr-1" /> 添加
                                </Button>
                            </div>

                            {isLoadingModels ? (
                                <div className="p-8 text-center">
                                    <Loader2 className="w-6 h-6 animate-spin text-slate-400 mx-auto" />
                                    <p className="text-slate-500 mt-2 text-sm">加载中...</p>
                                </div>
                            ) : currentConfigs.length === 0 ? (
                                <div className="p-8 text-center">
                                    <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3">
                                        <Cpu className="w-6 h-6 text-slate-400" />
                                    </div>
                                    <p className="text-slate-500 text-sm">暂无配置</p>
                                </div>
                            ) : (
                                <div className="divide-y divide-slate-100">
                                    {currentConfigs.map((config) => (
                                        <div key={config.id} className="p-4 hover:bg-slate-50/50 transition-colors">
                                            <div className="flex items-center gap-4">
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2 mb-1">
                                                        <span className="font-bold text-slate-900 text-sm">{config.name}</span>
                                                        {config.is_default && (
                                                            <Badge variant="blue" className="gap-1 text-xs">
                                                                <Star className="w-2.5 h-2.5" /> 默认
                                                            </Badge>
                                                        )}
                                                        {!config.is_active && <Badge variant="gray" className="text-xs">已禁用</Badge>}
                                                    </div>
                                                    <div className="flex items-center gap-2 text-xs text-slate-500">
                                                        <span className="font-medium text-slate-600">{config.provider}</span>
                                                        <span>·</span>
                                                        <span className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-xs">{config.model_name}</span>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    {getTestStatusBadge(config.last_test_status)}
                                                    <div className="flex gap-0.5">
                                                        <Button variant="ghost" size="icon" className="h-7 w-7 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-full" onClick={() => handleTestConnection(config.id)} disabled={isTesting} title="测试">
                                                            <Zap className="w-3.5 h-3.5" />
                                                        </Button>
                                                        {!config.is_default && (
                                                            <Button variant="ghost" size="icon" className="h-7 w-7 text-slate-400 hover:text-amber-600 hover:bg-amber-50 rounded-full" onClick={() => handleSetDefault(config)} title="设为默认">
                                                                <Star className="w-3.5 h-3.5" />
                                                            </Button>
                                                        )}
                                                        <Button variant="ghost" size="icon" className="h-7 w-7 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-full" onClick={() => handleOpenEdit(config)} title="编辑">
                                                            <Edit2 className="w-3.5 h-3.5" />
                                                        </Button>
                                                        <Button variant="ghost" size="icon" className="h-7 w-7 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-full" onClick={() => setDeleteTarget(config)} title="删除">
                                                            <Trash2 className="w-3.5 h-3.5" />
                                                        </Button>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </GlassCard>
                    </div>
                );
            default:
                return null;
        }
    };


    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Delete Confirm Dialog */}
            <ConfirmDialog
                open={!!deleteTarget}
                onOpenChange={(open) => !open && setDeleteTarget(null)}
                title="删除配置"
                description={`确定要删除「${deleteTarget?.name}」吗？此操作不可撤销。`}
                confirmText="删除"
                variant="danger"
                onConfirm={handleDelete}
                isLoading={isDeleting}
            />

            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight">系统设置</h1>
                    <p className="text-slate-500 mt-1">管理全局配置与参数</p>
                </div>
                <div className="flex gap-3">
                    {SETTINGS_READ_ONLY_TABS.has(activeTab) ? (
                        <div className="flex flex-col items-start gap-2 sm:flex-row sm:items-center">
                            <span id="settings-readonly-notice" className="text-sm text-amber-700">{READ_ONLY_SETTINGS_NOTICE}</span>
                            <Button variant="outline" className="rounded-full border-slate-200 text-slate-400" disabled title="未接入持久化接口">
                                <RefreshCw className="w-4 h-4 mr-2" /> 放弃更改
                            </Button>
                            <Button className="rounded-full bg-slate-300 text-white shadow-none px-6" disabled title="未接入持久化接口">
                                <Save className="w-4 h-4 mr-2" /> 保存配置
                            </Button>
                        </div>
                    ) : activeTab === "models" ? (
                        <Button
                            variant="outline"
                            className="rounded-full border-slate-200"
                            onClick={() => loadConfigs()}
                            disabled={isLoadingModels}
                        >
                            <RefreshCw className={`w-4 h-4 mr-2 ${isLoadingModels ? "animate-spin" : ""}`} />
                            刷新
                        </Button>
                    ) : null}
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
                {/* Sidebar Navigation */}
                <div className="col-span-1 md:col-span-3 space-y-2">
                    <GlassCard className="p-2 space-y-1">
                        {tabs.map((tab) => (
                            <div
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`flex items-center gap-3 px-4 py-3 rounded-xl cursor-pointer transition-all ${activeTab === tab.id ? 'bg-slate-900 text-white shadow-md' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'}`}
                            >
                                <tab.icon className="w-4 h-4" />
                                <span className="text-sm font-bold">{tab.label}</span>
                            </div>
                        ))}
                    </GlassCard>
                </div>

                {/* Main Content */}
                <div className="col-span-1 md:col-span-9">
                    {renderContent()}
                </div>
            </div>

            {/* Create/Edit Dialog */}
            <Dialog
                open={isCreateOpen || isEditOpen}
                onOpenChange={(open) => {
                    if (!open) {
                        setIsCreateOpen(false);
                        setIsEditOpen(false);
                        setEditingConfig(null);
                        resetForm();
                    }
                }}
            >
                <DialogContent className="max-w-lg">
                    <DialogHeader>
                        <DialogTitle>{isEditOpen ? "编辑配置" : "添加配置"}</DialogTitle>
                        <DialogDescription>
                            {isEditOpen ? "修改模型配置信息" : `添加新的 ${MODEL_TYPE_CONFIG[formData.model_type].label} 配置`}
                        </DialogDescription>
                    </DialogHeader>

                    <div className="py-4 space-y-4 max-h-[60vh] overflow-y-auto">
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">配置名称 *</label>
                            <input
                                className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                                placeholder="例如：GPT-4o 主力模型"
                                value={formData.name}
                                onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
                            />
                        </div>

                        {!isEditOpen && (
                            <div className="space-y-2">
                                <label className="text-xs font-bold text-slate-500 uppercase">模型类型 *</label>
                                <select
                                    className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none bg-white"
                                    value={formData.model_type}
                                    onChange={(e) => {
                                        const nextType = e.target.value as ModelType;
                                        const fallbackProvider = MODEL_PROVIDER_MAP[nextType][0];
                                        setFormData((prev) => ({
                                            ...prev,
                                            model_type: nextType,
                                            provider: MODEL_PROVIDER_MAP[nextType].includes(prev.provider) ? prev.provider : fallbackProvider,
                                        }));
                                    }}
                                >
                                    {(Object.keys(MODEL_TYPE_CONFIG) as ModelType[]).map((type) => (
                                        <option key={type} value={type}>{MODEL_TYPE_CONFIG[type].label}</option>
                                    ))}
                                </select>
                            </div>
                        )}

                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">服务提供商 *</label>
                            <select
                                className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none bg-white"
                                value={formData.provider}
                                onChange={(e) => setFormData((prev) => ({ ...prev, provider: e.target.value as ModelProvider }))}
                                disabled={isEditOpen}
                            >
                                {PROVIDER_OPTIONS.filter((opt) => MODEL_PROVIDER_MAP[formData.model_type].includes(opt.value)).map((opt) => (
                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                ))}
                            </select>
                        </div>

                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">
                                API 地址 {requiresBaseUrl(formData.model_type, formData.provider) ? "*" : "(可选)"}
                            </label>
                            <input
                                className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                                placeholder="https://api.openai.com/v1"
                                value={formData.base_url}
                                onChange={(e) => setFormData((prev) => ({ ...prev, base_url: e.target.value }))}
                            />
                        </div>

                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">
                                API Key {isEditOpen ? "(留空保持不变)" : (requiresApiKey(formData.model_type, formData.provider) ? "*" : "(可选)")}
                            </label>
                            <input
                                type="password"
                                className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                                placeholder={isEditOpen ? editingConfig?.api_key_masked : "sk-..."}
                                value={formData.api_key}
                                onChange={(e) => setFormData((prev) => ({ ...prev, api_key: e.target.value }))}
                            />
                        </div>

                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">模型名称 *</label>
                            <input
                                className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                                placeholder="gpt-4o / text-embedding-3-small"
                                value={formData.model_name}
                                onChange={(e) => setFormData((prev) => ({ ...prev, model_name: e.target.value }))}
                            />
                        </div>

                        {/* TTS 专属配置 */}
                        {formData.model_type === "tts" && (
                            <div className="space-y-4 p-4 bg-orange-50/50 rounded-xl border border-orange-100">
                                <div className="text-xs font-bold text-orange-600 uppercase flex items-center gap-2">
                                    <Volume2 className="w-3.5 h-3.5" /> TTS 语音参数
                                </div>
                                
                                {/* 语速 */}
                                <div className="space-y-2">
                                    <div className="flex justify-between items-center">
                                        <label className="text-xs font-medium text-slate-600">语速</label>
                                        <span className="text-xs font-mono text-slate-500">
                                            {(formData.extra_config as { rate?: string })?.rate || "+0%"}
                                        </span>
                                    </div>
                                    <input
                                        type="range"
                                        min="-50"
                                        max="100"
                                        step="10"
                                        className="w-full accent-orange-500"
                                        value={parseInt(((formData.extra_config as { rate?: string })?.rate || "+0%").replace(/[+%]/g, "")) || 0}
                                        onChange={(e) => {
                                            const val = parseInt(e.target.value);
                                            const rate = val >= 0 ? `+${val}%` : `${val}%`;
                                            setFormData((prev) => ({
                                                ...prev,
                                                extra_config: { ...prev.extra_config, rate },
                                            }));
                                        }}
                                    />
                                    <div className="flex justify-between text-[10px] text-slate-400">
                                        <span>慢速 (-50%)</span>
                                        <span>正常</span>
                                        <span>快速 (+100%)</span>
                                    </div>
                                </div>

                                {/* 音量 */}
                                <div className="space-y-2">
                                    <div className="flex justify-between items-center">
                                        <label className="text-xs font-medium text-slate-600">音量</label>
                                        <span className="text-xs font-mono text-slate-500">
                                            {(formData.extra_config as { volume?: string })?.volume || "+0%"}
                                        </span>
                                    </div>
                                    <input
                                        type="range"
                                        min="-50"
                                        max="50"
                                        step="10"
                                        className="w-full accent-orange-500"
                                        value={parseInt(((formData.extra_config as { volume?: string })?.volume || "+0%").replace(/[+%]/g, "")) || 0}
                                        onChange={(e) => {
                                            const val = parseInt(e.target.value);
                                            const volume = val >= 0 ? `+${val}%` : `${val}%`;
                                            setFormData((prev) => ({
                                                ...prev,
                                                extra_config: { ...prev.extra_config, volume },
                                            }));
                                        }}
                                    />
                                    <div className="flex justify-between text-[10px] text-slate-400">
                                        <span>低 (-50%)</span>
                                        <span>正常</span>
                                        <span>高 (+50%)</span>
                                    </div>
                                </div>

                                {/* 音调 */}
                                <div className="space-y-2">
                                    <div className="flex justify-between items-center">
                                        <label className="text-xs font-medium text-slate-600">音调</label>
                                        <span className="text-xs font-mono text-slate-500">
                                            {(formData.extra_config as { pitch?: string })?.pitch || "+0Hz"}
                                        </span>
                                    </div>
                                    <input
                                        type="range"
                                        min="-50"
                                        max="50"
                                        step="10"
                                        className="w-full accent-orange-500"
                                        value={parseInt(((formData.extra_config as { pitch?: string })?.pitch || "+0Hz").replace(/[+Hz]/g, "")) || 0}
                                        onChange={(e) => {
                                            const val = parseInt(e.target.value);
                                            const pitch = val >= 0 ? `+${val}Hz` : `${val}Hz`;
                                            setFormData((prev) => ({
                                                ...prev,
                                                extra_config: { ...prev.extra_config, pitch },
                                            }));
                                        }}
                                    />
                                    <div className="flex justify-between text-[10px] text-slate-400">
                                        <span>低沉 (-50Hz)</span>
                                        <span>正常</span>
                                        <span>尖锐 (+50Hz)</span>
                                    </div>
                                </div>

                                {/* 试听按钮 */}
                                <Button
                                    type="button"
                                    variant="outline"
                                    className="w-full rounded-full border-orange-200 text-orange-600 hover:bg-orange-50"
                                    onClick={isPreviewingTTS ? stopPreviewTTS : handlePreviewTTS}
                                    disabled={!formData.model_name}
                                >
                                    {isPreviewingTTS ? (
                                        <>
                                            <Square className="w-4 h-4 mr-2 fill-current" /> 停止试听
                                        </>
                                    ) : (
                                        <>
                                            <Volume2 className="w-4 h-4 mr-2" /> 试听效果
                                        </>
                                    )}
                                </Button>
                            </div>
                        )}

                        <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
                            <div>
                                <div className="text-sm font-medium text-slate-900">设为默认配置</div>
                                <div className="text-xs text-slate-500">系统将优先使用此配置</div>
                            </div>
                            <input
                                type="checkbox"
                                className="w-5 h-5 accent-slate-900 rounded"
                                checked={formData.is_default}
                                onChange={(e) => setFormData((prev) => ({ ...prev, is_default: e.target.checked }))}
                            />
                        </div>

                        {testResult && (
                            <div className={`p-3 rounded-xl flex items-start gap-2 ${testResult.success ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
                                {testResult.success ? <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" /> : <XCircle className="w-4 h-4 mt-0.5 shrink-0" />}
                                <span className="text-sm">{testResult.message}</span>
                            </div>
                        )}
                    </div>

                    <DialogFooter className="flex-col sm:flex-row gap-2">
                        <Button
                            variant="outline"
                            className="rounded-full"
                            onClick={() => handleTestConnection()}
                            disabled={
                                isTesting ||
                                !formData.model_name ||
                                (requiresBaseUrl(formData.model_type, formData.provider) && !formData.base_url) ||
                                (requiresApiKey(formData.model_type, formData.provider) && !formData.api_key)
                            }
                        >
                            {isTesting ? (
                                <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> 测试中...</>
                            ) : (
                                <><Zap className="w-4 h-4 mr-2" /> 测试连接</>
                            )}
                        </Button>
                        <div className="flex gap-2 w-full sm:w-auto">
                            <Button
                                variant="ghost"
                                className="rounded-full flex-1 sm:flex-none"
                                onClick={() => {
                                    setIsCreateOpen(false);
                                    setIsEditOpen(false);
                                    setEditingConfig(null);
                                    resetForm();
                                }}
                            >
                                取消
                            </Button>
                            <Button
                                className="rounded-full bg-slate-900 text-white flex-1 sm:flex-none"
                                onClick={isEditOpen ? handleUpdate : handleCreate}
                                disabled={isSubmitting}
                            >
                                {isSubmitting ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> 保存中...</> : "保存"}
                            </Button>
                        </div>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
