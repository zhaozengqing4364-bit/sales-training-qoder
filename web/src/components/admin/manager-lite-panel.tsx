"use client";

import Link from "next/link";
import { useState } from "react";
import type { ManagerLiteListsResponse } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";

interface ManagerLitePanelProps {
  data: ManagerLiteListsResponse;
  onRemind: (userId: string) => Promise<void>;
}

function SectionHeader({ title, count }: { title: string; count: number }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h4 className="text-sm font-bold text-slate-900">{title}</h4>
      <span className="text-xs text-slate-500">{count} 人</span>
    </div>
  );
}

export function ManagerLitePanel({ data, onRemind }: ManagerLitePanelProps) {
  const [remindingUserId, setRemindingUserId] = useState<string | null>(null);

  const handleRemind = async (userId: string) => {
    setRemindingUserId(userId);
    try {
      await onRemind(userId);
    } finally {
      setRemindingUserId(null);
    }
  };

  return (
    <GlassCard className="p-6">
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-lg font-bold text-slate-900">主管最小干预面板</h3>
        <span className="text-xs text-slate-500">三类名单 + 一键提醒</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="rounded-2xl bg-rose-50 border border-rose-100 p-4">
          <SectionHeader title="未达标名单" count={data.not_passed.length} />
          <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
            {data.not_passed.length === 0 ? (
              <p className="text-xs text-slate-500">暂无未达标成员</p>
            ) : (
              data.not_passed.map((item) => (
                <div key={`${item.user_id}-${item.session_id}`} className="rounded-xl bg-white/80 border border-rose-100 p-3">
                  <p className="text-sm font-semibold text-slate-900">{item.user_name}</p>
                  <p className="text-xs text-slate-500 mt-1">{item.department || "未分配部门"}</p>
                  <p className="text-xs text-rose-600 mt-1">结果：{item.overall_result}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button asChild size="sm" variant="outline" className="h-8 rounded-full">
                      <Link href={`/practice/${item.session_id}/report`}>查看报告</Link>
                    </Button>
                    <Button
                      size="sm"
                      className="h-8 rounded-full"
                      onClick={() => handleRemind(item.user_id)}
                      disabled={remindingUserId === item.user_id}
                    >
                      {remindingUserId === item.user_id ? "提醒中..." : "一键提醒"}
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="rounded-2xl bg-amber-50 border border-amber-100 p-4">
          <SectionHeader title="连续未练名单" count={data.inactive_streak.length} />
          <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
            {data.inactive_streak.length === 0 ? (
              <p className="text-xs text-slate-500">暂无连续未练成员</p>
            ) : (
              data.inactive_streak.map((item) => (
                <div key={item.user_id} className="rounded-xl bg-white/80 border border-amber-100 p-3">
                  <p className="text-sm font-semibold text-slate-900">{item.user_name}</p>
                  <p className="text-xs text-slate-500 mt-1">{item.department || "未分配部门"}</p>
                  <p className="text-xs text-amber-700 mt-1">连续未练：{item.inactive_days} 天</p>
                  <Button
                    size="sm"
                    className="mt-2 h-8 rounded-full"
                    onClick={() => handleRemind(item.user_id)}
                    disabled={remindingUserId === item.user_id}
                  >
                    {remindingUserId === item.user_id ? "提醒中..." : "一键提醒"}
                  </Button>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="rounded-2xl bg-emerald-50 border border-emerald-100 p-4">
          <SectionHeader title="达标上升名单" count={data.improving.length} />
          <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
            {data.improving.length === 0 ? (
              <p className="text-xs text-slate-500">暂无显著上升成员</p>
            ) : (
              data.improving.map((item) => (
                <div key={item.user_id} className="rounded-xl bg-white/80 border border-emerald-100 p-3">
                  <p className="text-sm font-semibold text-slate-900">{item.user_name}</p>
                  <p className="text-xs text-slate-500 mt-1">{item.department || "未分配部门"}</p>
                  <p className="text-xs text-emerald-700 mt-1">通过率提升：+{item.pass_gain}%</p>
                  <p className="text-[11px] text-slate-500 mt-1">
                    基线 {item.baseline_pass_rate}% → 当前 {item.current_pass_rate}%
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </GlassCard>
  );
}

export default ManagerLitePanel;
