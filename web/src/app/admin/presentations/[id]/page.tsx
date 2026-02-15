"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api/client";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    ArrowLeft,
    Presentation,
    FileText,
    AlertCircle,
    CheckCircle,
    Plus,
    Trash2,
    Loader2,
    Target,
    Ban
} from "lucide-react";
import Link from "next/link";

function PresentationThumbnail({
    presentationId,
    pageNumber,
    alt,
}: {
    presentationId: string;
    pageNumber: number;
    alt: string;
}) {
    const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);

    useEffect(() => {
        let active = true;
        let localObjectUrl: string | null = null;

        const loadThumbnail = async () => {
            try {
                const blob = await api.presentations.getThumbnailBlob(
                    presentationId,
                    pageNumber,
                );
                if (!active) {
                    return;
                }
                localObjectUrl = URL.createObjectURL(blob);
                setThumbnailUrl(localObjectUrl);
            } catch {
                if (active) {
                    setThumbnailUrl(null);
                }
            }
        };

        void loadThumbnail();

        return () => {
            active = false;
            if (localObjectUrl) {
                URL.revokeObjectURL(localObjectUrl);
            }
        };
    }, [presentationId, pageNumber]);

    if (!thumbnailUrl) {
        return <Presentation className="w-8 h-8 text-slate-300" />;
    }

    return (
        <img
            src={thumbnailUrl}
            alt={alt}
            className="w-full h-full object-cover rounded-lg"
        />
    );
}

// Types
interface PageDetail {
    page_id: string;
    page_number: number;
    image_url: string;
    extracted_text?: string;
}

interface TalkingPoint {
    point_id: string;
    description: string;
    is_ai_generated: boolean;
    confirmed_by_admin: boolean;
}

interface ForbiddenWord {
    word_id: string;
    phrase: string;
    suggested_alternative?: string;
    page_id?: string;
}

interface PresentationDetail {
    presentation_id: string;
    title: string;
    status: "processing" | "ready" | "error";
    file_size_bytes: number;
    page_count: number;
    pages: PageDetail[];
    created_at: string;
}

export default function PresentationDetailPage() {
    const params = useParams();
    const presentationId = params.id as string;
    const toast = useToast();

    const [presentation, setPresentation] = useState<PresentationDetail | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [activeTab, setActiveTab] = useState("pages");

    // Talking points state
    const [talkingPoints, setTalkingPoints] = useState<TalkingPoint[]>([]);
    const [selectedPage, setSelectedPage] = useState<number>(1);
    const [newPointDescription, setNewPointDescription] = useState("");
    const [isAddingPoint, setIsAddingPoint] = useState(false);

    // Forbidden words state
    const [forbiddenWords, setForbiddenWords] = useState<ForbiddenWord[]>([]);
    const [newForbiddenWord, setNewForbiddenWord] = useState("");
    const [newAlternative, setNewAlternative] = useState("");
    const [isAddingWord, setIsAddingWord] = useState(false);

    const loadPresentation = async () => {
        setIsLoading(true);
        try {
            const data = await api.presentations.get(presentationId);
            setPresentation(data);
        } catch (err) {
            console.error("Failed to load presentation:", err);
            toast.error("加载PPT详情失败");
        } finally {
            setIsLoading(false);
        }
    };

    const loadTalkingPoints = async () => {
        try {
            const data = await api.presentations.getTalkingPoints(presentationId, selectedPage);
            setTalkingPoints(data || []);
        } catch (err) {
            console.error("Failed to load talking points:", err);
        }
    };

    const loadForbiddenWords = async () => {
        try {
            const data = await api.presentations.getForbiddenWords(presentationId);
            setForbiddenWords(data || []);
        } catch (err) {
            console.error("Failed to load forbidden words:", err);
        }
    };

    useEffect(() => {
        if (presentationId) {
            loadPresentation();
            loadForbiddenWords();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [presentationId]);

    useEffect(() => {
        if (presentationId && selectedPage) {
            loadTalkingPoints();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [presentationId, selectedPage]);

    const handleAddTalkingPoint = async () => {
        if (!newPointDescription.trim()) {
            toast.error("请输入要点描述");
            return;
        }

        setIsAddingPoint(true);
        try {
            await api.presentations.addTalkingPoint(presentationId, selectedPage, {
                description: newPointDescription
            });
            setNewPointDescription("");
            toast.success("要点添加成功");
            loadTalkingPoints();
        } catch (err) {
            console.error("Failed to add talking point:", err);
            toast.error("添加要点失败");
        } finally {
            setIsAddingPoint(false);
        }
    };

    const handleDeleteTalkingPoint = async (pointId: string) => {
        try {
            await api.presentations.deleteTalkingPoint(presentationId, pointId);
            toast.success("要点已删除");
            loadTalkingPoints();
        } catch (err) {
            console.error("Failed to delete talking point:", err);
            toast.error("删除要点失败");
        }
    };

    const handleAddForbiddenWord = async () => {
        if (!newForbiddenWord.trim()) {
            toast.error("请输入禁忌词");
            return;
        }

        setIsAddingWord(true);
        try {
            await api.presentations.addForbiddenWord(presentationId, {
                phrase: newForbiddenWord,
                suggested_alternative: newAlternative || undefined
            });
            setNewForbiddenWord("");
            setNewAlternative("");
            toast.success("禁忌词添加成功");
            loadForbiddenWords();
        } catch (err) {
            console.error("Failed to add forbidden word:", err);
            toast.error("添加禁忌词失败");
        } finally {
            setIsAddingWord(false);
        }
    };

    const handleDeleteForbiddenWord = async (wordId: string) => {
        try {
            await api.presentations.deleteForbiddenWord(presentationId, wordId);
            toast.success("禁忌词已删除");
            loadForbiddenWords();
        } catch (err) {
            console.error("Failed to delete forbidden word:", err);
            toast.error("删除禁忌词失败");
        }
    };

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "ready":
                return (
                    <Badge variant="green" className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100">
                        <CheckCircle className="w-3 h-3 mr-1" />
                        可用
                    </Badge>
                );
            case "processing":
                return (
                    <Badge variant="blue" className="bg-blue-100 text-blue-700 hover:bg-blue-100">
                        <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                        处理中
                    </Badge>
                );
            case "error":
            case "failed":
                return (
                    <Badge variant="red" className="bg-red-100 text-red-700 hover:bg-red-100">
                        <AlertCircle className="w-3 h-3 mr-1" />
                        错误
                    </Badge>
                );
            default:
                return <Badge>{status}</Badge>;
        }
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-[400px]">
                <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
            </div>
        );
    }

    if (!presentation) {
        return (
            <div className="text-center py-16">
                <AlertCircle className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                <h2 className="text-xl font-bold text-slate-900 mb-2">PPT未找到</h2>
                <p className="text-slate-500 mb-4">该PPT可能已被删除或不存在</p>
                <Link href="/admin/presentations">
                    <Button variant="outline">返回列表</Button>
                </Link>
            </div>
        );
    }

    const selectedPageDetail = presentation.pages?.find((page) => page.page_number === selectedPage);

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                    <Link href="/admin/presentations">
                        <Button variant="ghost" size="icon" className="rounded-full">
                            <ArrowLeft className="w-5 h-5" />
                        </Button>
                    </Link>
                    <div>
                        <div className="flex items-center gap-3">
                            <h1 className="text-2xl font-black text-slate-900 tracking-tight">{presentation.title}</h1>
                            {getStatusBadge(presentation.status)}
                        </div>
                        <p className="text-slate-500 text-sm mt-1">
                            {presentation.page_count} 页 · {(presentation.file_size_bytes / 1024 / 1024).toFixed(2)} MB
                        </p>
                    </div>
                </div>
            </div>

            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
                <TabsList className="bg-slate-100 p-1 rounded-full">
                    <TabsTrigger value="pages" className="rounded-full px-6">
                        <FileText className="w-4 h-4 mr-2" />
                        页面管理
                    </TabsTrigger>
                    <TabsTrigger value="talking-points" className="rounded-full px-6">
                        <Target className="w-4 h-4 mr-2" />
                        要点配置
                    </TabsTrigger>
                    <TabsTrigger value="forbidden-words" className="rounded-full px-6">
                        <Ban className="w-4 h-4 mr-2" />
                        禁忌词
                    </TabsTrigger>
                </TabsList>

                {/* Pages Tab */}
                <TabsContent value="pages" className="space-y-4">
                    <GlassCard className="p-6">
                        <h3 className="text-lg font-bold text-slate-900 mb-4">页面列表</h3>
                        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                            {presentation.pages?.map((page) => (
                                <div
                                    key={page.page_id}
                                    className={`border rounded-xl p-3 cursor-pointer transition-all ${
                                        selectedPage === page.page_number
                                            ? "border-blue-500 bg-blue-50"
                                            : "border-slate-200 hover:border-slate-300"
                                    }`}
                                    onClick={() => setSelectedPage(page.page_number)}
                                >
                                    <div className="aspect-video bg-slate-100 rounded-lg mb-2 flex items-center justify-center">
                                        <PresentationThumbnail
                                            presentationId={presentationId}
                                            pageNumber={page.page_number}
                                            alt={`Page ${page.page_number}`}
                                        />
                                    </div>
                                    <p className="text-center text-sm font-medium text-slate-700">
                                        第 {page.page_number} 页
                                    </p>
                                </div>
                            ))}
                        </div>
                    </GlassCard>

                    <GlassCard className="p-6">
                        <h3 className="text-lg font-bold text-slate-900 mb-2">
                            第 {selectedPage} 页内容预览
                        </h3>
                        <p className="text-sm text-slate-500 mb-4">
                            基于后端解析结果展示当前页面的文本内容，可用于核对演练上下文。
                        </p>
                        {selectedPageDetail?.extracted_text ? (
                            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                                <p className="text-sm text-slate-700 whitespace-pre-wrap break-words leading-6">
                                    {selectedPageDetail.extracted_text}
                                </p>
                            </div>
                        ) : (
                            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                                当前页面暂无可预览内容。请检查该页是否解析成功，或在后台补充要点配置。
                            </div>
                        )}
                    </GlassCard>
                </TabsContent>

                {/* Talking Points Tab */}
                <TabsContent value="talking-points" className="space-y-4">
                    <GlassCard className="p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-bold text-slate-900">要点配置</h3>
                            <select
                                value={selectedPage}
                                onChange={(e) => setSelectedPage(Number(e.target.value))}
                                className="h-9 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                            >
                                {presentation.pages?.map((page) => (
                                    <option key={page.page_id} value={page.page_number}>
                                        第 {page.page_number} 页
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Add New Point */}
                        <div className="bg-slate-50 rounded-xl p-4 mb-6">
                            <h4 className="text-sm font-bold text-slate-700 mb-3">添加新要点</h4>
                            <div className="flex gap-3">
                                <input
                                    type="text"
                                    placeholder="输入要点描述..."
                                    value={newPointDescription}
                                    onChange={(e) => setNewPointDescription(e.target.value)}
                                    className="flex-1 h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                                />
                                <Button
                                    onClick={handleAddTalkingPoint}
                                    disabled={isAddingPoint}
                                    className="rounded-full bg-slate-900 text-white"
                                >
                                    {isAddingPoint ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <Plus className="w-4 h-4 mr-1" />
                                    )}
                                    添加
                                </Button>
                            </div>
                        </div>

                        {/* Points List */}
                        <div className="space-y-3">
                            {talkingPoints.length === 0 ? (
                                <div className="text-center py-8 text-slate-500">
                                    <Target className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                                    <p>该页面暂无要点配置</p>
                                    <p className="text-sm">添加上面要点以指导学员演讲</p>
                                </div>
                            ) : (
                                talkingPoints.map((point) => (
                                    <div
                                        key={point.point_id}
                                        className="flex items-center justify-between p-4 border border-slate-200 rounded-xl hover:border-slate-300 transition-colors"
                                    >
                                        <div className="flex items-start gap-3">
                                            <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                                                <CheckCircle className="w-3.5 h-3.5 text-blue-600" />
                                            </div>
                                            <div>
                                                <p className="text-slate-900">{point.description}</p>
                                                {point.is_ai_generated && (
                                                    <Badge variant="secondary" className="text-xs mt-1">
                                                        AI生成
                                                    </Badge>
                                                )}
                                            </div>
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-8 w-8 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-full"
                                            onClick={() => handleDeleteTalkingPoint(point.point_id)}
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </Button>
                                    </div>
                                ))
                            )}
                        </div>
                    </GlassCard>
                </TabsContent>

                {/* Forbidden Words Tab */}
                <TabsContent value="forbidden-words" className="space-y-4">
                    <GlassCard className="p-6">
                        <h3 className="text-lg font-bold text-slate-900 mb-4">禁忌词配置</h3>

                        {/* Add New Word */}
                        <div className="bg-slate-50 rounded-xl p-4 mb-6">
                            <h4 className="text-sm font-bold text-slate-700 mb-3">添加禁忌词</h4>
                            <div className="flex gap-3">
                                <input
                                    type="text"
                                    placeholder="输入禁忌词..."
                                    value={newForbiddenWord}
                                    onChange={(e) => setNewForbiddenWord(e.target.value)}
                                    className="flex-1 h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                                />
                                <input
                                    type="text"
                                    placeholder="建议替代词（可选）"
                                    value={newAlternative}
                                    onChange={(e) => setNewAlternative(e.target.value)}
                                    className="flex-1 h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                                />
                                <Button
                                    onClick={handleAddForbiddenWord}
                                    disabled={isAddingWord}
                                    className="rounded-full bg-slate-900 text-white"
                                >
                                    {isAddingWord ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <Plus className="w-4 h-4 mr-1" />
                                    )}
                                    添加
                                </Button>
                            </div>
                        </div>

                        {/* Words List */}
                        <div className="space-y-3">
                            {forbiddenWords.length === 0 ? (
                                <div className="text-center py-8 text-slate-500">
                                    <Ban className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                                    <p>暂无禁忌词配置</p>
                                    <p className="text-sm">添加禁忌词以提醒学员避免使用</p>
                                </div>
                            ) : (
                                forbiddenWords.map((word) => (
                                    <div
                                        key={word.word_id}
                                        className="flex items-center justify-between p-4 border border-slate-200 rounded-xl hover:border-slate-300 transition-colors"
                                    >
                                        <div className="flex items-center gap-3">
                                            <div className="w-6 h-6 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
                                                <Ban className="w-3.5 h-3.5 text-red-600" />
                                            </div>
                                            <div>
                                                <p className="text-slate-900 font-medium">{word.phrase}</p>
                                                {word.suggested_alternative && (
                                                    <p className="text-sm text-slate-500">
                                                        建议替代: {word.suggested_alternative}
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-8 w-8 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-full"
                                            onClick={() => handleDeleteForbiddenWord(word.word_id)}
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </Button>
                                    </div>
                                ))
                            )}
                        </div>
                    </GlassCard>
                </TabsContent>
            </Tabs>
        </div>
    );
}
