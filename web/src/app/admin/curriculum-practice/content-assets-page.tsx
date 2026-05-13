"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    CaseItemMutationRequest,
    CaseItemRecord,
    RoleProfileMutationRequest,
    RoleProfileRecord,
    RoleProfileVoiceCloneRequest,
} from "@/lib/api/types";
import { debug } from "@/lib/debug";

type AssetType = "case-item" | "role-profile";
type AssetRecord = CaseItemRecord | RoleProfileRecord;

interface CsvRowError {
    row: number;
    message: string;
}

interface CsvParseResult {
    caseRows: Array<{ row: number; payload: CaseItemMutationRequest }>;
    roleRows: Array<{ row: number; payload: RoleProfileMutationRequest }>;
    errors: CsvRowError[];
}

interface CaseItemFormState {
    industry: string;
    company_profile: string;
    customer_role: string;
    pain_points: string;
    objections: string;
    hidden_information: string;
    success_criteria: string;
    allowed_disclosure_phases: string;
    content_hash: string;
}

interface RoleProfileFormState {
    role_name: string;
    persona_ref: string;
    communication_style: string;
    pressure_level: "low" | "medium" | "high";
    knowledge_boundary: string;
    behavior_rules: string;
    voice_style_hint: string;
    content_hash: string;
    voice_name: string;
    voice_sample_url: string;
    voice_audio_base64: string;
    voice_content_type: string;
}

function statusVariant(status: string): "green" | "orange" | "gray" {
    if (status === "published") return "green";
    if (status === "draft") return "orange";
    return "gray";
}

function refsFromText(value: string): string[] {
    return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function listFromCsvCell(value: string): string[] {
    return value.split(/[;|]/).map((item) => item.trim()).filter(Boolean);
}

function emptyCaseItemForm(): CaseItemFormState {
    return {
        industry: "",
        company_profile: "",
        customer_role: "",
        pain_points: "",
        objections: "",
        hidden_information: "",
        success_criteria: "",
        allowed_disclosure_phases: "discovery,proposal",
        content_hash: "",
    };
}

function emptyRoleProfileForm(): RoleProfileFormState {
    return {
        role_name: "",
        persona_ref: "",
        communication_style: "",
        pressure_level: "medium",
        knowledge_boundary: "",
        behavior_rules: "",
        voice_style_hint: "",
        content_hash: "",
        voice_name: "",
        voice_sample_url: "",
        voice_audio_base64: "",
        voice_content_type: "audio/wav",
    };
}

function casePayload(form: CaseItemFormState): CaseItemMutationRequest {
    return {
        industry: form.industry,
        company_profile: form.company_profile,
        customer_role: form.customer_role,
        pain_points: refsFromText(form.pain_points),
        objections: refsFromText(form.objections),
        hidden_information: form.hidden_information,
        success_criteria: refsFromText(form.success_criteria),
        allowed_disclosure_policy: { phases: refsFromText(form.allowed_disclosure_phases) },
        content_hash: form.content_hash,
    };
}

function rolePayload(form: RoleProfileFormState): RoleProfileMutationRequest {
    return {
        role_type: "customer",
        role_name: form.role_name,
        persona_ref: form.persona_ref.trim() || null,
        communication_style: form.communication_style,
        pressure_level: form.pressure_level,
        knowledge_boundary: refsFromText(form.knowledge_boundary),
        behavior_rules: refsFromText(form.behavior_rules),
        voice_style_hint: form.voice_style_hint,
        content_hash: form.content_hash,
    };
}

function parseCsvRows(csvText: string, isCase: boolean): CsvParseResult {
    const result: CsvParseResult = { caseRows: [], roleRows: [], errors: [] };
    csvText.split(/\r?\n/).forEach((line, index) => {
        if (!line.trim()) return;
        const row = index + 1;
        const cells = line.split(",").map((cell) => cell.trim());
        if (isCase) {
            if (cells.length < 8 || cells.slice(0, 8).some((cell) => cell.length === 0)) {
                result.errors.push({ row, message: "CaseItem 需要 8 列：industry,company_profile,customer_role,pain_points,objections,hidden_information,success_criteria,content_hash。" });
                return;
            }
            result.caseRows.push({
                row,
                payload: {
                    industry: cells[0],
                    company_profile: cells[1],
                    customer_role: cells[2],
                    pain_points: listFromCsvCell(cells[3]),
                    objections: listFromCsvCell(cells[4]),
                    hidden_information: cells[5],
                    success_criteria: listFromCsvCell(cells[6]),
                    allowed_disclosure_policy: { phases: ["discovery"] },
                    content_hash: cells[7],
                },
            });
            return;
        }

        if (cells.length < 7 || cells.slice(0, 7).some((cell) => cell.length === 0)) {
            result.errors.push({ row, message: "RoleProfile 需要 7 列：role_name,communication_style,pressure_level,knowledge_boundary,behavior_rules,voice_style_hint,content_hash。" });
            return;
        }
        const pressureLevel = cells[2];
        if (pressureLevel !== "low" && pressureLevel !== "medium" && pressureLevel !== "high") {
            result.errors.push({ row, message: "pressure_level 必须是 low、medium 或 high。" });
            return;
        }
        result.roleRows.push({
            row,
            payload: {
                role_type: "customer",
                role_name: cells[0],
                communication_style: cells[1],
                pressure_level: pressureLevel,
                knowledge_boundary: listFromCsvCell(cells[3]),
                behavior_rules: listFromCsvCell(cells[4]),
                voice_style_hint: cells[5],
                content_hash: cells[6],
            },
        });
    });
    return result;
}

function caseFormFromRecord(item: CaseItemRecord): CaseItemFormState {
    const phases = Array.isArray(item.allowed_disclosure_policy.phases)
        ? item.allowed_disclosure_policy.phases.map(String)
        : [];
    return {
        industry: item.industry,
        company_profile: item.company_profile,
        customer_role: item.customer_role,
        pain_points: item.pain_points.join(","),
        objections: item.objections.join(","),
        hidden_information: item.hidden_information,
        success_criteria: item.success_criteria.join(","),
        allowed_disclosure_phases: phases.join(","),
        content_hash: item.content_hash,
    };
}

function roleFormFromRecord(item: RoleProfileRecord): RoleProfileFormState {
    return {
        role_name: item.role_name,
        persona_ref: item.persona_ref ?? "",
        communication_style: item.communication_style,
        pressure_level: item.pressure_level,
        knowledge_boundary: item.knowledge_boundary.join(","),
        behavior_rules: item.behavior_rules.join(","),
        voice_style_hint: item.voice_style_hint,
        content_hash: item.content_hash,
        voice_name: item.voice_id ?? "",
        voice_sample_url: item.voice_sample_url ?? "",
        voice_audio_base64: "",
        voice_content_type: "audio/wav",
    };
}

function recordStatus(item: AssetRecord): string {
    return `${item.status} · v${item.version}`;
}

function isCaseItem(item: AssetRecord): item is CaseItemRecord {
    return "case_item_id" in item;
}

function recordId(item: AssetRecord): string {
    return isCaseItem(item) ? item.case_item_id : item.role_profile_id;
}

function recordTitle(item: AssetRecord): string {
    return isCaseItem(item) ? `${item.industry} · ${item.customer_role}` : item.role_name;
}

function recordSubtitle(item: AssetRecord): string {
    return isCaseItem(item)
        ? `痛点 ${item.pain_points.length} · 异议 ${item.objections.length}`
        : `${item.role_type} · ${item.pressure_level} pressure · persona ${item.persona_ref ?? "未绑定"}`;
}

export function AdminContentAssetsPage({ assetType }: { assetType: AssetType }) {
    const isCase = assetType === "case-item";
    const title = isCase ? "CaseItem 案例库" : "RoleProfile 角色库";
    const description = isCase
        ? "管理客户行业、痛点、异议、隐藏信息和披露策略，发布后可绑定到课程训练模板。"
        : "管理客户角色画像、Persona 复用、压力等级、行为边界和 voice clone 字段。";
    const [items, setItems] = useState<AssetRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [busyId, setBusyId] = useState<string | null>(null);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [query, setQuery] = useState("");
    const [statusFilter, setStatusFilter] = useState("all");
    const [csvText, setCsvText] = useState("");
    const [csvErrors, setCsvErrors] = useState<CsvRowError[]>([]);
    const [caseForm, setCaseForm] = useState<CaseItemFormState>(() => emptyCaseItemForm());
    const [roleForm, setRoleForm] = useState<RoleProfileFormState>(() => emptyRoleProfileForm());

    const loadItems = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const filters = { status: statusFilter, query };
            const response = isCase ? await api.admin.listCaseItems(filters) : await api.admin.listRoleProfiles(filters);
            setItems(response.items);
        } catch (err) {
            setError(`${title} 加载失败：${getApiErrorMessage(err)}`);
            debug.warn("[AdminContentAssetsPage] failed to load content assets", { assetType, error: err });
        } finally {
            setLoading(false);
        }
    }, [assetType, isCase, query, statusFilter, title]);

    useEffect(() => {
        void Promise.resolve().then(loadItems);
    }, [loadItems]);

    const filteredItems = useMemo(() => {
        const normalizedQuery = query.trim().toLowerCase();
        return items.filter((item) => {
            if (!normalizedQuery) return true;
            return [recordTitle(item), recordSubtitle(item), recordId(item)]
                .join(" ")
                .toLowerCase()
                .includes(normalizedQuery);
        });
    }, [items, query]);

    const resetForm = () => {
        setEditingId(null);
        setCaseForm(emptyCaseItemForm());
        setRoleForm(emptyRoleProfileForm());
    };

    const handleEdit = (item: AssetRecord) => {
        setActionError(null);
        setNotice(null);
        setEditingId(recordId(item));
        if (isCaseItem(item)) {
            setCaseForm(caseFormFromRecord(item));
        } else {
            setRoleForm(roleFormFromRecord(item));
        }
    };

    const handleSubmit = async () => {
        setActionError(null);
        setNotice(null);
        try {
            if (isCase) {
                const payload = casePayload(caseForm);
                const saved = editingId
                    ? await api.admin.updateCaseItem(editingId, payload)
                    : await api.admin.createCaseItem(payload);
                setItems((current) => editingId
                    ? current.map((item) => (recordId(item) === saved.case_item_id ? saved : item))
                    : [saved, ...current]);
                setNotice(`${editingId ? "保存" : "创建"}完成：${saved.industry} · ${saved.customer_role}`);
            } else {
                const payload = rolePayload(roleForm);
                const saved = editingId
                    ? await api.admin.updateRoleProfile(editingId, payload)
                    : await api.admin.createRoleProfile(payload);
                setItems((current) => editingId
                    ? current.map((item) => (recordId(item) === saved.role_profile_id ? saved : item))
                    : [saved, ...current]);
                setNotice(`${editingId ? "保存" : "创建"}完成：${saved.role_name}`);
            }
            resetForm();
        } catch (err) {
            setActionError(`保存失败：${getApiErrorMessage(err)}`);
            debug.warn("[AdminContentAssetsPage] failed to save content asset", { assetType, error: err });
        }
    };

    const replaceItem = (next: AssetRecord) => {
        setItems((current) => current.map((item) => (recordId(item) === recordId(next) ? next : item)));
    };

    const handlePublish = async (item: AssetRecord) => {
        setActionError(null);
        setNotice(null);
        setBusyId(recordId(item));
        try {
            const published = isCaseItem(item)
                ? await api.admin.publishCaseItem(item.case_item_id)
                : await api.admin.publishRoleProfile(item.role_profile_id);
            replaceItem(published);
            setNotice(`发布完成：${recordTitle(published)}`);
        } catch (err) {
            setActionError(`发布失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyId(null);
        }
    };

    const handleArchive = async (item: AssetRecord) => {
        setActionError(null);
        setNotice(null);
        setBusyId(recordId(item));
        try {
            const archived = isCaseItem(item)
                ? await api.admin.archiveCaseItem(item.case_item_id)
                : await api.admin.archiveRoleProfile(item.role_profile_id);
            replaceItem(archived);
            setNotice(`归档完成：${recordTitle(archived)}`);
        } catch (err) {
            setActionError(`归档失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyId(null);
        }
    };

    const handleVoiceClone = async () => {
        if (!editingId || isCase) return;
        setActionError(null);
        const payload: RoleProfileVoiceCloneRequest = {
            voice_name: roleForm.voice_name,
            voice_sample_url: roleForm.voice_sample_url,
            audio_base64: roleForm.voice_audio_base64,
            content_type: roleForm.voice_content_type,
        };
        try {
            const result = await api.admin.cloneRoleProfileVoice(editingId, payload);
            setNotice(result.voice_id ? `声音克隆完成：${result.voice_id}` : `声音克隆降级：${result.reason_code ?? "fallback"}`);
            await loadItems();
        } catch (err) {
            setActionError(`声音克隆失败：${getApiErrorMessage(err)}`);
        }
    };

    const handleCsvValidate = () => {
        const parsed = parseCsvRows(csvText, isCase);
        setCsvErrors(parsed.errors);
        setNotice(parsed.errors.length === 0 ? "CSV 预检通过；可执行导入。" : null);
    };

    const handleCsvImport = async () => {
        setActionError(null);
        setNotice(null);
        const parsed = parseCsvRows(csvText, isCase);
        setCsvErrors(parsed.errors);
        if (parsed.errors.length > 0) {
            return;
        }
        const created: AssetRecord[] = [];
        const rowErrors: CsvRowError[] = [];
        const rows = isCase ? parsed.caseRows : parsed.roleRows;
        for (const item of rows) {
            try {
                const record = isCase
                    ? await api.admin.createCaseItem(item.payload as CaseItemMutationRequest)
                    : await api.admin.createRoleProfile(item.payload as RoleProfileMutationRequest);
                created.push(record);
            } catch (err) {
                rowErrors.push({ row: item.row, message: getApiErrorMessage(err) });
            }
        }
        setCsvErrors(rowErrors);
        if (created.length > 0) {
            setItems((current) => [...created, ...current]);
        }
        if (rowErrors.length > 0) {
            setActionError(`CSV 导入部分失败：${rowErrors.length} 行未导入。`);
            return;
        }
        setNotice(`CSV 导入完成：${created.length} 行。`);
    };

    if (loading) {
        return <div className="rounded-2xl border border-slate-100 bg-white/80 p-8 text-slate-600">正在加载{title}...</div>;
    }

    if (error) {
        return (
            <GlassCard className="space-y-4 border border-amber-200 bg-amber-50/80 p-8">
                <h1 className="text-2xl font-black text-slate-900">{title}</h1>
                <p className="text-sm text-amber-800">{error}</p>
                <Button onClick={loadItems}>重试加载</Button>
            </GlassCard>
        );
    }

    return (
        <div className="space-y-8 pb-20">
            <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900">{title}</h1>
                    <p className="mt-2 max-w-3xl text-sm text-slate-600">{description}</p>
                </div>
                <Button variant="outline" onClick={loadItems}>刷新</Button>
            </header>

            {notice && <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}
            {actionError && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{actionError}</div>}

            <GlassCard className="space-y-4 p-6">
                <h2 className="text-xl font-black text-slate-900">{editingId ? "编辑资产" : "创建资产"}</h2>
                {isCase ? (
                    <CaseItemForm form={caseForm} onChange={setCaseForm} />
                ) : (
                    <RoleProfileForm form={roleForm} onChange={setRoleForm} />
                )}
                <div className="flex flex-wrap gap-3">
                    <Button onClick={() => { void handleSubmit(); }}>{editingId ? "保存资产" : "创建资产"}</Button>
                    {editingId && <Button variant="outline" onClick={resetForm}>取消编辑</Button>}
                    {!isCase && editingId && (
                        <Button variant="outline" onClick={() => { void handleVoiceClone(); }}>提交声音克隆</Button>
                    )}
                </div>
            </GlassCard>

            <GlassCard className="space-y-4 p-6">
                <h2 className="text-xl font-black text-slate-900">CSV 批量导入预检</h2>
                <p className="text-sm text-slate-500">粘贴 CSV 后先做行级校验；发现错误会逐行展示，不会静默丢弃。</p>
                <textarea
                    className="min-h-28 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                    value={csvText}
                    onChange={(event) => setCsvText(event.target.value)}
                    placeholder={isCase ? "industry,company_profile,customer_role,pain1;pain2,objection1;objection2,hidden_information,success1;success2,content_hash" : "role_name,communication_style,pressure_level,knowledge1;knowledge2,rule1;rule2,voice_style_hint,content_hash"}
                />
                <div className="flex flex-wrap gap-3">
                    <Button variant="outline" onClick={handleCsvValidate}>校验 CSV</Button>
                    <Button onClick={() => { void handleCsvImport(); }}>导入 CSV</Button>
                </div>
                {csvErrors.length > 0 && (
                    <ul className="space-y-1 rounded-2xl border border-red-100 bg-red-50 p-4 text-sm text-red-700">
                        {csvErrors.map((item) => <li key={`${item.row}-${item.message}`}>第 {item.row} 行：{item.message}</li>)}
                    </ul>
                )}
            </GlassCard>

            <GlassCard className="space-y-4 p-6">
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div>
                        <h2 className="text-xl font-black text-slate-900">资产列表</h2>
                        <p className="text-xs text-slate-500">发布后可在 PracticeTemplate 编辑器中绑定。</p>
                    </div>
                    <Badge variant="gray">{filteredItems.length} / {items.length}</Badge>
                </div>
                <div className="grid gap-3 md:grid-cols-[1fr_180px]">
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>搜索</span>
                        <input className="w-full rounded-xl border border-slate-200 px-3 py-2" value={query} onChange={(event) => setQuery(event.target.value)} />
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>状态</span>
                        <select className="w-full rounded-xl border border-slate-200 px-3 py-2" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                            <option value="all">全部</option>
                            <option value="draft">draft</option>
                            <option value="published">published</option>
                            <option value="archived">archived</option>
                        </select>
                    </label>
                </div>
                <div className="grid gap-3">
                    {filteredItems.map((item) => (
                        <div key={recordId(item)} className="rounded-2xl border border-slate-100 bg-white/80 p-4">
                            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                                <div>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <h3 className="font-bold text-slate-900">{recordTitle(item)}</h3>
                                        <Badge variant={statusVariant(item.status)}>{recordStatus(item)}</Badge>
                                    </div>
                                    <p className="mt-1 text-sm text-slate-600">{recordSubtitle(item)}</p>
                                    <p className="mt-1 text-xs text-slate-500">hash: {item.content_hash}</p>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    {item.status === "draft" ? (
                                        <Button variant="outline" onClick={() => handleEdit(item)}>编辑资产</Button>
                                    ) : (
                                        <span className="self-center text-xs text-slate-500">仅 draft 可编辑</span>
                                    )}
                                    <Button onClick={() => { void handlePublish(item); }} disabled={item.status === "published" || busyId !== null}>
                                        {busyId === recordId(item) ? "发布中..." : "发布资产"}
                                    </Button>
                                    {item.status !== "archived" && (
                                        <Button variant="outline" onClick={() => { void handleArchive(item); }} disabled={busyId !== null}>
                                            {busyId === recordId(item) ? "归档中..." : "归档资产"}
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                    {filteredItems.length === 0 && (
                        <EmptyState title="暂无资产" description="调整搜索或创建一个新的内容资产。" />
                    )}
                </div>
            </GlassCard>
        </div>
    );
}

function CaseItemForm({ form, onChange }: { form: CaseItemFormState; onChange: (next: CaseItemFormState) => void }) {
    const update = (patch: Partial<CaseItemFormState>) => onChange({ ...form, ...patch });
    return (
        <div className="grid gap-4 md:grid-cols-2">
            <TextField label="行业" value={form.industry} onChange={(value) => update({ industry: value })} />
            <TextField label="客户角色" value={form.customer_role} onChange={(value) => update({ customer_role: value })} />
            <TextAreaField label="公司画像" value={form.company_profile} onChange={(value) => update({ company_profile: value })} />
            <TextAreaField label="隐藏信息" value={form.hidden_information} onChange={(value) => update({ hidden_information: value })} />
            <TextField label="痛点（逗号分隔）" value={form.pain_points} onChange={(value) => update({ pain_points: value })} />
            <TextField label="异议（逗号分隔）" value={form.objections} onChange={(value) => update({ objections: value })} />
            <TextField label="成功标准（逗号分隔）" value={form.success_criteria} onChange={(value) => update({ success_criteria: value })} />
            <TextField label="允许披露阶段（逗号分隔）" value={form.allowed_disclosure_phases} onChange={(value) => update({ allowed_disclosure_phases: value })} />
            <TextField label="Content Hash" value={form.content_hash} onChange={(value) => update({ content_hash: value })} />
        </div>
    );
}

function RoleProfileForm({ form, onChange }: { form: RoleProfileFormState; onChange: (next: RoleProfileFormState) => void }) {
    const update = (patch: Partial<RoleProfileFormState>) => onChange({ ...form, ...patch });
    return (
        <div className="grid gap-4 md:grid-cols-2">
            <TextField label="角色名称" value={form.role_name} onChange={(value) => update({ role_name: value })} />
            <TextField label="Persona Ref" value={form.persona_ref} onChange={(value) => update({ persona_ref: value })} />
            <label className="space-y-1 text-sm font-medium text-slate-700">
                <span>压力等级</span>
                <select className="w-full rounded-xl border border-slate-200 px-3 py-2" value={form.pressure_level} onChange={(event) => update({ pressure_level: event.target.value as RoleProfileFormState["pressure_level"] })}>
                    <option value="low">low</option>
                    <option value="medium">medium</option>
                    <option value="high">high</option>
                </select>
            </label>
            <TextField label="知识边界（逗号分隔）" value={form.knowledge_boundary} onChange={(value) => update({ knowledge_boundary: value })} />
            <TextField label="行为规则（逗号分隔）" value={form.behavior_rules} onChange={(value) => update({ behavior_rules: value })} />
            <TextField label="声音风格提示" value={form.voice_style_hint} onChange={(value) => update({ voice_style_hint: value })} />
            <TextAreaField label="沟通风格" value={form.communication_style} onChange={(value) => update({ communication_style: value })} />
            <TextField label="Content Hash" value={form.content_hash} onChange={(value) => update({ content_hash: value })} />
            <TextField label="Voice Name" value={form.voice_name} onChange={(value) => update({ voice_name: value })} />
            <TextField label="Voice Sample URL" value={form.voice_sample_url} onChange={(value) => update({ voice_sample_url: value })} />
            <TextField label="Voice Audio Base64" value={form.voice_audio_base64} onChange={(value) => update({ voice_audio_base64: value })} />
            <TextField label="Voice Content Type" value={form.voice_content_type} onChange={(value) => update({ voice_content_type: value })} />
        </div>
    );
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
    return (
        <label className="space-y-1 text-sm font-medium text-slate-700">
            <span>{label}</span>
            <input className="w-full rounded-xl border border-slate-200 px-3 py-2" value={value} onChange={(event) => onChange(event.target.value)} />
        </label>
    );
}

function TextAreaField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
    return (
        <label className="space-y-1 text-sm font-medium text-slate-700 md:col-span-2">
            <span>{label}</span>
            <textarea className="min-h-24 w-full rounded-xl border border-slate-200 px-3 py-2" value={value} onChange={(event) => onChange(event.target.value)} />
        </label>
    );
}
