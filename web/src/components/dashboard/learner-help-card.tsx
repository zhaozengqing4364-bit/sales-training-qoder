import { LifeBuoy, PanelLeftOpen, ShieldCheck } from "lucide-react";

import { GlassCard } from "@/components/ui/glass-card";
import { cn } from "@/lib/utils";

export function LearnerHelpCard({ className }: { className?: string }) {
    return (
        <GlassCard className={cn("p-5 bg-white/80 border-none shadow-sm ring-1 ring-slate-100", className)}>
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div className="space-y-2">
                    <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-slate-500">
                        <LifeBuoy className="h-3.5 w-3.5" />
                        帮助与反馈
                    </div>
                    <div>
                        <h2 className="text-lg font-bold text-slate-900">需要帮助或反馈？</h2>
                        <p className="mt-1 text-sm leading-6 text-slate-600">
                            统一入口在侧边栏底部的“帮助与反馈”里；手机端先打开左上角菜单。
                        </p>
                    </div>
                </div>

                <div className="grid gap-3 text-sm text-slate-600 md:max-w-[28rem]">
                    <div className="flex gap-3 rounded-2xl border border-slate-100 bg-slate-50/80 px-3 py-3">
                        <PanelLeftOpen className="mt-0.5 h-4 w-4 shrink-0 text-blue-600" />
                        <p>
                            页面异常、入口缺失或结果不对时，请通过这个统一入口反馈当前页面路径或会话编号。
                        </p>
                    </div>
                    <div className="flex gap-3 rounded-2xl border border-slate-100 bg-slate-50/80 px-3 py-3">
                        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                        <p>
                            当前 learner 默认只看到训练、历史、个人中心；运行状态和管理后台只对管理员或支持角色开放。
                        </p>
                    </div>
                </div>
            </div>
        </GlassCard>
    );
}
