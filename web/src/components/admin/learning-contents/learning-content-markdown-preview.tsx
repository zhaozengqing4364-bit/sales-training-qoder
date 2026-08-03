"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { markdownComponents } from "@/components/sales-trainer/coo-markdown-components";

interface LearningContentMarkdownPreviewProps {
    content: string;
}

export default function LearningContentMarkdownPreview({
    content,
}: LearningContentMarkdownPreviewProps) {
    return (
        <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={markdownComponents}
        >
            {content}
        </ReactMarkdown>
    );
}
