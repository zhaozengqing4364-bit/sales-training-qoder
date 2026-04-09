"use client";

import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api/client";
import type { CurrentUser } from "@/lib/auth/current-user";
import { authHandler } from "@/lib/auth-handler";
import { currentUserQueryKey } from "@/lib/query/auth";
import { Briefcase, Key, Loader2, LogOut, Mail, Settings, Volume2 } from "lucide-react";

type ProfileForm = {
    display_name: string;
    email: string;
    department: string;
};

type HistoryStats = {
    total_sessions: number;
    average_score: number;
    best_score: number;
    total_practice_time_seconds: number;
    total_practice_time_minutes: number;
};

type SessionStats = {
    total_sessions: number;
    weekly_sessions: number;
    average_score: number;
    completed_sessions: number;
    total_practice_minutes: number;
};

const DEFAULT_STATS: HistoryStats = {
    total_sessions: 0,
    average_score: 0,
    best_score: 0,
    total_practice_time_seconds: 0,
    total_practice_time_minutes: 0,
};

const DEFAULT_SESSION_STATS: SessionStats = {
    total_sessions: 0,
    weekly_sessions: 0,
    average_score: 0,
    completed_sessions: 0,
    total_practice_minutes: 0,
};

export default function ProfilePage() {
    const queryClient = useQueryClient();
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [isEditing, setIsEditing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [profile, setProfile] = useState<ProfileForm>({
        display_name: "",
        email: "",
        department: "",
    });
    const [stats, setStats] = useState<HistoryStats>(DEFAULT_STATS);
    const [sessionStats, setSessionStats] = useState<SessionStats>(DEFAULT_SESSION_STATS);

    useEffect(() => {
        let cancelled = false;

        const loadData = async () => {
            const [profileResult, statsResult, sessionStatsResult] = await Promise.allSettled([
                api.user.getMe(),
                api.dashboard.getHistoryStatistics(),
                api.sessions.getStats(),
            ]);

            if (cancelled) return;

            if (profileResult.status === "fulfilled") {
                setProfile({
                    display_name: profileResult.value.display_name || profileResult.value.name || "用户",
                    email: profileResult.value.email || "",
                    department: profileResult.value.department || "",
                });
            }

            if (statsResult.status === "fulfilled") {
                setStats(statsResult.value);
            }

            if (sessionStatsResult.status === "fulfilled") {
                setSessionStats(sessionStatsResult.value);
            }

            if (
                profileResult.status === "rejected"
                && statsResult.status === "rejected"
                && sessionStatsResult.status === "rejected"
            ) {
                setError("加载个人信息失败，请刷新重试。");
            }

            setIsLoading(false);
        };

        loadData();

        return () => {
            cancelled = true;
        };
    }, []);

    const avatarLabel = useMemo(() => {
        const value = profile.display_name.trim();
        return value ? value.charAt(0).toUpperCase() : "用";
    }, [profile.display_name]);

    const totalHours = useMemo(
        () => Number((stats.total_practice_time_minutes / 60).toFixed(1)),
        [stats.total_practice_time_minutes],
    );

    const onFieldChange = (field: keyof ProfileForm, value: string) => {
        setProfile((prev) => ({ ...prev, [field]: value }));
    };

    const handleSave = async () => {
        setIsSaving(true);
        setError(null);

        try {
            const updated = await api.user.updateProfile({
                display_name: profile.display_name.trim(),
                email: profile.email.trim(),
                department: profile.department.trim(),
            });

            const normalized = {
                display_name: updated.display_name || updated.name || "用户",
                email: updated.email || "",
                department: updated.department || "",
            };

            setProfile(normalized);
            setIsEditing(false);
            queryClient.setQueryData<CurrentUser | undefined>(currentUserQueryKey, (current) => (
                current
                    ? {
                        ...current,
                        name: normalized.display_name,
                        display_name: normalized.display_name,
                        email: normalized.email,
                        department: normalized.department || undefined,
                    }
                    : current
            ));
        } catch (err) {
            const message = err instanceof Error ? err.message : "保存失败，请稍后重试";
            setError(message);
        } finally {
            setIsSaving(false);
        }
    };

    const handleCancelEdit = async () => {
        setIsEditing(false);
        setError(null);

        try {
            const current = await api.user.getMe();
            setProfile({
                display_name: current.display_name || current.name || "用户",
                email: current.email || "",
                department: current.department || "",
            });
        } catch {
            // keep local draft when refetch fails
        }
    };

    const handleLogout = async () => {
        try {
            await api.auth.logout();
        } catch {
            // Ignore logout API failure and still leave the protected session shell.
        } finally {
            authHandler.logout("已退出登录", {
                redirectTo: "/login",
                notify: false,
            });
        }
    };

    if (isLoading) {
        return (
            <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-6">
                <div className="h-8 w-40 rounded bg-slate-100 animate-pulse" />
                <div className="h-36 rounded-2xl bg-white/60 animate-pulse" />
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div className="h-28 rounded-2xl bg-white/60 animate-pulse" />
                    <div className="h-28 rounded-2xl bg-white/60 animate-pulse" />
                    <div className="h-28 rounded-2xl bg-white/60 animate-pulse" />
                    <div className="h-28 rounded-2xl bg-white/60 animate-pulse" />
                </div>
            </div>
        );
    }

    return (
        <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-6">
            <h1 className="text-2xl font-bold text-slate-800">个人中心</h1>

            <GlassCard className="p-6 flex flex-col md:flex-row items-start md:items-center gap-6">
                <div className="w-24 h-24 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 text-3xl font-bold border-4 border-white shadow-lg">
                    {avatarLabel}
                </div>

                <div className="flex-1 w-full space-y-4">
                    {isEditing ? (
                        <div className="space-y-3">
                            <Input
                                value={profile.display_name}
                                onChange={(event) => onFieldChange("display_name", event.target.value)}
                                placeholder="姓名"
                            />
                            <Input
                                value={profile.email}
                                onChange={(event) => onFieldChange("email", event.target.value)}
                                placeholder="邮箱"
                            />
                            <Input
                                value={profile.department}
                                onChange={(event) => onFieldChange("department", event.target.value)}
                                placeholder="部门"
                            />
                            <div className="flex gap-2">
                                <Button onClick={handleSave} disabled={isSaving}>
                                    {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                                    保存
                                </Button>
                                <Button variant="outline" onClick={handleCancelEdit} disabled={isSaving}>
                                    取消
                                </Button>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            <h2 className="text-xl font-bold text-slate-800">{profile.display_name || "用户"}</h2>
                            <div className="flex flex-col md:flex-row gap-4 text-slate-500 text-sm">
                                <span className="flex items-center gap-1">
                                    <Mail className="w-4 h-4" /> {profile.email || "未设置邮箱"}
                                </span>
                                <span className="flex items-center gap-1">
                                    <Briefcase className="w-4 h-4" /> {profile.department || "未设置部门"}
                                </span>
                            </div>
                        </div>
                    )}
                </div>

                {!isEditing ? (
                    <Button variant="outline" className="shrink-0" onClick={() => setIsEditing(true)}>
                        编辑资料
                    </Button>
                ) : null}
            </GlassCard>

            {error ? <div className="text-sm text-red-600">{error}</div> : null}

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <GlassCard className="p-6 text-center">
                    <div className="text-slate-500 text-sm mb-1">总练习时长</div>
                    <div className="text-2xl font-bold text-slate-800">
                        {totalHours} <span className="text-sm font-normal text-slate-400">小时</span>
                    </div>
                </GlassCard>
                <GlassCard className="p-6 text-center">
                    <div className="text-slate-500 text-sm mb-1">累计练习</div>
                    <div className="text-2xl font-bold text-slate-800">
                        {stats.total_sessions} <span className="text-sm font-normal text-slate-400">次</span>
                    </div>
                </GlassCard>
                <GlassCard className="p-6 text-center">
                    <div className="text-slate-500 text-sm mb-1">平均评分</div>
                    <div className="text-2xl font-bold text-indigo-600">
                        {Math.round(stats.average_score || sessionStats.average_score || 0)} <span className="text-sm font-normal text-slate-400">分</span>
                    </div>
                </GlassCard>
                <GlassCard className="p-6 text-center">
                    <div className="text-slate-500 text-sm mb-1">本周练习</div>
                    <div className="text-2xl font-bold text-slate-800">
                        {sessionStats.weekly_sessions} <span className="text-sm font-normal text-slate-400">次</span>
                    </div>
                </GlassCard>
            </div>

            <GlassCard className="p-6">
                <h3 className="text-lg font-semibold text-slate-700 mb-4 flex items-center gap-2">
                    <Settings className="w-5 h-5" /> 系统设置
                </h3>
                <div className="space-y-6">
                    <div className="flex items-center justify-between py-2 border-b border-slate-100">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-blue-50 flex items-center justify-center text-blue-600">
                                <Volume2 className="w-4 h-4" />
                            </div>
                            <div>
                                <div className="text-slate-700 font-medium">语音播放速度</div>
                                <div className="text-xs text-slate-400">调节 AI 回复的语速</div>
                            </div>
                        </div>
                        <select
                            className="bg-slate-50 border border-slate-200 rounded-md text-sm p-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                            value={(() => {
                                if (typeof window === "undefined") return "1.0";
                                return localStorage.getItem("voice_speed_preference") || "1.0";
                            })()}
                            onChange={(e) => {
                                const value = e.target.value;
                                localStorage.setItem("voice_speed_preference", value);
                                // Persist to user profile API when available
                                try {
                                    api.user.updateProfile({ voice_speed_preference: parseFloat(value) } as Parameters<typeof api.user.updateProfile>[0]);
                                } catch {
                                    // Silently ignore - will be persisted when API supports it
                                }
                            }}
                        >
                            <option value="0.75">0.75x</option>
                            <option value="1.0">1.0x</option>
                            <option value="1.25">1.25x</option>
                            <option value="1.5">1.5x</option>
                        </select>
                    </div>

                    <div className="flex items-center justify-between py-2 border-b border-slate-100">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-emerald-50 flex items-center justify-center text-emerald-600">
                                <Key className="w-4 h-4" />
                            </div>
                            <div>
                                <div className="text-slate-700 font-medium">修改密码</div>
                                <div className="text-xs text-slate-400">通过邮箱重置密码，沿用现有邮箱找回流程</div>
                            </div>
                        </div>
                        <Button variant="outline" size="sm" className="rounded-full text-sm" asChild>
                            <Link href="/forgot-password">通过邮箱重置密码</Link>
                        </Button>
                    </div>
                </div>
            </GlassCard>

            <Button variant="destructive" className="w-full md:w-auto" size="lg" onClick={handleLogout}>
                <LogOut className="w-4 h-4 mr-2" />
                退出登录
            </Button>
        </div>
    );
}
