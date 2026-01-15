"use client";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
// Note: Avatar might not exist in ui folder, check if I need to use simple img or create it. 
// I'll check ui folder content later. If it fails, I'll use <img>. 
// Actually, standard shadcn has Avatar. I should check if it's there. 
// Assuming it might not be there based on `list_dir` output earlier (only 11 files).
// So I will implement a simple Avatar div.

import { User, Mail, Briefcase, Settings, LogOut, Bell, Moon, Volume2 } from "lucide-react";
import { Input } from "@/components/ui/input"; // Checking if input exists. list_dir showed input.tsx.

export default function ProfilePage() {
    return (
        <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-6">
            <h1 className="text-2xl font-bold text-slate-800 mb-6">个人中心</h1>

            {/* User Info Card */}
            <GlassCard className="p-6 flex flex-col md:flex-row items-center gap-6">
                <div className="w-24 h-24 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 text-3xl font-bold border-4 border-white shadow-lg">
                    张
                </div>
                <div className="flex-1 text-center md:text-left space-y-2">
                    <h2 className="text-xl font-bold text-slate-800">张三</h2>
                    <div className="flex flex-col md:flex-row gap-4 text-slate-500 text-sm md:justify-start justify-center">
                        <span className="flex items-center gap-1"><Mail className="w-4 h-4" /> zhangsan@company.com</span>
                        <span className="flex items-center gap-1"><Briefcase className="w-4 h-4" /> 销售部</span>
                    </div>
                </div>
                <Button variant="outline" className="shrink-0">
                    编辑资料
                </Button>
            </GlassCard>

            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <GlassCard className="p-6 text-center">
                    <div className="text-slate-500 text-sm mb-1">总练习时长</div>
                    <div className="text-2xl font-bold text-slate-800">12.5 <span className="text-sm font-normal text-slate-400">小时</span></div>
                </GlassCard>
                <GlassCard className="p-6 text-center">
                    <div className="text-slate-500 text-sm mb-1">本月练习</div>
                    <div className="text-2xl font-bold text-slate-800">12 <span className="text-sm font-normal text-slate-400">次</span></div>
                </GlassCard>
                <GlassCard className="p-6 text-center">
                    <div className="text-slate-500 text-sm mb-1">平均评分</div>
                    <div className="text-2xl font-bold text-indigo-600">76 <span className="text-sm font-normal text-slate-400">分</span></div>
                </GlassCard>
            </div>

            {/* Settings Section */}
            <GlassCard className="p-6">
                <h3 className="text-lg font-semibold text-slate-700 mb-4 flex items-center gap-2">
                    <Settings className="w-5 h-5" /> 系统设置
                </h3>
                <div className="space-y-6">
                    {/* Setting Item */}
                    <div className="flex items-center justify-between py-2 border-b border-slate-100">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-blue-50 flex items-center justify-center text-blue-600">
                                <Volume2 className="w-4 h-4" />
                            </div>
                            <div>
                                <div className="text-slate-700 font-medium">语音播放速度</div>
                                <div className="text-xs text-slate-400">调节 AI 回复的语速</div>
                            </div>
                        </div>
                        <select className="bg-slate-50 border border-slate-200 rounded-md text-sm p-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500/20">
                            <option>0.75x</option>
                            <option>1.0x</option>
                            <option>1.25x</option>
                        </select>
                    </div>

                    {/* Setting Item */}
                    <div className="flex items-center justify-between py-2 border-b border-slate-100">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-amber-50 flex items-center justify-center text-amber-600">
                                <Bell className="w-4 h-4" />
                            </div>
                            <div>
                                <div className="text-slate-700 font-medium">消息通知</div>
                                <div className="text-xs text-slate-400">接收练习提醒和报告推送</div>
                            </div>
                        </div>
                        <div className="relative inline-flex h-6 w-11 items-center rounded-full bg-indigo-600">
                            <span className="translate-x-6 inline-block h-4 w-4 transform rounded-full bg-white transition" />
                        </div>
                    </div>

                    {/* Setting Item */}
                    <div className="flex items-center justify-between py-2">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-slate-600">
                                <Moon className="w-4 h-4" />
                            </div>
                            <div>
                                <div className="text-slate-700 font-medium">深色模式</div>
                                <div className="text-xs text-slate-400">切换系统外观</div>
                            </div>
                        </div>
                        <div className="relative inline-flex h-6 w-11 items-center rounded-full bg-slate-200">
                            <span className="translate-x-1 inline-block h-4 w-4 transform rounded-full bg-white transition" />
                        </div>
                    </div>
                </div>
            </GlassCard>

            <Button variant="destructive" className="w-full md:w-auto" size="lg">
                <LogOut className="w-4 h-4 mr-2" />
                退出登录
            </Button>
        </div>
    );
}
