"use client";

import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CheckCircle2,
  FileDown,
  PauseCircle,
  Search,
  Upload,
  UserPlus,
} from "lucide-react";

import { FoundationAdminCapabilityBoundary } from "@/components/admin/newcomer-training/workspace-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/glass-modal";
import { Input } from "@/components/ui/input";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { createIdempotencyTokenStore } from "@/lib/idempotency-token-store";
import type {
  FoundationBatchPreview,
  FoundationMigrationPreview,
} from "@/lib/api/types/foundation-admin";

type DialogMode = "import" | "migration" | "status" | null;

export function FoundationCohortDetailWorkspace({
  cohortId,
}: {
  cohortId: string;
}) {
  const queryClient = useQueryClient();
  const tokenStore = useRef(createIdempotencyTokenStore());
  const [learnerSearch, setLearnerSearch] = useState("");
  const [submittedLearnerSearch, setSubmittedLearnerSearch] = useState("");
  const [selectedLearners, setSelectedLearners] = useState<string[]>([]);
  const [csvEmails, setCsvEmails] = useState<string[]>([]);
  const [selectedEnrollments, setSelectedEnrollments] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [dialogMode, setDialogMode] = useState<DialogMode>(null);
  const [importPreview, setImportPreview] =
    useState<FoundationBatchPreview | null>(null);
  const [migrationPreview, setMigrationPreview] =
    useState<FoundationMigrationPreview | null>(null);
  const [targetRevisionId, setTargetRevisionId] = useState("");
  const [targetStatus, setTargetStatus] = useState<
    "active" | "paused" | "cancelled" | "closed"
  >("paused");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showQuickUser, setShowQuickUser] = useState(false);
  const [newUserName, setNewUserName] = useState("");
  const [newUserEmail, setNewUserEmail] = useState("");

  const cohort = useQuery({
    queryKey: ["foundation-admin", "cohort", cohortId],
    queryFn: () => api.admin.newcomerTraining.getCohortWorkspace(cohortId),
  });
  const learnerOptions = useQuery({
    queryKey: ["foundation-admin", "learner-options", submittedLearnerSearch],
    queryFn: () =>
      api.admin.newcomerTraining.listLearnerOptions({
        search: submittedLearnerSearch || undefined,
        limit: 100,
      }),
  });
  const paths = useQuery({
    queryKey: ["foundation-admin", "paths", "migration-options"],
    queryFn: () => api.admin.newcomerTraining.listPaths({ limit: 100 }),
  });
  const enrolledLearnerIds = useMemo(
    () =>
      new Set(cohort.data?.enrollments.map((item) => item.learner_id) ?? []),
    [cohort.data],
  );
  const availableLearners =
    learnerOptions.data?.items.filter(
      (item) => !enrolledLearnerIds.has(item.learner_id),
    ) ?? [];
  const targetPaths =
    paths.data?.items.filter(
      (item) =>
        item.published_revision_id &&
        item.published_revision_id !== cohort.data?.cohort.path_revision_id,
    ) ?? [];

  const importPreviewMutation = useMutation({
    mutationFn: async () => {
      if (selectedLearners.length === 0 && csvEmails.length === 0)
        throw new Error("请至少选择一名学员或导入一份名单。");
      if (!reason.trim()) throw new Error("请填写批量分配原因。");
      return csvEmails.length
        ? api.admin.newcomerTraining.previewEnrollmentEmailImport(
            cohortId,
            csvEmails,
            reason.trim(),
          )
        : api.admin.newcomerTraining.previewEnrollmentImport(
            cohortId,
            selectedLearners,
            reason.trim(),
          );
    },
    onSuccess: (value) => {
      setImportPreview(value);
      setResult(null);
      setDialogMode("import");
      setError(null);
    },
    onError: (caught) => setError(getApiErrorMessage(caught)),
  });
  const importConfirm = useMutation({
    mutationFn: async () => {
      if (!importPreview) throw new Error("分配预览已失效，请重新预览。");
      const key = `confirm-import:${importPreview.import_id ?? importPreview.impact_hash}`;
      const value = await api.admin.newcomerTraining.confirmEnrollmentImport(
        importPreview,
        tokenStore.current.tokenFor(key),
      );
      tokenStore.current.complete(key);
      return value;
    },
    onSuccess: async (value) => {
      setResult(value);
      setSelectedLearners([]);
      setCsvEmails([]);
      await queryClient.invalidateQueries({
        queryKey: ["foundation-admin", "cohort", cohortId],
      });
    },
    onError: (caught) => setError(getApiErrorMessage(caught)),
  });
  const migrationPreviewMutation = useMutation({
    mutationFn: async () => {
      if (selectedEnrollments.length === 0)
        throw new Error("请至少选择一名在训学员。");
      if (!targetRevisionId) throw new Error("请选择迁移目标版本。");
      if (!reason.trim()) throw new Error("请填写版本迁移原因。");
      return api.admin.newcomerTraining.previewEnrollmentMigration(
        selectedEnrollments,
        targetRevisionId,
        reason.trim(),
      );
    },
    onSuccess: (value) => {
      setMigrationPreview(value);
      setResult(null);
      setDialogMode("migration");
      setError(null);
    },
    onError: (caught) => setError(getApiErrorMessage(caught)),
  });
  const migrationConfirm = useMutation({
    mutationFn: async () => {
      if (!migrationPreview) throw new Error("迁移预览已失效，请重新预览。");
      const key = `confirm-migration:${migrationPreview.migration_id}`;
      const value = await api.admin.newcomerTraining.confirmEnrollmentMigration(
        migrationPreview,
        reason.trim(),
        tokenStore.current.tokenFor(key),
      );
      tokenStore.current.complete(key);
      return value;
    },
    onSuccess: async (value) => {
      setResult(value);
      setSelectedEnrollments([]);
      await queryClient.invalidateQueries({
        queryKey: ["foundation-admin", "cohort", cohortId],
      });
    },
    onError: (caught) => setError(getApiErrorMessage(caught)),
  });
  const changeStatus = useMutation({
    mutationFn: async () => {
      if (!cohort.data) throw new Error("班级信息尚未加载。");
      if (!reason.trim()) throw new Error("请填写状态调整原因。");
      const key = `cohort-status:${cohortId}:${cohort.data.cohort.version}:${targetStatus}:${reason.trim()}`;
      const value = await api.admin.newcomerTraining.changeCohortStatus(
        cohortId,
        targetStatus,
        reason.trim(),
        cohort.data.cohort.version,
        tokenStore.current.tokenFor(key),
      );
      tokenStore.current.complete(key);
      return value;
    },
    onSuccess: async () => {
      setDialogMode(null);
      setReason("");
      setMessage("班级状态已更新；已有 Enrollment 的冻结版本没有变化。");
      await queryClient.invalidateQueries({
        queryKey: ["foundation-admin", "cohort", cohortId],
      });
    },
    onError: (caught) => setError(getApiErrorMessage(caught)),
  });
  const createUser = useMutation({
    mutationFn: async () => {
      if (!newUserName.trim() || !newUserEmail.trim())
        throw new Error("请填写学员姓名和邮箱。");
      return api.admin.createUser({
        name: newUserName.trim(),
        email: newUserEmail.trim(),
        role: "user",
      });
    },
    onSuccess: async (value) => {
      setCsvEmails([]);
      setSelectedLearners((current) => [...current, value.id]);
      setNewUserName("");
      setNewUserEmail("");
      setShowQuickUser(false);
      setMessage(
        "学员账号已创建并选中；临时凭证只在账号创建结果中向有权限人员展示。",
      );
      await queryClient.invalidateQueries({
        queryKey: ["foundation-admin", "learner-options"],
      });
    },
    onError: (caught) => setError(getApiErrorMessage(caught)),
  });

  const readEnrollmentCsv = async (file: File) => {
    try {
      if (file.size > 1024 * 1024) {
        throw new Error("导入文件不能超过 1 MB，请拆分后重试。");
      }
      const emails = parseEnrollmentCsv(await file.text());
      setCsvEmails(emails);
      setSelectedLearners([]);
      setImportPreview(null);
      setResult(null);
      setMessage(
        `已读取 ${emails.length} 个学员邮箱；正式分配前仍会逐项校验账号、重复分配和班级状态。`,
      );
      setError(null);
    } catch (caught) {
      setError(getApiErrorMessage(caught));
    }
  };

  if (cohort.isPending)
    return (
      <main className="px-4 py-6 md:px-6">
        <div className="mx-auto h-[600px] max-w-7xl animate-pulse rounded-2xl bg-slate-100" />
      </main>
    );
  if (cohort.error || !cohort.data)
    return (
      <main className="px-4 py-6 md:px-6">
        <div
          role="alert"
          className="mx-auto max-w-3xl rounded-2xl border border-red-200 bg-red-50 p-6 text-red-900"
        >
          {getApiErrorMessage(cohort.error)}
          <button
            type="button"
            className="ml-2 font-semibold underline"
            onClick={() => void cohort.refetch()}
          >
            重试
          </button>
        </div>
      </main>
    );
  const status = cohort.data.cohort.status;
  const statusActions: Array<{ value: typeof targetStatus; label: string }> =
    status === "active"
      ? [
          { value: "paused", label: "暂停班级" },
          { value: "closed", label: "结束班级" },
          { value: "cancelled", label: "取消班级" },
        ]
      : status === "paused" || status === "closed"
        ? [
            { value: "active", label: "恢复班级" },
            { value: "cancelled", label: "取消班级" },
          ]
        : [];

  return (
    <FoundationAdminCapabilityBoundary capability="manage_cohorts">
      <main className="px-4 py-6 md:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <header className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 md:flex-row md:items-start md:justify-between">
            <div>
              <Link
                href="/admin/newcomer-training/cohorts"
                prefetch={false}
                className="inline-flex items-center gap-2 text-sm font-medium text-slate-600"
              >
                <ArrowLeft className="h-4 w-4" />
                返回班级列表
              </Link>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <h1 className="text-2xl font-bold text-slate-950">
                  {cohort.data.cohort.name}
                </h1>
                <Badge
                  variant={
                    status === "active"
                      ? "green"
                      : status === "cancelled"
                        ? "red"
                        : "gray"
                  }
                >
                  {status === "active"
                    ? "进行中"
                    : status === "paused"
                      ? "已暂停"
                      : status === "closed"
                        ? "已结束"
                        : "已取消"}
                </Badge>
              </div>
              <p className="mt-2 text-sm text-slate-500">
                已绑定路径版本保持不变；任何迁移都需要单独预览并逐项确认。
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {statusActions.map((action) => (
                <Button
                  key={action.value}
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setTargetStatus(action.value);
                    setReason("");
                    setDialogMode("status");
                    setError(null);
                  }}
                >
                  <PauseCircle className="mr-2 h-4 w-4" />
                  {action.label}
                </Button>
              ))}
            </div>
          </header>
          {message ? (
            <div
              role="status"
              className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900"
            >
              {message}
            </div>
          ) : null}
          {error ? (
            <div
              role="alert"
              className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900"
            >
              {error}
            </div>
          ) : null}
          <section
            aria-labelledby="enrollment-title"
            className="rounded-2xl border border-slate-200 bg-white p-5"
          >
            <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
              <div>
                <h2
                  id="enrollment-title"
                  className="font-semibold text-slate-950"
                >
                  班级学员
                </h2>
                <p className="mt-1 text-sm text-slate-600">
                  共 {cohort.data.enrollments.length}{" "}
                  人；勾选后可对指定范围预览版本迁移。
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <select
                  aria-label="迁移目标版本"
                  className={`${selectClassName} min-w-60`}
                  value={targetRevisionId}
                  onChange={(event) => setTargetRevisionId(event.target.value)}
                >
                  <option value="">选择迁移目标版本</option>
                  {targetPaths.map((path) => (
                    <option
                      key={path.path_id}
                      value={path.published_revision_id ?? ""}
                    >
                      {path.title}
                    </option>
                  ))}
                </select>
                <Button
                  type="button"
                  variant="outline"
                  disabled={selectedEnrollments.length === 0}
                  onClick={() => {
                    setReason("");
                    setMigrationPreview(null);
                    setDialogMode("migration");
                  }}
                >
                  预览迁移（{selectedEnrollments.length}）
                </Button>
              </div>
            </div>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="border-b border-slate-200 text-xs text-slate-500">
                  <tr>
                    <th className="px-3 py-2">选择</th>
                    <th className="px-3 py-2">学员</th>
                    <th className="px-3 py-2">邮箱</th>
                    <th className="px-3 py-2">训练状态</th>
                    <th className="px-3 py-2">冻结版本</th>
                    <th className="px-3 py-2">分配时间</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {cohort.data.enrollments.map((item) => (
                    <tr key={item.enrollment_id}>
                      <td className="px-3 py-3">
                        <input
                          type="checkbox"
                          aria-label={`选择${item.learner_name}进行版本迁移`}
                          checked={selectedEnrollments.includes(
                            item.enrollment_id,
                          )}
                          onChange={(event) =>
                            setSelectedEnrollments((current) =>
                              event.target.checked
                                ? [...current, item.enrollment_id]
                                : current.filter(
                                    (id) => id !== item.enrollment_id,
                                  ),
                            )
                          }
                        />
                      </td>
                      <td className="px-3 py-3 font-medium text-slate-900">
                        {item.learner_name}
                      </td>
                      <td className="px-3 py-3 text-slate-600">
                        {item.learner_email ?? "未填写"}
                      </td>
                      <td className="px-3 py-3">
                        <Badge
                          variant={item.status === "active" ? "green" : "gray"}
                        >
                          {item.status === "active" ? "训练中" : "已结束"}
                        </Badge>
                      </td>
                      <td className="px-3 py-3 text-slate-600">分配时版本</td>
                      <td className="px-3 py-3 text-slate-500">
                        {new Date(item.assigned_at).toLocaleString("zh-CN")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {cohort.data.enrollments.length === 0 ? (
                <div className="py-10 text-center text-sm text-slate-500">
                  班级尚未分配学员。
                </div>
              ) : null}
            </div>
          </section>
          <section
            aria-labelledby="assign-title"
            className="rounded-2xl border border-slate-200 bg-white p-5"
          >
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div>
                <h2 id="assign-title" className="font-semibold text-slate-950">
                  批量分配学员
                </h2>
                <p className="mt-1 text-sm text-slate-600">
                  在当前流程搜索已有账号或快速新建最小账号，再预览逐项校验结果。
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button asChild type="button" variant="outline">
                  <a href={ENROLLMENT_TEMPLATE_HREF} download="新人训练学员导入模板.csv">
                    <FileDown className="mr-2 h-4 w-4" />
                    下载导入模板
                  </a>
                </Button>
                <label className="inline-flex h-10 cursor-pointer items-center justify-center rounded-xl border border-slate-200 bg-white px-4 text-sm font-medium text-slate-700 hover:bg-slate-50 focus-within:ring-2 focus-within:ring-slate-900/20">
                  <Upload className="mr-2 h-4 w-4" />
                  导入 CSV
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    className="sr-only"
                    aria-label="导入学员 CSV"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) void readEnrollmentCsv(file);
                      event.target.value = "";
                    }}
                  />
                </label>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowQuickUser((value) => !value)}
                >
                  <UserPlus className="mr-2 h-4 w-4" />
                  {showQuickUser ? "返回选择" : "快速新建学员"}
                </Button>
              </div>
            </div>
            {csvEmails.length ? (
              <div className="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
                已读取 {csvEmails.length} 个邮箱。当前名单将通过服务端逐项校验；手动勾选学员会替换这份名单。
              </div>
            ) : null}
            {showQuickUser ? (
              <form
                className="mt-4 grid gap-3 rounded-xl border border-blue-200 bg-blue-50/50 p-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
                onSubmit={(event) => {
                  event.preventDefault();
                  setError(null);
                  createUser.mutate();
                }}
              >
                <Field label="学员姓名">
                  <Input
                    value={newUserName}
                    onChange={(event) => setNewUserName(event.target.value)}
                  />
                </Field>
                <Field label="工作邮箱">
                  <Input
                    type="email"
                    value={newUserEmail}
                    onChange={(event) => setNewUserEmail(event.target.value)}
                  />
                </Field>
                <Button type="submit" disabled={createUser.isPending}>
                  {createUser.isPending ? "正在创建…" : "创建并选中"}
                </Button>
              </form>
            ) : (
              <>
                <form
                  role="search"
                  className="mt-4 flex gap-2"
                  onSubmit={(event) => {
                    event.preventDefault();
                    setSubmittedLearnerSearch(learnerSearch.trim());
                  }}
                >
                  <label className="relative min-w-0 flex-1">
                    <span className="sr-only">搜索学员</span>
                    <Search className="pointer-events-none absolute left-4 top-3.5 h-4 w-4 text-slate-400" />
                    <Input
                      className="pl-10"
                      value={learnerSearch}
                      onChange={(event) => setLearnerSearch(event.target.value)}
                      placeholder="按姓名或邮箱搜索"
                    />
                  </label>
                  <Button type="submit" variant="outline">
                    搜索
                  </Button>
                </form>
                <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {learnerOptions.isPending
                    ? [0, 1, 2].map((item) => (
                        <div
                          key={item}
                          className="h-20 animate-pulse rounded-xl bg-slate-100"
                        />
                      ))
                    : availableLearners.map((learner) => (
                        <label
                          key={learner.learner_id}
                          className="flex items-start gap-3 rounded-xl border border-slate-200 p-3 text-sm"
                        >
                          <input
                            type="checkbox"
                            className="mt-1"
                            checked={selectedLearners.includes(
                              learner.learner_id,
                            )}
                            onChange={(event) => {
                              setCsvEmails([]);
                              setSelectedLearners((current) =>
                                event.target.checked
                                  ? [...current, learner.learner_id]
                                  : current.filter(
                                      (id) => id !== learner.learner_id,
                                    ),
                              );
                            }}
                          />
                          <span>
                            <span className="block font-medium text-slate-950">
                              {learner.name}
                            </span>
                            <span className="mt-1 block text-xs text-slate-500">
                              {learner.email ?? "未填写邮箱"}
                            </span>
                          </span>
                        </label>
                      ))}
                </div>
              </>
            )}
            <div className="mt-4 flex justify-end">
              <Button
                type="button"
                disabled={
                  (selectedLearners.length === 0 && csvEmails.length === 0) ||
                  status !== "active"
                }
                onClick={() => {
                  setReason("");
                  setImportPreview(null);
                  setResult(null);
                  setDialogMode("import");
                }}
              >
                {status !== "active"
                  ? "班级恢复后才能分配"
                  : `预览分配（${csvEmails.length || selectedLearners.length} 人）`}
              </Button>
            </div>
          </section>
        </div>
      </main>
      <Dialog
        open={dialogMode !== null}
        onOpenChange={(open) => {
          if (
            !open &&
            !importConfirm.isPending &&
            !migrationConfirm.isPending &&
            !changeStatus.isPending
          )
            setDialogMode(null);
        }}
      >
        <DialogContent className="max-h-[85vh] max-w-xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {dialogMode === "import"
                ? "批量分配预览"
                : dialogMode === "migration"
                  ? "路径版本迁移预览"
                  : "调整班级状态"}
            </DialogTitle>
            <DialogDescription>
              {dialogMode === "import"
                ? "确认学员资格、重复分配和部分失败。"
                : dialogMode === "migration"
                  ? "活跃学员默认不迁移；这里只处理明确选择的范围。"
                  : "状态调整不会改变已存在 Enrollment 的冻结版本。"}
            </DialogDescription>
          </DialogHeader>
          {!result ? (
            <Field label="操作原因">
              <Input
                value={reason}
                onChange={(event) => {
                  setReason(event.target.value);
                  if (dialogMode === "import") setImportPreview(null);
                  if (dialogMode === "migration") setMigrationPreview(null);
                }}
                maxLength={2000}
              />
            </Field>
          ) : null}
          {dialogMode === "import" && importPreview ? (
            <PreviewSummary
              eligible={importPreview.eligible_count}
              failed={importPreview.failure_count}
              items={importPreview.items}
            />
          ) : null}
          {dialogMode === "migration" && migrationPreview ? (
            <PreviewSummary
              eligible={migrationPreview.eligible_count}
              failed={migrationPreview.failure_count}
              items={migrationPreview.items}
            />
          ) : null}
          {result ? <ResultPanel result={result} /> : null}
          {error ? (
            <p role="alert" className="text-sm text-red-700">
              {error}
            </p>
          ) : null}
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setDialogMode(null)}
              disabled={
                importConfirm.isPending ||
                migrationConfirm.isPending ||
                changeStatus.isPending
              }
            >
              {result ? "关闭" : "取消"}
            </Button>
            {!result && dialogMode === "import" && !importPreview ? (
              <Button
                type="button"
                onClick={() => importPreviewMutation.mutate()}
                disabled={importPreviewMutation.isPending}
              >
                {importPreviewMutation.isPending ? "正在预览…" : "生成分配预览"}
              </Button>
            ) : null}
            {!result && dialogMode === "import" && importPreview ? (
              <Button
                type="button"
                onClick={() => importConfirm.mutate()}
                disabled={
                  importPreview.eligible_count === 0 || importConfirm.isPending
                }
              >
                {importConfirm.isPending ? "正在分配…" : "确认分配可执行项"}
              </Button>
            ) : null}
            {!result && dialogMode === "migration" && !migrationPreview ? (
              <Button
                type="button"
                onClick={() => migrationPreviewMutation.mutate()}
                disabled={migrationPreviewMutation.isPending}
              >
                {migrationPreviewMutation.isPending
                  ? "正在预览…"
                  : "生成迁移预览"}
              </Button>
            ) : null}
            {!result && dialogMode === "migration" && migrationPreview ? (
              <Button
                type="button"
                onClick={() => migrationConfirm.mutate()}
                disabled={
                  migrationPreview.eligible_count === 0 ||
                  migrationConfirm.isPending
                }
              >
                {migrationConfirm.isPending ? "正在迁移…" : "确认迁移可执行项"}
              </Button>
            ) : null}
            {dialogMode === "status" ? (
              <Button
                type="button"
                onClick={() => changeStatus.mutate()}
                disabled={changeStatus.isPending}
              >
                {changeStatus.isPending
                  ? "正在更新…"
                  : `确认${targetStatus === "active" ? "恢复" : targetStatus === "paused" ? "暂停" : targetStatus === "closed" ? "结束" : "取消"}班级`}
              </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </FoundationAdminCapabilityBoundary>
  );
}

interface PreviewItem {
  learner_id?: string;
  learner_name?: string | null;
  enrollment_id?: string | null;
  status: string;
  reason?: string | null;
}

function PreviewSummary({
  eligible,
  failed,
  items,
}: {
  eligible: number;
  failed: number;
  items: PreviewItem[];
}) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <p className="text-xs text-slate-500">可执行</p>
          <p className="mt-1 text-lg font-semibold">{eligible} 项</p>
        </div>
        <div
          className={`rounded-xl border p-4 ${failed ? "border-red-200 bg-red-50" : "border-slate-200 bg-slate-50"}`}
        >
          <p className="text-xs text-slate-500">无法执行</p>
          <p className="mt-1 text-lg font-semibold">{failed} 项</p>
        </div>
      </div>
      <div className="space-y-2">
        {items.map((item, index) => (
          <div
            key={String(item.learner_id ?? item.enrollment_id ?? index)}
            className={`rounded-xl border p-3 text-sm ${item.status === "eligible" ? "border-emerald-100 bg-emerald-50" : "border-red-100 bg-red-50"}`}
          >
            <span className="font-medium">
              {item.status === "eligible" ? "可以执行" : "无法执行"}
            </span>
            {typeof item.learner_name === "string" ? (
              <span className="ml-2">{item.learner_name}</span>
            ) : null}
            {typeof item.reason === "string" ? (
              <p className="mt-1 text-xs text-slate-600">
                {reasonLabel(item.reason)}
              </p>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
function ResultPanel({ result }: { result: Record<string, unknown> }) {
  const items = Array.isArray(result.items)
    ? result.items.filter(
        (item): item is Record<string, unknown> =>
          Boolean(item) && typeof item === "object" && !Array.isArray(item),
      )
    : [];
  const succeeded =
    typeof result.succeeded_count === "number"
      ? result.succeeded_count
      : typeof result.migrated_count === "number"
        ? result.migrated_count
        : items.filter((item) => item.status === "succeeded").length;
  const failed =
    typeof result.failure_count === "number"
      ? result.failure_count
      : items.filter((item) => item.status === "failed").length;
  return (
    <div
      role="status"
      className={`rounded-xl border p-5 ${failed ? "border-amber-200 bg-amber-50" : "border-emerald-200 bg-emerald-50"}`}
    >
      <CheckCircle2 className="h-5 w-5 text-emerald-600" />
      <h3 className="mt-2 font-semibold text-slate-950">
        {failed ? "操作部分完成" : "操作已完成"}
      </h3>
      <p className="mt-1 text-sm text-slate-700">
        成功 {succeeded} 项，未成功 {failed}{" "}
        项。逐项结果已保存，可只处理失败项。
      </p>
    </div>
  );
}
function reasonLabel(value: string): string {
  return (
    {
      active_enrollment_exists: "该学员已有进行中的训练分配",
      learner_not_found_or_inactive: "学员不存在或已停用",
      learner_email_not_found_or_inactive: "邮箱对应的学员不存在或已停用",
      enrollment_not_active: "该训练分配当前不是进行中",
      already_on_target_revision: "学员已经使用目标版本",
      not_found_or_out_of_scope: "对象不存在或不在权限范围内",
    }[value] ?? value
  );
}
function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="space-y-1 text-sm font-medium text-slate-700">
      <span>{label}</span>
      {children}
    </label>
  );
}
const selectClassName =
  "h-12 rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-slate-900/20";
const ENROLLMENT_TEMPLATE_HREF = `data:text/csv;charset=utf-8,${encodeURIComponent("\uFEFFemail\nnewcomer@example.com\n")}`;

export function parseEnrollmentCsv(raw: string): string[] {
  const rows = raw
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/)
    .map((row) => row.trim())
    .filter(Boolean);
  if (rows.length < 2) {
    throw new Error("CSV 需要包含 email 表头和至少一行学员邮箱。");
  }
  const header = csvCell(rows[0] ?? "").toLowerCase();
  if (header !== "email") {
    throw new Error("CSV 表头必须为 email，请使用下载的导入模板。");
  }
  const emails = rows.slice(1).map((row, index) => {
    if (row.includes(",")) {
      throw new Error(`第 ${index + 2} 行列数不正确，模板只需要 email 一列。`);
    }
    const email = csvCell(row).toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      throw new Error(`第 ${index + 2} 行邮箱格式不正确。`);
    }
    return email;
  });
  if (emails.length > 1_000) {
    throw new Error("单次最多导入 1000 名学员，请拆分文件后重试。");
  }
  if (new Set(emails).size !== emails.length) {
    throw new Error("CSV 中存在重复邮箱，请去重后重试。");
  }
  return emails;
}

function csvCell(value: string): string {
  const trimmed = value.trim();
  if (trimmed.startsWith('"') && trimmed.endsWith('"')) {
    return trimmed.slice(1, -1).replace(/""/g, '"').trim();
  }
  return trimmed;
}
