import type { ReactNode } from "react";

export const markdownComponents = {
    h1: ({ children }: { readonly children?: ReactNode }) => (
        <h1 className="mb-5 mt-8 text-3xl font-black leading-tight text-slate-950 first:mt-0">{children}</h1>
    ),
    h2: ({ children }: { readonly children?: ReactNode }) => (
        <h2 className="mb-4 mt-7 text-2xl font-black leading-snug text-slate-950 first:mt-0">{children}</h2>
    ),
    h3: ({ children }: { readonly children?: ReactNode }) => (
        <h3 className="mb-3 mt-6 text-xl font-bold leading-snug text-slate-900 first:mt-0">{children}</h3>
    ),
    p: ({ children }: { readonly children?: ReactNode }) => (
        <p className="mb-4 text-base leading-8 text-slate-700 last:mb-0">{children}</p>
    ),
    ul: ({ children }: { readonly children?: ReactNode }) => (
        <ul className="mb-4 list-disc space-y-2 pl-6 text-base leading-8 text-slate-700">{children}</ul>
    ),
    ol: ({ children }: { readonly children?: ReactNode }) => (
        <ol className="mb-4 list-decimal space-y-2 pl-6 text-base leading-8 text-slate-700">{children}</ol>
    ),
    li: ({ children }: { readonly children?: ReactNode }) => (
        <li className="leading-relaxed">{children}</li>
    ),
    strong: ({ children }: { readonly children?: ReactNode }) => (
        <strong className="font-semibold text-slate-900">{children}</strong>
    ),
    blockquote: ({ children }: { readonly children?: ReactNode }) => (
        <blockquote className="mb-5 rounded-r-2xl border-l-4 border-slate-300 bg-slate-50 px-5 py-4 text-base leading-8 text-slate-600">
            {children}
        </blockquote>
    ),
    code: ({ children }: { readonly children?: ReactNode }) => (
        <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-800">{children}</code>
    ),
    pre: ({ children }: { readonly children?: ReactNode }) => (
        <pre className="mb-3 overflow-x-auto rounded-xl bg-slate-900 p-4 text-xs text-slate-100">{children}</pre>
    ),
    a: ({ href, children }: { readonly href?: string; readonly children?: ReactNode }) => (
        <a href={href} className="font-medium text-blue-600 underline underline-offset-2 hover:text-blue-800">
            {children}
        </a>
    ),
    hr: () => <hr className="my-8 border-slate-200" />,
    table: ({ children }: { readonly children?: ReactNode }) => (
        <div className="my-6 overflow-x-auto rounded-2xl border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm text-slate-700">
                {children}
            </table>
        </div>
    ),
    th: ({ children }: { readonly children?: ReactNode }) => (
        <th className="bg-slate-50 px-4 py-3 font-bold text-slate-900">{children}</th>
    ),
    td: ({ children }: { readonly children?: ReactNode }) => (
        <td className="border-t border-slate-100 px-4 py-3 align-top leading-6">{children}</td>
    ),
};
