"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { CaseItemRecord, RoleProfileRecord, RoleProfileVoiceCloneRequest } from "@/lib/api/types";
import { debug } from "@/lib/debug";

import { CaseItemForm } from "./case-item-form";
import {
    caseFormFromRecord,
    casePayload,
    CONTENT_ASSET_META,
    emptyCaseItemForm,
    emptyRoleProfileForm,
    roleFormFromRecord,
    rolePayload,
    validateRoleProfilePersonaRef,
    type CaseItemFormState,
    type ContentAssetType,
    type RoleProfileFormState,
} from "./content-asset-utils";
import { RoleProfileForm } from "./role-profile-form";

export interface ContentAssetFormPageProps {
    assetType: ContentAssetType;
    mode: "create" | "edit";
    assetId?: string;
}

export function ContentAssetFormPage({ assetType, mode, assetId }: ContentAssetFormPageProps) {
    const router = useRouter();
    const searchParams = useSearchParams();
    const sourceId = searchParams.get("from");
    const meta = CONTENT_ASSET_META[assetType];
    const isCase = assetType === "case-item";
    const isEdit = mode === "edit";

    const [loading, setLoading] = useState(isEdit || Boolean(sourceId));
    const [loadError, setLoadError] = useState<string | null>(null);
    const [caseForm, setCaseForm] = useState<CaseItemFormState>(() => emptyCaseItemForm());
    const [roleForm, setRoleForm] = useState<RoleProfileFormState>(() => emptyRoleProfileForm());
    const [personaRefError, setPersonaRefError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);
    const [editTitle, setEditTitle] = useState("");
    const [prefillNotice, setPrefillNotice] = useState<string | null>(null);

    useEffect(() => {
        if (isEdit && assetId) {
            void (async () => {
                setLoading(true);
                setLoadError(null);
                try {
                    const found = isCase
                        ? await api.admin.getCaseItem(assetId)
                        : await api.admin.getRoleProfile(assetId);

                    if (found.status !== "draft") {
                        setLoadError("仅草稿资产可编辑。");
                        return;
                    }

                    if (isCase) {
                        const record = found as CaseItemRecord;
                        setCaseForm(caseFormFromRecord(record));
                        setEditTitle(`${record.industry} · ${record.customer_role}`);
                    } else {
                        const record = found as RoleProfileRecord;
                        setRoleForm(roleFormFromRecord(record));
                        setEditTitle(record.role_name);
                    }
                } catch (err) {
                    setLoadError(getApiErrorMessage(err));
                    debug.warn("[ContentAssetFormPage] failed to load asset", { assetType, assetId, error: err });
                } finally {
                    setLoading(false);
                }
            })();
            return;
        }

        if (!isEdit && sourceId) {
            void (async () => {
                setLoading(true);
                setLoadError(null);
                try {
                    const source = isCase
                        ? await api.admin.getCaseItem(sourceId)
                        : await api.admin.getRoleProfile(sourceId);
                    if (isCase) {
                        const record = source as CaseItemRecord;
                        const nextForm = caseFormFromRecord(record);
                        nextForm.customer_role = nextForm.customer_role.endsWith(" (副本)")
                            ? nextForm.customer_role
                            : `${nextForm.customer_role} (副本)`;
                        setCaseForm(nextForm);
                        setPrefillNotice("已基于已发布资产预填。修改内容后请更新 Content Hash，或使用列表中的「复制为新草稿」由服务端自动计算。");
                    } else {
                        const record = source as RoleProfileRecord;
                        const nextForm = roleFormFromRecord(record);
                        nextForm.role_name = nextForm.role_name.endsWith(" (副本)")
                            ? nextForm.role_name
                            : `${nextForm.role_name} (副本)`;
                        setRoleForm(nextForm);
                        setPrefillNotice("已基于已发布资产预填。修改内容后请更新 Content Hash，或使用列表中的「复制为新草稿」由服务端自动计算。");
                    }
                } catch (err) {
                    setLoadError(getApiErrorMessage(err));
                } finally {
                    setLoading(false);
                }
            })();
        }
    }, [assetId, assetType, isCase, isEdit, sourceId]);

    const handleSubmit = async () => {
        setActionError(null);
        setNotice(null);
        setBusy(true);
        try {
            if (isCase) {
                const payload = casePayload(caseForm);
                const saved = isEdit && assetId
                    ? await api.admin.updateCaseItem(assetId, payload)
                    : await api.admin.createCaseItem(payload);
                setNotice(`${isEdit ? "保存" : "创建"}完成：${saved.industry} · ${saved.customer_role}`);
                router.push(meta.basePath);
                return;
            }

            const personaError = await validateRoleProfilePersonaRef(
                (id) => api.admin.getPersona(id),
                roleForm.persona_ref,
            );
            if (personaError) {
                setPersonaRefError(personaError);
                setActionError(`保存失败：${personaError}`);
                return;
            }
            setPersonaRefError(null);
            const payload = rolePayload(roleForm);
            const saved = isEdit && assetId
                ? await api.admin.updateRoleProfile(assetId, payload)
                : await api.admin.createRoleProfile(payload);
            setNotice(`${isEdit ? "保存" : "创建"}完成：${saved.role_name}`);
            router.push(meta.basePath);
        } catch (err) {
            setActionError(`保存失败：${getApiErrorMessage(err)}`);
            debug.warn("[ContentAssetFormPage] failed to save asset", { assetType, error: err });
        } finally {
            setBusy(false);
        }
    };

    const handleVoiceClone = async () => {
        if (!isEdit || !assetId || isCase) return;
        setActionError(null);
        setBusy(true);
        const payload: RoleProfileVoiceCloneRequest = {
            voice_name: roleForm.voice_name,
            voice_sample_url: roleForm.voice_sample_url,
            audio_base64: roleForm.voice_audio_base64,
            content_type: roleForm.voice_content_type,
        };
        try {
            const result = await api.admin.cloneRoleProfileVoice(assetId, payload);
            setNotice(result.voice_id ? `声音克隆完成：${result.voice_id}` : `声音克隆降级：${result.reason_code ?? "fallback"}`);
        } catch (err) {
            setActionError(`声音克隆失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusy(false);
        }
    };

    if (loading) {
        return <GlassCard className="p-8 text-slate-600">正在加载资产...</GlassCard>;
    }

    if (loadError) {
        return (
            <GlassCard className="space-y-4 p-8">
                <p className="text-red-700">{loadError}</p>
                <Button variant="outline" onClick={() => router.push(meta.basePath)}>返回列表</Button>
            </GlassCard>
        );
    }

    const title = isEdit ? `编辑：${editTitle || "草稿资产"}` : `新建${isCase ? "训练案例" : "客户角色"}`;

    return (
        <AdminFormShell
            backHref={meta.basePath}
            backLabel="返回列表"
            title={title}
            description={isEdit ? "草稿资产编辑完成后可返回列表发布。" : meta.description}
        >
            {notice && <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}
            {prefillNotice && <div className="rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">{prefillNotice}</div>}
            {actionError && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{actionError}</div>}

            <GlassCard className="space-y-4 p-6">
                {isCase ? (
                    <CaseItemForm form={caseForm} onChange={setCaseForm} />
                ) : (
                    <RoleProfileForm
                        form={roleForm}
                        onChange={setRoleForm}
                        personaRefError={personaRefError}
                        onPersonaRefChange={() => setPersonaRefError(null)}
                        showVoiceCloneFields={isEdit}
                    />
                )}
                <div className="flex flex-wrap gap-3">
                    <Button onClick={() => { void handleSubmit(); }} disabled={busy}>
                        {busy ? "保存中..." : isEdit ? "保存资产" : "创建资产"}
                    </Button>
                    <Button variant="outline" onClick={() => router.push(meta.basePath)} disabled={busy}>取消</Button>
                    {!isCase && isEdit ? (
                        <Button variant="outline" onClick={() => { void handleVoiceClone(); }} disabled={busy}>
                            提交声音克隆
                        </Button>
                    ) : null}
                </div>
            </GlassCard>
        </AdminFormShell>
    );
}
