"use client";

import { useCallback, useEffect, useState } from "react";

import { ReadinessDossierView } from "@/components/newcomer-training/readiness-dossier-view";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api/client";
import { getFoundationUserErrorMessage } from "@/lib/newcomer-training/errors";
import type { EvidenceDossierV1 } from "@/lib/api/types/newcomer-training";

export default function NewcomerTrainingDossierPage() {
    const [dossier, setDossier] = useState<EvidenceDossierV1 | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    const load = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            setDossier(await api.newcomerTraining.getDossier());
        } catch (loadError) {
            setDossier(null);
            setError(getFoundationUserErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        void load();
    }, [load]);

    if (isLoading) {
        return <main className="min-h-screen bg-slate-50 px-4 py-8"><div className="mx-auto max-w-5xl space-y-4" aria-busy="true" aria-label="正在加载训练档案"><Skeleton className="h-8 w-48" /><Skeleton className="h-44 w-full rounded-3xl" /><Skeleton className="h-80 w-full rounded-3xl" /></div></main>;
    }
    if (error || !dossier) {
        return <main className="min-h-screen bg-slate-50 px-4 py-8"><GlassCard className="mx-auto max-w-xl p-6"><h1 className="text-xl font-semibold text-slate-950">训练档案暂时无法显示</h1><p role="alert" className="mt-2 text-sm leading-6 text-slate-600">{error ?? "档案尚未生成，请先继续完成训练任务。"}</p><Button className="mt-4" onClick={() => void load()}>重新加载</Button></GlassCard></main>;
    }
    return <ReadinessDossierView dossier={dossier} />;
}
