import Link from "next/link";
import { Bell, CheckCircle2, Clock3, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { NotificationCenterViewModel } from "@/lib/newcomer-training/view-models";

const KIND_STYLES = {
    notification: "bg-blue-50 text-blue-700",
    task: "bg-violet-50 text-violet-700",
    decision: "bg-emerald-50 text-emerald-700",
    retraining: "bg-amber-50 text-amber-800",
} as const;

export function NotificationCenter({ model }: { model: NotificationCenterViewModel }) {
    return (
        <main className="min-h-screen bg-slate-50 px-4 py-6 md:px-6 md:py-8">
            <div className="mx-auto max-w-4xl space-y-5">
                <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                        <p className="text-sm font-medium text-blue-700">训练结果位置</p>
                        <h1 className="mt-1 text-2xl font-semibold text-slate-950">通知与后台任务</h1>
                        <p className="mt-2 text-sm leading-6 text-slate-600">离开处理页面不会中断任务；完成后可从这里返回正式业务结果。</p>
                    </div>
                    <Button asChild variant="outline"><Link href="/newcomer-training">返回当前训练</Link></Button>
                </header>

                {model.partialMessage ? (
                    <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{model.partialMessage}</div>
                ) : null}

                {model.items.length === 0 ? (
                    <section className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
                        <Bell aria-hidden="true" className="mx-auto h-9 w-9 text-slate-300" />
                        <h2 className="mt-3 font-semibold text-slate-950">当前没有新的训练通知</h2>
                        <p className="mt-2 text-sm text-slate-600">提交录音、测验或复核后，处理进度和结果入口会保存在这里。</p>
                    </section>
                ) : (
                    <section aria-label="训练通知列表" className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                        <ol className="divide-y divide-slate-100">
                            {model.items.map((item) => (
                                <li key={item.id} className="p-5">
                                    <article className="flex flex-col gap-4 sm:flex-row sm:items-start">
                                        <div className="min-w-0 flex-1">
                                            <div className="flex flex-wrap items-center gap-2">
                                                <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${KIND_STYLES[item.kind]}`}>{item.kindLabel}</span>
                                                <span className="inline-flex items-center gap-1 text-xs text-slate-500">{item.unread ? <Clock3 aria-hidden="true" className="h-3.5 w-3.5" /> : <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5" />}{item.statusLabel}</span>
                                            </div>
                                            <h2 className="mt-3 break-words font-semibold text-slate-950">{item.title}</h2>
                                            <p className="mt-1 break-words text-sm leading-6 text-slate-600">{item.description}</p>
                                            <p className="mt-2 text-xs text-slate-400">更新于 {new Date(item.createdAt).toLocaleString("zh-CN")}</p>
                                        </div>
                                        <Button asChild variant={item.unread ? "primary" : "outline"} className="shrink-0">
                                            <Link href={item.href}>{item.actionLabel}</Link>
                                        </Button>
                                    </article>
                                </li>
                            ))}
                        </ol>
                    </section>
                )}

                {model.page > 1 || model.hasMore ? (
                    <nav aria-label="通知分页" className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3">
                        <span className="text-sm text-slate-500">第 {model.page} 页</span>
                        <div className="flex gap-2">
                            {model.page > 1 ? (
                                <Button asChild size="sm" variant="outline"><Link href={`/newcomer-training/notifications?page=${model.page - 1}`}>上一页</Link></Button>
                            ) : (
                                <Button size="sm" variant="outline" disabled>上一页</Button>
                            )}
                            {model.hasMore ? (
                                <Button asChild size="sm" variant="outline"><Link href={`/newcomer-training/notifications?page=${model.page + 1}`}>下一页</Link></Button>
                            ) : (
                                <Button size="sm" variant="outline" disabled>下一页</Button>
                            )}
                        </div>
                    </nav>
                ) : null}

                <p className="flex items-start gap-2 text-xs leading-5 text-slate-500"><RotateCcw aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0" />网络中断不会把已接受的后台任务标成失败。任务页会在重新连接后继续刷新。</p>
            </div>
        </main>
    );
}
