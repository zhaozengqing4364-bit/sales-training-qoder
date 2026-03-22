"use client";

import Image from "next/image";
import * as React from "react";
import { ChevronLeft, ChevronRight, Presentation } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import { api } from "@/lib/api/client";

export interface SlideViewerProps {
    presentationId?: string;
    currentPage: number;
    totalPages: number;
    slideContent?: string;
    slideImageUrl?: string;
    onPageChange: (page: number) => void;
}

export function SlideViewer({
    presentationId,
    currentPage,
    totalPages,
    slideContent,
    slideImageUrl,
    onPageChange,
}: SlideViewerProps) {
    const [thumbnailUrl, setThumbnailUrl] = React.useState<string | null>(null);
    const [isThumbnailLoading, setIsThumbnailLoading] = React.useState(false);

    React.useEffect(() => {
        let active = true;
        let localObjectUrl: string | null = null;

        setThumbnailUrl(null);

        if (!presentationId || currentPage < 1) {
            setIsThumbnailLoading(false);
            return () => {
                active = false;
            };
        }

        setIsThumbnailLoading(true);

        const loadThumbnail = async () => {
            try {
                const blob = await api.presentations.getThumbnailBlob(
                    presentationId,
                    currentPage,
                );
                if (!active) {
                    return;
                }
                localObjectUrl = URL.createObjectURL(blob);
                setThumbnailUrl(localObjectUrl);
            } catch {
                if (active) {
                    setThumbnailUrl(null);
                }
            } finally {
                if (active) {
                    setIsThumbnailLoading(false);
                }
            }
        };

        void loadThumbnail();

        return () => {
            active = false;
            if (localObjectUrl) {
                URL.revokeObjectURL(localObjectUrl);
            }
        };
    }, [presentationId, currentPage]);

    const resolvedSlideImage = thumbnailUrl || slideImageUrl || null;

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

    // 计算进度百分比
    const progress = totalPages > 0 ? (currentPage / totalPages) * 100 : 0;

    return (
        <div className="bg-white/50 backdrop-blur-sm rounded-2xl p-4 border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
            {/* 头部标题 */}
            <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-violet-500" />
                <Presentation className="w-4 h-4 text-violet-500" />
                幻灯片
            </h3>

            {/* 幻灯片内容区域 */}
            <div className="relative bg-white rounded-xl border border-slate-200 overflow-hidden min-h-[180px] md:min-h-[200px] flex items-center justify-center">
                {resolvedSlideImage ? (
                    <motion.div
                        key={`${currentPage}-image`}
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                        transition={{ duration: 0.3 }}
                        className="w-full h-full"
                    >
                        <div className="relative w-full h-full">
                            <Image
                                src={resolvedSlideImage}
                                alt={`第${currentPage}页幻灯片`}
                                fill
                                unoptimized
                                className="object-contain"
                            />
                        </div>
                    </motion.div>
                ) : slideContent ? (
                    <motion.div
                        key={`${currentPage}-text`}
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                        transition={{ duration: 0.3 }}
                        className="p-4 text-center"
                    >
                        <p className="text-sm text-slate-700 leading-relaxed">
                            {slideContent}
                        </p>
                    </motion.div>
                ) : (
                    <div className="text-center p-4">
                        <Presentation className="w-12 h-12 text-slate-300 mx-auto mb-2" />
                        <p className="text-xs text-slate-400">
                            {isThumbnailLoading ? "幻灯片加载中..." : "幻灯片内容加载中..."}
                        </p>
                    </div>
                )}

                {/* 页码指示器 */}
                <div className="absolute top-2 right-2 bg-slate-100/80 backdrop-blur-sm px-2 py-1 rounded-full">
                    <span className="text-xs font-medium text-slate-600">
                        {currentPage} / {totalPages}
                    </span>
                </div>
            </div>

            {/* 进度条 */}
            <div className="mt-3">
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <motion.div
                        className="h-full bg-violet-500 rounded-full"
                        initial={{ width: 0 }}
                        animate={{ width: `${progress}%` }}
                        transition={{ duration: 0.5, ease: "easeOut" }}
                    />
                </div>
            </div>

            {/* 导航按钮 */}
            <div className="flex items-center justify-between mt-3">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={handlePrev}
                    disabled={currentPage <= 1}
                    className={cn(
                        "text-slate-600 hover:text-violet-600 hover:bg-violet-50",
                        currentPage <= 1 && "opacity-50 cursor-not-allowed"
                    )}
                >
                    <ChevronLeft className="w-4 h-4 mr-1" />
                    上一页
                </Button>

                <span className="text-xs text-slate-500">
                    {Math.round(progress)}%
                </span>

                <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleNext}
                    disabled={currentPage >= totalPages}
                    className={cn(
                        "text-slate-600 hover:text-violet-600 hover:bg-violet-50",
                        currentPage >= totalPages && "opacity-50 cursor-not-allowed"
                    )}
                >
                    下一页
                    <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
            </div>
        </div>
    );
}
