"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
    Archive,
    Copy,
    RefreshCw,
    RotateCcw,
    ShieldCheck,
    SlidersHorizontal,
} from "lucide-react";

import { AdminPageHeader, PolicyPageShell } from "@/components/admin/admin-layout-shells";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    ConfigBundleLifecycleMutationResponse,
    ConfigBundlePreviewResponse,
    ConfigBundleValidationResponse,
    ConfigBundleVersionItem,
    RoleplaySituationPack,
    RoleplaySituationPackListResponse,
    RoleplaySituationPackReferenceResponse,
    RoleplaySituationPackResolveResponse,
} from "@/lib/api/types";
import { debug } from "@/lib/debug";
import { cn } from "@/lib/utils";

const ROLEPLAY_SITUATION_PACKS_BUNDLE_KEY = "roleplay.situation_packs.ruleset";
const RUNTIME_POLICY_KEYS = [
    "relationship_history_contradiction",
    "hidden_information_leak",
    "forbidden_topic",
    "persona_style_drift",
];
const RUNTIME_POLICY_ACTIONS = [
    "cancel_or_regenerate_once",
    "regenerate_once",
    "mark_and_continue",
    "mark_for_report",
];

type PackStatus = "draft" | "published" | "archived" | string;

interface RoleplaySituationPackRulesetConfig {
    [key: string]: unknown;
    version: string;
    enabled: boolean;
    packs: Array<Record<string, unknown>>;
}

interface PackFormState {
    code: string;
    label: string;
    version: string;
    status: PackStatus;
    initialStageHint: string;
    relationshipJson: string;
    initialVisibleKeys: string;
    conditionallyVisibleKeys: string;
    hiddenByDefaultKeys: string;
    forbiddenClaimPatterns: string;
    forbiddenTopicCodes: string;
    forbiddenStageCodes: string;
    stageTransitionNotes: string;
    conflictResponseStrategy: string;
    behaviorRulesForPromptOnly: string;
    runtimeViolationPolicyJson: string;
    disclosurePolicyJson: string;
    compatiblePracticeModes: string;
    compatibleScenarioTypes: string;
}

type ConfirmAction =
    | { type: "publish" }
    | { type: "rollback"; version: ConfigBundleVersionItem }
    | { type: "disable" }
    | null;

function asRecord(value: unknown): Record<string, unknown> {
    return value && typeof value === "object" && !Array.isArray(value)
        ? value as Record<string, unknown>
        : {};
}

function asString(value: unknown, fallback = ""): string {
    return typeof value === "string" ? value : fallback;
}

function asStringArray(value: unknown): string[] {
    if (!Array.isArray(value)) return [];
    return value
        .map((item) => (typeof item === "string" ? item.trim() : ""))
        .filter(Boolean);
}

function lineListToText(items?: string[]): string {
    return (items || []).join("\n");
}

function textToLineList(value: string): string[] {
    return value
        .split(/[\n,，]/)
        .map((item) => item.trim())
        .filter(Boolean);
}

function formatJson(value: Record<string, unknown>): string {
    return JSON.stringify(value || {}, null, 2);
}

function parseJsonObject(value: string, label: string): { ok: true; value: Record<string, unknown> } | { ok: false; message: string } {
    try {
        const parsed = JSON.parse(value || "{}");
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
            return { ok: false, message: `${label} 必须是 JSON 对象。` };
        }
        return { ok: true, value: parsed as Record<string, unknown> };
    } catch (error) {
        return {
            ok: false,
            message: `${label} JSON 格式无效：${error instanceof Error ? error.message : "未知错误"}`,
        };
    }
}

function parseJsonObjectOrEmpty(value: string): Record<string, unknown> {
    const parsed = parseJsonObject(value, "field");
    return parsed.ok ? parsed.value : {};
}

function formatStatus(status?: string | null): string {
    switch (status) {
        case "draft": return "草稿";
        case "published": return "已发布";
        case "archived": return "已归档";
        case "disabled": return "已停用";
        case "default": return "默认兜底";
        default: return status || "未记录";
    }
}

function statusVariant(status?: string | null): "green" | "orange" | "gray" | "red" {
    if (status === "published") return "green";
    if (status === "draft") return "orange";
    if (status === "disabled" || status === "archived") return "gray";
    return "gray";
}

function formatDateTime(value?: string | null): string {
    if (!value) return "未记录";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "未记录";
    return date.toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
    });
}

function adminPackFromConfig(pack: Record<string, unknown>): RoleplaySituationPack {
    const visibleScope = asRecord(pack.default_visible_information_scope);
    return {
        code: asString(pack.code),
        label: asString(pack.label),
        version: asString(pack.version),
        status: asString(pack.status, "draft"),
        initial_stage_hint: asString(pack.initial_stage_hint, "opening"),
        relationship_context_defaults: asRecord(
            pack.default_relationship_context ?? pack.relationship_context_defaults,
        ),
        default_visible_information_scope: {
            initial_visible_keys: asStringArray(visibleScope.initial_visible_keys),
            conditionally_visible_keys: asStringArray(visibleScope.conditionally_visible_keys),
            hidden_by_default_keys: asStringArray(visibleScope.hidden_by_default_keys),
        },
        default_forbidden_claim_patterns: asStringArray(pack.default_forbidden_claim_patterns),
        default_forbidden_topic_codes: asStringArray(pack.default_forbidden_topic_codes),
        default_forbidden_stage_codes: asStringArray(pack.default_forbidden_stage_codes),
        stage_transition_notes: asStringArray(pack.stage_transition_notes),
        default_conflict_response_strategy: asString(pack.default_conflict_response_strategy, "neutral_clarification"),
        default_behavior_rules_for_prompt_only: asStringArray(pack.default_behavior_rules_for_prompt_only),
        default_runtime_violation_policy: asRecord(pack.default_runtime_violation_policy) as Record<string, string>,
        default_disclosure_policy: asRecord(pack.default_disclosure_policy),
        compatible_practice_modes: asStringArray(pack.compatible_practice_modes),
        compatible_scenario_types: asStringArray(pack.compatible_scenario_types),
        audit: asRecord(pack.audit),
    };
}

function configPackFromAdmin(pack: RoleplaySituationPack): Record<string, unknown> {
    return {
        code: pack.code,
        label: pack.label,
        version: pack.version,
        status: pack.status,
        initial_stage_hint: pack.initial_stage_hint || "opening",
        default_relationship_context: pack.relationship_context_defaults || {},
        default_visible_information_scope: {
            initial_visible_keys: pack.default_visible_information_scope?.initial_visible_keys || [],
            conditionally_visible_keys: pack.default_visible_information_scope?.conditionally_visible_keys || [],
            hidden_by_default_keys: pack.default_visible_information_scope?.hidden_by_default_keys || [],
        },
        default_forbidden_claim_patterns: pack.default_forbidden_claim_patterns || [],
        default_forbidden_topic_codes: pack.default_forbidden_topic_codes || [],
        default_forbidden_stage_codes: pack.default_forbidden_stage_codes || [],
        stage_transition_notes: pack.stage_transition_notes || [],
        default_conflict_response_strategy: pack.default_conflict_response_strategy || "neutral_clarification",
        default_behavior_rules_for_prompt_only: pack.default_behavior_rules_for_prompt_only || [],
        default_disclosure_policy: pack.default_disclosure_policy || {
            default_hidden: true,
            phases: [],
            never_disclose_keys: [],
        },
        default_runtime_violation_policy: pack.default_runtime_violation_policy || {},
        compatible_practice_modes: pack.compatible_practice_modes || [],
        compatible_scenario_types: pack.compatible_scenario_types || [],
    };
}

function rulesetFromAdminPacks(items: RoleplaySituationPack[]): RoleplaySituationPackRulesetConfig {
    return {
        version: "roleplay_situation_packs_v1",
        enabled: true,
        packs: items.map(configPackFromAdmin),
    };
}

function rulesetFromSnapshot(snapshot?: Record<string, unknown> | null): RoleplaySituationPackRulesetConfig | null {
    if (!snapshot || !Array.isArray(snapshot.packs)) return null;
    return {
        version: asString(snapshot.version, "roleplay_situation_packs_v1"),
        enabled: snapshot.enabled !== false,
        packs: snapshot.packs
            .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item))
            .map((item) => ({ ...item })),
    };
}

function versionSnapshot(version?: ConfigBundleVersionItem | null): Record<string, unknown> | null {
    if (!version) return null;
    return version.snapshot_json ?? version.snapshot ?? null;
}

function lifecycleRuleset(response: ConfigBundleLifecycleMutationResponse): RoleplaySituationPackRulesetConfig | null {
    return rulesetFromSnapshot(response.version?.snapshot_json ?? response.version?.snapshot ?? null);
}

function pickWorkingVersion(versions: ConfigBundleVersionItem[]): ConfigBundleVersionItem | null {
    return versions.find((item) => item.status === "draft")
        ?? versions.find((item) => item.status === "published" || item.status === "disabled")
        ?? versions[0]
        ?? null;
}

function formFromPack(pack: RoleplaySituationPack): PackFormState {
    return {
        code: pack.code,
        label: pack.label,
        version: pack.version,
        status: pack.status,
        initialStageHint: pack.initial_stage_hint || "opening",
        relationshipJson: formatJson(pack.relationship_context_defaults),
        initialVisibleKeys: lineListToText(pack.default_visible_information_scope?.initial_visible_keys),
        conditionallyVisibleKeys: lineListToText(pack.default_visible_information_scope?.conditionally_visible_keys),
        hiddenByDefaultKeys: lineListToText(pack.default_visible_information_scope?.hidden_by_default_keys),
        forbiddenClaimPatterns: lineListToText(pack.default_forbidden_claim_patterns),
        forbiddenTopicCodes: lineListToText(pack.default_forbidden_topic_codes),
        forbiddenStageCodes: lineListToText(pack.default_forbidden_stage_codes),
        stageTransitionNotes: lineListToText(pack.stage_transition_notes),
        conflictResponseStrategy: pack.default_conflict_response_strategy || "neutral_clarification",
        behaviorRulesForPromptOnly: lineListToText(pack.default_behavior_rules_for_prompt_only),
        runtimeViolationPolicyJson: formatJson(pack.default_runtime_violation_policy),
        disclosurePolicyJson: formatJson(pack.default_disclosure_policy || {
            default_hidden: true,
            phases: [],
            never_disclose_keys: [],
        }),
        compatiblePracticeModes: lineListToText(pack.compatible_practice_modes),
        compatibleScenarioTypes: lineListToText(pack.compatible_scenario_types),
    };
}

function buildPackFromForm(form: PackFormState): { ok: true; value: RoleplaySituationPack } | { ok: false; message: string } {
    const code = form.code.trim();
    const label = form.label.trim();
    const version = form.version.trim();
    if (!code || !label || !version) {
        return { ok: false, message: "code、label、version 都必须填写。" };
    }

    const relationship = parseJsonObject(form.relationshipJson, "Relationship defaults");
    if (!relationship.ok) return relationship;
    const violationPolicy = parseJsonObject(form.runtimeViolationPolicyJson, "Runtime violation policy");
    if (!violationPolicy.ok) return violationPolicy;
    const disclosurePolicy = parseJsonObject(form.disclosurePolicyJson, "Disclosure policy");
    if (!disclosurePolicy.ok) return disclosurePolicy;

    return {
        ok: true,
        value: {
            code,
            label,
            version,
            status: form.status || "draft",
            initial_stage_hint: form.initialStageHint.trim() || "opening",
            relationship_context_defaults: relationship.value,
            default_visible_information_scope: {
                initial_visible_keys: textToLineList(form.initialVisibleKeys),
                conditionally_visible_keys: textToLineList(form.conditionallyVisibleKeys),
                hidden_by_default_keys: textToLineList(form.hiddenByDefaultKeys),
            },
            default_forbidden_claim_patterns: textToLineList(form.forbiddenClaimPatterns),
            default_forbidden_topic_codes: textToLineList(form.forbiddenTopicCodes),
            default_forbidden_stage_codes: textToLineList(form.forbiddenStageCodes),
            stage_transition_notes: textToLineList(form.stageTransitionNotes),
            default_conflict_response_strategy: form.conflictResponseStrategy.trim() || "neutral_clarification",
            default_behavior_rules_for_prompt_only: textToLineList(form.behaviorRulesForPromptOnly),
            default_runtime_violation_policy: violationPolicy.value as Record<string, string>,
            default_disclosure_policy: disclosurePolicy.value,
            compatible_practice_modes: textToLineList(form.compatiblePracticeModes),
            compatible_scenario_types: textToLineList(form.compatibleScenarioTypes),
        },
    };
}

function referenceItems(references: RoleplaySituationPackReferenceResponse | null) {
    if (!references) return [];
    return [
        ...references.practice_templates,
        ...references.case_items,
        ...references.personas,
    ];
}

function previewSummaryText(preview: ConfigBundlePreviewResponse | null): string | null {
    if (!preview) return null;
    const summary = preview.preview_summary ?? preview.summary ?? {};
    if (!summary || Object.keys(summary).length === 0) {
        return "后端预览通过，未返回额外摘要。";
    }
    return JSON.stringify(summary, null, 2);
}

export default function RoleplaySituationPacksPage() {
    const [listResponse, setListResponse] = useState<RoleplaySituationPackListResponse | null>(null);
    const [ruleset, setRuleset] = useState<RoleplaySituationPackRulesetConfig | null>(null);
    const [versions, setVersions] = useState<ConfigBundleVersionItem[]>([]);
    const [selectedCode, setSelectedCode] = useState<string | null>(null);
    const [form, setForm] = useState<PackFormState | null>(null);
    const [references, setReferences] = useState<RoleplaySituationPackReferenceResponse | null>(null);
    const [resolvedPack, setResolvedPack] = useState<RoleplaySituationPackResolveResponse | null>(null);
    const [reason, setReason] = useState("");
    const [loading, setLoading] = useState(true);
    const [referencesLoading, setReferencesLoading] = useState(false);
    const [resolveLoading, setResolveLoading] = useState(false);
    const [resolveError, setResolveError] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [validation, setValidation] = useState<ConfigBundleValidationResponse | null>(null);
    const [preview, setPreview] = useState<ConfigBundlePreviewResponse | null>(null);
    const [busyAction, setBusyAction] = useState<string | null>(null);
    const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null);

    const packs = useMemo(
        () => (ruleset?.packs || []).map(adminPackFromConfig),
        [ruleset],
    );
    const selectedPack = useMemo(
        () => packs.find((pack) => pack.code === selectedCode) ?? packs[0] ?? null,
        [packs, selectedCode],
    );
    const activeVersion = useMemo(
        () => versions.find((item) => item.status === "published" || item.status === "disabled") ?? null,
        [versions],
    );
    const draftVersion = useMemo(
        () => versions.find((item) => item.status === "draft") ?? null,
        [versions],
    );
    const historyVersions = useMemo(
        () => versions.filter((item) => item.status !== "draft"),
        [versions],
    );
    const referenceList = referenceItems(references);
    const previewText = previewSummaryText(preview);
    const relationshipDefaults = useMemo(
        () => parseJsonObjectOrEmpty(form?.relationshipJson ?? "{}"),
        [form?.relationshipJson],
    );
    const runtimeViolationPolicy = useMemo(
        () => parseJsonObjectOrEmpty(form?.runtimeViolationPolicyJson ?? "{}"),
        [form?.runtimeViolationPolicyJson],
    );
    const disclosurePolicy = useMemo(
        () => parseJsonObjectOrEmpty(form?.disclosurePolicyJson ?? "{}"),
        [form?.disclosurePolicyJson],
    );

    const patchRelationshipDefaults = (patch: Record<string, unknown>) => {
        if (!form) return;
        setForm({ ...form, relationshipJson: formatJson({ ...relationshipDefaults, ...patch }) });
    };
    const patchRuntimeViolationPolicy = (key: string, value: string) => {
        if (!form) return;
        setForm({
            ...form,
            runtimeViolationPolicyJson: formatJson({ ...runtimeViolationPolicy, [key]: value }),
        });
    };
    const patchDisclosurePolicy = (patch: Record<string, unknown>) => {
        if (!form) return;
        setForm({
            ...form,
            disclosurePolicyJson: formatJson({ ...disclosurePolicy, ...patch }),
        });
    };

    const loadPage = useCallback(async (preferredCode?: string | null) => {
        setLoading(true);
        setError(null);
        try {
            const [packList, versionList] = await Promise.all([
                api.admin.listRoleplaySituationPacks(),
                api.admin.listConfigBundleVersions(ROLEPLAY_SITUATION_PACKS_BUNDLE_KEY),
            ]);
            const workingVersion = pickWorkingVersion(versionList.items || []);
            const nextRuleset = rulesetFromSnapshot(versionSnapshot(workingVersion))
                ?? rulesetFromAdminPacks(packList.items || []);
            const nextPacks = nextRuleset.packs.map(adminPackFromConfig);
            const nextCode = preferredCode && nextPacks.some((pack) => pack.code === preferredCode)
                ? preferredCode
                : nextPacks[0]?.code ?? null;

            setListResponse(packList);
            setVersions(versionList.items || []);
            setRuleset(nextRuleset);
            setSelectedCode(nextCode);
            setValidation(null);
            setPreview(null);
            setNotice(null);
            setActionError(null);
        } catch (err) {
            setError(`角色情景包加载失败：${getApiErrorMessage(err)}`);
            debug.warn("[RoleplaySituationPacksPage] failed to load config bundle", { error: err });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void Promise.resolve().then(() => loadPage());
    }, [loadPage]);

    useEffect(() => {
        if (!selectedPack) {
            setForm(null);
            return;
        }
        setForm(formFromPack(selectedPack));
    }, [selectedPack]);

    useEffect(() => {
        if (!selectedCode) {
            setReferences(null);
            setResolvedPack(null);
            setResolveError(null);
            return;
        }

        let cancelled = false;
        setReferencesLoading(true);
        setResolveLoading(true);
        setReferences(null);
        setResolvedPack(null);
        setResolveError(null);

        void Promise.all([
            api.admin.getRoleplaySituationPackReferences(selectedCode),
            api.admin.resolveRoleplaySituationPack(selectedCode),
        ])
            .then(([referenceData, resolveData]) => {
                if (cancelled) return;
                setReferences(referenceData);
                setResolvedPack(resolveData);
            })
            .catch((err) => {
                if (cancelled) return;
                setReferences({
                    practice_templates: [],
                    case_items: [],
                    personas: [],
                    total: 0,
                });
                setResolvedPack(null);
                setResolveError(`解析已发布情景包失败：${getApiErrorMessage(err)}`);
                debug.warn("[RoleplaySituationPacksPage] failed to load references/resolve", { code: selectedCode, error: err });
            })
            .finally(() => {
                if (!cancelled) {
                    setReferencesLoading(false);
                    setResolveLoading(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, [selectedCode]);

    const requireReason = () => {
        const trimmed = reason.trim();
        if (!trimmed) {
            setActionError("保存、发布、回滚或停用前必须填写操作原因，原因会进入审计记录。");
            return null;
        }
        return trimmed;
    };

    const mergedRulesetFromForm = (override?: Partial<RoleplaySituationPack>): { ok: true; value: RoleplaySituationPackRulesetConfig; code: string } | { ok: false; message: string } => {
        if (!ruleset || !form || !selectedPack) {
            return { ok: false, message: "当前没有可编辑的情景包。" };
        }
        const packResult = buildPackFromForm(form);
        if (!packResult.ok) return packResult;
        const nextPack: RoleplaySituationPack = {
            ...packResult.value,
            ...override,
        };
        const nextCode = nextPack.code;
        const duplicate = ruleset.packs
            .map(adminPackFromConfig)
            .some((pack) => pack.code === nextCode && pack.code !== selectedPack.code);
        if (duplicate) {
            return { ok: false, message: `code 已存在：${nextCode}` };
        }
        return {
            ok: true,
            code: nextCode,
            value: {
                ...ruleset,
                packs: [
                    ...ruleset.packs.filter((pack) => adminPackFromConfig(pack).code !== selectedPack.code),
                    configPackFromAdmin(nextPack),
                ],
            },
        };
    };

    const applyLifecycleResponse = async (
        response: ConfigBundleLifecycleMutationResponse,
        preferredCode: string | null,
    ) => {
        const responseRuleset = lifecycleRuleset(response);
        if (responseRuleset) {
            setRuleset(responseRuleset);
            setSelectedCode(preferredCode);
        }
        const latestVersions = await api.admin.listConfigBundleVersions(ROLEPLAY_SITUATION_PACKS_BUNDLE_KEY);
        setVersions(latestVersions.items || []);
    };

    const handleValidate = async () => {
        setActionError(null);
        setNotice(null);
        setPreview(null);
        const next = mergedRulesetFromForm();
        if (!next.ok) {
            setActionError(next.message);
            return;
        }

        setBusyAction("validate");
        try {
            const result = await api.admin.validateConfigBundle(
                ROLEPLAY_SITUATION_PACKS_BUNDLE_KEY,
                { value: next.value, reason: reason.trim() || undefined },
            );
            setValidation(result);
            if (result.normalized_value) {
                const normalized = rulesetFromSnapshot(result.normalized_value);
                if (normalized) setRuleset(normalized);
            }
            setNotice(result.valid ? "后端配置校验通过。" : "后端配置校验未通过，请查看错误。");
        } catch (err) {
            setValidation(null);
            setActionError(`后端校验失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAction(null);
        }
    };

    const handlePreview = async () => {
        setActionError(null);
        setNotice(null);
        setPreview(null);
        const next = mergedRulesetFromForm();
        if (!next.ok) {
            setActionError(next.message);
            return;
        }

        setBusyAction("preview");
        try {
            const result = await api.admin.previewConfigBundle(
                ROLEPLAY_SITUATION_PACKS_BUNDLE_KEY,
                { value: next.value, reason: reason.trim() || undefined },
            );
            setPreview(result);
            setNotice("预览完成；当前运行时仍只消费已发布并冻结到 session 的合同。");
        } catch (err) {
            setActionError(`预览失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAction(null);
        }
    };

    const handleSaveDraft = async (override?: Partial<RoleplaySituationPack>, successCode?: string) => {
        setActionError(null);
        setNotice(null);
        setPreview(null);
        setValidation(null);
        const trimmedReason = requireReason();
        if (!trimmedReason) return;
        const next = mergedRulesetFromForm(override);
        if (!next.ok) {
            setActionError(next.message);
            return;
        }

        setBusyAction("save");
        try {
            const response = await api.admin.createConfigBundleDraft(
                ROLEPLAY_SITUATION_PACKS_BUNDLE_KEY,
                { value: next.value, reason: trimmedReason },
            );
            const nextCode = successCode ?? next.code;
            await applyLifecycleResponse(response, nextCode);
            setNotice(`草稿已保存；audit ${response.audit?.audit_id ?? response.audit_id ?? "已记录"}。`);
        } catch (err) {
            setActionError(`保存草稿失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAction(null);
        }
    };

    const handleCopyAsDraft = async () => {
        if (!selectedPack || !form || !ruleset) return;
        const trimmedReason = requireReason();
        if (!trimmedReason) return;
        const copyBase = `${selectedPack.code}_copy`;
        let copyCode = copyBase;
        let index = 2;
        const codes = new Set(packs.map((pack) => pack.code));
        while (codes.has(copyCode)) {
            copyCode = `${copyBase}_${index}`;
            index += 1;
        }
        const copiedPack: RoleplaySituationPack = {
            ...selectedPack,
            code: copyCode,
            label: `${selectedPack.label} 副本`,
            status: "draft",
            audit: {},
            references: undefined,
        };
        const nextRuleset = {
            ...ruleset,
            packs: [...ruleset.packs, configPackFromAdmin(copiedPack)],
        };

        setBusyAction("copy");
        setActionError(null);
        setNotice(null);
        try {
            const response = await api.admin.createConfigBundleDraft(
                ROLEPLAY_SITUATION_PACKS_BUNDLE_KEY,
                { value: nextRuleset, reason: trimmedReason },
            );
            await applyLifecycleResponse(response, copyCode);
            setNotice(`已复制为草稿：${copyCode}。`);
        } catch (err) {
            setActionError(`复制草稿失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAction(null);
        }
    };

    const handlePublish = async () => {
        const trimmedReason = requireReason();
        if (!trimmedReason) return;
        setBusyAction("publish");
        setActionError(null);
        setNotice(null);
        try {
            const response = await api.admin.publishConfigBundle(
                ROLEPLAY_SITUATION_PACKS_BUNDLE_KEY,
                {
                    config_id: draftVersion?.source_config_id ?? null,
                    reason: trimmedReason,
                },
            );
            await applyLifecycleResponse(response, selectedCode);
            setNotice(`发布完成；audit ${response.audit?.audit_id ?? response.audit_id ?? "已记录"}。`);
        } catch (err) {
            setActionError(`发布失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAction(null);
        }
    };

    const handleRollback = async (version: ConfigBundleVersionItem) => {
        const trimmedReason = requireReason();
        if (!trimmedReason) return;
        setBusyAction("rollback");
        setActionError(null);
        setNotice(null);
        try {
            const response = await api.admin.rollbackConfigBundle(
                ROLEPLAY_SITUATION_PACKS_BUNDLE_KEY,
                {
                    target_config_id: version.source_config_id ?? null,
                    target_version: version.version_number ?? version.version ?? null,
                    reason: trimmedReason,
                },
            );
            await applyLifecycleResponse(response, selectedCode);
            setNotice(`回滚完成；audit ${response.audit?.audit_id ?? response.audit_id ?? "已记录"}。`);
        } catch (err) {
            setActionError(`回滚失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAction(null);
        }
    };

    const handleDisable = async () => {
        const trimmedReason = requireReason();
        if (!trimmedReason) return;
        setBusyAction("disable");
        setActionError(null);
        setNotice(null);
        try {
            const response = await api.admin.disableConfigBundle(
                ROLEPLAY_SITUATION_PACKS_BUNDLE_KEY,
                { reason: trimmedReason },
            );
            await applyLifecycleResponse(response, selectedCode);
            setNotice(`规则集已停用；audit ${response.audit?.audit_id ?? response.audit_id ?? "已记录"}。`);
        } catch (err) {
            setActionError(`停用失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAction(null);
        }
    };

    const handleConfirmAction = () => {
        const action = confirmAction;
        setConfirmAction(null);
        if (!action) return;
        if (action.type === "publish") {
            void handlePublish();
            return;
        }
        if (action.type === "disable") {
            void handleDisable();
            return;
        }
        void handleRollback(action.version);
    };

    if (loading) {
        return (
            <div className="rounded-2xl border border-slate-100 bg-white/80 p-8 text-slate-600">
                正在加载角色情景包...
            </div>
        );
    }

    if (error) {
        return (
            <GlassCard className="space-y-4 border border-amber-200 bg-amber-50/80 p-8">
                <h1 className="text-2xl font-black text-slate-900">角色情景包</h1>
                <p className="text-sm text-amber-800">{error}</p>
                <Button onClick={() => loadPage(selectedCode)}>重试加载</Button>
            </GlassCard>
        );
    }

    return (
        <PolicyPageShell
            header={(
                <AdminPageHeader
                    title="角色情景包"
                    description="管理 Roleplay Situation Pack。页面按单个情景包编辑，保存和发布仍走 ConfigBundle 审计、校验、回滚生命周期。"
                    icon={<SlidersHorizontal className="h-7 w-7 text-slate-700" />}
                    primaryAction={(
                        <Button variant="outline" onClick={() => loadPage(selectedCode)} disabled={busyAction !== null}>
                            <RefreshCw className="mr-2 h-4 w-4" />
                            刷新
                        </Button>
                    )}
                    secondaryActions={(
                        <Badge variant={activeVersion?.status === "disabled" ? "orange" : "green"}>
                            {activeVersion ? formatStatus(activeVersion.status) : "默认配置"}
                        </Badge>
                    )}
                />
            )}
        >
            <ConfirmDialog
                open={!!confirmAction}
                onOpenChange={(open) => {
                    if (!open) setConfirmAction(null);
                }}
                title={confirmAction?.type === "rollback" ? "确认回滚情景包规则集" : confirmAction?.type === "disable" ? "确认停用情景包规则集" : "确认发布情景包草稿"}
                description={confirmAction?.type === "rollback"
                    ? `将规则集回滚到 ${confirmAction.version.version_label ?? `v${confirmAction.version.version_number}`}。原因：${reason.trim()}`
                    : confirmAction?.type === "disable"
                        ? `停用后新发布模板会被配置门禁阻断，历史 session 不重算。原因：${reason.trim()}`
                        : `发布当前 draft，之后新 session 会冻结新合同。原因：${reason.trim()}`}
                confirmText={confirmAction?.type === "rollback" ? "确认回滚" : confirmAction?.type === "disable" ? "确认停用" : "确认发布"}
                variant={confirmAction?.type === "disable" ? "danger" : "warning"}
                onConfirm={handleConfirmAction}
                isLoading={busyAction === "publish" || busyAction === "rollback" || busyAction === "disable"}
            />

            <p className="text-xs text-slate-500">
                配置标识：{ROLEPLAY_SITUATION_PACKS_BUNDLE_KEY} · 读取位置：{listResponse?.management?.read_path as string || "SituationPackRepository"} · 运行时只消费已冻结合同。
            </p>

            <div className="grid gap-4 lg:grid-cols-4">
                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Packs</div>
                    <div className="mt-2 text-2xl font-black text-slate-900">{packs.length}</div>
                    <p className="mt-2 text-sm text-slate-600">当前工作规则集中的情景包数量。</p>
                </GlassCard>
                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Published</div>
                    <div className="mt-2 text-2xl font-black text-slate-900">{packs.filter((pack) => pack.status === "published").length}</div>
                    <p className="mt-2 text-sm text-slate-600">发布状态的情景包会参与新合同编译。</p>
                </GlassCard>
                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Draft Version</div>
                    <div className="mt-2 text-2xl font-black text-slate-900">{draftVersion ? `v${draftVersion.version_number}` : "无"}</div>
                    <p className="mt-2 text-sm text-slate-600">保存草稿后需发布才会生效。</p>
                </GlassCard>
                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Active Version</div>
                    <div className="mt-2 text-2xl font-black text-slate-900">{activeVersion ? `v${activeVersion.version_number}` : "默认"}</div>
                    <p className="mt-2 text-sm text-slate-600">{activeVersion?.version_label || "使用后端默认配置兜底。"}</p>
                </GlassCard>
            </div>

            <div className="grid gap-6 xl:grid-cols-[320px_1fr]">
                <GlassCard className="space-y-4 p-5">
                    <div>
                        <h2 className="text-lg font-black text-slate-900">情景包列表</h2>
                        <p className="mt-1 text-sm text-slate-600">选择一个情景包查看引用、编辑结构化字段。</p>
                    </div>
                    <div className="space-y-2">
                        {packs.map((pack) => (
                            <button
                                type="button"
                                key={pack.code}
                                onClick={() => {
                                    setSelectedCode(pack.code);
                                    setActionError(null);
                                    setNotice(null);
                                    setPreview(null);
                                    setValidation(null);
                                }}
                                className={cn(
                                    "w-full rounded-2xl border p-4 text-left transition-colors",
                                    selectedPack?.code === pack.code
                                        ? "border-blue-200 bg-blue-50/80"
                                        : "border-slate-100 bg-white/80 hover:border-slate-200",
                                )}
                            >
                                <div className="flex items-center justify-between gap-3">
                                    <div className="font-bold text-slate-900">{pack.label}</div>
                                    <Badge variant={statusVariant(pack.status)}>{formatStatus(pack.status)}</Badge>
                                </div>
                                <div className="mt-1 text-xs font-mono text-slate-500">{pack.code}</div>
                                <div className="mt-2 text-xs text-slate-500">version {pack.version}</div>
                            </button>
                        ))}
                    </div>
                </GlassCard>

                <div className="space-y-6">
                    {selectedPack && form ? (
                        <>
                            <GlassCard className="space-y-4 p-6">
                                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                    <div>
                                        <h2 className="text-xl font-black text-slate-900">{selectedPack.label}</h2>
                                        <p className="mt-1 text-sm text-slate-600">
                                            {selectedPack.code} · {selectedPack.version} · {formatStatus(selectedPack.status)}
                                        </p>
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                        <Button variant="outline" onClick={handleCopyAsDraft} disabled={busyAction !== null}>
                                            <Copy className="mr-2 h-4 w-4" />
                                            复制为 draft
                                        </Button>
                                        <Button
                                            variant="outline"
                                            onClick={() => void handleSaveDraft({ status: "archived" }, selectedPack.code)}
                                            disabled={busyAction !== null}
                                        >
                                            <Archive className="mr-2 h-4 w-4" />
                                            标记归档
                                        </Button>
                                    </div>
                                </div>

                                <div className="grid gap-4 md:grid-cols-3">
                                    <div className="rounded-2xl border border-slate-100 bg-slate-50/80 p-4">
                                        <div className="text-xs font-bold uppercase tracking-widest text-slate-500">References</div>
                                        <div className="mt-2 text-2xl font-black text-slate-900">{referencesLoading ? "..." : references?.total ?? 0}</div>
                                    </div>
                                    <div className="rounded-2xl border border-slate-100 bg-slate-50/80 p-4">
                                        <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Initial Visible</div>
                                        <div className="mt-2 text-2xl font-black text-slate-900">{selectedPack.default_visible_information_scope.initial_visible_keys?.length ?? 0}</div>
                                    </div>
                                    <div className="rounded-2xl border border-slate-100 bg-slate-50/80 p-4">
                                        <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Hidden Default</div>
                                        <div className="mt-2 text-2xl font-black text-slate-900">{selectedPack.default_visible_information_scope.hidden_by_default_keys?.length ?? 0}</div>
                                    </div>
                                </div>

                                {referenceList.length > 0 ? (
                                    <div className="rounded-2xl border border-slate-100 bg-white/80 p-4">
                                        <h3 className="text-sm font-bold text-slate-900">引用资产</h3>
                                        <div className="mt-3 grid gap-2">
                                            {referenceList.slice(0, 8).map((item) => (
                                                <div key={`${item.asset_type}-${item.asset_id}`} className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
                                                    <Badge variant="gray">{item.asset_type}</Badge>
                                                    <span className="font-medium text-slate-800">{item.name || item.label || item.asset_id}</span>
                                                    {item.status ? <span className="text-xs text-slate-500">{item.status}</span> : null}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                ) : null}

                                <div className="rounded-2xl border border-slate-100 bg-white/80 p-4 space-y-3">
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <h3 className="text-sm font-bold text-slate-900">已发布 canonical 解析</h3>
                                        <Badge variant={resolveLoading ? "gray" : resolvedPack ? "green" : "orange"}>
                                            {resolveLoading ? "解析中" : resolvedPack ? "已解析" : "不可用"}
                                        </Badge>
                                    </div>
                                    {resolveError ? (
                                        <p className="text-sm text-amber-800">{resolveError}</p>
                                    ) : null}
                                    {resolvedPack ? (
                                        <>
                                            <div className="grid gap-2 text-xs text-slate-600 md:grid-cols-2">
                                                <div>read_path: {resolvedPack.metadata.read_path}</div>
                                                <div>source: {resolvedPack.metadata.source}</div>
                                                <div>ruleset: {resolvedPack.metadata.ruleset_version}</div>
                                                <div>resolved_at: {formatDateTime(resolvedPack.metadata.resolved_at)}</div>
                                            </div>
                                            <div className="grid gap-2 md:grid-cols-3">
                                                <div className="rounded-xl border border-slate-100 bg-slate-50/80 p-3 text-xs text-slate-600">
                                                    visible keys: {resolvedPack.pack.visible_information_scope.initial_visible_keys?.length ?? 0}
                                                </div>
                                                <div className="rounded-xl border border-slate-100 bg-slate-50/80 p-3 text-xs text-slate-600">
                                                    hidden keys: {resolvedPack.pack.visible_information_scope.hidden_by_default_keys?.length ?? 0}
                                                </div>
                                                <div className="rounded-xl border border-slate-100 bg-slate-50/80 p-3 text-xs text-slate-600">
                                                    forbidden patterns: {resolvedPack.pack.forbidden_claim_patterns.length}
                                                </div>
                                            </div>
                                            <p className="text-xs text-slate-500">
                                                编辑区仍合并回 ConfigBundle draft；resolve API 只读展示当前已发布 canonical 合同，供对照引用与发布前审查。
                                            </p>
                                        </>
                                    ) : (
                                        !resolveLoading && !resolveError ? (
                                            <p className="text-sm text-slate-500">当前 code 暂无可解析的已发布情景包。</p>
                                        ) : null
                                    )}
                                </div>
                            </GlassCard>

                            <GlassCard className="space-y-6 p-6">
                                <div>
                                    <h2 className="text-xl font-black text-slate-900">结构化编辑</h2>
                                    <p className="mt-1 text-sm text-slate-600">
                                        编辑当前 pack 后会合并回整个 ruleset draft；后端 validator 负责 schema、首访关系史和 hidden/visible 冲突校验。
                                    </p>
                                </div>

                                <section className="grid gap-4 lg:grid-cols-5">
                                    <label className="space-y-2 text-sm font-semibold text-slate-700">
                                        Code
                                        <input
                                            value={form.code}
                                            onChange={(event) => setForm({ ...form, code: event.target.value })}
                                            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                                        />
                                    </label>
                                    <label className="space-y-2 text-sm font-semibold text-slate-700 lg:col-span-2">
                                        Label
                                        <input
                                            value={form.label}
                                            onChange={(event) => setForm({ ...form, label: event.target.value })}
                                            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                                        />
                                    </label>
                                    <label className="space-y-2 text-sm font-semibold text-slate-700">
                                        Version
                                        <input
                                            value={form.version}
                                            onChange={(event) => setForm({ ...form, version: event.target.value })}
                                            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                                        />
                                    </label>
                                    <label className="space-y-2 text-sm font-semibold text-slate-700">
                                        Status
                                        <select
                                            value={form.status}
                                            onChange={(event) => setForm({ ...form, status: event.target.value })}
                                            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                                        >
                                            <option value="draft">draft</option>
                                            <option value="published">published</option>
                                            <option value="archived">archived</option>
                                        </select>
                                    </label>
                                </section>

                                <section className="grid gap-4 lg:grid-cols-2">
                                    <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
                                        <h3 className="text-sm font-bold text-slate-900">Relationship defaults</h3>
                                        <label className="space-y-2 text-sm font-semibold text-slate-700">
                                            prior_interactions
                                            <select
                                                value={asString(relationshipDefaults.prior_interactions, "none")}
                                                onChange={(event) => patchRelationshipDefaults({ prior_interactions: event.target.value })}
                                                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                                            >
                                                <option value="none">none</option>
                                                <option value="known_contact">known_contact</option>
                                                <option value="prior_meeting">prior_meeting</option>
                                            </select>
                                        </label>
                                        {[
                                            "has_prior_meeting",
                                            "has_seen_proposal",
                                            "has_discussed_budget",
                                            "has_existing_partnership",
                                        ].map((key) => (
                                            <label key={key} className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 px-3 py-2 text-sm font-semibold text-slate-700">
                                                {key}
                                                <input
                                                    type="checkbox"
                                                    checked={Boolean(relationshipDefaults[key])}
                                                    onChange={(event) => patchRelationshipDefaults({ [key]: event.target.checked })}
                                                    className="h-4 w-4"
                                                />
                                            </label>
                                        ))}
                                        <label className="space-y-2 text-sm font-semibold text-slate-700">
                                            meeting_history_summary
                                            <textarea
                                                value={asString(relationshipDefaults.meeting_history_summary)}
                                                onChange={(event) => patchRelationshipDefaults({ meeting_history_summary: event.target.value || null })}
                                                className="min-h-20 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                                            />
                                        </label>
                                    </div>
                                    <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
                                        <h3 className="text-sm font-bold text-slate-900">Runtime violation policy</h3>
                                        {RUNTIME_POLICY_KEYS.map((key) => (
                                            <label key={key} className="grid gap-2 text-sm font-semibold text-slate-700">
                                                <span>{key}</span>
                                                <select
                                                    value={asString(runtimeViolationPolicy[key], "mark_and_continue")}
                                                    onChange={(event) => patchRuntimeViolationPolicy(key, event.target.value)}
                                                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                                                >
                                                    {RUNTIME_POLICY_ACTIONS.map((action) => (
                                                        <option key={action} value={action}>{action}</option>
                                                    ))}
                                                </select>
                                            </label>
                                        ))}
                                    </div>
                                </section>

                                <section className="grid gap-4 lg:grid-cols-3">
                                    <ListTextarea label="Initial visible keys" value={form.initialVisibleKeys} onChange={(value) => setForm({ ...form, initialVisibleKeys: value })} />
                                    <ListTextarea label="Conditionally visible keys" value={form.conditionallyVisibleKeys} onChange={(value) => setForm({ ...form, conditionallyVisibleKeys: value })} />
                                    <ListTextarea label="Hidden by default keys" value={form.hiddenByDefaultKeys} onChange={(value) => setForm({ ...form, hiddenByDefaultKeys: value })} />
                                </section>

                                <section className="grid gap-4 lg:grid-cols-3">
                                    <ListTextarea label="Forbidden claim patterns" value={form.forbiddenClaimPatterns} onChange={(value) => setForm({ ...form, forbiddenClaimPatterns: value })} />
                                    <ListTextarea label="Forbidden topic codes" value={form.forbiddenTopicCodes} onChange={(value) => setForm({ ...form, forbiddenTopicCodes: value })} />
                                    <ListTextarea label="Forbidden stage codes" value={form.forbiddenStageCodes} onChange={(value) => setForm({ ...form, forbiddenStageCodes: value })} />
                                </section>

                                <section className="grid gap-4 lg:grid-cols-2">
                                    <label className="space-y-2 text-sm font-semibold text-slate-700">
                                        Conflict response strategy
                                        <select
                                            value={form.conflictResponseStrategy}
                                            onChange={(event) => setForm({ ...form, conflictResponseStrategy: event.target.value })}
                                            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                                        >
                                            <option value="customer_confused_correction">customer_confused_correction</option>
                                            <option value="neutral_clarification">neutral_clarification</option>
                                            <option value="strict_refusal">strict_refusal</option>
                                        </select>
                                    </label>
                                    <label className="space-y-2 text-sm font-semibold text-slate-700">
                                        Initial stage hint
                                        <input
                                            value={form.initialStageHint}
                                            onChange={(event) => setForm({ ...form, initialStageHint: event.target.value })}
                                            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                                        />
                                    </label>
                                </section>

                                <section className="grid gap-4 lg:grid-cols-2">
                                    <ListTextarea label="Prompt-only behavior rules" value={form.behaviorRulesForPromptOnly} onChange={(value) => setForm({ ...form, behaviorRulesForPromptOnly: value })} />
                                    <ListTextarea label="Stage transition notes" value={form.stageTransitionNotes} onChange={(value) => setForm({ ...form, stageTransitionNotes: value })} />
                                </section>

                                <section className="grid gap-4 lg:grid-cols-2">
                                    <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
                                        <h3 className="text-sm font-bold text-slate-900">Disclosure policy</h3>
                                        <label className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 px-3 py-2 text-sm font-semibold text-slate-700">
                                            default_hidden
                                            <input type="checkbox" checked readOnly className="h-4 w-4" />
                                        </label>
                                        <ListTextarea
                                            label="never_disclose_keys"
                                            value={lineListToText(asStringArray(disclosurePolicy.never_disclose_keys))}
                                            onChange={(value) => patchDisclosurePolicy({ default_hidden: true, never_disclose_keys: textToLineList(value) })}
                                            rows={5}
                                        />
                                        <textarea
                                            readOnly
                                            value={JSON.stringify({ ...disclosurePolicy, default_hidden: true }, null, 2)}
                                            className="min-h-40 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-600"
                                            aria-label="Canonical disclosure policy preview"
                                        />
                                    </div>
                                    <div className="grid gap-4">
                                        <ListTextarea label="Compatible practice modes" value={form.compatiblePracticeModes} onChange={(value) => setForm({ ...form, compatiblePracticeModes: value })} rows={5} />
                                        <ListTextarea label="Compatible scenario types" value={form.compatibleScenarioTypes} onChange={(value) => setForm({ ...form, compatibleScenarioTypes: value })} rows={5} />
                                    </div>
                                </section>

                                <div className="grid gap-3 lg:grid-cols-[1fr_auto_auto_auto_auto] lg:items-center">
                                    <input
                                        value={reason}
                                        onChange={(event) => setReason(event.target.value)}
                                        placeholder="操作原因（保存 / 发布 / 回滚 / 停用必填，进入审计记录）"
                                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                                    />
                                    <Button variant="outline" onClick={handleValidate} disabled={busyAction !== null}>
                                        {busyAction === "validate" ? "校验中..." : "后端校验"}
                                    </Button>
                                    <Button variant="outline" onClick={handlePreview} disabled={busyAction !== null}>
                                        {busyAction === "preview" ? "预览中..." : "预览影响"}
                                    </Button>
                                    <Button variant="outline" onClick={() => void handleSaveDraft()} disabled={busyAction !== null}>
                                        {busyAction === "save" ? "保存中..." : "保存 draft"}
                                    </Button>
                                    <Button
                                        onClick={() => {
                                            const trimmed = requireReason();
                                            if (!trimmed) return;
                                            setConfirmAction({ type: "publish" });
                                        }}
                                        disabled={!draftVersion || busyAction !== null}
                                    >
                                        <ShieldCheck className="mr-2 h-4 w-4" />
                                        发布 draft
                                    </Button>
                                </div>

                                {notice ? (
                                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>
                                ) : null}
                                {actionError ? (
                                    <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{actionError}</div>
                                ) : null}
                                {validation && !validation.valid ? (
                                    <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                                        {validation.errors.map((item) => `${item.field}: ${item.message}`).join("；")}
                                    </div>
                                ) : null}
                                {previewText ? (
                                    <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-2xl border border-blue-100 bg-blue-50/80 p-4 text-xs text-blue-900">
                                        {previewText}
                                    </pre>
                                ) : null}
                            </GlassCard>

                            <GlassCard className="space-y-4 p-6">
                                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                    <div>
                                        <h2 className="text-xl font-black text-slate-900">版本与回滚</h2>
                                        <p className="mt-1 text-sm text-slate-600">回滚、停用和发布都由 ConfigBundle 审计。</p>
                                    </div>
                                    <Button
                                        variant="outline"
                                        onClick={() => {
                                            const trimmed = requireReason();
                                            if (!trimmed) return;
                                            setConfirmAction({ type: "disable" });
                                        }}
                                        disabled={busyAction !== null}
                                    >
                                        停用规则集
                                    </Button>
                                </div>
                                <div className="grid gap-3">
                                    {historyVersions.map((item) => (
                                        <div key={item.version_id} className="flex flex-col gap-3 rounded-2xl border border-slate-100 bg-white/80 p-4 md:flex-row md:items-center md:justify-between">
                                            <div>
                                                <div className="flex flex-wrap items-center gap-2">
                                                    <span className="font-bold text-slate-900">{item.version_label || `v${item.version_number}`}</span>
                                                    <Badge variant={statusVariant(item.status)}>{formatStatus(item.status)}</Badge>
                                                </div>
                                                <div className="mt-1 text-xs text-slate-500">
                                                    source: {item.source_config_id || "default"} · 更新 {formatDateTime(item.updated_at || item.created_at)}
                                                </div>
                                            </div>
                                            <Button
                                                variant="outline"
                                                onClick={() => {
                                                    const trimmed = requireReason();
                                                    if (!trimmed) return;
                                                    setConfirmAction({ type: "rollback", version: item });
                                                }}
                                                disabled={busyAction !== null || item.version_id === activeVersion?.version_id}
                                            >
                                                <RotateCcw className="mr-2 h-4 w-4" />
                                                回滚到此版本
                                            </Button>
                                        </div>
                                    ))}
                                </div>
                            </GlassCard>
                        </>
                    ) : (
                        <GlassCard className="p-8 text-sm text-slate-600">当前规则集没有可编辑的情景包。</GlassCard>
                    )}
                </div>
            </div>
        </PolicyPageShell>
    );
}

function ListTextarea({
    label,
    value,
    onChange,
    rows = 7,
}: {
    label: string;
    value: string;
    onChange: (value: string) => void;
    rows?: number;
}) {
    return (
        <label className="block space-y-2 text-sm font-semibold text-slate-700">
            {label}
            <textarea
                value={value}
                onChange={(event) => onChange(event.target.value)}
                rows={rows}
                className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 font-mono text-xs leading-5 text-slate-700 outline-none focus:ring-2 focus:ring-slate-300"
                placeholder="一行一个值，也支持逗号分隔"
            />
        </label>
    );
}
