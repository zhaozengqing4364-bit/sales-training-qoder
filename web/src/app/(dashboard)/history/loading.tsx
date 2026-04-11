export default function HistoryLoading() {
    return (
        <div
            role="status"
            aria-live="polite"
            aria-busy="true"
            className="p-6 md:p-8 max-w-4xl mx-auto space-y-6 animate-pulse"
        >
            <span className="sr-only">正在加载历史记录</span>
            <div className="h-8 w-32 rounded bg-slate-100" />
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="h-28 rounded-2xl bg-slate-100" />
                <div className="h-28 rounded-2xl bg-slate-100" />
                <div className="h-28 rounded-2xl bg-slate-100" />
                <div className="h-28 rounded-2xl bg-slate-100" />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="h-40 rounded-2xl bg-slate-100" />
                <div className="h-40 rounded-2xl bg-slate-100" />
                <div className="h-40 rounded-2xl bg-slate-100" />
                <div className="h-40 rounded-2xl bg-slate-100" />
            </div>
        </div>
    );
}
