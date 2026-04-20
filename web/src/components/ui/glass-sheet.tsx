"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, Variants } from "framer-motion";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface GlassSheetProps {
    isOpen: boolean;
    onClose: () => void;
    children: React.ReactNode;
    side?: "left" | "right" | "bottom";
    className?: string;
}

export function GlassSheet({
    isOpen,
    onClose,
    children,
    side = "left",
    className,
}: GlassSheetProps) {
    const [mounted, setMounted] = React.useState(false);
    const panelRef = React.useRef<HTMLDivElement>(null);
    const previousFocusRef = React.useRef<HTMLElement | null>(null);

    React.useEffect(() => {
        setMounted(true);
        if (isOpen) {
            previousFocusRef.current = document.activeElement instanceof HTMLElement
                ? document.activeElement
                : null;
            document.body.style.overflow = "hidden";
            window.setTimeout(() => {
                panelRef.current?.focus();
            }, 0);
        } else {
            document.body.style.overflow = "unset";
            previousFocusRef.current?.focus();
        }
        return () => {
            document.body.style.overflow = "unset";
        };
    }, [isOpen]);

    React.useEffect(() => {
        if (!isOpen) return;

        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                event.preventDefault();
                onClose();
            }
        };

        document.addEventListener("keydown", handleKeyDown);
        return () => {
            document.removeEventListener("keydown", handleKeyDown);
        };
    }, [isOpen, onClose]);

    if (!mounted) return null;

    const variants: Variants = {
        closed: {
            x: side === "left" ? "-100%" : side === "right" ? "100%" : 0,
            y: side === "bottom" ? "100%" : 0,
            opacity: 0,
        },
        open: {
            x: 0,
            y: 0,
            opacity: 1,
            transition: { type: "spring", damping: 30, stiffness: 300 },
        },
    };

    return createPortal(
        <AnimatePresence>
            {isOpen && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onClose}
                        className="fixed inset-0 z-50 bg-slate-900/20 backdrop-blur-sm"
                    />

                    {/* Sheet Content */}
                    <motion.div
                        ref={panelRef}
                        role="dialog"
                        aria-modal="true"
                        tabIndex={-1}
                        variants={variants}
                        initial="closed"
                        animate="open"
                        exit="closed"
                        className={cn(
                            "fixed z-50 p-6 bg-white/70 backdrop-blur-3xl border-r border-white/50 shadow-[0_8px_32px_rgba(0,0,0,0.08)]",
                            side === "left" && "top-0 left-0 bottom-0 w-[85vw] max-w-xs rounded-r-[2.5rem]",
                            side === "right" && "top-0 right-0 bottom-0 w-[85vw] max-w-xs rounded-l-[2.5rem]",
                            side === "bottom" && "bottom-0 left-0 right-0 h-auto max-h-[90vh] rounded-t-[2.5rem]",
                            className
                        )}
                    >
                        {/* Close Button */}
                        <Button
                            variant="ghost"
                            size="icon"
                            aria-label="关闭面板"
                            onClick={onClose}
                            className="absolute right-4 top-4 rounded-full hover:bg-white/50 text-slate-500"
                        >
                            <X className="w-5 h-5" />
                        </Button>

                        {children}
                    </motion.div>
                </>
            )}
        </AnimatePresence>,
        document.body
    );
}
