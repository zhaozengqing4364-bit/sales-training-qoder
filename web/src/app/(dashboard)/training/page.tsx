"use client";

import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { Mic, Presentation, Headphones, ArrowRight, Layers, Sparkles } from "lucide-react";
import Link from "next/link";

const TRAINING_CATEGORIES = [
    {
        id: "sales",
        title: "销售能力训练",
        description: "通过与不同性格的 AI 客户进行实战演练，提升 SPIN 提问技巧、异议处理能力和成交率。",
        icon: Mic,
        color: "bg-blue-50 text-blue-600",
        href: "/training/sales",
        agentCount: 4,
        tags: ["谈判技巧", "异议处理", "顾问式销售"]
    },
    {
        id: "presentation",
        title: "演讲与表达训练",
        description: "在模拟舞台中练习演讲，获得关于语速、肢体语言、声音自信度的实时 AI 反馈。",
        icon: Presentation,
        color: "bg-purple-50 text-purple-600",
        href: "/training/presentation",
        agentCount: 3,
        tags: ["融资路演", "产品发布", "季度汇报"]
    },
    {
        id: "customer-service",
        title: "客户服务训练",
        description: "模拟应对愤怒客户、复杂投诉等高压场景，提升共情能力和问题解决效率。",
        icon: Headphones,
        color: "bg-amber-50 text-amber-600",
        href: "/training/customer-service",
        agentCount: 3,
        tags: ["情绪安抚", "投诉处理"]
    }
];

export default function TrainingCategoriesPage() {
    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 pb-20">
            {/* Header */}
            <div className="flex items-end justify-between px-2">
                <div>
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight">训练模式</h1>
                    <div className="mt-2 flex items-center gap-4 flex-wrap">
                        <p className="text-slate-500 text-lg font-medium">选择一个专业领域开始专项提升。</p>
                        <div className="h-4 w-px bg-slate-300 hidden sm:block"></div>
                        <Link href="/history" className="group flex items-center gap-1 text-sm font-bold text-blue-600 hover:text-blue-700 transition-colors">
                            查看我的训练历史 
                            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
                        </Link>
                    </div>
                </div>
            </div>

            {/* Categories Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {TRAINING_CATEGORIES.map((category) => (
                    <Link 
                        key={category.id} 
                        href={category.href}
                        className="block group h-full"
                    >
                        <GlassCard hoverEffect className="h-full p-8 flex flex-col border-transparent group-hover:border-blue-100 transition-all relative overflow-hidden">
                            
                            {/* Background Decoration */}
                            <div className={`absolute -right-10 -top-10 w-40 h-40 rounded-full opacity-10 blur-3xl transition-transform duration-700 group-hover:scale-150 ${category.color.split(' ')[0].replace('50', '400')}`} />

                            <div className="flex justify-between items-start mb-6 relative z-10">
                                <div className={`w-16 h-16 rounded-[1.2rem] flex items-center justify-center ${category.color} shadow-sm group-hover:scale-110 transition-transform duration-300`}>
                                    <category.icon className="w-8 h-8" />
                                </div>
                                <div className="flex items-center gap-1 text-xs font-bold text-slate-400 bg-slate-50 px-2 py-1 rounded-full group-hover:bg-white group-hover:text-blue-600 transition-colors">
                                    <Layers className="w-3 h-3" />
                                    {category.agentCount} 个场景
                                </div>
                            </div>
                            
                            <div className="flex-1 relative z-10">
                                <h3 className="text-2xl font-bold text-slate-900 mb-3 group-hover:text-blue-700 transition-colors">
                                    {category.title}
                                </h3>
                                <p className="text-slate-500 font-medium leading-relaxed mb-6">
                                    {category.description}
                                </p>
                                
                                <div className="flex flex-wrap gap-2">
                                    {category.tags.map(tag => (
                                        <Badge key={tag} variant="secondary" className="bg-white/60 text-slate-600 border border-slate-100/50">
                                            {tag}
                                        </Badge>
                                    ))}
                                </div>
                            </div>

                            <div className="mt-8 pt-6 border-t border-slate-100/60 flex items-center justify-between text-slate-400 group-hover:text-blue-600 transition-colors relative z-10">
                                <span className="text-sm font-bold flex items-center gap-2">
                                    <Sparkles className="w-4 h-4" /> 进入场景库
                                </span>
                                <ArrowRight className="w-5 h-5 transition-transform group-hover:translate-x-1" />
                            </div>
                        </GlassCard>
                    </Link>
                ))}
            </div>
        </div>
    );
}