
export default function Loading() {
    return (
        <div
            role="status"
            aria-live="polite"
            aria-busy="true"
            className="w-full h-[600px] flex items-center justify-center"
        >
            <div className="flex flex-col items-center gap-6">
                <span className="sr-only">正在加载管理后台</span>
                {/* 玻璃拟态加载动画 */}
                <div className="relative w-24 h-24">
                    <div className="absolute inset-0 rounded-full border-4 border-slate-100/50" />
                    <div className="absolute inset-0 rounded-full border-4 border-blue-500/30 border-t-blue-600 animate-spin" />
                    {/* 内层脉冲动画 */}
                    <div className="absolute inset-4 rounded-full bg-blue-500/10 animate-pulse backdrop-blur-sm" />
                </div>
                <div className="text-slate-400 text-sm font-medium tracking-widest animate-pulse">
                    正在加载系统资源...
                </div>
            </div>
        </div>
    )
}
