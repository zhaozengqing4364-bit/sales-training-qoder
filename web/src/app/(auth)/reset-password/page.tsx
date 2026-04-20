"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2, AlertCircle, CheckCircle2, KeyRound } from "lucide-react";

import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, getApiErrorMessage } from "@/lib/api/client";

export default function ResetPasswordPage() {
    return (
        <Suspense
            fallback={
                <div className="min-h-screen flex items-center justify-center" role="status" aria-live="polite" aria-busy="true">
                    <span className="sr-only">正在加载重置密码页面</span>
                    <p className="text-slate-500">加载中...</p>
                </div>
            }
        >
            <ResetPasswordContent />
        </Suspense>
    );
}

function ResetPasswordContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const queryToken = searchParams.get("token")?.trim() || "";

    const [token, setToken] = useState(queryToken);
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState("");
    const [isSuccess, setIsSuccess] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");

        const normalizedToken = token.trim();

        if (!normalizedToken) {
            setError("请输入邮件中的重置令牌");
            return;
        }

        if (newPassword.length < 8) {
            setError("密码至少需要 8 个字符");
            return;
        }

        if (newPassword !== confirmPassword) {
            setError("两次输入的密码不一致");
            return;
        }

        setIsLoading(true);

        try {
            await api.auth.resetPassword(normalizedToken, newPassword);
            setToken(normalizedToken);
            setIsSuccess(true);
        } catch (err: unknown) {
            setError(getApiErrorMessage(err));
        } finally {
            setIsLoading(false);
        }
    };

    if (isSuccess) {
        return (
            <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
                <div className="absolute top-[-20%] left-[-20%] w-[800px] h-[800px] bg-blue-100/30 rounded-full blur-[140px] pointer-events-none" />
                <div className="absolute bottom-[-20%] right-[-20%] w-[800px] h-[800px] bg-indigo-100/30 rounded-full blur-[140px] pointer-events-none" />

                <GlassCard className="w-full max-w-md p-8 md:p-12 animate-in fade-in zoom-in-95 duration-500 border-white/40 shadow-card">
                    <div className="text-center space-y-6">
                        <div className="w-16 h-16 rounded-full bg-emerald-50 flex items-center justify-center mx-auto">
                            <CheckCircle2 className="w-8 h-8 text-emerald-600" />
                        </div>
                        <div>
                            <h1 className="text-2xl font-bold text-slate-900">密码已重置</h1>
                            <p className="text-slate-500 mt-2">您的新密码已生效，请使用新密码登录。</p>
                        </div>
                        <Button
                            className="w-full h-12 rounded-full bg-slate-900 hover:bg-slate-800 text-white"
                            onClick={() => router.push("/login")}
                        >
                            去登录
                        </Button>
                    </div>
                </GlassCard>
            </div>
        );
    }

    return (
        <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
            <div className="absolute top-[-20%] left-[-20%] w-[800px] h-[800px] bg-blue-100/30 rounded-full blur-[140px] pointer-events-none" />
            <div className="absolute bottom-[-20%] right-[-20%] w-[800px] h-[800px] bg-indigo-100/30 rounded-full blur-[140px] pointer-events-none" />

            <GlassCard className="w-full max-w-md p-8 md:p-12 animate-in fade-in zoom-in-95 duration-500 border-white/40 shadow-card">
                <div className="mb-10 text-center">
                    <div className="w-14 h-14 rounded-2xl bg-slate-900 mx-auto flex items-center justify-center text-white mb-6 shadow-xl shadow-slate-900/20">
                        <KeyRound className="w-6 h-6" />
                    </div>
                    <h1 className="text-2xl font-bold text-slate-900 tracking-tight">设置新密码</h1>
                    <p className="text-slate-500 mt-2">请输入邮件中的重置令牌和您的新密码</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    {error && (
                        <div role="alert" className="p-3 rounded-lg bg-red-50 border border-red-100 text-red-600 text-sm flex items-center">
                            <AlertCircle className="w-4 h-4 mr-2 shrink-0" />
                            {error}
                        </div>
                    )}

                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="token">重置令牌</label>
                        <Input
                            id="token"
                            type="text"
                            name="token"
                            autoComplete="off"
                            placeholder="粘贴邮件中的重置令牌"
                            className="bg-white/50 focus:bg-white transition-colors h-12 rounded-full px-6"
                            value={token}
                            onChange={(e) => setToken(e.target.value)}
                            required
                        />
                        <p className="text-xs text-slate-400">
                            {queryToken
                                ? "已从重置链接自动填入，如有需要可手动修改。"
                                : "若您在本地开发环境，请粘贴邮件或控制台中的重置令牌。"}
                        </p>
                    </div>

                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="new-password">新密码</label>
                        <Input
                            id="new-password"
                            type="password"
                            name="new-password"
                            autoComplete="new-password"
                            placeholder="至少 8 个字符"
                            className="bg-white/50 focus:bg-white transition-colors h-12 rounded-full px-6"
                            value={newPassword}
                            onChange={(e) => setNewPassword(e.target.value)}
                            required
                            minLength={8}
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="confirm-password">确认新密码</label>
                        <Input
                            id="confirm-password"
                            type="password"
                            name="confirm-password"
                            autoComplete="new-password"
                            placeholder="再次输入新密码"
                            className="bg-white/50 focus:bg-white transition-colors h-12 rounded-full px-6"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            required
                            minLength={8}
                        />
                    </div>

                    <Button
                        type="submit"
                        disabled={isLoading || !token.trim() || !newPassword || !confirmPassword}
                        className="w-full h-12 rounded-full mt-4 text-base shadow-lg shadow-slate-900/20 bg-slate-900 hover:bg-slate-800 text-white"
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 重置中...
                            </>
                        ) : (
                            "重置密码"
                        )}
                    </Button>
                </form>

                <div className="mt-6 text-center">
                    <Link
                        href="/login"
                        className="text-sm text-slate-500 hover:text-slate-900 transition-colors inline-flex items-center gap-1"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        返回登录
                    </Link>
                </div>
            </GlassCard>
        </div>
    );
}
