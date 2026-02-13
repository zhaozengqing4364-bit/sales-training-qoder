"use client";

import * as React from "react";
import { CheckCircle2, Circle, Target } from "lucide-react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";

export interface Point {
    id: string;
    content: string;
    isCovered: boolean;
}

export interface PointTrackerProps {
    points: Point[];
}

export function PointTracker({ points }: PointTrackerProps) {
    const coveredCount = points.filter((p) => p.isCovered).length;
    const totalCount = points.length;
    const progress = totalCount > 0 ? (coveredCount / totalCount) * 100 : 0;

    return (
        <div className="bg-white/50 backdrop-blur-sm rounded-2xl p-4 border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
            <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                <Target className="w-4 h-4 text-emerald-500" />
                要点跟踪
            </h3>

            <div className="mb-3">
                <div className="flex justify-between text-xs text-slate-500 mb-1">
                    <span>完成度</span>
                    <span>
                        {coveredCount}/{totalCount}
                    </span>
                </div>
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <motion.div
                        className="h-full bg-gradient-to-r from-emerald-400 to-emerald-500 rounded-full"
                        initial={{ width: 0 }}
                        animate={{ width: `${progress}%` }}
                        transition={{ duration: 0.5, ease: "easeOut" }}
                    />
                </div>
            </div>

            <div className="space-y-2 max-h-[200px] overflow-y-auto">
                <AnimatePresence>
                    {points.length === 0 ? (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="text-center py-4 text-slate-400 text-xs"
                        >
                            暂无要点数据
                        </motion.div>
                    ) : (
                        points.map((point, index) => (
                            <motion.div
                                key={point.id}
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: 10 }}
                                transition={{
                                    duration: 0.3,
                                    delay: index * 0.05,
                                }}
                                className={cn(
                                    "flex items-start gap-2 p-2 rounded-lg transition-all duration-300",
                                    point.isCovered
                                        ? "bg-emerald-50 border border-emerald-100"
                                        : "bg-slate-50 border border-slate-100"
                                )}
                            >
                                <div className="shrink-0 mt-0.5">
                                    {point.isCovered ? (
                                        <motion.div
                                            initial={{ scale: 0 }}
                                            animate={{ scale: 1 }}
                                            transition={{
                                                type: "spring",
                                                stiffness: 500,
                                                damping: 30,
                                            }}
                                        >
                                            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                        </motion.div>
                                    ) : (
                                        <Circle className="w-4 h-4 text-slate-300" />
                                    )}
                                </div>
                                <span
                                    className={cn(
                                        "text-xs leading-relaxed",
                                        point.isCovered
                                            ? "text-emerald-700 line-through"
                                            : "text-slate-600"
                                    )}
                                >
                                    {point.content}
                                </span>
                            </motion.div>
                        ))
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
}
