"use client";

import { useEffect, useState } from "react";

import { JourneyHome } from "@/components/newcomer-training/journey-home";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import type { JourneyResponse } from "@/lib/api/types/newcomer-training";

export default function NewcomerTrainingPage() {
    const [journey, setJourney] = useState<JourneyResponse | null>(null);
    const [error, setError] = useState(false);

    useEffect(() => {
        let active = true;
        void api.newcomerTraining.getJourney().then((result) => {
            if (active) setJourney(result);
        }).catch(() => {
            if (active) setError(true);
        });
        return () => { active = false; };
    }, []);

    const retry = async () => {
        setError(false);
        try { setJourney(await api.newcomerTraining.getJourney()); }
        catch { setError(true); }
    };

    if (error) return <div role="alert" className="mx-auto mt-12 max-w-lg rounded-2xl bg-red-50 p-6 text-red-800"><p className="font-semibold">训练路径暂时无法加载</p><Button className="mt-4" variant="secondary" onClick={() => void retry()}>重新加载</Button></div>;
    if (!journey) return <div className="flex min-h-[50vh] items-center justify-center text-sm text-slate-500">正在准备你的训练路径…</div>;
    return <JourneyHome journey={journey} />;
}
