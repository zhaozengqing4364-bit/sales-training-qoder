"use client";
import { debug } from "@/lib/debug";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, getApiErrorMessage } from "@/lib/api/client";
import {
    AdminPersona,
    AdminKnowledgeBase,
    AdminPersonaCustomerPressure,
    AdminPersonaIndustryPackContract,
    AdminPersonaPolicy,
} from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";
import { ArrowLeft, Save, AlertCircle, Loader2, Database, Plus, X, Volume2, Square } from "lucide-react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/glass-modal";

interface LinkedKnowledgeBase {
    id: string;
    name: string;
    description?: string;
    category: string;
    document_count: number;
}

interface TTSConfig {
    voice: string;
    rate: string;
    volume: string;
    pitch: string;
}

interface ToolPolicyFormState {
    lockToKnowledgeBase: boolean;
    allowWebSearch: boolean;
}

interface CustomerPressureFormState {
    source: string;
    salesFocus: string;
    valueAxesText: string;
    objectionAxesText: string;
    questionStrategy: string;
    revisitOnEvasion: boolean;
    requireEvidence: boolean;
    expectedQuestionsText: string;
}

const SALES_FOCUS_OPTIONS = [
    { value: "proof", label: "案例证据" },
    { value: "price", label: "价格" },
    { value: "budget_priority", label: "预算优先级" },
    { value: "customer_value", label: "客户价值" },
    { value: "value_translation", label: "价值翻译" },
    { value: "implementation_risk", label: "实施风险" },
    { value: "competitor", label: "竞品替代" },
];

const QUESTION_STRATEGY_OPTIONS = [
    { value: "single_issue", label: "单点追问" },
    { value: "progressive_follow_up", label: "递进追问" },
];

const PRESSURE_SOURCE_LABELS: Record<string, string> = {
    explicit: "显式 pressure model",
    legacy_sales_focus_extensions: "legacy sales_focus 回填",
    none: "未配置",
};

const PRESSURE_AUDIT_LABELS: Record<string, string> = {
    kb_lock_unbound: "知识库强制模式已开启，但当前没有绑定知识库。",
    pressure_model_legacy_only: "当前仍依赖旧 sales_focus 字段推导 pressure model；保存后会写回显式结构。",
    no_pressure_context: "当前还没有可追问的压力方向、价值轴或示例追问。",
};

const OWNED_FIELD_LABELS: Record<string, string> = {
    persona: "persona",
    customer_pressure: "customer pressure",
    knowledge_bundle: "knowledge bundle",
    scenario: "scenario",
};

const emptyCustomerPressureFormState = (): CustomerPressureFormState => ({
    source: "none",
    salesFocus: "",
    valueAxesText: "",
    objectionAxesText: "",
    questionStrategy: "",
    revisitOnEvasion: false,
    requireEvidence: false,
    expectedQuestionsText: "",
});

const toRecord = (value: unknown): Record<string, unknown> => (
    value && typeof value === "object" ? value as Record<string, unknown> : {}
);

const normalizeStringList = (value: unknown): string[] => {
    if (!Array.isArray(value)) {
        return [];
    }

    const normalized: string[] = [];
    const seen = new Set<string>();
    for (const item of value) {
        const text = String(item ?? "").trim();
        if (!text) {
            continue;
        }
        const dedupeKey = text.toLowerCase();
        if (seen.has(dedupeKey)) {
            continue;
        }
        seen.add(dedupeKey);
        normalized.push(text);
    }
    return normalized;
};

const toMultilineText = (items: string[]): string => items.join("\n");

const parseAxisList = (raw: string): string[] => {
    const normalized: string[] = [];
    const seen = new Set<string>();

    raw
        .split(/[\n,，；;]+/)
        .map((item) => item.trim())
        .filter(Boolean)
        .forEach((item) => {
            const dedupeKey = item.toLowerCase();
            if (seen.has(dedupeKey)) {
                return;
            }
            seen.add(dedupeKey);
            normalized.push(item);
        });

    return normalized;
};

const parseQuestionList = (raw: string): string[] => {
    const normalized: string[] = [];
    const seen = new Set<string>();

    raw
        .split(/\n+/)
        .map((item) => item.trim())
        .filter(Boolean)
        .forEach((item) => {
            const dedupeKey = item.toLowerCase();
            if (seen.has(dedupeKey)) {
                return;
            }
            seen.add(dedupeKey);
            normalized.push(item);
        });

    return normalized;
};

const buildCustomerPressureFormState = (personaPolicy?: AdminPersonaPolicy): CustomerPressureFormState => {
    const customerPressure = toRecord(personaPolicy?.customer_pressure);
    const pressureDirection = toRecord(customerPressure.pressure_direction);
    const followUpBehavior = toRecord(customerPressure.follow_up_behavior);

    return {
        source:
            String(customerPressure.source || "").trim()
            || (personaPolicy?.sales_focus || personaPolicy?.value_axes?.length || personaPolicy?.objection_axes?.length
                ? "legacy_sales_focus_extensions"
                : "none"),
        salesFocus:
            String(pressureDirection.sales_focus || personaPolicy?.sales_focus || "").trim(),
        valueAxesText: toMultilineText(
            normalizeStringList(pressureDirection.value_axes || personaPolicy?.value_axes),
        ),
        objectionAxesText: toMultilineText(
            normalizeStringList(pressureDirection.objection_axes || personaPolicy?.objection_axes),
        ),
        questionStrategy: String(followUpBehavior.question_strategy || "").trim(),
        revisitOnEvasion: Boolean(followUpBehavior.revisit_on_evasion),
        requireEvidence: Boolean(followUpBehavior.require_evidence),
        expectedQuestionsText: toMultilineText(
            normalizeStringList(
                followUpBehavior.expected_customer_questions || personaPolicy?.expected_customer_questions,
            ),
        ),
    };
};

const buildCustomerPressurePayload = (
    personaPolicy: AdminPersonaPolicy | null,
    customerPressureForm: CustomerPressureFormState,
): {
    salesFocus: string;
    valueAxes: string[];
    objectionAxes: string[];
    expectedCustomerQuestions: string[];
    customerPressure: AdminPersonaCustomerPressure;
} => {
    const existingCustomerPressure = toRecord(personaPolicy?.customer_pressure);
    const existingPressureDirection = toRecord(existingCustomerPressure.pressure_direction);
    const existingFollowUpBehavior = toRecord(existingCustomerPressure.follow_up_behavior);
    const salesFocus = customerPressureForm.salesFocus.trim();
    const valueAxes = parseAxisList(customerPressureForm.valueAxesText);
    const objectionAxes = parseAxisList(customerPressureForm.objectionAxesText);
    const expectedCustomerQuestions = parseQuestionList(customerPressureForm.expectedQuestionsText);
    const hasPressureContext = Boolean(
        salesFocus
        || valueAxes.length
        || objectionAxes.length
        || expectedCustomerQuestions.length,
    );
    const questionStrategy = customerPressureForm.questionStrategy.trim() || (hasPressureContext ? "single_issue" : "");

    return {
        salesFocus,
        valueAxes,
        objectionAxes,
        expectedCustomerQuestions,
        customerPressure: {
            ...existingCustomerPressure,
            source: hasPressureContext ? "explicit" : "none",
            pressure_direction: {
                ...existingPressureDirection,
                sales_focus: salesFocus,
                value_axes: valueAxes,
                objection_axes: objectionAxes,
            },
            follow_up_behavior: {
                ...existingFollowUpBehavior,
                question_strategy: questionStrategy,
                revisit_on_evasion: customerPressureForm.revisitOnEvasion,
                require_evidence: customerPressureForm.requireEvidence,
                expected_customer_questions: expectedCustomerQuestions,
            },
        },
    };
};

const describeQuestionStrategy = (value: string): string => {
    if (value === "single_issue") {
        return "单点追问";
    }
    if (!value) {
        return "未配置";
    }
    const matched = QUESTION_STRATEGY_OPTIONS.find((option) => option.value === value);
    return matched?.label || value;
};

const describeSalesFocus = (value: string): string => {
    if (!value) {
        return "未配置";
    }
    return SALES_FOCUS_OPTIONS.find((option) => option.value === value)?.label || value;
};

// 可用的中文语音列表
const VOICE_OPTIONS = [
    { value: "zh-CN-XiaoxiaoNeural", label: "晓晓 (女声-温柔)" },
    { value: "zh-CN-YunxiNeural", label: "云希 (男声-阳光)" },
    { value: "zh-CN-YunjianNeural", label: "云健 (男声-沉稳)" },
    { value: "zh-CN-XiaoyiNeural", label: "晓伊 (女声-活泼)" },
    { value: "zh-CN-YunyangNeural", label: "云扬 (男声-新闻)" },
    { value: "zh-CN-XiaochenNeural", label: "晓辰 (女声-知性)" },
    { value: "zh-CN-XiaohanNeural", label: "晓涵 (女声-甜美)" },
    { value: "zh-CN-XiaomengNeural", label: "晓梦 (女声-可爱)" },
    { value: "zh-CN-XiaomoNeural", label: "晓墨 (女声-文艺)" },
    { value: "zh-CN-XiaoqiuNeural", label: "晓秋 (女声-成熟)" },
    { value: "zh-CN-XiaoruiNeural", label: "晓睿 (女声-专业)" },
    { value: "zh-CN-XiaoshuangNeural", label: "晓双 (女声-童声)" },
    { value: "zh-CN-XiaoxuanNeural", label: "晓萱 (女声-优雅)" },
    { value: "zh-CN-XiaoyanNeural", label: "晓颜 (女声-客服)" },
    { value: "zh-CN-XiaoyouNeural", label: "晓悠 (女声-童声)" },
    { value: "zh-CN-YunfengNeural", label: "云枫 (男声-磁性)" },
    { value: "zh-CN-YunhaoNeural", label: "云皓 (男声-广告)" },
    { value: "zh-CN-YunxiaNeural", label: "云夏 (男声-童声)" },
    { value: "zh-CN-YunyeNeural", label: "云野 (男声-叙述)" },
    { value: "zh-CN-YunzeNeural", label: "云泽 (男声-纪录片)" },
];

export default function EditPersonaPage() {
    const toast = useToast();
    const params = useParams();
    const router = useRouter();
    const personaId = params.id as string;

    const [persona, setPersona] = useState<AdminPersona | null>(null);
    const [personaPolicy, setPersonaPolicy] = useState<AdminPersonaPolicy | null>(null);
    const [industryPackContract, setIndustryPackContract] = useState<AdminPersonaIndustryPackContract | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Form state
    const [formData, setFormData] = useState({
        name: "",
        description: "",
        category: "customer" as "customer" | "interviewer" | "coach" | "examiner",
        difficulty: "medium" as "easy" | "medium" | "hard",
        system_prompt: "",
    });

    // Knowledge Base State
    const [linkedKnowledgeBases, setLinkedKnowledgeBases] = useState<LinkedKnowledgeBase[]>([]);
    const [availableKnowledgeBases, setAvailableKnowledgeBases] = useState<AdminKnowledgeBase[]>([]);
    const [isAddKBOpen, setIsAddKBOpen] = useState(false);
    const [selectedKBId, setSelectedKBId] = useState<string>("");
    const [isAddingKB, setIsAddingKB] = useState(false);
    const [removeKBTarget, setRemoveKBTarget] = useState<LinkedKnowledgeBase | null>(null);
    const [isRemovingKB, setIsRemovingKB] = useState(false);

    // TTS Config State
    const [ttsConfig, setTtsConfig] = useState<TTSConfig>({
        voice: "zh-CN-XiaoxiaoNeural",
        rate: "+0%",
        volume: "+0%",
        pitch: "+0Hz",
    });
    const [toolPolicyForm, setToolPolicyForm] = useState<ToolPolicyFormState>({
        lockToKnowledgeBase: false,
        allowWebSearch: false,
    });
    const [customerPressureForm, setCustomerPressureForm] = useState<CustomerPressureFormState>(
        emptyCustomerPressureFormState(),
    );
    const [isPreviewingTTS, setIsPreviewingTTS] = useState(false);
    const previewAudioRef = useRef<HTMLAudioElement | null>(null);

    useEffect(() => {
        loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [personaId]);

    const loadData = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const [personaData, allKnowledgeBases, personaIndustryPackContract] = await Promise.all([
                api.admin.getPersona(personaId),
                api.admin.getKnowledgeBases({ page_size: 100 }),
                api.admin.getPersonaIndustryPackContract(),
            ]);
            setPersona(personaData);
            setPersonaPolicy(personaData.persona_policy || null);
            setIndustryPackContract(personaIndustryPackContract);
            setCustomerPressureForm(buildCustomerPressureFormState(personaData.persona_policy));
            setFormData({
                name: personaData.name || "",
                description: personaData.description || "",
                category: (personaData.category || "customer") as "customer" | "interviewer" | "coach" | "examiner",
                difficulty: (personaData.difficulty || "medium") as "easy" | "medium" | "hard",
                system_prompt:
                    String(
                        personaData.persona_policy?.system_prompt ||
                        personaData.system_prompt ||
                        "",
                    ),
            });
            
            // Load TTS config
            if (personaData.tts_config) {
                setTtsConfig({
                    voice: personaData.tts_config.voice || "zh-CN-XiaoxiaoNeural",
                    rate: personaData.tts_config.rate || "+0%",
                    volume: personaData.tts_config.volume || "+0%",
                    pitch: personaData.tts_config.pitch || "+0Hz",
                });
            }
            
            setAvailableKnowledgeBases(allKnowledgeBases.items);

            // Load linked knowledge bases
            const policyKbIds = Array.isArray(personaData.persona_policy?.knowledge_base_ids)
                ? personaData.persona_policy.knowledge_base_ids
                : null;
            const legacyKbIds = Array.isArray(personaData.knowledge_base_ids)
                ? personaData.knowledge_base_ids
                : [];
            const kbIds =
                policyKbIds !== null && (policyKbIds.length > 0 || legacyKbIds.length === 0)
                    ? policyKbIds
                    : legacyKbIds;
            const rawToolPolicy = (
                personaData.persona_policy?.tool_policy &&
                typeof personaData.persona_policy.tool_policy === "object"
                    ? personaData.persona_policy.tool_policy
                    : {}
            ) as Record<string, unknown>;
            const hasBoundKb = kbIds.length > 0;
            const lockToKnowledgeBase = typeof rawToolPolicy.require_kb_grounding === "boolean"
                ? rawToolPolicy.require_kb_grounding
                : hasBoundKb;
            const allowWebSearch = lockToKnowledgeBase
                ? false
                : (
                    String(rawToolPolicy.network_access_mode || "").toLowerCase() === "controlled"
                    || rawToolPolicy.enable_web_search === true
                );
            setToolPolicyForm({
                lockToKnowledgeBase,
                allowWebSearch,
            });

            if (kbIds.length > 0) {
                const linkedKBs = allKnowledgeBases.items.filter((kb: AdminKnowledgeBase) => kbIds.includes(kb.id));
                setLinkedKnowledgeBases(linkedKBs.map(kb => ({
                    id: kb.id,
                    name: kb.name,
                    description: kb.description,
                    category: kb.category,
                    document_count: kb.doc_count || kb.document_count || 0,
                })));
            }
        } catch (err) {
            debug.error("Failed to load persona:", err);
            setError(err instanceof Error ? err.message : "加载失败");
        } finally {
            setIsLoading(false);
        }
    };

    const buildPersonaToolPolicyPayload = (): Record<string, unknown> => {
        const lockToKnowledgeBase = toolPolicyForm.lockToKnowledgeBase;
        const allowWebSearch = !lockToKnowledgeBase && toolPolicyForm.allowWebSearch;
        return {
            enable_internal_retrieval: true,
            retrieval_priority: lockToKnowledgeBase ? "kb_only" : "kb_first",
            strict_instruction_following: true,
            require_grounding: true,
            require_kb_grounding: lockToKnowledgeBase,
            network_access_mode: allowWebSearch ? "controlled" : "off",
            enable_web_search: allowWebSearch,
            allow_web_search_without_kb: allowWebSearch,
        };
    };

    const handleSave = async () => {
        if (!formData.name.trim()) {
            toast.error("请输入角色名称");
            return;
        }
        if (!formData.system_prompt.trim()) {
            toast.error("请输入系统提示词");
            return;
        }

        setIsSaving(true);
        try {
            const {
                salesFocus,
                valueAxes,
                objectionAxes,
                expectedCustomerQuestions,
                customerPressure,
            } = buildCustomerPressurePayload(personaPolicy, customerPressureForm);

            await api.admin.updatePersona(personaId, {
                ...formData,
                knowledge_base_ids: linkedKnowledgeBases.map(kb => kb.id),
                persona_policy: {
                    ...(personaPolicy || {}),
                    version: 1,
                    system_prompt: formData.system_prompt,
                    knowledge_base_ids: linkedKnowledgeBases.map((kb) => kb.id),
                    tool_policy: buildPersonaToolPolicyPayload(),
                    sales_focus: salesFocus,
                    value_axes: valueAxes,
                    objection_axes: objectionAxes,
                    expected_customer_questions: expectedCustomerQuestions,
                    customer_pressure: customerPressure,
                },
                tts_config: ttsConfig,
            });
            router.push("/admin/personas");
        } catch (err) {
            debug.error("Failed to save persona:", err);
            toast.error(`保存失败: ${err instanceof Error ? err.message : "未知错误"}`);
        } finally {
            setIsSaving(false);
        }
    };

    // Filter out already linked knowledge bases
    const unlinkedKnowledgeBases = availableKnowledgeBases.filter(
        kb => !linkedKnowledgeBases.some(lkb => lkb.id === kb.id)
    );

    // Handle add knowledge base
    const handleAddKnowledgeBase = async () => {
        if (!selectedKBId) {
            return;
        }
        
        setIsAddingKB(true);
        try {
            const addedKB = availableKnowledgeBases.find(kb => kb.id === selectedKBId);
            if (addedKB) {
                setLinkedKnowledgeBases(prev => [...prev, {
                    id: addedKB.id,
                    name: addedKB.name,
                    description: addedKB.description,
                    category: addedKB.category,
                    document_count: addedKB.doc_count || addedKB.document_count || 0,
                }]);
            }
            
            setIsAddKBOpen(false);
            setSelectedKBId("");
        } finally {
            setIsAddingKB(false);
        }
    };

    // Handle remove knowledge base
    const handleRemoveKnowledgeBase = async () => {
        if (!removeKBTarget) return;
        
        setIsRemovingKB(true);
        try {
            setLinkedKnowledgeBases(prev => prev.filter(kb => kb.id !== removeKBTarget.id));
            setRemoveKBTarget(null);
        } finally {
            setIsRemovingKB(false);
        }
    };

    const pressureValueAxes = parseAxisList(customerPressureForm.valueAxesText);
    const pressureObjectionAxes = parseAxisList(customerPressureForm.objectionAxesText);
    const pressureExpectedQuestions = parseQuestionList(customerPressureForm.expectedQuestionsText);
    const hasPressureContext = Boolean(
        customerPressureForm.salesFocus
        || pressureValueAxes.length
        || pressureObjectionAxes.length
        || pressureExpectedQuestions.length,
    );
    const dynamicQuestionStrategyOptions = customerPressureForm.questionStrategy
        && !QUESTION_STRATEGY_OPTIONS.some((option) => option.value === customerPressureForm.questionStrategy)
        ? [
            ...QUESTION_STRATEGY_OPTIONS,
            {
                value: customerPressureForm.questionStrategy,
                label: `当前值：${customerPressureForm.questionStrategy}`,
            },
        ]
        : QUESTION_STRATEGY_OPTIONS;
    const localAuditIssues = [
        toolPolicyForm.lockToKnowledgeBase && linkedKnowledgeBases.length === 0 ? "kb_lock_unbound" : null,
        customerPressureForm.source === "legacy_sales_focus_extensions" ? "pressure_model_legacy_only" : null,
        !hasPressureContext ? "no_pressure_context" : null,
    ].filter((value): value is string => Boolean(value));
    const contractOwnedFieldEntries = Object.entries(industryPackContract?.owned_fields || {});
    const runtimeTargets = industryPackContract?.runtime_targets || {};

    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-[400px]">
                <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
            </div>
        );
    }

    if (error) {
        return (
            <GlassCard className="p-8 text-center">
                <div className="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center text-red-500 mb-4 mx-auto">
                    <AlertCircle className="w-8 h-8" />
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">加载失败</h3>
                <p className="text-slate-500 text-sm mb-4">{error}</p>
                <Button onClick={() => router.back()} className="rounded-full">
                    返回
                </Button>
            </GlassCard>
        );
    }

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Remove Knowledge Base Confirm */}
            <ConfirmDialog
                open={!!removeKBTarget}
                onOpenChange={(open) => !open && setRemoveKBTarget(null)}
                title="移除知识库"
                description={`确定要从该角色移除「${removeKBTarget?.name}」吗？`}
                confirmText="移除"
                variant="danger"
                onConfirm={handleRemoveKnowledgeBase}
                isLoading={isRemovingKB}
            />

            {/* Header */}
            <div className="flex items-center gap-4">
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => router.back()}
                    className="rounded-full"
                >
                    <ArrowLeft className="w-5 h-5" />
                </Button>
                <div className="flex-1">
                    <h1 className="text-2xl font-black text-slate-900 tracking-tight">编辑角色</h1>
                    <p className="text-slate-500 text-sm">{persona?.name}</p>
                </div>
                <Button
                    onClick={handleSave}
                    disabled={isSaving}
                    className="rounded-full bg-slate-900 hover:bg-slate-800 text-white"
                >
                    {isSaving ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                        <Save className="w-4 h-4 mr-2" />
                    )}
                    保存
                </Button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Main Form */}
                <GlassCard className="lg:col-span-2 p-6 space-y-6">
                    {/* Basic Info */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">角色名称</label>
                            <input
                                className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                                placeholder="例如：急躁的CEO"
                                value={formData.name}
                                onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">描述</label>
                            <input
                                className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                                placeholder="角色的简短描述"
                                value={formData.description}
                                onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">角色类型</label>
                            <select
                                className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none bg-white"
                                value={formData.category}
                                onChange={(e) => setFormData(prev => ({ ...prev, category: e.target.value as typeof formData.category }))}
                            >
                                <option value="customer">客户</option>
                                <option value="interviewer">面试官</option>
                                <option value="coach">教练</option>
                                <option value="examiner">考官</option>
                            </select>
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">难度</label>
                            <select
                                className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none bg-white"
                                value={formData.difficulty}
                                onChange={(e) => setFormData(prev => ({ ...prev, difficulty: e.target.value as typeof formData.difficulty }))}
                            >
                                <option value="easy">简单</option>
                                <option value="medium">中等</option>
                                <option value="hard">困难</option>
                            </select>
                        </div>
                    </div>

                    {/* System Prompt */}
                    <div className="space-y-2">
                        <label className="text-xs font-bold text-slate-500 uppercase">系统提示词</label>
                        <p className="text-xs text-slate-400">定义角色的性格、行为特点和回复风格</p>
                        <textarea
                            className="w-full h-64 rounded-lg border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none resize-none font-mono"
                            placeholder="你是一个...的角色，你的特点是：&#10;- 特点1&#10;- 特点2&#10;- 用中文回复"
                            value={formData.system_prompt}
                            onChange={(e) => setFormData(prev => ({ ...prev, system_prompt: e.target.value }))}
                        />
                    </div>

                    <div className="space-y-5 rounded-3xl border border-slate-200 bg-slate-50/70 p-5">
                        <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                            <div>
                                <h3 className="text-base font-bold text-slate-900">当前 Persona 压力模型</h3>
                                <p className="text-xs text-slate-500">
                                    把角色从“提示词风格”升级成可冻结、可审计的 customer pressure contract。这里修改的字段会直接写进 persona_policy.customer_pressure。
                                </p>
                            </div>
                            <Badge variant={customerPressureForm.source === "explicit" ? "green" : customerPressureForm.source === "legacy_sales_focus_extensions" ? "orange" : "secondary"}>
                                {PRESSURE_SOURCE_LABELS[customerPressureForm.source] || customerPressureForm.source || "未配置"}
                            </Badge>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="space-y-2">
                                <label htmlFor="pressure-sales-focus" className="text-xs font-bold text-slate-500 uppercase">主压测方向</label>
                                <select
                                    id="pressure-sales-focus"
                                    aria-label="主压测方向"
                                    className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none bg-white"
                                    value={customerPressureForm.salesFocus}
                                    onChange={(e) => setCustomerPressureForm((prev) => ({ ...prev, salesFocus: e.target.value }))}
                                >
                                    <option value="">未配置</option>
                                    {SALES_FOCUS_OPTIONS.map((option) => (
                                        <option key={option.value} value={option.value}>{option.label}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="space-y-2">
                                <label htmlFor="pressure-question-strategy" className="text-xs font-bold text-slate-500 uppercase">追问策略</label>
                                <select
                                    id="pressure-question-strategy"
                                    aria-label="追问策略"
                                    className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none bg-white"
                                    value={customerPressureForm.questionStrategy}
                                    onChange={(e) => setCustomerPressureForm((prev) => ({ ...prev, questionStrategy: e.target.value }))}
                                >
                                    <option value="">自动回落为单点追问</option>
                                    {dynamicQuestionStrategyOptions.map((option) => (
                                        <option key={option.value} value={option.value}>{option.label}</option>
                                    ))}
                                </select>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="space-y-2">
                                <label htmlFor="pressure-value-axes" className="text-xs font-bold text-slate-500 uppercase">价值维度</label>
                                <p className="text-xs text-slate-400">一行一个，也支持逗号分隔。用于约束角色优先追问客户收益、ROI、预算等价值翻译。</p>
                                <textarea
                                    id="pressure-value-axes"
                                    aria-label="价值维度"
                                    className="w-full h-28 rounded-lg border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none resize-none bg-white"
                                    placeholder="ROI&#10;客户收益&#10;预算优先级"
                                    value={customerPressureForm.valueAxesText}
                                    onChange={(e) => setCustomerPressureForm((prev) => ({ ...prev, valueAxesText: e.target.value }))}
                                />
                            </div>
                            <div className="space-y-2">
                                <label htmlFor="pressure-objection-axes" className="text-xs font-bold text-slate-500 uppercase">异议维度</label>
                                <p className="text-xs text-slate-400">一行一个，也支持逗号分隔。用于约束角色在模糊回答后优先追问的阻塞点。</p>
                                <textarea
                                    id="pressure-objection-axes"
                                    aria-label="异议维度"
                                    className="w-full h-28 rounded-lg border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none resize-none bg-white"
                                    placeholder="价格&#10;竞品替代&#10;实施风险"
                                    value={customerPressureForm.objectionAxesText}
                                    onChange={(e) => setCustomerPressureForm((prev) => ({ ...prev, objectionAxesText: e.target.value }))}
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <label htmlFor="pressure-expected-questions" className="text-xs font-bold text-slate-500 uppercase">示例追问</label>
                            <p className="text-xs text-slate-400">写入 follow_up_behavior.expected_customer_questions，帮助后台预览和后续审计“这个角色会怎么压”。</p>
                            <textarea
                                id="pressure-expected-questions"
                                aria-label="示例追问"
                                className="w-full h-32 rounded-lg border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none resize-none bg-white"
                                placeholder="你拿什么证明这个 ROI 不是口号？&#10;如果预算卡死，你怎么证明这笔钱值？"
                                value={customerPressureForm.expectedQuestionsText}
                                onChange={(e) => setCustomerPressureForm((prev) => ({ ...prev, expectedQuestionsText: e.target.value }))}
                            />
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <label className="flex items-start gap-3 cursor-pointer rounded-2xl border border-slate-200 bg-white p-4">
                                <input
                                    type="checkbox"
                                    aria-label="回避时继续追问"
                                    className="mt-0.5 rounded border-slate-300"
                                    checked={customerPressureForm.revisitOnEvasion}
                                    onChange={(e) => setCustomerPressureForm((prev) => ({ ...prev, revisitOnEvasion: e.target.checked }))}
                                />
                                <div className="space-y-1">
                                    <div className="text-sm font-semibold text-slate-800">回避时继续追问</div>
                                    <div className="text-xs text-slate-500">开启后，销售绕开当前问题时，角色会继续盯住同一个阻塞点，不接受换题带过。</div>
                                </div>
                            </label>
                            <label className="flex items-start gap-3 cursor-pointer rounded-2xl border border-slate-200 bg-white p-4">
                                <input
                                    type="checkbox"
                                    aria-label="要求可验证证据"
                                    className="mt-0.5 rounded border-slate-300"
                                    checked={customerPressureForm.requireEvidence}
                                    onChange={(e) => setCustomerPressureForm((prev) => ({ ...prev, requireEvidence: e.target.checked }))}
                                />
                                <div className="space-y-1">
                                    <div className="text-sm font-semibold text-slate-800">要求可验证证据</div>
                                    <div className="text-xs text-slate-500">开启后，角色会把案例、数据、边界条件等视为“问题解决”的最小凭据。</div>
                                </div>
                            </label>
                        </div>
                    </div>
                </GlassCard>

                {/* Side Panel - Knowledge Base */}
                <div className="space-y-6">
                    <GlassCard className="p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-sm font-bold text-slate-800">专属知识库</h3>
                            {linkedKnowledgeBases.length > 0 && (
                                <Button 
                                    variant="ghost" 
                                    size="sm" 
                                    className="text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-full h-7 px-2"
                                    onClick={() => setIsAddKBOpen(true)}
                                >
                                    <Plus className="w-3 h-3" />
                                </Button>
                            )}
                        </div>
                        <p className="text-xs text-slate-400 mb-4">
                            角色专属知识库，仅在使用此角色时生效
                        </p>
                        {linkedKnowledgeBases.length === 0 ? (
                            <div 
                                className="text-center py-8 border-2 border-dashed border-slate-200 rounded-2xl cursor-pointer hover:border-blue-300 hover:bg-blue-50/30 transition-all"
                                onClick={() => setIsAddKBOpen(true)}
                            >
                                <Database className="w-6 h-6 text-slate-300 mx-auto mb-2" />
                                <p className="text-xs font-bold text-slate-400">+ 关联知识库</p>
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {linkedKnowledgeBases.map((kb) => (
                                    <div 
                                        key={kb.id}
                                        className="flex items-center gap-2 p-3 rounded-xl border border-slate-100 bg-slate-50/50 group hover:bg-white hover:border-slate-200 transition-all"
                                    >
                                        <Database className="w-4 h-4 text-blue-500 flex-shrink-0" />
                                        <div className="flex-1 min-w-0">
                                            <div className="text-sm font-medium text-slate-800 truncate">{kb.name}</div>
                                            <div className="text-[10px] text-slate-400">{kb.document_count} 文档</div>
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-6 w-6 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                                            onClick={() => setRemoveKBTarget(kb)}
                                        >
                                            <X className="w-3 h-3" />
                                        </Button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </GlassCard>

                    <GlassCard className="p-6 space-y-4">
                        <div className="flex items-center justify-between gap-3">
                            <div>
                                <h3 className="text-sm font-bold text-slate-800">压力模型预览</h3>
                                <p className="text-xs text-slate-400 mt-1">
                                    这里显示当前会被冻结到 runtime snapshot 的 customer pressure 关键信号，便于发版前做最后审查。
                                </p>
                            </div>
                            <Badge variant={customerPressureForm.source === "explicit" ? "green" : customerPressureForm.source === "legacy_sales_focus_extensions" ? "orange" : "secondary"}>
                                {PRESSURE_SOURCE_LABELS[customerPressureForm.source] || customerPressureForm.source || "未配置"}
                            </Badge>
                        </div>

                        <div className="grid grid-cols-1 gap-3 text-sm">
                            <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3">
                                <div className="text-[11px] font-bold uppercase tracking-wide text-slate-400">主压测方向</div>
                                <div className="mt-1 font-semibold text-slate-900">{describeSalesFocus(customerPressureForm.salesFocus)}</div>
                            </div>
                            <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3">
                                <div className="text-[11px] font-bold uppercase tracking-wide text-slate-400">追问策略</div>
                                <div className="mt-1 font-semibold text-slate-900">{describeQuestionStrategy(customerPressureForm.questionStrategy)}</div>
                            </div>
                            <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3 space-y-2">
                                <div>
                                    <div className="text-[11px] font-bold uppercase tracking-wide text-slate-400">价值维度</div>
                                    <div className="mt-1 flex flex-wrap gap-2">
                                        {pressureValueAxes.length > 0 ? pressureValueAxes.map((axis) => (
                                            <Badge key={axis} variant="secondary">{axis}</Badge>
                                        )) : <span className="text-xs text-slate-500">未配置</span>}
                                    </div>
                                </div>
                                <div>
                                    <div className="text-[11px] font-bold uppercase tracking-wide text-slate-400">异议维度</div>
                                    <div className="mt-1 flex flex-wrap gap-2">
                                        {pressureObjectionAxes.length > 0 ? pressureObjectionAxes.map((axis) => (
                                            <Badge key={axis} variant="secondary">{axis}</Badge>
                                        )) : <span className="text-xs text-slate-500">未配置</span>}
                                    </div>
                                </div>
                            </div>
                            <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3 space-y-2">
                                <div className="flex items-center justify-between text-xs text-slate-500">
                                    <span>回避后追问</span>
                                    <span className="font-semibold text-slate-900">{customerPressureForm.revisitOnEvasion ? "开启" : "关闭"}</span>
                                </div>
                                <div className="flex items-center justify-between text-xs text-slate-500">
                                    <span>要求可验证证据</span>
                                    <span className="font-semibold text-slate-900">{customerPressureForm.requireEvidence ? "开启" : "关闭"}</span>
                                </div>
                            </div>
                        </div>

                        <div className="space-y-2">
                            <div className="text-[11px] font-bold uppercase tracking-wide text-slate-400">示例追问</div>
                            {pressureExpectedQuestions.length > 0 ? (
                                <ul className="space-y-2 text-sm text-slate-700">
                                    {pressureExpectedQuestions.map((question) => (
                                        <li key={question} className="rounded-2xl border border-slate-100 bg-slate-50/70 px-3 py-2">
                                            {question}
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <div className="rounded-2xl border border-dashed border-slate-200 px-3 py-4 text-xs text-slate-500">
                                    还没有示例追问。保存前至少给出 1 条真实客户会抛出的追问，方便运营预览角色压测方向。
                                </div>
                            )}
                        </div>

                        {localAuditIssues.length > 0 ? (
                            <div className="space-y-2 rounded-2xl border border-orange-200 bg-orange-50 p-4">
                                <div className="text-xs font-bold uppercase tracking-wide text-orange-700">本地审计提醒</div>
                                <ul className="space-y-2 text-xs text-orange-800">
                                    {localAuditIssues.map((issueType) => (
                                        <li key={issueType}>{PRESSURE_AUDIT_LABELS[issueType] || issueType}</li>
                                    ))}
                                </ul>
                            </div>
                        ) : (
                            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs text-emerald-800">
                                当前 pressure model 已具备可冻结的显式结构；保存后，runtime snapshot 可以直接审计这些字段。
                            </div>
                        )}
                    </GlassCard>

                    {industryPackContract ? (
                        <GlassCard className="p-6 space-y-4">
                            <div className="space-y-2">
                                <h3 className="text-sm font-bold text-slate-800">Industry Pack 合同</h3>
                                <p className="text-xs text-slate-500">
                                    当前运营入口仍复用 persona / knowledge / scenario surfaces，下面这些字段会落到 runtime snapshot 与报告证据里。
                                </p>
                            </div>

                            <div className="flex flex-wrap gap-2">
                                {contractOwnedFieldEntries.map(([group, fields]) => (
                                    <Badge key={group} variant="secondary">
                                        {(OWNED_FIELD_LABELS[group] || group).replace(/_/g, " ") + ` · ${fields.length} 个字段`}
                                    </Badge>
                                ))}
                            </div>

                            <div className="space-y-3 text-xs text-slate-600">
                                <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4 space-y-2">
                                    <div className="font-semibold text-slate-800">当前运行时落点</div>
                                    <div className="space-y-2">
                                        {runtimeTargets.customer_pressure?.persisted_in ? (
                                            <div className="space-y-1">
                                                <div className="font-medium text-slate-700">Customer pressure</div>
                                                <code className="block rounded-xl bg-white px-3 py-2 text-[11px] text-slate-700 break-all">
                                                    {String(runtimeTargets.customer_pressure.persisted_in)}
                                                </code>
                                            </div>
                                        ) : null}
                                        {runtimeTargets.knowledge_bundle?.persisted_in ? (
                                            <div className="space-y-1">
                                                <div className="font-medium text-slate-700">Knowledge bundle</div>
                                                <code className="block rounded-xl bg-white px-3 py-2 text-[11px] text-slate-700 break-all">
                                                    {String(runtimeTargets.knowledge_bundle.persisted_in)}
                                                </code>
                                            </div>
                                        ) : null}
                                    </div>
                                </div>

                                <div className="rounded-2xl border border-blue-200 bg-blue-50 p-4 space-y-2">
                                    <div className="font-semibold text-blue-900">当前绑定摘要</div>
                                    <div className="flex flex-wrap gap-2">
                                        <Badge variant="blue">{`source · ${PRESSURE_SOURCE_LABELS[customerPressureForm.source] || customerPressureForm.source || "未配置"}`}</Badge>
                                        <Badge variant="secondary">{`sales focus · ${describeSalesFocus(customerPressureForm.salesFocus)}`}</Badge>
                                        <Badge variant="secondary">{`KB · ${linkedKnowledgeBases.length}`}</Badge>
                                    </div>
                                    {pressureExpectedQuestions.length > 0 ? (
                                        <div className="rounded-xl bg-white px-3 py-2 text-[11px] text-slate-700">
                                            {pressureExpectedQuestions[0]}
                                        </div>
                                    ) : null}
                                </div>
                            </div>
                        </GlassCard>
                    ) : null}

                    <GlassCard className="p-6 space-y-4">
                        <h3 className="text-sm font-bold text-slate-800">知识库回答策略</h3>
                        <p className="text-xs text-slate-400">
                            控制是否允许联网，以及是否仅基于知识库回答。此设置会写入角色中心策略并在后端强制执行。
                        </p>

                        <label className="flex items-start gap-3 cursor-pointer">
                            <input
                                type="checkbox"
                                className="mt-0.5 rounded border-slate-300"
                                checked={toolPolicyForm.lockToKnowledgeBase}
                                onChange={(e) => {
                                    const nextLocked = e.target.checked;
                                    setToolPolicyForm((prev) => ({
                                        lockToKnowledgeBase: nextLocked,
                                        allowWebSearch: nextLocked ? false : prev.allowWebSearch,
                                    }));
                                }}
                            />
                            <div className="space-y-1">
                                <div className="text-sm font-semibold text-slate-800">仅根据知识库回答（严格锁）</div>
                                <div className="text-xs text-slate-500">
                                    开启后：必须先命中内部知识库才可回答，未命中会明确拒绝猜测；同时禁用联网检索。
                                </div>
                            </div>
                        </label>

                        <label className="flex items-start gap-3 cursor-pointer">
                            <input
                                type="checkbox"
                                className="mt-0.5 rounded border-slate-300"
                                checked={toolPolicyForm.allowWebSearch}
                                disabled={toolPolicyForm.lockToKnowledgeBase}
                                onChange={(e) => {
                                    setToolPolicyForm((prev) => ({
                                        ...prev,
                                        allowWebSearch: e.target.checked,
                                    }));
                                }}
                            />
                            <div className="space-y-1">
                                <div className="text-sm font-semibold text-slate-800">允许联网补充</div>
                                <div className="text-xs text-slate-500">
                                    关闭时仅允许使用内部知识库。开启后可在知识库不足时联网补充公开信息。
                                </div>
                            </div>
                        </label>
                    </GlassCard>

                    {/* TTS Configuration */}
                    <GlassCard className="p-6">
                        <div className="flex items-center gap-2 mb-4">
                            <Volume2 className="w-4 h-4 text-orange-500" />
                            <h3 className="text-sm font-bold text-slate-800">语音配置</h3>
                        </div>
                        <p className="text-xs text-slate-400 mb-4">
                            为该角色配置专属语音，覆盖系统默认设置
                        </p>
                        
                        {/* Voice Selection */}
                        <div className="space-y-4">
                            <div className="space-y-2">
                                <label className="text-xs font-medium text-slate-600">语音角色</label>
                                <select
                                    className="w-full h-9 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-orange-500 outline-none bg-white"
                                    value={ttsConfig.voice}
                                    onChange={(e) => setTtsConfig(prev => ({ ...prev, voice: e.target.value }))}
                                >
                                    {VOICE_OPTIONS.map(opt => (
                                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                                    ))}
                                </select>
                            </div>

                            {/* Rate */}
                            <div className="space-y-2">
                                <div className="flex justify-between items-center">
                                    <label className="text-xs font-medium text-slate-600">语速</label>
                                    <span className="text-xs font-mono text-slate-500">{ttsConfig.rate}</span>
                                </div>
                                <input
                                    type="range"
                                    min="-50"
                                    max="100"
                                    step="10"
                                    className="w-full accent-orange-500"
                                    value={parseInt(ttsConfig.rate.replace(/[+%]/g, "")) || 0}
                                    onChange={(e) => {
                                        const val = parseInt(e.target.value);
                                        const rate = val >= 0 ? `+${val}%` : `${val}%`;
                                        setTtsConfig(prev => ({ ...prev, rate }));
                                    }}
                                />
                                <div className="flex justify-between text-[10px] text-slate-400">
                                    <span>慢</span>
                                    <span>正常</span>
                                    <span>快</span>
                                </div>
                            </div>

                            {/* Volume */}
                            <div className="space-y-2">
                                <div className="flex justify-between items-center">
                                    <label className="text-xs font-medium text-slate-600">音量</label>
                                    <span className="text-xs font-mono text-slate-500">{ttsConfig.volume}</span>
                                </div>
                                <input
                                    type="range"
                                    min="-50"
                                    max="50"
                                    step="10"
                                    className="w-full accent-orange-500"
                                    value={parseInt(ttsConfig.volume.replace(/[+%]/g, "")) || 0}
                                    onChange={(e) => {
                                        const val = parseInt(e.target.value);
                                        const volume = val >= 0 ? `+${val}%` : `${val}%`;
                                        setTtsConfig(prev => ({ ...prev, volume }));
                                    }}
                                />
                                <div className="flex justify-between text-[10px] text-slate-400">
                                    <span>低</span>
                                    <span>正常</span>
                                    <span>高</span>
                                </div>
                            </div>

                            {/* Pitch */}
                            <div className="space-y-2">
                                <div className="flex justify-between items-center">
                                    <label className="text-xs font-medium text-slate-600">音调</label>
                                    <span className="text-xs font-mono text-slate-500">{ttsConfig.pitch}</span>
                                </div>
                                <input
                                    type="range"
                                    min="-50"
                                    max="50"
                                    step="10"
                                    className="w-full accent-orange-500"
                                    value={parseInt(ttsConfig.pitch.replace(/[+Hz]/g, "")) || 0}
                                    onChange={(e) => {
                                        const val = parseInt(e.target.value);
                                        const pitch = val >= 0 ? `+${val}Hz` : `${val}Hz`;
                                        setTtsConfig(prev => ({ ...prev, pitch }));
                                    }}
                                />
                                <div className="flex justify-between text-[10px] text-slate-400">
                                    <span>低沉</span>
                                    <span>正常</span>
                                    <span>尖锐</span>
                                </div>
                            </div>

                            {/* Preview Button */}
                            <Button
                                type="button"
                                variant="outline"
                                className="w-full rounded-full border-orange-200 text-orange-600 hover:bg-orange-50"
                                onClick={async () => {
                                    if (isPreviewingTTS) {
                                        if (previewAudioRef.current) {
                                            previewAudioRef.current.pause();
                                            previewAudioRef.current = null;
                                        }
                                        setIsPreviewingTTS(false);
                                        return;
                                    }
                                    
                                    setIsPreviewingTTS(true);
                                    try {
                                        const blob = await api.adminTools.previewTTSBlob({
                                            text: `你好，我是${formData.name || "AI助手"}，很高兴为您服务。`,
                                            voice: ttsConfig.voice,
                                            rate: ttsConfig.rate,
                                            volume: ttsConfig.volume,
                                            pitch: ttsConfig.pitch,
                                        });

                                        const audioUrl = URL.createObjectURL(blob);
                                        const audio = new Audio(audioUrl);
                                        previewAudioRef.current = audio;
                                        
                                        audio.onended = () => {
                                            setIsPreviewingTTS(false);
                                            URL.revokeObjectURL(audioUrl);
                                        };
                                        // M015/S02/T01 inventory: preview playback/request failures
                                        // should migrate together onto the toast seam.
                                        audio.onerror = () => {
                                            setIsPreviewingTTS(false);
                                            URL.revokeObjectURL(audioUrl);
                                            toast.error("音频播放失败");
                                        };
                                        
                                        await audio.play();
                                    } catch (err) {
                                        debug.error("TTS preview failed:", err);
                                        toast.error(`试听失败：${getApiErrorMessage(err)}`);
                                        setIsPreviewingTTS(false);
                                    }
                                }}
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
                    </GlassCard>
                </div>
            </div>

            {/* Add Knowledge Base Dialog */}
            <Dialog open={isAddKBOpen} onOpenChange={setIsAddKBOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>关联知识库</DialogTitle>
                        <DialogDescription>选择知识库关联到该角色，对话时将自动检索相关内容。</DialogDescription>
                    </DialogHeader>
                    <div className="py-6">
                        {unlinkedKnowledgeBases.length === 0 ? (
                            <div className="text-center py-8 text-slate-400">
                                <p>没有可添加的知识库</p>
                                <p className="text-xs mt-1">请先在知识库管理中创建知识库</p>
                            </div>
                        ) : (
                            <div className="space-y-2 max-h-[300px] overflow-y-auto">
                                {unlinkedKnowledgeBases.map((kb) => {
                                    const isSelected = selectedKBId === kb.id;
                                    return (
                                        <div
                                            key={kb.id}
                                            onClick={() => setSelectedKBId(kb.id)}
                                            className={`flex items-center gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all ${
                                                isSelected 
                                                    ? "border-blue-500 bg-blue-50/50" 
                                                    : "border-slate-100 hover:border-slate-200 hover:bg-slate-50"
                                            }`}
                                        >
                                            <Database className={`w-8 h-8 ${isSelected ? "text-blue-500" : "text-slate-400"}`} />
                                            <div className="flex-1">
                                                <div className="font-bold text-slate-800">{kb.name}</div>
                                                <div className="flex items-center gap-2 mt-1">
                                                    <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                                                        {kb.doc_count || kb.document_count || 0} 文档
                                                    </span>
                                                    {kb.description && (
                                                        <span className="text-xs text-slate-400 truncate max-w-[150px]">
                                                            {kb.description}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                            <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                                                isSelected ? "border-blue-500 bg-blue-500" : "border-slate-300"
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
                            onClick={() => setIsAddKBOpen(false)}
                        >
                            取消
                        </Button>
                        <Button 
                            className="rounded-full bg-slate-900 text-white"
                            onClick={handleAddKnowledgeBase}
                            disabled={!selectedKBId || isAddingKB}
                        >
                            {isAddingKB ? "关联中..." : "关联"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
