"use client";

import * as React from "react";
import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { Sparkles, User, Zap, TrendingUp, AlertTriangle, Headphones, Mic2, MonitorPlay, Users, Presentation } from "lucide-react";
import { cn } from "@/lib/utils";

// 统一的图标映射
const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
    "User": User,
    "Sparkles": Sparkles,
    "Zap": Zap,
    "TrendingUp": TrendingUp,
    "AlertTriangle": AlertTriangle,
    "Headphones": Headphones,
    "Mic2": Mic2,
    "MonitorPlay": MonitorPlay,
    "Users": Users,
    "Presentation": Presentation,
};

// 难度配置
const DIFFICULTY_CONFIG: Record<string, { label: string; className: string }> = {
    easy: { label: "简单", className: "text-emerald-600 border-emerald-200 bg-emerald-50" },
    medium: { label: "中等", className: "text-blue-600 border-blue-200 bg-blue-50" },
    hard: { label: "困难", className: "text-orange-600 border-orange-200 bg-orange-50" },
    expert: { label: "专家", className: "text-red-600 border-red-200 bg-red-50" },
};

// 主题色配置（用于hover效果）
const THEME_HOVER_MAP: Record<string, string> = {
    sales: "group-hover:border-blue-100 group-hover:text-blue-600",
    presentation: "group-hover:border-purple-100 group-hover:text-purple-600",
    interview: "group-hover:border-emerald-100 group-hover:text-emerald-600",
};

export interface AgentCardProps {
    id: string;
    name: string;
    description: string;
    role?: string;
    difficulty?: string;
    iconKey?: string;
    themeColor?: string;
    tags?: string[];
    category?: string;
    actionText?: string;
    onClick?: () => void;
    className?: string;
}

export function AgentCard({
    id,
    name,
    description,
    role,
    difficulty = "medium",
    iconKey = "User",
    themeColor = "bg-blue-50 text-blue-600",
    tags = [],
    category = "sales",
    actionText = "点击开始对练",
    onClick,
    className,
}: AgentCardProps) {
    const IconComponent = ICON_MAP[iconKey] || User;
    const difficultyConfig = DIFFICULTY_CONFIG[difficulty] || DIFFICULTY_CONFIG.medium;
    const hoverClass = THEME_HOVER_MAP[category] || THEME_HOVER_MAP.sales;

    return (
        <div 
            className={cn("block h-full group cursor-pointer", className)}
            onClick={onClick}
        >
            <GlassCard 
                hoverEffect 
                className={cn(
                    "h-full p-6 flex flex-col justify-between border-transparent transition-all",
                    hoverClass.split(" ")[0]
                )}
            >
                <div>
                    {/* 头部：图标 + 难度 */}
                    <div className="flex justify-between items-start mb-4">
                        <div className={cn(
                            "w-14 h-14 rounded-2xl flex items-center justify-center shadow-sm",
                            "group-hover:scale-110 transition-transform duration-300",
                            themeColor
                        )}>
                            <IconComponent className="w-7 h-7" />
                        </div>
                        {difficulty && (
                            <Badge 
                                variant="secondary" 
                                className={cn("border", difficultyConfig.className)}
                            >
                                {difficultyConfig.label}
                            </Badge>
                        )}
                    </div>
                    
                    {/* 标题和描述 */}
                    <div className="space-y-2">
                        <h3 className={cn(
                            "text-xl font-bold text-slate-900 transition-colors",
                            hoverClass.split(" ").slice(1).join(" ")
                        )}>
                            {name}
                        </h3>
                        {role && (
                            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                                {role}
                            </p>
                        )}
                        <p className="text-sm text-slate-600 font-medium leading-relaxed pt-2">
                            {description}
                        </p>
                    </div>
                </div>

                {/* 底部：标签 + 操作提示 */}
                <div className="mt-6 pt-4 border-t border-slate-100 space-y-4">
                    {tags.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                            {tags.map(tag => (
                                <span 
                                    key={tag} 
                                    className="text-[10px] font-bold text-slate-500 bg-slate-100 px-2 py-1 rounded-md"
                                >
                                    {tag}
                                </span>
                            ))}
                        </div>
                    )}
                    <div className={cn(
                        "flex items-center gap-2 text-xs font-bold text-slate-400 transition-colors",
                        hoverClass.split(" ").slice(1).join(" ")
                    )}>
                        <Sparkles className="w-3 h-3" />
                        <span>{actionText}</span>
                    </div>
                </div>
            </GlassCard>
        </div>
    );
}
