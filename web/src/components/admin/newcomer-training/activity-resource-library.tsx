import Link from "next/link";
import {
    BookOpen,
    ClipboardCheck,
    MessageSquareText,
    Presentation,
    type LucideIcon,
} from "lucide-react";

type ActivityResourceGroup = {
    description: string;
    icon: LucideIcon;
    label: string;
    rules: readonly string[];
};

const RESOURCE_GROUPS: readonly ActivityResourceGroup[] = [
    {
        label: "学习资料与学习单元",
        description: "原始资料、整理后的学习单元和来源位置分别保留版本，训练活动只绑定已发布修订。",
        icon: BookOpen,
        rules: ["正式内容保留来源位置", "已发布修订不可原地修改", "历史学习记录继续引用原版本"],
    },
    {
        label: "题目与测验",
        description: "生成结果先进入候选审核，人工批准后才能成为正式题目；测验固定题目和评分规则版本。",
        icon: ClipboardCheck,
        rules: ["候选题不能进入正式测验", "人工审核决定是否入库", "学员开始作答后快照不再变化"],
    },
] as const;

export function ActivityResourceLibrary() {
    return <main className="min-h-screen bg-slate-50 p-4 md:p-6">
        <div className="mx-auto max-w-6xl space-y-6">
            <header className="rounded-2xl border border-slate-200 bg-white p-6">
                <div className="flex items-start gap-4">
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-slate-900 text-white"><Presentation className="h-5 w-5" /></div>
                    <div>
                        <p className="text-sm font-medium text-blue-700">新人训练</p>
                        <h1 className="mt-1 text-2xl font-semibold tracking-[-0.02em] text-slate-950">活动内容库</h1>
                        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">查看新人基础学习与测验采用的版本治理规则。正式编辑、审核和发布操作只向具备对应权限的管理员开放。</p>
                    </div>
                </div>
                <div className="mt-5 flex items-start gap-2 rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm leading-6 text-emerald-900">
                    <MessageSquareText aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>发布新版本不会改变在训学员已经分配的训练版本；需要调整时，必须单独预览影响并确认迁移。</span>
                </div>
            </header>

            <section aria-label="活动内容管理入口" className="grid gap-4 md:grid-cols-2">
                {RESOURCE_GROUPS.map((group) => <article key={group.label} className="rounded-2xl border border-slate-200 bg-white p-5">
                    <div className="flex items-start gap-3">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-700"><group.icon className="h-5 w-5" /></div>
                        <div className="min-w-0"><h2 className="text-lg font-semibold text-slate-950">{group.label}</h2><p className="mt-1 text-sm leading-6 text-slate-600">{group.description}</p></div>
                    </div>
                    <ul className="mt-4 space-y-2 text-sm text-slate-700">{group.rules.map((rule) => <li key={rule} className="flex items-start gap-2"><span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-600" /><span>{rule}</span></li>)}</ul>
                </article>)}
            </section>

            <div className="flex justify-end">
                <Link href="/admin/newcomer-training/learners" prefetch={false} className="inline-flex min-h-10 items-center rounded-lg border border-slate-200 bg-white px-4 text-sm font-medium text-slate-700 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">查看学员训练进度</Link>
            </div>
        </div>
    </main>;
}
