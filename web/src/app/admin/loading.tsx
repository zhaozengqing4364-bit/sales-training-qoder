
export default function Loading() {
    return (
        <div
            role="status"
            aria-live="polite"
            aria-busy="true"
            className="mx-auto w-full max-w-6xl space-y-5 py-4"
        >
            <span className="sr-only">正在打开管理页面</span>
            <div className="flex items-center justify-between gap-4">
                <div className="space-y-2">
                    <div className="h-7 w-40 rounded-lg bg-slate-200/80 motion-safe:animate-pulse" />
                    <div className="h-4 w-64 max-w-[65vw] rounded bg-slate-100 motion-safe:animate-pulse" />
                </div>
                <div className="h-9 w-24 rounded-full bg-slate-100 motion-safe:animate-pulse" />
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
                <div className="h-4 w-1/3 rounded bg-slate-100 motion-safe:animate-pulse" />
                <div className="mt-4 space-y-3">
                    <div className="h-12 rounded-xl bg-slate-50 motion-safe:animate-pulse" />
                    <div className="h-12 rounded-xl bg-slate-50 motion-safe:animate-pulse" />
                    <div className="h-12 rounded-xl bg-slate-50 motion-safe:animate-pulse" />
                </div>
            </div>
        </div>
    );
}
