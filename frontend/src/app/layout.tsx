import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import "./auth.css";
import "./auth-pixel.css";
import "./workspace-pixel.css";
import AppFrame from "../components/app-frame";
import { AuthProvider } from "../components/auth-provider";
import { Suspense } from "react";

const inter = Inter({ subsets: ["latin", "vietnamese"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "ALPR Vietnam | Nhận diện biển số xe",
  description: "Không gian phân tích và quản lý kết quả nhận diện biển số xe Việt Nam.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body className={`${inter.className} ${inter.variable} min-h-screen text-slate-900 antialiased selection:bg-teal-200 selection:text-slate-950`}>
        <AuthProvider><Suspense fallback={<div className="session-state">Đang tải PlateSight…</div>}><AppFrame>{children}</AppFrame></Suspense></AuthProvider>
      </body>
    </html>
  );
}
