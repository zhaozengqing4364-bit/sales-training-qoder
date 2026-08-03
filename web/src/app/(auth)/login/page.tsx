"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, ArrowRight, BookOpenCheck, Eye, EyeOff, Loader2 } from "lucide-react";

import { ApiRequestError, api, getApiErrorMessage } from "@/lib/api/client";
import { REMEMBER_EMAIL_STORAGE_KEY } from "@/lib/auth/clear-client-auth-state";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";

type ProviderStatus = {
    enabled: boolean;
    loginUrl: string;
    message: string;
};

type AuthProviderState = {
    environment: string;
    wecom: ProviderStatus;
    devFallback: ProviderStatus;
};

const DEFAULT_PROVIDER_STATE: AuthProviderState = {
    environment: "development",
    wecom: {
        enabled: false,
        loginUrl: "",
        message: "正在检查企业微信登录配置…",
    },
    devFallback: {
        enabled: false,
        loginUrl: "",
        message: "",
    },
};

const AUTH_ERROR_MESSAGE_MAP: Record<string, string> = {
    "wecom-unavailable": "当前环境未配置企业微信 SSO，请联系管理员或使用明确标注的开发者登录。",
    "wecom-state-invalid": "企业微信登录状态已失效，请重新发起登录。",
    "wecom-user-disabled": "当前企业微信账号已被停用，请联系管理员。",
    "wecom-callback-failed": "企业微信登录失败，请稍后重试。",
};
function toProviderStatus(input: unknown, fallbackMessage: string): ProviderStatus {
    const record = input && typeof input === "object" ? input as Record<string, unknown> : {};
    return {
        enabled: record.enabled === true,
        loginUrl: typeof record.login_url === "string" ? record.login_url : "",
        message: typeof record.message === "string" && record.message.trim()
            ? record.message.trim()
            : fallbackMessage,
    };
}

function toAuthProviderState(payload: unknown): AuthProviderState {
    const root = payload && typeof payload === "object" ? payload as Record<string, unknown> : {};
    const data = root.data && typeof root.data === "object" ? root.data as Record<string, unknown> : root;

    return {
        environment: typeof data.environment === "string" && data.environment.trim()
            ? data.environment.trim()
            : "development",
        wecom: toProviderStatus(data.wecom, "当前环境未配置企业微信 SSO。"),
        devFallback: toProviderStatus(data.dev_fallback, "开发者登录当前不可用。"),
    };
}

function getAuthErrorMessageFromLocation(): string {
    if (typeof window === "undefined") {
        return "";
    }

    const authError = new URLSearchParams(window.location.search).get("authError");
    if (!authError) {
        return "";
    }

    return AUTH_ERROR_MESSAGE_MAP[authError] || "登录失败，请稍后重试。";
}

function isUnconfirmedPasswordChange(error: unknown): boolean {
    if (error instanceof ApiRequestError) {
        return error.errorCode === "[REQUEST_TIMEOUT]" || error.errorCode === "[NETWORK_ERROR]";
    }
    const message = error instanceof Error ? error.message : "";
    return /超时|network|failed to fetch/i.test(message);
}

function routeAfterLogin(role: string | undefined): string {
    return role?.trim().toLowerCase() === "training_manager" ? "/team" : "/";
}

export default function LoginPage() {
    const router = useRouter();
    const toast = useToast();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [requiresPasswordChange, setRequiresPasswordChange] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const [rememberEmail, setRememberEmail] = useState(false);
    const [isPasswordLoginLoading, setIsPasswordLoginLoading] = useState(false);
    const [isDevLoginLoading, setIsDevLoginLoading] = useState(false);
    const [error, setError] = useState("");
    const [providerState, setProviderState] = useState<AuthProviderState>(DEFAULT_PROVIDER_STATE);
    const devLoginInFlight = useRef(false);
    const normalizedEmail = email.trim();
    const forgotPasswordHref = normalizedEmail
        ? `/forgot-password?email=${encodeURIComponent(normalizedEmail)}`
        : "/forgot-password";

    useEffect(() => {
        let active = true;
        const rememberedEmail = window.localStorage.getItem(REMEMBER_EMAIL_STORAGE_KEY);
        if (rememberedEmail) {
            setEmail(rememberedEmail);
            setRememberEmail(true);
        }

        const authErrorMessage = getAuthErrorMessageFromLocation();
        if (authErrorMessage) {
            setError(authErrorMessage);
        }

        const loadProviders = async () => {
            try {
                const payload = await api.auth.getProviders();
                if (active) {
                    setProviderState(toAuthProviderState(payload));
                }
            } catch (loadError) {
                if (!active) {
                    return;
                }
                setProviderState({
                    environment: "development",
                    wecom: {
                        enabled: false,
                        loginUrl: "",
                        message: "登录配置加载失败，请刷新页面后重试。",
                    },
                    devFallback: {
                        enabled: false,
                        loginUrl: "",
                        message: "开发者登录当前不可用。",
                    },
                });
                if (!authErrorMessage) {
                    setError(getApiErrorMessage(loadError));
                }
            }
        };

        void loadProviders();
        return () => {
            active = false;
        };
    }, []);

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsPasswordLoginLoading(true);
        setError("");

        try {
            const response = await api.auth.login({ email, password });
            if (rememberEmail && normalizedEmail) {
                window.localStorage.setItem(REMEMBER_EMAIL_STORAGE_KEY, normalizedEmail);
            } else {
                window.localStorage.removeItem(REMEMBER_EMAIL_STORAGE_KEY);
            }
            if (response.requires_password_change) {
                setRequiresPasswordChange(true);
                setPassword("");
                return;
            }
            router.push(routeAfterLogin(response?.user?.role));
        } catch (err: unknown) {
            const message = getApiErrorMessage(err);
            setError(message);
            if (message.includes("超时")) {
                toast.error("登录超时，请重试");
            }
        } finally {
            setIsPasswordLoginLoading(false);
        }
    };

    const handleTemporaryPasswordChange = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        if (password !== confirmPassword) {
            setError("两次输入的新密码不一致。");
            return;
        }
        setIsPasswordLoginLoading(true);
        try {
            const response = await api.auth.changeTemporaryPassword(password);
            router.push(routeAfterLogin(response?.user?.role));
        } catch (err: unknown) {
            if (isUnconfirmedPasswordChange(err)) {
                try {
                    const reconciled = await api.auth.login({
                        email: normalizedEmail,
                        password,
                    });
                    if (!reconciled.requires_password_change) {
                        router.push(routeAfterLogin(reconciled?.user?.role));
                        return;
                    }
                } catch {
                    // The original write may still be pending or may not have reached the server.
                    // Keep both password fields intact so the user can recover in place.
                }
                setError("密码修改结果暂未确认。新密码输入已保留，请再次提交；若仍失败，请刷新后使用刚设置的新密码登录。");
                return;
            }
            setError(getApiErrorMessage(err));
        } finally {
            setIsPasswordLoginLoading(false);
        }
    };

    const handleWecomLogin = () => {
        if (!providerState.wecom.enabled || !providerState.wecom.loginUrl) {
            return;
        }
        window.location.assign(providerState.wecom.loginUrl);
    };

    const handleDevLogin = async () => {
        if (
            devLoginInFlight.current ||
            !providerState.devFallback.enabled ||
            !providerState.devFallback.loginUrl
        ) {
            return;
        }

        devLoginInFlight.current = true;
        setIsDevLoginLoading(true);
        setError("");
        try {
            const response = await api.auth.devLogin();
            router.push(routeAfterLogin(response?.user?.role));
        } catch (err) {
            const message = getApiErrorMessage(err);
            setError(message);
            if (message.includes("超时")) {
                toast.error("登录超时，请重试");
            }
        } finally {
            devLoginInFlight.current = false;
            setIsDevLoginLoading(false);
        }
    };

    const isWecomDisabled = !providerState.wecom.enabled;

    return (
        <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
            <div className="absolute top-[-20%] left-[-20%] w-[800px] h-[800px] bg-blue-100/30 rounded-full blur-[140px] pointer-events-none" />
            <div className="absolute bottom-[-20%] right-[-20%] w-[800px] h-[800px] bg-indigo-100/30 rounded-full blur-[140px] pointer-events-none" />

            <GlassCard className="w-full max-w-md p-8 md:p-12 animate-in fade-in zoom-in-95 duration-500 border-white/40 shadow-card">
                <div className="mb-10 text-center">
                    <div className="w-14 h-14 rounded-2xl bg-slate-900 mx-auto flex items-center justify-center text-white text-xl font-bold shadow-xl shadow-slate-900/20 mb-6">
                        <BookOpenCheck className="h-6 w-6" aria-hidden="true" />
                    </div>
                    <h1 className="text-2xl font-bold text-slate-900 tracking-tight">欢迎回来</h1>
                    <p className="text-slate-500 mt-2">登录新人销售训练平台，继续当前训练任务</p>
                </div>

                <div className="space-y-4">
                    <div className="space-y-2">
                        <Button
                            type="button"
                            disabled={isWecomDisabled}
                            aria-describedby="wecom-login-status"
                            className={`w-full h-12 rounded-full font-medium ${
                                isWecomDisabled
                                    ? "bg-slate-100 text-slate-400 border border-slate-200 shadow-none cursor-not-allowed opacity-70"
                                    : "bg-slate-900 hover:bg-slate-800 text-white shadow-lg shadow-slate-900/20"
                            }`}
                            title={providerState.wecom.message}
                            onClick={handleWecomLogin}
                        >
                            企业微信登录 (WeCom)
                        </Button>
                        <p id="wecom-login-status" className="text-center text-xs text-slate-400">
                            {providerState.wecom.message}
                        </p>
                    </div>

                    {providerState.devFallback.enabled && (
                        <div className="space-y-2">
                            <Button
                                type="button"
                                variant="outline"
                                className="w-full h-12 rounded-full border-slate-200 text-slate-700"
                                disabled={isDevLoginLoading}
                                onClick={handleDevLogin}
                            >
                                {isDevLoginLoading ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 开发者登录中...
                                    </>
                                ) : (
                                    "开发者快速登录"
                                )}
                            </Button>
                            <p className="text-center text-xs text-amber-600">
                                {providerState.devFallback.message}
                            </p>
                        </div>
                    )}

                    <div className="relative flex justify-center text-xs uppercase my-6">
                        <span className="bg-white/50 px-3 text-slate-400 z-10 font-medium">或者使用账号登录</span>
                        <div className="absolute top-1/2 left-0 w-full border-t border-slate-200 -z-0" />
                    </div>

                    <form method="post" onSubmit={requiresPasswordChange ? handleTemporaryPasswordChange : handleLogin} className="space-y-4">
                        {error && (
                            <div role="alert" className="p-3 rounded-lg bg-red-50 border border-red-100 text-red-600 text-sm flex items-center">
                                <AlertCircle className="w-4 h-4 mr-2" />
                                {error}
                            </div>
                        )}
                        <div className="space-y-2">
                            <label className="sr-only" htmlFor="login-email">邮箱地址</label>
                            <Input
                                id="login-email"
                                type="email"
                                autoComplete="username"
                                placeholder="name@company.com"
                                className="bg-white/50 focus:bg-white transition-colors h-12 rounded-full px-6"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                disabled={requiresPasswordChange}
                                required
                            />
                        </div>
                        <div className="space-y-2">
                            {!requiresPasswordChange && <div className="flex justify-end">
                                <Link
                                    href={forgotPasswordHref}
                                    className="text-xs text-slate-500 hover:text-slate-900 transition-colors"
                                >
                                    忘记密码？
                                </Link>
                            </div>}
                            <label className="sr-only" htmlFor="login-password">{requiresPasswordChange ? "新密码" : "密码"}</label>
                            <div className="relative">
                                <Input
                                    id="login-password"
                                    type={showPassword ? "text" : "password"}
                                    autoComplete={requiresPasswordChange ? "new-password" : "current-password"}
                                    placeholder={requiresPasswordChange ? "设置新密码" : "••••••••"}
                                    className="bg-white/50 focus:bg-white transition-colors h-12 rounded-full pl-6 pr-14"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    required
                                />
                                <button
                                    type="button"
                                    aria-label={showPassword ? "隐藏密码" : "显示密码"}
                                    aria-pressed={showPassword}
                                    onClick={() => setShowPassword((current) => !current)}
                                    className="absolute right-4 top-1/2 -translate-y-1/2 inline-flex h-8 w-8 items-center justify-center rounded-full text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
                                >
                                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                </button>
                            </div>
                            {requiresPasswordChange && (
                                <Input
                                    id="confirm-password"
                                    type="password"
                                    autoComplete="new-password"
                                    placeholder="再次输入新密码"
                                    className="bg-white/50 focus:bg-white transition-colors h-12 rounded-full px-6"
                                    value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    required
                                />
                            )}
                        </div>
                        {!requiresPasswordChange && <div className="flex items-start gap-3 rounded-2xl border border-slate-200/70 bg-white/50 p-3">
                            <input
                                id="remember-email"
                                type="checkbox"
                                checked={rememberEmail}
                                onChange={(event) => setRememberEmail(event.target.checked)}
                                className="mt-1 h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900"
                            />
                            <label htmlFor="remember-email" className="text-sm text-slate-600">
                                记住邮箱，下次自动填入；登录有效期仍由后端会话配置决定。
                            </label>
                        </div>}
                        <Button
                            type="submit"
                            disabled={isPasswordLoginLoading}
                            className="w-full h-12 rounded-full mt-4 text-base shadow-lg shadow-slate-900/20 bg-slate-900 hover:bg-slate-800 text-white"
                        >
                            {isPasswordLoginLoading ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 登录中...
                                </>
                            ) : (
                                <>
                                    {requiresPasswordChange ? "保存新密码并进入" : "登录"} <ArrowRight className="ml-2 w-4 h-4" />
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
    );
}
