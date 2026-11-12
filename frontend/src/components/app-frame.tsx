"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ScanLine } from "lucide-react";
import SiteNavigation from "./site-navigation";
import { AccountMenu } from "./auth-provider";
import LiveClock from "./live-clock";

export default function AppFrame({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/login" || pathname === "/register") return <main>{children}</main>;
  return <div className="app-shell">
    <aside className="sidebar">
      <Link href="/" className="brand"><span className="brand-mark"><ScanLine aria-hidden="true" size={23} /></span><span>PlateSight<span className="brand-sub">NHẬN DIỆN BIỂN SỐ</span></span></Link>
      <SiteNavigation />
      <div className="sidebar-note"><span className="mini-label">MỖI HÌNH ẢNH, MỘT KẾT QUẢ</span><p>Nhìn rõ hơn.<br />Quản lý dễ hơn.</p><span>Hệ thống nhận diện biển số Việt Nam</span></div>
    </aside>
    <div className="app-content">
      <header className="topbar">
        <LiveClock />
        <AccountMenu />
      </header>
      <main className="workspace">{children}</main>
      <footer className="workspace-footer"><span>PlateSight — Nhận diện biển số Việt Nam</span><span>Phân tích hình ảnh · Lưu trữ kết quả</span></footer>
    </div>
  </div>;
}
