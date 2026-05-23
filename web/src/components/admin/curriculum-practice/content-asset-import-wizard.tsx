"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { CaseItemMutationRequest, RoleProfileMutationRequest } from "@/lib/api/types";
import { debug } from "@/lib/debug";

import {
    CONTENT_ASSET_META,
    parseCsvRows,
    type ContentAssetType,
    type CsvRowError,
} from "./content-asset-utils";

export interface ContentAssetImportWizardProps {
    assetType: ContentAssetType;
}

export function ContentAssetImportWizard({ assetType }: ContentAssetImportWizardProps) {
    const router = useRouter();
    const meta = CONTENT_ASSET_META[assetType];
    const isCase = assetType === "case-item";
    const [csvText, setCsvText] = useState("");
    const [csvErrors, setCsvErrors] = useState<CsvRowError[]>([]);
    const [notice, setNotice] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);

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

        setBusy(true);
        const rowErrors: CsvRowError[] = [];
        let createdCount = 0;
        const rows = isCase ? parsed.caseRows : parsed.roleRows;

        for (const item of rows) {
            try {
                if (isCase) {
                    await api.admin.createCaseItem(item.payload as CaseItemMutationRequest);
                } else {
                    await api.admin.createRoleProfile(item.payload as RoleProfileMutationRequest);
                }
                createdCount += 1;
            } catch (err) {
                rowErrors.push({ row: item.row, message: getApiErrorMessage(err) });
            }
        }

        setCsvErrors(rowErrors);
        setBusy(false);

        if (rowErrors.length > 0) {
            setActionError(`CSV 导入部分失败：${rowErrors.length} 行未导入。`);
            return;
        }

        setNotice(`CSV 导入完成：${createdCount} 行。`);
        debug.log("[ContentAssetImportWizard] import completed", { assetType, createdCount });
    };

    return (
        <AdminFormShell
            backHref={meta.basePath}
            backLabel="返回列表"
            title={`批量导入 · ${meta.title}`}
            description="粘贴 CSV 后先做行级校验；发现错误会逐行展示，不会静默丢弃。"
        >
            {notice && <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}
            {actionError && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{actionError}</div>}

            <GlassCard className="space-y-4 p-6">
                <textarea
                    className="min-h-28 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                    value={csvText}
                    onChange={(event) => setCsvText(event.target.value)}
                    placeholder={isCase
                        ? "CSV 列格式：industry,company_profile,customer_role,pain1;pain2,objection1;objection2,hidden_information,success1;success2,content_hash"
                        : "CSV 列格式：role_name,communication_style,pressure_level,knowledge1;knowledge2,rule1;rule2,voice_style_hint,content_hash"}
                />
                <div className="flex flex-wrap gap-3">
                    <Button variant="outline" onClick={handleCsvValidate} disabled={busy}>校验 CSV</Button>
                    <Button onClick={() => { void handleCsvImport(); }} disabled={busy}>
                        {busy ? "导入中..." : "导入 CSV"}
                    </Button>
                    <Button variant="outline" onClick={() => router.push(meta.basePath)}>完成并返回列表</Button>
                </div>
                {csvErrors.length > 0 && (
                    <ul className="space-y-1 rounded-2xl border border-red-100 bg-red-50 p-4 text-sm text-red-700">
                        {csvErrors.map((item) => <li key={`${item.row}-${item.message}`}>第 {item.row} 行：{item.message}</li>)}
                    </ul>
                )}
            </GlassCard>
        </AdminFormShell>
    );
}
