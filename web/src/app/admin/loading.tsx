
export default function Loading() {
    return (
        <div className="w-full h-[600px] flex items-center justify-center">
            <div className="flex flex-col items-center gap-6">
                {/* Glassmorphism Loader */}
                <div className="relative w-24 h-24">
                    <div className="absolute inset-0 rounded-full border-4 border-slate-100/50" />
                    <div className="absolute inset-0 rounded-full border-4 border-blue-500/30 border-t-blue-600 animate-spin" />
                    {/* Inner Pulse */}
                    <div className="absolute inset-4 rounded-full bg-blue-500/10 animate-pulse backdrop-blur-sm" />
                </div>
                <div className="text-slate-400 text-sm font-medium tracking-widest uppercase animate-pulse">
                    Loading System Resources...
                </div>
            </div>
        </div>
    )
}
