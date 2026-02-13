"use client";

import { AlertTriangle, X, Volume2, Ban } from "lucide-react";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";

export interface ForbiddenWordDetection {
    word: string;
    suggestion: string;
}

export interface ForbiddenWordsAlertProps {
    detections: ForbiddenWordDetection[];
    onDismiss?: (index: number) => void;
}

export function ForbiddenWordsAlert({
    detections,
    onDismiss,
}: ForbiddenWordsAlertProps) {
    if (detections.length === 0) {
        return null;
    }

    return (
        <div className="bg-white/50 backdrop-blur-sm rounded-2xl p-4 border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
            <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-rose-500" />
                <Ban className="w-4 h-4 text-rose-500" />
                禁止词检测
                {detections.length > 0 && (
                    <span className="ml-auto bg-rose-100 text-rose-600 text-xs font-medium px-2 py-0.5 rounded-full">
                        {detections.length}
                    </span>
                )}
            </h3>

            <div className="space-y-2 max-h-[200px] overflow-y-auto">
                <AnimatePresence mode="popLayout">
                    {detections.map((detection, index) => (
                        <motion.div
                            key={`${detection.word}-${index}`}
                            initial={{ opacity: 0, y: -10, scale: 0.95 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.9 }}
                            transition={{ duration: 0.2, delay: index * 0.05 }}
                            className="bg-rose-50 border border-rose-100 rounded-xl p-3 relative group"
                        >
                            {onDismiss && (
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="absolute top-1 right-1 h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                                    onClick={() => onDismiss(index)}
                                >
                                    <X className="w-3 h-3 text-rose-400" />
                                </Button>
                            )}

                            <div className="flex items-start gap-2">
                                <div className="shrink-0">
                                    <AlertTriangle className="w-4 h-4 text-rose-500 mt-0.5" />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-xs font-medium text-rose-700 mb-1">
                                        检测到禁止词
                                    </p>
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="inline-flex items-center gap-1 bg-rose-100 text-rose-600 text-xs font-medium px-2 py-0.5 rounded">
                                            <Volume2 className="w-3 h-3" />
                                            {detection.word}
                                        </span>
                                    </div>
                                    <p className="text-xs text-rose-600/80 leading-relaxed">
                                        建议：{detection.suggestion}
                                    </p>
                                </div>
                            </div>
                        </motion.div>
                    ))}
                </AnimatePresence>
            </div>

            {detections.length > 1 && onDismiss && (
                <Button
                    variant="ghost"
                    size="sm"
                    className="w-full mt-2 text-xs text-slate-500 hover:text-slate-700"
                    onClick={() => {
                        for (let i = detections.length - 1; i >= 0; i--) {
                            onDismiss(i);
                        }
                    }}
                >
                    清除所有提示
                </Button>
            )}
        </div>
    );
}
