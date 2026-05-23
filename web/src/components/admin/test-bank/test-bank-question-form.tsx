"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api/client";
import type { QuestionCategory, QuestionItem } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { JsonEditorWithValidation } from "@/components/ui/json-editor-with-validation";
import {
    getScoringCriteriaValidation,
    linesFromList,
    listFromLines,
    parseScoringCriteria,
} from "@/lib/admin/test-bank-scoring";

export interface TestBankQuestionFormProps {
    mode: "create" | "edit";
    questionId?: string;
    initialQuestion?: QuestionItem;
    onSaved: () => void;
    onCancel: () => void;
}

export function TestBankQuestionForm({ mode, questionId, initialQuestion, onSaved, onCancel }: TestBankQuestionFormProps) {
    const [categories, setCategories] = useState<QuestionCategory[]>([]);
    const [formTitle, setFormTitle] = useState(initialQuestion?.title ?? "");
    const [formStem, setFormStem] = useState(initialQuestion?.stem ?? "");
    const [formReferenceAnswer, setFormReferenceAnswer] = useState(initialQuestion?.reference_answer ?? "");
    const [formCategoryId, setFormCategoryId] = useState(initialQuestion?.category_id ?? "");
    const [formDifficulty, setFormDifficulty] = useState<"easy" | "medium" | "hard">(initialQuestion?.difficulty ?? "medium");
    const [formTags, setFormTags] = useState(initialQuestion ? linesFromList(initialQuestion.tags) : "");
    const [formScoringDimensions, setFormScoringDimensions] = useState(initialQuestion ? linesFromList(initialQuestion.scoring_dimensions) : "");
    const [formScoringCriteria, setFormScoringCriteria] = useState(initialQuestion ? JSON.stringify(initialQuestion.scoring_criteria, null, 2) : "");
    const [formSafetyFlagged, setFormSafetyFlagged] = useState(initialQuestion?.safety_flagged ?? false);
    const [formDepartment, setFormDepartment] = useState(initialQuestion?.department ?? "");
    const [formError, setFormError] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const scoringCriteriaValidation = getScoringCriteriaValidation(formScoringCriteria);

    useEffect(() => {
        void api.testBank.listCategories().then((result) => setCategories(result.items || []));
    }, []);

    useEffect(() => {
        if (!initialQuestion) return;
        setFormTitle(initialQuestion.title);
        setFormStem(initialQuestion.stem);
        setFormReferenceAnswer(initialQuestion.reference_answer || "");
        setFormCategoryId(initialQuestion.category_id);
        setFormDifficulty(initialQuestion.difficulty);
        setFormTags(linesFromList(initialQuestion.tags));
        setFormScoringDimensions(linesFromList(initialQuestion.scoring_dimensions));
        setFormScoringCriteria(JSON.stringify(initialQuestion.scoring_criteria, null, 2));
        setFormSafetyFlagged(initialQuestion.safety_flagged);
        setFormDepartment(initialQuestion.department || "");
    }, [initialQuestion]);

    const handleSubmit = async () => {
        if (!formTitle.trim() || !formStem.trim() || !formCategoryId) {
            setFormError("标题、题干和分类为必填项");
            return;
        }
        const criteria = parseScoringCriteria(formScoringCriteria);
        if (criteria === null) {
            setFormError("评分标准格式无效，请输入有效的 JSON 对象");
            return;
        }
        setSubmitting(true);
        setFormError(null);
        try {
            const payload = {
                title: formTitle.trim(),
                stem: formStem.trim(),
                reference_answer: formReferenceAnswer.trim() || null,
                category_id: formCategoryId,
                difficulty: formDifficulty,
                tags: listFromLines(formTags),
                scoring_dimensions: listFromLines(formScoringDimensions),
                scoring_criteria: criteria,
                safety_flagged: formSafetyFlagged,
                department: formDepartment.trim() || null,
            };
            if (mode === "edit" && questionId) {
                await api.testBank.updateQuestion(questionId, payload);
            } else {
                await api.testBank.createQuestion(payload);
            }
            onSaved();
        } catch (err) {
            setFormError(err instanceof Error ? err.message : "保存失败");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <GlassCard className="space-y-4 p-6">
            <h2 className="text-xl font-black text-slate-900">{mode === "edit" ? "编辑题目" : "新建题目"}</h2>
            {formError && <div className="rounded-lg bg-red-50 p-2 text-sm text-red-600">{formError}</div>}
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <input type="text" placeholder="题目标题 *" className="h-10 rounded-lg border border-slate-200 px-3 text-sm" value={formTitle} onChange={(e) => setFormTitle(e.target.value)} />
                <select className="h-10 rounded-lg border border-slate-200 px-3 text-sm" value={formCategoryId} onChange={(e) => setFormCategoryId(e.target.value)} data-testid="form-category">
                    <option value="">选择分类 *</option>
                    {categories.map((c) => (<option key={c.category_id} value={c.category_id}>{c.name}</option>))}
                </select>
                <textarea placeholder="题干 *" className="min-h-20 rounded-lg border border-slate-200 p-3 text-sm md:col-span-2" value={formStem} onChange={(e) => setFormStem(e.target.value)} />
                <textarea placeholder="参考答案" className="min-h-16 rounded-lg border border-slate-200 p-3 text-sm md:col-span-2" value={formReferenceAnswer} onChange={(e) => setFormReferenceAnswer(e.target.value)} />
                <select className="h-10 rounded-lg border border-slate-200 px-3 text-sm" value={formDifficulty} onChange={(e) => setFormDifficulty(e.target.value as "easy" | "medium" | "hard")} aria-label="题目难度">
                    <option value="easy">简单</option><option value="medium">中等</option><option value="hard">困难</option>
                </select>
                <textarea aria-label="标签" placeholder="标签：每行一个" className="min-h-20 rounded-lg border px-3 py-2 text-sm" value={formTags} onChange={(e) => setFormTags(e.target.value)} />
                <textarea aria-label="评分维度" placeholder="评分维度：每行一个" className="min-h-20 rounded-lg border px-3 py-2 text-sm" value={formScoringDimensions} onChange={(e) => setFormScoringDimensions(e.target.value)} />
                <input type="text" placeholder="部门" className="h-10 rounded-lg border px-3 text-sm" value={formDepartment} onChange={(e) => setFormDepartment(e.target.value)} />
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={formSafetyFlagged} onChange={(e) => setFormSafetyFlagged(e.target.checked)} />安全标记</label>
                <JsonEditorWithValidation label="评分标准 JSON" value={formScoringCriteria} onChange={setFormScoringCriteria} rows={4} className="md:col-span-2" isValid={scoringCriteriaValidation.ok} validationMessage={scoringCriteriaValidation.message} helpText="必须是 JSON 对象；留空会提交空对象。" />
            </div>
            <div className="flex gap-2">
                <Button className="rounded-full" onClick={() => void handleSubmit()} disabled={submitting}>{submitting ? "保存中..." : mode === "edit" ? "更新" : "创建"}</Button>
                <Button variant="outline" className="rounded-full" onClick={onCancel}>取消</Button>
            </div>
        </GlassCard>
    );
}
