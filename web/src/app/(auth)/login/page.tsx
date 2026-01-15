"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ArrowRight, Loader2, AlertCircle } from "lucide-react";
import { api } from "@/lib/api/client";

export default function LoginPage() {
    const router = useRouter();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState("");

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError("");

        try {
            const res = await api.auth.login({ email, password });
            if (res.token) {
                localStorage.setItem("token", res.token);
                // Store user info for sidebar display
                if (res.user) {
                    localStorage.setItem("user", JSON.stringify({
                        id: res.user.id,
                        name: res.user.name,
                        display_name: res.user.name,
                        email: res.user.email,
                        role: res.user.role,
                    }));
                }
                
                // Redirect based on role or default to dashboard
                router.push("/");
            } else {
                setError("登录失败，未获取到令牌");
            }
        } catch (err: any) {
            console.error("Login failed", err);
            setError(err.message || "登录失败，请检查账号密码");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
            {/* Background Decor */}
            <div className="absolute top-[-20%] left-[-20%] w-[800px] h-[800px] bg-blue-100/30 rounded-full blur-[140px] pointer-events-none" />
            <div className="absolute bottom-[-20%] right-[-20%] w-[800px] h-[800px] bg-indigo-100/30 rounded-full blur-[140px] pointer-events-none" />

            <GlassCard className="w-full max-w-md p-8 md:p-12 animate-in fade-in zoom-in-95 duration-500 border-white/40 shadow-card">
                <div className="mb-10 text-center">
                    <div className="w-14 h-14 rounded-2xl bg-slate-900 mx-auto flex items-center justify-center text-white text-xl font-bold shadow-xl shadow-slate-900/20 mb-6">
                        AI
                    </div>
                    <h1 className="text-2xl font-bold text-slate-900 tracking-tight">欢迎回来</h1>
                    <p className="text-slate-500 mt-2">登录 AI 智能练习平台 开始训练</p>
                </div>

                <div className="space-y-4">
                    <Button className="w-full h-12 bg-[#3370ff] hover:bg-[#2060f0] text-white shadow-md rounded-full border-none font-medium">
                        企业微信登录 (WeCom)
                    </Button>

                    <div className="relative flex justify-center text-xs uppercase my-6">
                        <span className="bg-white/50 px-3 text-slate-400 z-10 font-medium">或者使用账号登录</span>
                        <div className="absolute top-1/2 left-0 w-full border-t border-slate-200 -z-0"></div>
                    </div>

                    <form onSubmit={handleLogin} className="space-y-4">
                        {error && (
                            <div className="p-3 rounded-lg bg-red-50 border border-red-100 text-red-600 text-sm flex items-center">
                                <AlertCircle className="w-4 h-4 mr-2" />
                                {error}
                            </div>
                        )}
                        <div className="space-y-2">
                            <Input 
                                type="email"
                                placeholder="name@company.com" 
                                className="bg-white/50 focus:bg-white transition-colors h-12 rounded-full px-6"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                            />
                        </div>
                        <div className="space-y-2">
                            <Input 
                                type="password" 
                                placeholder="••••••••" 
                                className="bg-white/50 focus:bg-white transition-colors h-12 rounded-full px-6"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                            />
                        </div>
                        <Button 
                            type="submit" 
                            disabled={isLoading}
                            className="w-full h-12 rounded-full mt-4 text-base shadow-lg shadow-slate-900/20 bg-slate-900 hover:bg-slate-800 text-white"
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 登录中...
                                </>
                            ) : (
                                <>
                                    登录 <ArrowRight className="ml-2 w-4 h-4" />
                                </>
                            )}
                        </Button>
                    </form>

                    <p className="text-center text-xs text-slate-400 mt-6">
                        仅供内部人员使用，如需帮助请联系管理员
                    </p>
                </div>
            </GlassCard>
        </div>
    )
}