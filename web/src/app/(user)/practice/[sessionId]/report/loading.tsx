export default function ReportLoading() {
    return (
        <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-6 animate-pulse">
            <div className="h-8 w-48 rounded bg-slate-100" />
            <div className="h-36 rounded-2xl bg-slate-100" />
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="h-28 rounded-2xl bg-slate-100" />
                <div className="h-28 rounded-2xl bg-slate-100" />
                <div className="h-28 rounded-2xl bg-slate-100" />
            </div>
            <div className="h-48 rounded-2xl bg-slate-100" />
        </div>
    );
}
