"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { ArrowRight, Check, Eye, EyeOff, LoaderCircle, ScanLine, ShieldCheck } from "lucide-react";
import { apiError, apiFetch } from "../lib/api";
import { useAuth } from "./auth-provider";

export default function AuthForm({ mode }: { mode: "login" | "register" }) {
  const registering = mode === "register";
  const { status } = useAuth();
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const errorRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);
  useEffect(() => { if (status === "authenticated") window.location.replace("/"); }, [status]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password") ?? "");
    if (registering && password !== form.get("confirmation")) { setError("Mật khẩu nhập lại chưa khớp."); return; }
    setBusy(true); setError("");
    try {
      const response = await apiFetch(`/api/auth/${mode}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: String(form.get("email")).trim(), password, ...(registering ? { name: String(form.get("name")).trim() } : {}) }),
      });
      if (!response.ok) throw new Error(await apiError(response, "Thông tin chưa hợp lệ. Vui lòng kiểm tra và thử lại."));
      const destination = new URLSearchParams(window.location.search).get("next");
      window.location.replace(destination === "/history" ? "/history" : "/");
    } catch (reason) {
      setError(reason instanceof TypeError ? "Không kết nối được máy chủ. Vui lòng thử lại sau." : reason instanceof Error ? reason.message : "Có lỗi xảy ra. Vui lòng thử lại.");
      setBusy(false);
    }
  }

  return <div className="auth-page">
    <section className="auth-story" aria-label="Giới thiệu PlateSight">
      <Link href="/" className="brand"><span className="brand-mark"><ScanLine size={24} aria-hidden="true" /></span><span>PlateSight<span className="brand-sub">NHẬN DIỆN BIỂN SỐ</span></span></Link>
      <div className="auth-story-body"><span className="auth-eyebrow">KHÔNG GIAN LÀM VIỆC CỦA BẠN</span><h2>Từ hình ảnh<br />đến <span>thông tin.</span></h2><p>Nhận diện biển số và quản lý những lượt quét của bạn trong cùng một không gian.</p>
        <div className="auth-scan-preview" aria-hidden="true"><div className="auth-scan-corners"><ScanLine size={38} strokeWidth={1.4} /><span>NHẬN DIỆN · LƯU TRỮ · TRA CỨU</span></div></div>
        <ul className="auth-benefits"><li><Check size={16} aria-hidden="true" />Tải ảnh và xem kết quả nhận diện</li><li><Check size={16} aria-hidden="true" />Tra cứu lịch sử riêng của bạn</li></ul>
      </div><p className="auth-story-foot">PlateSight · Hệ thống nhận diện biển số Việt Nam</p>
    </section>
    <section className="auth-form-panel"><div className="auth-form-wrap">
      <div className="auth-mobile-brand"><ScanLine aria-hidden="true" size={24} /><span>PlateSight</span></div>
      <div className="auth-tabs" aria-label="Tài khoản"><Link href="/login" aria-current={!registering ? "page" : undefined}>Đăng nhập</Link><Link href="/register" aria-current={registering ? "page" : undefined}>Đăng ký</Link></div>
      <span className="auth-kicker">{registering ? "BẮT ĐẦU VỚI PLATESIGHT" : "CHÀO MỪNG BẠN TRỞ LẠI"}</span>
      <h1>{registering ? "Tạo tài khoản" : "Đăng nhập"}</h1>
      <p className="auth-intro">{registering ? "Tạo không gian riêng để lưu và tra cứu kết quả nhận diện." : "Tiếp tục nhận diện và xem lại những kết quả đã lưu."}</p>
      {error && <div ref={errorRef} tabIndex={-1} className="auth-error" role="alert">{error}</div>}
      <form onSubmit={submit} className="auth-form" aria-busy={busy}>
        {registering && <label htmlFor="name">Họ và tên<input id="name" name="name" autoComplete="name" minLength={2} maxLength={60} required placeholder="Tên của bạn" disabled={busy} /></label>}
        <label htmlFor="email">Email<input id="email" name="email" type="email" autoComplete="username" maxLength={254} required placeholder="ban@example.com" disabled={busy} /></label>
        <label htmlFor="password">Mật khẩu<span className="password-field"><input id="password" name="password" type={visible ? "text" : "password"} autoComplete={registering ? "new-password" : "current-password"} minLength={registering ? 8 : 1} maxLength={128} required placeholder={registering ? "Ít nhất 8 ký tự" : "Nhập mật khẩu"} aria-describedby={registering ? "password-hint" : undefined} disabled={busy} /><button type="button" onClick={() => setVisible(!visible)} aria-label={visible ? "Ẩn mật khẩu" : "Hiện mật khẩu"} aria-pressed={visible}>{visible ? <EyeOff size={19} aria-hidden="true" /> : <Eye size={19} aria-hidden="true" />}</button></span></label>
        {registering && <><p id="password-hint" className="password-hint">Dùng từ 8 đến 128 ký tự. Bạn có thể dùng trình quản lý mật khẩu.</p><label htmlFor="confirmation">Nhập lại mật khẩu<input id="confirmation" name="confirmation" type={visible ? "text" : "password"} autoComplete="new-password" minLength={8} maxLength={128} required placeholder="Nhập lại mật khẩu của bạn" disabled={busy} /></label></>}
        <button className="auth-submit" type="submit" disabled={busy}>{busy ? <><LoaderCircle size={18} className="animate-spin" aria-hidden="true" />{registering ? "Đang tạo tài khoản…" : "Đang đăng nhập…"}</> : <>{registering ? "Tạo tài khoản" : "Đăng nhập"}<ArrowRight size={18} aria-hidden="true" /></>}</button>
      </form>
      <p className="auth-switch">{registering ? "Đã có tài khoản?" : "Chưa có tài khoản?"} <Link href={registering ? "/login" : "/register"}>{registering ? "Đăng nhập" : "Đăng ký ngay"}</Link></p>
      <div className="auth-privacy"><ShieldCheck size={17} aria-hidden="true" /><span>Lịch sử nhận diện được lưu riêng theo tài khoản.</span></div>
    </div></section>
  </div>;
}
