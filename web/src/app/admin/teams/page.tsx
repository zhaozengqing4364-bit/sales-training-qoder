"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, CheckCircle2, Loader2, Network, Plus, ShieldCheck, UserPlus, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api/client";
import type { AdminTeam, AdminTeamLeaderCandidate, AdminUser, CreatedAdminUser } from "@/lib/api/types";

type LoadState = "loading" | "ready" | "error";

function personLabel(person: { name?: string | null; email?: string | null }): string {
    return person.name || person.email || "未命名账号";
}

export default function AdminTeamsPage() {
    const toast = useToast();
    const [loadState, setLoadState] = useState<LoadState>("loading");
    const [errorMessage, setErrorMessage] = useState("");
    const [teams, setTeams] = useState<AdminTeam[]>([]);
    const [learners, setLearners] = useState<AdminUser[]>([]);
    const [leaderCandidates, setLeaderCandidates] = useState<AdminTeamLeaderCandidate[]>([]);
    const [selectedTeamId, setSelectedTeamId] = useState("");
    const [selectedLearnerId, setSelectedLearnerId] = useState("");
    const [selectedLeaderId, setSelectedLeaderId] = useState("");
    const [leaderRole, setLeaderRole] = useState<"primary" | "proxy">("primary");
    const [isAssigningMember, setIsAssigningMember] = useState(false);
    const [isAssigningLeader, setIsAssigningLeader] = useState(false);
    const [showCreate, setShowCreate] = useState(false);
    const [isCreating, setIsCreating] = useState(false);
    const [createForm, setCreateForm] = useState({ code: "", name: "", primaryLeaderUserId: "" });
    const [quickCreateRole, setQuickCreateRole] = useState<"user" | "training_manager" | null>(null);
    const [quickCreateForm, setQuickCreateForm] = useState({ name: "", email: "" });
    const [isQuickCreating, setIsQuickCreating] = useState(false);
    const [createdCredential, setCreatedCredential] = useState<CreatedAdminUser | null>(null);

    const loadData = useCallback(async () => {
        setLoadState("loading");
        setErrorMessage("");
        try {
            const [teamData, learnerData, leaderData] = await Promise.all([
                api.admin.getTeams(),
                api.admin.getUsers({ page: 1, page_size: 100, role: "user", status: "active" }),
                api.admin.getTeamLeaderCandidates(),
            ]);
            setTeams(teamData.items || []);
            setLearners(learnerData.items || []);
            setLeaderCandidates(leaderData.items || []);
            setSelectedTeamId((current) => (
                teamData.items.some((team) => team.team_id === current)
                    ? current
                    : teamData.items[0]?.team_id || ""
            ));
            setLoadState("ready");
        } catch (error) {
            setErrorMessage(error instanceof Error ? error.message : "团队关系加载失败，请重试。");
            setLoadState("error");
        }
    }, []);

    useEffect(() => {
        void loadData();
    }, [loadData]);

    const selectedTeam = teams.find((team) => team.team_id === selectedTeamId) || null;
    const currentMemberIds = useMemo(
        () => new Set(teams.flatMap((team) => team.members.map((member) => member.user_id))),
        [teams],
    );
    const assignableLearners = learners.filter((learner) => !selectedTeam?.members.some((member) => member.user_id === learner.id));

    const handleCreateTeam = async () => {
        if (!createForm.code.trim() || !createForm.name.trim() || !createForm.primaryLeaderUserId) {
            setErrorMessage("请填写团队编码、团队名称并选择主组长。");
            return;
        }
        setIsCreating(true);
        setErrorMessage("");
        try {
            const created = await api.admin.createTeam({
                code: createForm.code.trim(),
                name: createForm.name.trim(),
                primary_leader_user_id: createForm.primaryLeaderUserId,
            });
            setCreateForm({ code: "", name: "", primaryLeaderUserId: "" });
            setShowCreate(false);
            await loadData();
            setSelectedTeamId(created.team_id);
            toast.success("团队已创建");
        } catch (error) {
            setErrorMessage(error instanceof Error ? error.message : "团队创建失败，请检查编码是否重复。");
        } finally {
            setIsCreating(false);
        }
    };

    const handleAssignMember = async () => {
        if (!selectedTeam || !selectedLearnerId) return;
        setIsAssigningMember(true);
        setErrorMessage("");
        try {
            await api.admin.assignTeamMember(selectedTeam.team_id, selectedLearnerId);
            setSelectedLearnerId("");
            await loadData();
            setSelectedTeamId(selectedTeam.team_id);
            toast.success("学员已分配到团队");
        } catch (error) {
            setErrorMessage(error instanceof Error ? error.message : "学员分配失败，原关系未改变。");
        } finally {
            setIsAssigningMember(false);
        }
    };

    const handleAssignLeader = async () => {
        if (!selectedTeam || !selectedLeaderId) return;
        setIsAssigningLeader(true);
        setErrorMessage("");
        try {
            await api.admin.assignTeamLeader(selectedTeam.team_id, {
                leader_user_id: selectedLeaderId,
                assignment_role: leaderRole,
            });
            setSelectedLeaderId("");
            await loadData();
            setSelectedTeamId(selectedTeam.team_id);
            toast.success(leaderRole === "primary" ? "主组长已更新" : "代理组长已添加");
        } catch (error) {
            setErrorMessage(error instanceof Error ? error.message : "组长关系保存失败，原关系未改变。");
        } finally {
            setIsAssigningLeader(false);
        }
    };

    const handleQuickCreateAccount = async () => {
        if (!quickCreateRole || !quickCreateForm.name.trim() || !quickCreateForm.email.trim()) {
            setErrorMessage("请填写账号姓名和公司邮箱。");
            return;
        }
        setIsQuickCreating(true);
        setErrorMessage("");
        try {
            const created = await api.admin.createUser({
                name: quickCreateForm.name.trim(),
                email: quickCreateForm.email.trim(),
                role: quickCreateRole,
            });
            setCreatedCredential(created);
            await loadData();
            if (quickCreateRole === "user") {
                setSelectedLearnerId(created.id);
            } else {
                setSelectedLeaderId(created.id);
                setCreateForm((form) => ({ ...form, primaryLeaderUserId: created.id }));
            }
            setQuickCreateForm({ name: "", email: "" });
            setQuickCreateRole(null);
            toast.success("账号已创建，请继续保存团队关系");
        } catch (error) {
            setErrorMessage(error instanceof Error ? error.message : "账号创建失败，已填写内容仍保留。");
        } finally {
            setIsQuickCreating(false);
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div>
                    <Link href="/admin/users" prefetch={false} className="mb-3 inline-flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-900">
                        <ArrowLeft className="h-4 w-4" />返回用户管理
                    </Link>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900">团队与成员</h1>
                    <p className="mt-1 text-slate-500">指定销售组长和其负责的学员。授权以这里的显式团队关系为准，不使用部门字段。</p>
                </div>
                <Button onClick={() => setShowCreate((value) => !value)} className="rounded-full bg-slate-900 text-white">
                    <Plus className="mr-2 h-4 w-4" />新建团队
                </Button>
            </div>

            <GlassCard className="grid gap-4 border border-blue-100 bg-blue-50/50 p-5 md:grid-cols-3">
                <div className="flex gap-3"><ShieldCheck className="mt-0.5 h-5 w-5 text-blue-700" /><div><p className="font-bold text-slate-900">1. 创建账号</p><p className="text-sm text-slate-600">在用户管理添加学员、培训管理员、技术支持或平台管理员。</p></div></div>
                <div className="flex gap-3"><Network className="mt-0.5 h-5 w-5 text-blue-700" /><div><p className="font-bold text-slate-900">2. 建立团队关系</p><p className="text-sm text-slate-600">培训管理员被指定到团队后，才成为该团队的销售组长。</p></div></div>
                <div className="flex gap-3"><Users className="mt-0.5 h-5 w-5 text-blue-700" /><div><p className="font-bold text-slate-900">3. 分配学员</p><p className="text-sm text-slate-600">本期销售组长只读查看结果，训练任务仍由平台管理员分配。</p></div></div>
            </GlassCard>

            {errorMessage && (
                <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {errorMessage}
                </div>
            )}

            {createdCredential && (
                <GlassCard className="border border-amber-200 bg-amber-50 p-5">
                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <div><h2 className="font-bold text-slate-900">账号已创建，临时密码仅显示一次</h2><p className="mt-1 text-sm text-slate-600">请安全交付给 {createdCredential.display_name || createdCredential.email}，首次登录必须修改密码。</p></div>
                        <Button variant="outline" onClick={() => setCreatedCredential(null)} className="rounded-full border-amber-300">我已保存</Button>
                    </div>
                    <div className="mt-4 grid gap-3 rounded-xl bg-white p-4 text-sm md:grid-cols-2"><div><span className="text-slate-500">登录邮箱</span><p className="mt-1 font-mono font-bold text-slate-900">{createdCredential.email}</p></div><div><span className="text-slate-500">临时密码</span><p className="mt-1 font-mono font-bold text-slate-900">{createdCredential.temporary_password}</p></div></div>
                </GlassCard>
            )}

            {quickCreateRole && (
                <GlassCard className="space-y-4 border border-blue-200 p-5">
                    <div><h2 className="text-lg font-bold text-slate-900">快速创建{quickCreateRole === "user" ? "学员" : "培训管理员"}账号</h2><p className="text-sm text-slate-500">无需离开当前页面；创建后会自动选中该账号，请继续保存团队关系。</p></div>
                    <div className="grid gap-4 md:grid-cols-2"><label className="space-y-2 text-sm font-medium text-slate-700">姓名<input aria-label="快速创建姓名" value={quickCreateForm.name} onChange={(event) => setQuickCreateForm((form) => ({ ...form, name: event.target.value }))} className="h-10 w-full rounded-lg border border-slate-200 px-3 font-normal" /></label><label className="space-y-2 text-sm font-medium text-slate-700">公司邮箱<input aria-label="快速创建邮箱" type="email" value={quickCreateForm.email} onChange={(event) => setQuickCreateForm((form) => ({ ...form, email: event.target.value }))} className="h-10 w-full rounded-lg border border-slate-200 px-3 font-normal" /></label></div>
                    <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setQuickCreateRole(null)} className="rounded-full">取消</Button><Button onClick={() => void handleQuickCreateAccount()} disabled={isQuickCreating} className="rounded-full bg-slate-900 text-white">{isQuickCreating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}创建并选中</Button></div>
                </GlassCard>
            )}

            {showCreate && (
                <GlassCard className="space-y-4 p-5">
                    <div><h2 className="text-lg font-bold text-slate-900">新建团队</h2><p className="text-sm text-slate-500">主组长必须先拥有“培训管理员”账号角色。</p></div>
                    <div className="grid gap-4 md:grid-cols-3">
                        <label className="space-y-2 text-sm font-medium text-slate-700">团队编码<input aria-label="团队编码" value={createForm.code} onChange={(event) => setCreateForm((form) => ({ ...form, code: event.target.value }))} placeholder="east-sales" className="h-10 w-full rounded-lg border border-slate-200 px-3 font-normal" /></label>
                        <label className="space-y-2 text-sm font-medium text-slate-700">团队名称<input aria-label="团队名称" value={createForm.name} onChange={(event) => setCreateForm((form) => ({ ...form, name: event.target.value }))} placeholder="华东销售一组" className="h-10 w-full rounded-lg border border-slate-200 px-3 font-normal" /></label>
                        <label className="space-y-2 text-sm font-medium text-slate-700">主组长<select aria-label="主组长" value={createForm.primaryLeaderUserId} onChange={(event) => setCreateForm((form) => ({ ...form, primaryLeaderUserId: event.target.value }))} className="h-10 w-full rounded-lg border border-slate-200 px-3 font-normal"><option value="">选择培训管理员</option>{leaderCandidates.map((candidate) => <option key={candidate.user_id} value={candidate.user_id}>{personLabel(candidate)}</option>)}</select><button type="button" onClick={() => setQuickCreateRole("training_manager")} className="text-left text-xs font-medium text-blue-700 hover:text-blue-900">没有候选账号？在此创建</button></label>
                    </div>
                    <div className="flex justify-end"><Button onClick={() => void handleCreateTeam()} disabled={isCreating} className="rounded-full bg-slate-900 text-white">{isCreating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}创建团队</Button></div>
                </GlassCard>
            )}

            {loadState === "loading" && <GlassCard className="p-10 text-center text-slate-500"><Loader2 className="mx-auto mb-3 h-6 w-6 animate-spin" />正在加载团队关系…</GlassCard>}
            {loadState === "error" && <Button onClick={() => void loadData()} variant="outline">重新加载</Button>}

            {loadState === "ready" && teams.length === 0 && (
                <GlassCard className="p-10 text-center"><Network className="mx-auto mb-3 h-8 w-8 text-slate-400" /><h2 className="font-bold text-slate-900">还没有团队</h2><p className="mt-1 text-sm text-slate-500">点击“新建团队”；如果没有候选组长，可直接在表单内创建培训管理员账号。</p></GlassCard>
            )}

            {loadState === "ready" && teams.length > 0 && (
                <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
                    <GlassCard className="overflow-hidden p-2">
                        <div className="px-3 py-2 text-xs font-bold uppercase tracking-wide text-slate-400">团队列表</div>
                        {teams.map((team) => (
                            <button key={team.team_id} type="button" onClick={() => setSelectedTeamId(team.team_id)} className={`w-full rounded-xl px-4 py-3 text-left ${selectedTeamId === team.team_id ? "bg-slate-900 text-white" : "hover:bg-slate-50"}`}>
                                <div className="font-bold">{team.name}</div>
                                <div className={`mt-1 text-xs ${selectedTeamId === team.team_id ? "text-slate-300" : "text-slate-500"}`}>{team.member_count} 位学员 · {team.code}</div>
                            </button>
                        ))}
                    </GlassCard>

                    {selectedTeam && (
                        <div className="space-y-5">
                            <GlassCard className="p-5">
                                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                                    <div><h2 className="text-xl font-black text-slate-900">{selectedTeam.name}</h2><p className="mt-1 text-sm text-slate-500">编码 {selectedTeam.code} · {selectedTeam.member_count} 位学员</p></div>
                                    <div className="text-sm text-slate-600">主组长：<span className="font-bold text-slate-900">{personLabel(selectedTeam.leaders.find((leader) => leader.assignment_role === "primary") || {})}</span></div>
                                </div>
                            </GlassCard>

                            <div className="grid gap-5 xl:grid-cols-2">
                                <GlassCard className="space-y-4 p-5">
                                    <div><h3 className="font-bold text-slate-900">设置销售组长</h3><p className="text-sm text-slate-500">主组长替换原主组长；代理组长可并存。本期均为只读。</p></div>
                                    <label className="block text-sm font-medium text-slate-700">账号<select aria-label="销售组长账号" value={selectedLeaderId} onChange={(event) => setSelectedLeaderId(event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-slate-200 px-3 font-normal"><option value="">选择培训管理员</option>{leaderCandidates.map((candidate) => <option key={candidate.user_id} value={candidate.user_id}>{personLabel(candidate)}</option>)}</select></label>
                                    <button type="button" onClick={() => setQuickCreateRole("training_manager")} className="text-left text-sm font-medium text-blue-700 hover:text-blue-900">没有候选账号？在此创建培训管理员</button>
                                    <label className="block text-sm font-medium text-slate-700">关系<select aria-label="组长关系" value={leaderRole} onChange={(event) => setLeaderRole(event.target.value as "primary" | "proxy")} className="mt-2 h-10 w-full rounded-lg border border-slate-200 px-3 font-normal"><option value="primary">主组长</option><option value="proxy">代理组长</option></select></label>
                                    <Button onClick={() => void handleAssignLeader()} disabled={!selectedLeaderId || isAssigningLeader} className="w-full rounded-full bg-slate-900 text-white">{isAssigningLeader && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}保存组长关系</Button>
                                </GlassCard>

                                <GlassCard className="space-y-4 p-5">
                                    <div><h3 className="font-bold text-slate-900">分配学员</h3><p className="text-sm text-slate-500">每位学员只能有一个主团队；重新分配会结束原团队关系。</p></div>
                                    <label className="block text-sm font-medium text-slate-700">学员<select aria-label="待分配学员" value={selectedLearnerId} onChange={(event) => setSelectedLearnerId(event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-slate-200 px-3 font-normal"><option value="">选择学员</option>{assignableLearners.map((learner) => <option key={learner.id} value={learner.id}>{learner.display_name || learner.email || learner.id}{currentMemberIds.has(learner.id) ? "（调组）" : ""}</option>)}</select></label>
                                    <button type="button" onClick={() => setQuickCreateRole("user")} className="text-left text-sm font-medium text-blue-700 hover:text-blue-900">没有学员账号？在此创建并继续分配</button>
                                    <Button onClick={() => void handleAssignMember()} disabled={!selectedLearnerId || isAssigningMember} className="w-full rounded-full bg-blue-600 text-white hover:bg-blue-700">{isAssigningMember ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <UserPlus className="mr-2 h-4 w-4" />}分配到当前团队</Button>
                                </GlassCard>
                            </div>

                            <GlassCard className="overflow-hidden">
                                <div className="border-b border-slate-100 px-5 py-4"><h3 className="font-bold text-slate-900">当前成员</h3></div>
                                {selectedTeam.members.length === 0 ? (
                                    <div className="p-8 text-center text-sm text-slate-500">当前团队还没有学员，请从上方分配。</div>
                                ) : (
                                    <div className="divide-y divide-slate-100">{selectedTeam.members.map((member) => <div key={member.user_id} className="flex items-center justify-between px-5 py-3"><div><p className="font-medium text-slate-900">{personLabel(member)}</p><p className="text-xs text-slate-500">{member.email}</p></div><span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700"><CheckCircle2 className="h-4 w-4" />已分配</span></div>)}</div>
                                )}
                            </GlassCard>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
