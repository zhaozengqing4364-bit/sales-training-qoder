export default function NewcomerTrainingLoading() {
    return (
        <main aria-busy="true" aria-label="正在准备你的训练路径" className="mx-auto max-w-5xl space-y-4 px-4 py-8">
            <div className="h-8 w-48 animate-pulse rounded-lg bg-slate-200" />
            <div className="h-72 animate-pulse rounded-3xl bg-slate-100" />
            <div className="h-40 animate-pulse rounded-2xl bg-slate-100" />
        </main>
    );
}
