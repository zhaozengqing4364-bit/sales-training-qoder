"use client";
import { use, useEffect, useState } from "react";
import { ModuleDetail } from "@/components/newcomer-training/module-detail";
import { api } from "@/lib/api/client";
import type { ModuleDetailResponse } from "@/lib/api/types/newcomer-training";
export default function NewcomerModulePage({ params }: { params: Promise<{ moduleId: string }> }) { const { moduleId } = use(params); const [detail, setDetail] = useState<ModuleDetailResponse | null>(null); const [error, setError] = useState(false); useEffect(() => { api.newcomerTraining.getModule(moduleId).then(setDetail).catch(() => setError(true)); }, [moduleId]); if (error) return <div role="alert" className="p-8 text-center text-red-700">模块加载失败，请返回训练路径重试。</div>; if (!detail) return <div className="p-8 text-center text-slate-500">正在加载模块…</div>; return <ModuleDetail detail={detail} />; }
