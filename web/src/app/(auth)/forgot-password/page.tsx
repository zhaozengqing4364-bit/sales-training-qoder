"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ArrowLeft, Loader2, AlertCircle, CheckCircle2, Mail } from "lucide-react";
import { api, getApiErrorMessage } from "@/lib/api/client";
import Link from "next/link";

export default function ForgotPasswordPage() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const handoffEmail = searchParams.get("email")?.trim() || "";
    const [email, setEmail] = useState(handoffEmail);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState("");
    const [isSuccess, setIsSuccess] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        const normalizedEmail = email.trim();

        if (!normalizedEmail) {
            setError("请输入邮箱地址");
            return;
        }

        setIsLoading(true);
        setError("");

        try {
            await api.auth.forgotPassword(normalizedEmail);
            setEmail(normalizedEmail);
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
                            <h1 className="text-2xl font-bold text-slate-900">邮件已发送</h1>
                            <p className="text-slate-500 mt-2">
                                如果 <span className="font-medium text-slate-700">{email}</span> 是已注册的邮箱，您将收到一封包含密码重置链接的邮件。
                            </p>
                        </div>
                        <p className="text-xs text-slate-400">邮件可能需要几分钟才能到达，请检查垃圾邮件文件夹。</p>
                        <Button
                            className="w-full h-12 rounded-full bg-slate-900 hover:bg-slate-800 text-white"
                            onClick={() => router.push("/login")}
                        >
                            返回登录
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
                        <Mail className="w-6 h-6" />
                    </div>
                    <h1 className="text-2xl font-bold text-slate-900 tracking-tight">忘记密码</h1>
                    <p className="text-slate-500 mt-2">输入您的邮箱地址，我们将发送重置链接</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    {error && (
                        <div className="p-3 rounded-lg bg-red-50 border border-red-100 text-red-600 text-sm flex items-center">
                            <AlertCircle className="w-4 h-4 mr-2 shrink-0" />
                            {error}
                        </div>
                    )}

                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="email">邮箱地址</label>
                        <Input
                            id="email"
                            type="email"
                            name="email"
                            autoComplete="email"
                            placeholder="name@company.com"
                            className="bg-white/50 focus:bg-white transition-colors h-12 rounded-full px-6"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                        />
                        {handoffEmail ? (
                            <p className="text-xs text-slate-400">已从登录或个人中心带入邮箱，可直接发送重置邮件。</p>
                        ) : null}
                    </div>

                    <Button
                        type="submit"
                        disabled={isLoading || !email.trim()}
                        className="w-full h-12 rounded-full mt-4 text-base shadow-lg shadow-slate-900/20 bg-slate-900 hover:bg-slate-800 text-white"
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 发送中...
                            </>
                        ) : (
                            "发送重置链接"
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
