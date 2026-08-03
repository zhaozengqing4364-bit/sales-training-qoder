export default function NotificationsLoading() {
    return <main aria-busy="true" aria-label="正在加载通知与任务" className="mx-auto max-w-4xl space-y-3 px-4 py-8">{[0, 1, 2].map((item) => <div key={item} className="h-28 animate-pulse rounded-2xl bg-slate-100" />)}</main>;
}
