"use client";

import * as React from "react";
import { ChevronLeft, ChevronRight, Layers } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export interface PageNavigatorProps {
    currentPage: number;
    totalPages: number;
    onPageChange: (page: number) => void;
}

export function PageNavigator({
    currentPage,
    totalPages,
    onPageChange,
}: PageNavigatorProps) {
    const handlePrev = () => {
        if (currentPage > 1) {
            onPageChange(currentPage - 1);
        }
    };

    const handleNext = () => {
        if (currentPage < totalPages) {
            onPageChange(currentPage + 1);
        }
    };

    const progress = totalPages > 0 ? (currentPage / totalPages) * 100 : 0;

    return (
        <div className="bg-white/50 backdrop-blur-sm rounded-2xl p-4 border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
            <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-cyan-500" />
                <Layers className="w-4 h-4 text-cyan-500" />
                页码导航
            </h3>

            <div className="flex items-center justify-between mb-3">
                <Button
                    variant="outline"
                    size="icon"
                    onClick={handlePrev}
                    disabled={currentPage <= 1}
                    className={cn(
                        "h-10 w-10 rounded-xl border-slate-200 hover:border-cyan-300 hover:bg-cyan-50",
                        currentPage <= 1 && "opacity-50 cursor-not-allowed"
                    )}
                >
                    <ChevronLeft className="w-5 h-5 text-slate-600" />
                </Button>

                <div className="text-center">
                    <span className="text-2xl font-bold text-slate-800">
                        {currentPage}
                    </span>
                    <span className="text-sm text-slate-400 mx-1">/</span>
                    <span className="text-sm text-slate-500">{totalPages}</span>
                </div>

                <Button
                    variant="outline"
                    size="icon"
                    onClick={handleNext}
                    disabled={currentPage >= totalPages}
                    className={cn(
                        "h-10 w-10 rounded-xl border-slate-200 hover:border-cyan-300 hover:bg-cyan-50",
                        currentPage >= totalPages && "opacity-50 cursor-not-allowed"
                    )}
                >
                    <ChevronRight className="w-5 h-5 text-slate-600" />
                </Button>
            </div>

            <div className="space-y-2">
                <div className="flex justify-between text-xs text-slate-500">
                    <span>演讲进度</span>
                    <span>{Math.round(progress)}%</span>
                </div>
                <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-gradient-to-r from-cyan-400 to-cyan-500 rounded-full transition-all duration-300"
                        style={{ width: `${progress}%` }}
                    />
                </div>
            </div>

            <div className="mt-3 flex gap-1 flex-wrap justify-center">
                {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => i + 1).map((page) => (
                    <button
                        key={page}
                        onClick={() => onPageChange(page)}
                        className={cn(
                            "w-8 h-8 rounded-lg text-xs font-medium transition-all duration-200",
                            page === currentPage
                                ? "bg-cyan-500 text-white shadow-md"
                                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                        )}
                    >
                        {page}
                    </button>
                ))}
                {totalPages > 10 && (
                    <span className="w-8 h-8 flex items-center justify-center text-xs text-slate-400">
                        ...
                    </span>
                )}
            </div>
        </div>
    );
}
