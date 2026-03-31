import Image from "next/image";
import * as React from "react";
import { cn } from "@/lib/utils";
import { User, Sparkles, AlertCircle, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import type { KnowledgeAnswerDiagnostics } from "@/hooks/websocket/types";

export interface ChatBubbleProps {
    message: string;
    sender: "user" | "ai";
    timestamp?: string;
    status?: "sending" | "sent" | "error" | "typing";
    avatar?: string;
    className?: string;
    knowledgeAnswerDiagnostics?: KnowledgeAnswerDiagnostics | null;
}

export function ChatBubble({
    message,
    sender,
    timestamp,
    status = "sent",
    avatar,
    className,
    knowledgeAnswerDiagnostics,
}: ChatBubbleProps) {
    const isUser = sender === "user";
    const citations = !isUser && Array.isArray(knowledgeAnswerDiagnostics?.citations)
        ? knowledgeAnswerDiagnostics.citations.filter((item) => Boolean(item?.snippet))
        : [];

    return (
        <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            className={cn(
                "flex w-full mb-6",
                isUser ? "justify-end" : "justify-start",
                className
            )}
        >
            <div
                className={cn(
                    "flex max-w-[85%] md:max-w-[70%] gap-3",
                    isUser ? "flex-row-reverse" : "flex-row"
                )}
            >
                {/* Avatar */}
                <div className="shrink-0">
                    <div
                        className={cn(
                            "relative overflow-hidden w-8 h-8 md:w-10 md:h-10 rounded-full flex items-center justify-center shadow-sm",
                            isUser
                                ? "bg-gradient-to-br from-blue-500 to-indigo-600 text-white"
                                : "bg-white/80 backdrop-blur-md border border-white/40 text-indigo-600"
                        )}
                    >
                        {avatar ? (
                            <Image
                                src={avatar}
                                alt={sender}
                                fill
                                unoptimized
                                className="rounded-full object-cover"
                            />
                        ) : isUser ? (
                            <User size={16} className="md:w-5 md:h-5" />
                        ) : (
                            <Sparkles size={16} className="md:w-5 md:h-5" />
                        )}
                    </div>
                </div>

                {/* Message Content */}
                <div className={cn("flex flex-col", isUser ? "items-end" : "items-start")}>
                    <span className="text-xs text-slate-400 mb-1 px-1">
                        {isUser ? "You" : "AI"}
                    </span>

                    <div
                        className={cn(
                            "relative px-4 py-3 md:px-5 md:py-4 rounded-2xl shadow-sm text-sm md:text-base leading-relaxed break-words",
                            isUser
                                ? "bg-blue-600 text-white rounded-tr-sm"
                                : "bg-white/70 backdrop-blur-md border border-white/50 text-slate-800 rounded-tl-sm"
                        )}
                    >
                        {status === "typing" ? (
                            <div className="flex items-center gap-1 h-6">
                                <span className="w-1.5 h-1.5 bg-current rounded-full animate-bounce [animation-delay:-0.3s]" />
                                <span className="w-1.5 h-1.5 bg-current rounded-full animate-bounce [animation-delay:-0.15s]" />
                                <span className="w-1.5 h-1.5 bg-current rounded-full animate-bounce" />
                            </div>
                        ) : (
                            <div className="space-y-3">
                                <p>{message}</p>
                                {citations.length > 0 && (
                                    <div className="rounded-xl border border-slate-200 bg-slate-50/90 p-3 text-slate-700">
                                        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-2">知识库依据</p>
                                        <div className="space-y-2">
                                            {citations.map((citation, index) => (
                                                <div key={`${citation.document_title || citation.knowledge_base_id || index}-${index}`} className="rounded-lg bg-white/90 px-3 py-2 border border-slate-200">
                                                    <p className="text-[11px] font-medium text-slate-500 mb-1">
                                                        {[citation.knowledge_base_name, citation.document_title].filter(Boolean).join(" · ") || citation.knowledge_base_id || "内部知识片段"}
                                                    </p>
                                                    <p className="text-sm text-slate-800">{citation.snippet}</p>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {status === "error" && (
                            <div className="absolute -right-6 top-1/2 -translate-y-1/2 text-red-500">
                                <AlertCircle size={16} />
                            </div>
                        )}

                        {status === "sending" && (
                            <div className="absolute -right-6 top-1/2 -translate-y-1/2 text-slate-400">
                                <Loader2 size={16} className="animate-spin" />
                            </div>
                        )}
                    </div>

                    {timestamp && (
                        <span className="text-[10px] md:text-xs text-slate-400 mt-1 px-1">
                            {timestamp}
                        </span>
                    )}
                </div>
            </div>
        </motion.div>
    );
}
