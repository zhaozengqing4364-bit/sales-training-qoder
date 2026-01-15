import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { Trophy, Medal, User } from "lucide-react";

export default function LeaderboardPage() {
    const top3 = [
        { rank: 2, name: "李四", score: 92, count: 15, avatar: "bg-slate-200" },
        { rank: 1, name: "张三", score: 95, count: 20, avatar: "bg-yellow-100" },
        { rank: 3, name: "王五", score: 88, count: 12, avatar: "bg-orange-100" },
    ];

    const list = [
        { rank: 4, name: "赵六", score: 85, count: 10, change: "up" },
        { rank: 5, name: "你", score: 82, count: 8, change: "down", isMe: true },
        { rank: 6, name: "钱七", score: 80, count: 7, change: "same" },
    ];

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <header className="flex justify-between items-center">
                <h1 className="text-2xl font-bold text-slate-900">排行榜</h1>
                <div className="flex bg-white p-1 rounded-full shadow-sm border border-slate-100">
                    <button className="px-4 py-1.5 rounded-full bg-slate-900 text-white text-sm font-medium shadow-md">本周</button>
                    <button className="px-4 py-1.5 rounded-full text-slate-500 text-sm font-medium hover:bg-slate-50">本月</button>
                    <button className="px-4 py-1.5 rounded-full text-slate-500 text-sm font-medium hover:bg-slate-50">总榜</button>
                </div>
            </header>

            {/* Top 3 */}
            <div className="flex flex-col md:flex-row items-center md:items-end justify-center gap-6 md:gap-4 py-8">
                {/* Rank 1 (Mobile: First, Desktop: Center/Second) */}
                <GlassCard className="order-1 md:order-2 w-full md:w-1/3 max-w-[280px] p-8 flex flex-col items-center relative z-10 md:-mb-4 bg-gradient-to-t from-yellow-50/50 to-white/90 border-yellow-100 ring-4 ring-yellow-50/50 md:ring-0">
                    <div className="absolute -top-6 text-4xl animate-bounce">👑</div>
                    <div className="w-20 h-20 rounded-full bg-yellow-100 border-4 border-white shadow-xl mb-4 flex items-center justify-center text-2xl">🥇</div>
                    <div className="text-xl font-bold text-slate-900">张三</div>
                    <div className="text-4xl font-black text-yellow-600 mt-2">95<span className="text-sm font-normal text-yellow-500/60">分</span></div>
                    <div className="text-xs text-slate-400 mt-1">20次练习</div>
                </GlassCard>

                {/* Rank 2 (Mobile: Second, Desktop: Left/First) */}
                <GlassCard className="order-2 md:order-1 w-full md:w-1/3 max-w-[240px] p-6 flex flex-col items-center bg-gradient-to-t from-slate-100/50 to-white/80 scale-95 md:scale-100">
                    <div className="w-16 h-16 rounded-full bg-slate-200 border-4 border-white shadow-lg mb-4 flex items-center justify-center text-xl">🥈</div>
                    <div className="text-lg font-bold text-slate-900">李四</div>
                    <div className="text-2xl font-black text-slate-700 mt-2">92<span className="text-sm font-normal text-slate-400">分</span></div>
                    <div className="text-xs text-slate-400 mt-1">15次练习</div>
                </GlassCard>

                {/* Rank 3 (Mobile: Third, Desktop: Right/Third) */}
                <GlassCard className="order-3 md:order-3 w-full md:w-1/3 max-w-[240px] p-6 flex flex-col items-center bg-gradient-to-t from-orange-50/30 to-white/80 scale-95 md:scale-100">
                    <div className="w-16 h-16 rounded-full bg-orange-100 border-4 border-white shadow-lg mb-4 flex items-center justify-center text-xl">🥉</div>
                    <div className="text-lg font-bold text-slate-900">王五</div>
                    <div className="text-2xl font-black text-slate-700 mt-2">88<span className="text-sm font-normal text-slate-400">分</span></div>
                    <div className="text-xs text-slate-400 mt-1">12次练习</div>
                </GlassCard>
            </div>

            {/* List */}
            <GlassCard className="p-0 overflow-hidden">
                <div className="p-4 border-b border-slate-100 flex text-xs font-bold text-slate-400 uppercase tracking-widest bg-slate-50/50">
                    <div className="w-12 md:w-16 text-center">排名</div>
                    <div className="flex-1">用户</div>
                    <div className="w-16 md:w-24 text-center">平均分</div>
                    <div className="w-16 md:w-24 text-center hidden sm:block">练习次数</div>
                    <div className="w-12 md:w-16 text-center hidden sm:block">趋势</div>
                </div>
                <div className="divide-y divide-slate-100">
                    {list.map(item => (
                        <div key={item.rank} className={`flex items-center p-4 hover:bg-slate-50 transition-colors ${item.isMe ? 'bg-blue-50/50 hover:bg-blue-50' : ''}`}>
                            <div className="w-12 md:w-16 text-center font-bold text-slate-500">{item.rank}</div>
                            <div className="flex-1 flex items-center gap-3">
                                <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center shrink-0"><User className="w-4 h-4 text-slate-500" /></div>
                                <span className={`font-medium truncate ${item.isMe ? 'text-blue-700 font-bold' : 'text-slate-700'}`}>
                                    {item.name} {item.isMe && <Badge variant="blue" className="ml-2 scale-75 origin-left">我</Badge>}
                                </span>
                            </div>
                            <div className="w-16 md:w-24 text-center font-bold text-slate-900">{item.score}</div>
                            <div className="w-16 md:w-24 text-center text-slate-500 hidden sm:block">{item.count}</div>
                            <div className="w-12 md:w-16 text-center text-xs hidden sm:block">
                                {item.change === 'up' && <span className="text-emerald-500">▲ 2</span>}
                                {item.change === 'down' && <span className="text-red-500">▼ 1</span>}
                                {item.change === 'same' && <span className="text-slate-300">-</span>}
                            </div>
                        </div>
                    ))}
                </div>
            </GlassCard>
        </div>
    )
}
