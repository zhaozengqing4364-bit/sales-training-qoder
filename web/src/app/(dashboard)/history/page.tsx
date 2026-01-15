import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button"; 
import { Mic, Calendar, Clock, ArrowRight, Presentation, ChevronLeft } from "lucide-react";
import Link from "next/link";

export default function HistoryPage() {
    const history = [
        { id: '1', title: "销售对练 - 怀疑型客户", date: "2024-01-15 14:30", duration: "8分32秒", score: 78, type: "sales" },
        { id: '2', title: "PPT 演讲 - 产品介绍", date: "2024-01-13 16:45", duration: "12分05秒", score: 85, type: "ppt" },
        { id: '3', title: "销售对练 - 价格敏感型", date: "2024-01-12 09:15", duration: "6分18秒", score: 82, type: "sales" },
        { id: '4', title: "销售对练 - 急躁CEO", date: "2024-01-10 11:20", duration: "5分45秒", score: 65, type: "sales" },
    ];

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 pb-20">
            {/* Back Button */}
            <div>
                <Link href="/training">
                    <Button variant="ghost" className="pl-0 text-slate-500 hover:text-slate-900 hover:bg-transparent gap-1">
                        <ChevronLeft className="w-4 h-4" />
                        返回训练大厅
                    </Button>
                </Link>
            </div>

            <header className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">训练历史记录</h1>
                    <p className="text-sm text-slate-500 mt-1">回顾您的每一次练习表现</p>
                </div>
                <div className="flex gap-2">
                    <select className="bg-white border-none rounded-lg text-sm text-slate-600 px-3 py-2 shadow-sm focus:ring-2 focus:ring-slate-200 outline-none">
                        <option>全部场景</option>
                        <option>销售对练</option>
                        <option>PPT 演讲</option>
                    </select>
                </div>
            </header>

            <div className="space-y-4">
                {history.map(item => (
                    <Link href={`/practice/${item.id}/report`} key={item.id} className="block group">
                        <GlassCard hoverEffect className="p-6 flex items-center justify-between border border-transparent group-hover:border-blue-200 transition-all">
                            <div className="flex items-center gap-6">
                                <div className={`w-12 h-12 rounded-2xl flex items-center justify-center ${item.type === 'sales' ? 'bg-blue-50 text-blue-600' : 'bg-purple-50 text-purple-600'}`}>
                                    {item.type === 'sales' ? <Mic className="w-6 h-6" /> : <Presentation className="w-6 h-6" />}
                                </div>
                                <div>
                                    <h3 className="text-lg font-bold text-slate-900 group-hover:text-blue-700 transition-colors">{item.title}</h3>
                                    <div className="flex items-center gap-4 text-sm text-slate-500 mt-1">
                                        <span className="flex items-center gap-1.5"><Calendar className="w-4 h-4" /> {item.date}</span>
                                        <span className="flex items-center gap-1.5"><Clock className="w-4 h-4" /> {item.duration}</span>
                                    </div>
                                </div>
                            </div>

                            <div className="flex items-center gap-10">
                                <div className="text-right">
                                    <div className={`text-2xl font-bold ${item.score >= 80 ? 'text-emerald-600' : item.score >= 60 ? 'text-amber-600' : 'text-red-600'}`}>
                                        {item.score}<span className="text-sm font-normal text-slate-400 ml-1">分</span>
                                    </div>
                                    <span className="text-xs text-slate-400 font-medium">综合评分</span>
                                </div>
                                <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center group-hover:bg-blue-600 group-hover:text-white transition-all text-slate-400">
                                    <ArrowRight className="w-5 h-5" />
                                </div>
                            </div>
                        </GlassCard>
                    </Link>
                ))}
            </div>

            <div className="text-center pt-8">
                <Button variant="ghost" className="text-slate-400 hover:text-slate-600">加载更多...</Button>
            </div>
        </div>
    )
}
