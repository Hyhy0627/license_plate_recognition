"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ScanLine, History, ArrowUpRight, Radio, ChevronRight } from "lucide-react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function SiteNavigation() {
  const pathname = usePathname();
  const [status, setStatus] = useState("checking");
  useEffect(() => {
    const controller = new AbortController();
    async function check() {
      try {
        const response = await fetch(`${API_BASE_URL}/`, { cache: "no-store", signal: controller.signal });
        const data = await response.json();
        if (!controller.signal.aborted) setStatus(response.ok && data.status === "online" ? "online" : "offline");
      } catch { if (!controller.signal.aborted) setStatus("offline"); }
    }
    void check();
    const interval = window.setInterval(check, 30000);
    return () => { controller.abort(); window.clearInterval(interval); };
  }, []);
  return <>
    <nav className="side-nav" aria-label="Điều hướng chính">
      <span className="nav-caption">KHÔNG GIAN LÀM VIỆC</span>
      {[{ href: "/", label: "Nhận diện biển số", icon: ScanLine }, { href: "/history", label: "Lịch sử nhận diện", icon: History }].map(({ href, label, icon: Icon }) => <Link key={href} href={href} className={`side-link ${pathname === href ? "is-active" : ""}`} aria-current={pathname === href ? "page" : undefined}><Icon size={19} aria-hidden="true" /><span>{label}</span>{pathname === href && <ChevronRight size={14} aria-hidden="true" />}</Link>)}
      <a className="side-link documentation-link" href={`${API_BASE_URL}/docs`} target="_blank" rel="noreferrer"><ArrowUpRight size={19} aria-hidden="true" /><span>Tài liệu API</span></a>
    </nav>
    <div className={`connection-status ${status}`} role="status"><Radio size={16} aria-hidden="true" /><div>{status === "online" ? "Hệ thống sẵn sàng" : status === "offline" ? "Chưa kết nối máy chủ" : "Đang kết nối…"}<small>{status === "online" ? "Có thể bắt đầu nhận diện" : "Trạng thái dịch vụ nhận diện"}</small></div><span className="connection-dot" /></div>
  </>;
}