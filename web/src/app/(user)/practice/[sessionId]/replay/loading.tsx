export default function ReplayLoading() {
    return (
        <div
            role="status"
            aria-live="polite"
            aria-busy="true"
            className="p-6 md:p-8 max-w-4xl mx-auto space-y-6 animate-pulse"
        >
            <span className="sr-only">正在加载训练回放</span>
            <div className="h-8 w-40 rounded bg-slate-100" />
            <div className="h-24 rounded-2xl bg-slate-100" />
            <div className="h-64 rounded-2xl bg-slate-100" />
        </div>
    );
}
