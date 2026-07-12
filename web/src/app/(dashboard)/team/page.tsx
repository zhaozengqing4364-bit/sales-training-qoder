"use client";

import Link from "next/link";
import { AlertTriangle, ArrowRight, RefreshCw, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useCurrentUser } from "@/hooks/use-current-user";
import { useTeamJourneys } from "@/hooks/use-team-journeys";
import { getApiErrorMessage } from "@/lib/api/client";
import { toTeamJourneyRow } from "@/lib/team-journey/view-models";

export default function TeamDashboardPage() {
    const { data: currentUser } = useCurrentUser();
    const team = useTeamJourneys({ limit: 50, offset: 0 });
    const role = currentUser?.role;
    if (role && !["training_manager", "admin", "super_admin"].includes(role)) return <EmptyState title="该页面仅向培训负责人开放" description="如需查看团队学习情况，请联系管理员开通相应权限。" icon={<Users className="h-10 w-10 text-slate-300" />} />;
    if (team.isLoading) return <div className="space-y-3">{[1, 2, 3].map((item) => <Skeleton key={item} className="h-24 rounded-2xl" />)}</div>;
    if (team.isError) return <EmptyState title="团队数据加载失败" description={getApiErrorMessage(team.error)} actionLabel="重新加载" onAction={() => void team.refetch()} icon={<RefreshCw className="h-10 w-10 text-slate-300" />} />;
    const rows = (team.journeys.data?.items ?? []).map(toTeamJourneyRow);
    return <main className="space-y-6 pb-20"><header><h1 className="text-3xl font-black text-slate-900">我的团队</h1><p className="mt-2 text-slate-500">按当前训练阶段查看团队进度和需要辅导的活动。</p></header>{rows.length === 0 ? <EmptyState title="本部门暂无训练学员" description="学员进入新人训练路径后会出现在这里。" icon={<Users className="h-10 w-10 text-slate-300" />} /> : <div className="space-y-3">{rows.map((row) => <Link key={row.learnerId} href={`/team/${encodeURIComponent(row.learnerId)}`} className="block rounded-2xl border border-slate-200 bg-white p-5 shadow-sm hover:border-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"><div className="flex items-center gap-4"><div className="flex h-11 w-11 items-center justify-center rounded-full bg-slate-100 font-semibold text-slate-700">{row.learnerName.slice(0, 1)}</div><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><h2 className="truncate font-semibold text-slate-900">{row.learnerName}</h2>{row.riskLabels.length > 0 && <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-1 text-xs text-amber-800"><AlertTriangle className="mr-1 h-3 w-3" />待辅导</span>}</div><p className="mt-1 text-sm text-slate-500">{row.department} · 当前阶段：{row.currentPhase}</p><div className="mt-3 flex items-center gap-3"><div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-600" style={{ width: `${row.progressPercent}%` }} /></div><span className="text-xs text-slate-500">{row.completedCount}/{row.totalRequired}</span></div>{row.riskLabels.length > 0 && <p className="mt-2 text-xs text-amber-800">需关注：{row.riskLabels.join("、")}</p>}</div><ArrowRight className="h-4 w-4 text-slate-400" /></div></Link>)}</div>}<Button variant="outline" onClick={() => void team.refetch()}><RefreshCw className="mr-2 h-4 w-4" />刷新</Button></main>;
}
