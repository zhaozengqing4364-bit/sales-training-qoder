import type { Metadata } from "next";
import { AppProviders } from "@/components/providers/app-providers";
import { ToastProvider } from "@/components/ui/toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI 智能练习平台",
  description: "销售教练高保真原型",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body
        className="antialiased bg-slate-50 text-slate-900 relative min-h-screen overflow-x-hidden selection:bg-blue-100 selection:text-blue-900"
      >
        <AppProviders>
          <ToastProvider>
            {/* Airy Soft Cloud Background */}
            <div className="fixed inset-0 z-[-1] overflow-hidden pointer-events-none">
              {/* Gradient Orbs */}
              <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-blue-100/40 rounded-full blur-[120px] mix-blend-multiply animate-pulse" style={{ animationDuration: '8s' }} />
              <div className="absolute top-[20%] right-[-10%] w-[40%] h-[40%] bg-purple-100/40 rounded-full blur-[100px] mix-blend-multiply animate-pulse" style={{ animationDuration: '10s', animationDelay: '2s' }} />
              <div className="absolute bottom-[-10%] left-[20%] w-[40%] h-[40%] bg-emerald-50/40 rounded-full blur-[100px] mix-blend-multiply animate-pulse" style={{ animationDuration: '12s', animationDelay: '4s' }} />

              {/* Noise Texture Overlay */}
              <div className="absolute inset-0 opacity-[0.015] bg-[url('/noise.svg')] brightness-100 contrast-150" />
            </div>
            {children}
          </ToastProvider>
        </AppProviders>
      </body>
    </html>
  );
}
