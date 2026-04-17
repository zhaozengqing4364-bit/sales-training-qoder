"use client";

import { useEffect, useMemo, useState } from "react";
import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api/client";
import { TrainingCategory } from "@/lib/api/types";
import {
    ArrowRight,
    Layers,
    Mic,
    Presentation,
    Sparkles,
} from "lucide-react";
import Link from "next/link";

type CategoryViewModel = {
    id: string;
    title: string;
    description: string;
    color: string;
    href: string;
    icon: typeof Mic;
    agentCount: number;
    tags: string[];
    status: "active" | "coming_soon" | "inactive";
};

const CATEGORY_UI_META: Record<
    string,
    {
        icon: typeof Mic;
        color: string;
        href: string;
        defaultTags: string[];
    }
> = {
    sales: {
        icon: Mic,
        color: "bg-blue-50 text-blue-600",
        href: "/training/sales",
        defaultTags: ["谈判技巧", "异议处理", "顾问式销售"],
    },
    presentation: {
        icon: Presentation,
        color: "bg-purple-50 text-purple-600",
        href: "/training/presentation",
        defaultTags: ["融资路演", "产品发布", "季度汇报"],
    },
};

const FALLBACK_CATEGORIES: TrainingCategory[] = [
    {
        id: "sales",
        title: "销售能力训练",
        description: "通过与不同性格的 AI 客户进行实战演练，提升 SPIN 提问技巧、异议处理能力和成交率。",
        icon_key: "Mic",
        color_theme: "bg-blue-50 text-blue-600",
        agent_count: 0,
        tags: ["谈判技巧", "异议处理", "顾问式销售"],
        status: "active",
    },
    {
        id: "presentation",
        title: "演讲与表达训练",
        description: "在模拟舞台中练习演讲，获得关于语速、肢体语言、声音自信度的实时 AI 反馈。",
        icon_key: "Presentation",
        color_theme: "bg-purple-50 text-purple-600",
        agent_count: 0,
        tags: ["融资路演", "产品发布", "季度汇报"],
        status: "active",
    },
];

function mapCategoryToViewModel(category: TrainingCategory): CategoryViewModel {
    const categoryId = category.id.replace(/-/g, "_");
    const meta = CATEGORY_UI_META[categoryId] || {
        icon: Mic,
        color: category.color_theme || "bg-slate-100 text-slate-600",
        href: `/training/${category.id.replace(/_/g, "-")}`,
        defaultTags: [] as string[],
    };

    return {
        id: category.id,
        title: category.title,
        description: category.description,
        color: category.color_theme || meta.color,
        href: meta.href,
        icon: meta.icon,
        agentCount: Number.isFinite(category.agent_count) ? category.agent_count : 0,
        tags: category.tags?.length ? category.tags : meta.defaultTags,
        status: category.status,
    };
}

export default function TrainingCategoriesPage() {
    const [categories, setCategories] = useState<TrainingCategory[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isDegraded, setIsDegraded] = useState(false);
    const [reloadVersion, setReloadVersion] = useState(0);

    useEffect(() => {
        let cancelled = false;

        const loadCategories = async () => {
            setIsLoading(true);
            try {
                const result = await api.training.getCategories();
                if (!cancelled) {
                    setCategories(result.length ? result : FALLBACK_CATEGORIES);
                    setIsDegraded(false);
                }
            } catch {
                if (!cancelled) {
                    setCategories(FALLBACK_CATEGORIES);
                    setIsDegraded(true);
                }
            } finally {
                if (!cancelled) {
                    setIsLoading(false);
                }
            }
        };

        loadCategories();

        return () => {
            cancelled = true;
        };
    }, [reloadVersion]);

    const viewModels = useMemo(() => categories.map(mapCategoryToViewModel), [categories]);

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 pb-20">
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

            {isDegraded && (
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    <span>训练分类暂不可用，当前展示的是本地兜底入口，不代表后端没有训练模式。</span>
                    <button
                        type="button"
                        onClick={() => setReloadVersion((version) => version + 1)}
                        className="rounded-full border border-amber-300 bg-white px-3 py-1 text-xs font-bold text-amber-800 shadow-sm hover:bg-amber-100"
                    >
                        重试训练分类
                    </button>
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {isLoading
                    ? Array.from({ length: 2 }).map((_, index) => (
                          <div key={index} className="h-[360px] rounded-3xl bg-white/50 animate-pulse border border-white/60" />
                      ))
                    : viewModels.map((category) => {
                          const CardContent = (
                              <GlassCard
                                  hoverEffect={category.status === "active"}
                                  className="h-full p-8 flex flex-col border-transparent relative overflow-hidden"
                              >
                                  <div className={`absolute -right-10 -top-10 w-40 h-40 rounded-full opacity-10 blur-3xl transition-transform duration-700 ${category.color.split(" ")[0].replace("50", "400")}`} />

                                  <div className="flex justify-between items-start mb-6 relative z-10">
                                      <div className={`w-16 h-16 rounded-[1.2rem] flex items-center justify-center ${category.color} shadow-sm transition-transform duration-300`}>
                                          <category.icon className="w-8 h-8" />
                                      </div>
                                      <div className="flex items-center gap-1 text-xs font-bold text-slate-400 bg-slate-50 px-2 py-1 rounded-full">
                                          <Layers className="w-3 h-3" />
                                          {category.agentCount} 个场景
                                      </div>
                                  </div>

                                  <div className="flex-1 relative z-10">
                                      <h3 className="text-2xl font-bold text-slate-900 mb-3">{category.title}</h3>
                                      <p className="text-slate-500 font-medium leading-relaxed mb-6">{category.description}</p>

                                      <div className="flex flex-wrap gap-2">
                                          {category.tags.map((tag) => (
                                              <Badge key={tag} variant="secondary" className="bg-white/60 text-slate-600 border border-slate-100/50">
                                                  {tag}
                                              </Badge>
                                          ))}
                                      </div>
                                  </div>

                                  <div className="mt-8 pt-6 border-t border-slate-100/60 flex items-center justify-between text-slate-400 transition-colors relative z-10">
                                      {category.status === "active" ? (
                                          <span className="text-sm font-bold flex items-center gap-2">
                                              <Sparkles className="w-4 h-4" /> 进入场景库
                                          </span>
                                      ) : (
                                          <span className="text-sm font-bold text-amber-600">即将上线</span>
                                      )}
                                      <ArrowRight className="w-5 h-5" />
                                  </div>
                              </GlassCard>
                          );

                          if (category.status !== "active") {
                              return (
                                  <div key={category.id} className="block h-full cursor-not-allowed opacity-80">
                                      {CardContent}
                                  </div>
                              );
                          }

                          return (
                              <Link key={category.id} href={category.href} className="block group h-full">
                                  {CardContent}
                              </Link>
                          );
                      })}
            </div>
        </div>
    );
}
