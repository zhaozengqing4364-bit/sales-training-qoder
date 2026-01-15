"use client";

import { ReactNode } from "react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/glass-modal";
import { Button } from "@/components/ui/button";
import { AlertTriangle } from "lucide-react";

interface ConfirmDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    title: string;
    description: string;
    confirmText?: string;
    cancelText?: string;
    variant?: "danger" | "warning" | "default";
    onConfirm: () => void;
    isLoading?: boolean;
    icon?: ReactNode;
}

export function ConfirmDialog({
    open,
    onOpenChange,
    title,
    description,
    confirmText = "确认",
    cancelText = "取消",
    variant = "default",
    onConfirm,
    isLoading = false,
    icon,
}: ConfirmDialogProps) {
    const variantStyles = {
        danger: "bg-red-600 hover:bg-red-700 text-white",
        warning: "bg-amber-500 hover:bg-amber-600 text-white",
        default: "bg-slate-900 hover:bg-slate-800 text-white",
    };

    const iconColors = {
        danger: "text-red-500 bg-red-50",
        warning: "text-amber-500 bg-amber-50",
        default: "text-slate-500 bg-slate-50",
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-sm">
                <DialogHeader>
                    <div className="flex items-start gap-4">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${iconColors[variant]}`}>
                            {icon || <AlertTriangle className="w-5 h-5" />}
                        </div>
                        <div>
                            <DialogTitle>{title}</DialogTitle>
                            <DialogDescription className="mt-1">{description}</DialogDescription>
                        </div>
                    </div>
                </DialogHeader>
                <DialogFooter className="mt-4">
                    <Button
                        variant="ghost"
                        className="rounded-full"
                        onClick={() => onOpenChange(false)}
                        disabled={isLoading}
                    >
                        {cancelText}
                    </Button>
                    <Button
                        className={`rounded-full ${variantStyles[variant]}`}
                        onClick={() => {
                            onConfirm();
                        }}
                        disabled={isLoading}
                    >
                        {isLoading ? "处理中..." : confirmText}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
