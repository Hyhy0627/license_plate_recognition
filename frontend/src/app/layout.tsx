import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ALPR System - Hệ Thống Nhận Diện Biển Số Xe Tự Động",
  description: "Automatic License Plate Recognition System for Vietnamese License Plates",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi" className="dark">
      <body className={`${inter.className} min-h-screen bg-slate-950 text-slate-100 antialiased selection:bg-blue-600 selection:text-white`}>
        {/* Navigation Bar */}
        <header className="sticky top-0 z-50 border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 shadow-lg shadow-blue-500/20">
                <span className="text-xl font-black tracking-wider text-white">VN</span>
              </div>
              <div>
                <h1 className="text-base font-bold tracking-tight text-white sm:text-lg">
                  ALPR Vietnam System
                </h1>
                <p className="text-xs text-slate-400">
                  Nhận diện & Nhận dạng biển số xe tự động
                </p>
              </div>
            </div>

            <nav className="flex items-center gap-1 sm:gap-4">
              <a
                href="/"
                className="rounded-lg px-3 py-1.5 text-sm font-medium text-blue-400 bg-blue-500/10 border border-blue-500/20 transition hover:bg-blue-500/20"
              >
                Nhận Diện
              </a>
              <a
                href="/history"
                className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-300 transition hover:bg-slate-800 hover:text-white"
              >
                Lịch Sử
              </a>
              <a
                href="http://localhost:8000/docs"
                target="_blank"
                rel="noreferrer"
                className="hidden rounded-lg px-3 py-1.5 text-sm font-medium text-slate-400 transition hover:bg-slate-800 hover:text-white sm:inline-block"
              >
                FastAPI Docs
              </a>
              <div className="ml-2 flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-400">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                API v1.0
              </div>
            </nav>
          </div>
        </header>

        {/* Main Content Area */}
        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          {children}
        </main>
      </body>
    </html>
  );
}
