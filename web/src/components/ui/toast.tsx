"use client";

import { createContext, useContext, useState, useCallback, useEffect, useRef, ReactNode } from "react";
import { CheckCircle2, AlertCircle, X, LogOut } from "lucide-react";
import { authHandler } from "@/lib/auth-handler";

type ToastType = "success" | "error" | "info" | "auth";

interface Toast {
    id: string;
    message: string;
    type: ToastType;
    exiting: boolean;
}

interface ToastContextType {
    showToast: (message: string, type?: ToastType) => void;
    success: (message: string) => void;
    error: (message: string) => void;
}

const ToastContext = createContext<ToastContextType | null>(null);

export function useToast() {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error("useToast must be used within a ToastProvider");
    }
    return context;
}

function ToastItem({ toast, onClose }: { toast: Toast; onClose: () => void }) {
    const icons = {
        success: <CheckCircle2 className="w-4 h-4" />,
        error: <AlertCircle className="w-4 h-4" />,
        info: <AlertCircle className="w-4 h-4" />,
        auth: <LogOut className="w-4 h-4" />,
    };

    const styles = {
        success: "bg-emerald-50 text-emerald-700 border-emerald-200",
        error: "bg-red-50 text-red-700 border-red-200",
        info: "bg-blue-50 text-blue-700 border-blue-200",
        auth: "bg-amber-50 text-amber-700 border-amber-200",
    };

    return (
        <div
            role="status"
            aria-atomic="true"
            data-motion-kind="spatial"
            data-state={toast.exiting ? "closed" : "open"}
            className={`motion-toast flex items-center gap-2 rounded-2xl border px-4 py-3 shadow-lg ${styles[toast.type]}`}
        >
            {icons[toast.type]}
            <span className="text-sm font-medium flex-1">{toast.message}</span>
            <button type="button" aria-label="关闭通知" onClick={onClose} className="rounded-full p-1 transition-colors hover:bg-black/5">
                <X className="w-3 h-3" />
            </button>
        </div>
    );
}

export function ToastProvider({ children }: { children: ReactNode }) {
    const [toasts, setToasts] = useState<Toast[]>([]);
    const autoDismissTimers = useRef(new Map<string, number>());
    const removalTimers = useRef(new Map<string, number>());

    const removeToast = useCallback((id: string) => {
        if (removalTimers.current.has(id)) return;
        const autoDismissTimer = autoDismissTimers.current.get(id);
        if (autoDismissTimer !== undefined) {
            window.clearTimeout(autoDismissTimer);
            autoDismissTimers.current.delete(id);
        }
        setToasts(prev => prev.map(toast => toast.id === id ? { ...toast, exiting: true } : toast));
        const removalTimer = window.setTimeout(() => {
            setToasts(prev => prev.filter(toast => toast.id !== id));
            removalTimers.current.delete(id);
        }, 200);
        removalTimers.current.set(id, removalTimer);
    }, []);

    const showToast = useCallback((message: string, type: ToastType = "info") => {
        const id = Math.random().toString(36).slice(2);
        setToasts(prev => [...prev, { id, message, type, exiting: false }]);

        // Auto remove after 4 seconds (auth toast stays longer)
        const duration = type === "auth" ? 2000 : 4000;
        const timer = window.setTimeout(() => removeToast(id), duration);
        autoDismissTimers.current.set(id, timer);
    }, [removeToast]);

    const success = useCallback((message: string) => showToast(message, "success"), [showToast]);
    const error = useCallback((message: string) => showToast(message, "error"), [showToast]);

    // Subscribe to auth handler events
    useEffect(() => {
        const unsubscribe = authHandler.subscribe((message) => {
            showToast(message, "auth");
        });
        return unsubscribe;
    }, [showToast]);

    useEffect(() => () => {
        autoDismissTimers.current.forEach((timer) => window.clearTimeout(timer));
        removalTimers.current.forEach((timer) => window.clearTimeout(timer));
    }, []);

    return (
        <ToastContext.Provider value={{ showToast, success, error }}>
            {children}
            {/* Toast Container */}
            <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
                {toasts.map(toast => (
                    <ToastItem key={toast.id} toast={toast} onClose={() => removeToast(toast.id)} />
                ))}
            </div>
        </ToastContext.Provider>
    );
}
