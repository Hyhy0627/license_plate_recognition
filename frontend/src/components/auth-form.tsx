"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Image from "next/image";
import Link from "next/link";
import { ArrowRight, Check, Eye, EyeOff, Lock, Mail, ScanLine, ShieldCheck } from "lucide-react";
import { apiError, apiFetch } from "../lib/api";
import { useAuth } from "./auth-provider";

type AuthMode = "login" | "register";

export default function AuthForm({ mode }: { mode: AuthMode }) {
  const registering = mode === "register";
  const { status } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const errorRef = useRef<HTMLDivElement>(null);

  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);
  useEffect(() => { if (status === "authenticated") window.location.replace("/"); }, [status]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (registering && password !== confirmation) {
      setError("Mật khẩu nhập lại chưa khớp.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      const response = await apiFetch(registering ? "/api/auth/register" : "/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password, ...(registering ? { name: name.trim() } : {}) }),
      });
      if (!response.ok) throw new Error(await apiError(response, "Thông tin chưa hợp lệ. Vui lòng kiểm tra và thử lại."));

      // Reload once so the auth provider and protected pages read the new cookie.
      const next = new URLSearchParams(window.location.search).get("next");
      window.location.replace(next === "/history" ? "/history" : "/");
    } catch (reason) {
      setError(reason instanceof TypeError ? "Không kết nối được máy chủ. Vui lòng thử lại sau." : reason instanceof Error ? reason.message : "Có lỗi xảy ra. Vui lòng thử lại.");
      setBusy(false);
    }
  }

  return (
    <div className="ps-auth-page h-screen overflow-hidden bg-[#111C28]" data-mode={mode}>
      <section className="ps-story-panel" aria-label="Giới thiệu PlateSight">
        <div className="ps-story-inner">
          <Link href="/" className="ps-brand flex shrink-0 items-center gap-3" aria-label="PlateSight — Trang chủ">
            <span className="ps-brand-mark grid h-11 w-11 place-items-center rounded-xl text-white"><ScanLine size={23} aria-hidden="true" /></span>
            <span className="leading-tight"><strong className="block text-[19px] tracking-tight text-[#F0F6FC]">PlateSight</strong><small className="mt-0.5 block text-[9px] font-bold tracking-[.18em] text-[#8B9CAE]">NHẬN DIỆN BIỂN SỐ</small></span>
          </Link>

          <div className="ps-story-copy">
            <p className="mb-3 text-[10px] font-bold tracking-[.2em] text-[#35C6D9]">HÀNH TRÌNH NHẬN DIỆN BIỂN SỐ</p>
            <h2 className="ps-story-title max-w-[580px] font-bold text-[#F0F6FC]">Mỗi hành trình<br />đều có <span className="text-[#F4B77D]">dấu vết.</span></h2>
            <p className="ps-story-description mt-4 max-w-[450px] text-[14px] leading-7 text-[#8B9CAE]">Quét biển số, lưu trữ kết quả và tra cứu lịch sử trong không gian của riêng bạn.</p>
          </div>

          {/* The car image is shared with the existing pixel art assets. The scan box moves with it. */}
          <div className="ps-pixel-scene" role="img" aria-label="Xe sedan pixel màu xanh ngọc chạy trong thành phố ban đêm; AI đang quét biển số 51K-982.34">
            <div className="ps-star-field" aria-hidden="true" />
            <div className="ps-pixel-moon" aria-hidden="true" />
            <div className="ps-skyline" aria-hidden="true" />
            <div className="ps-skyline ps-skyline-near" aria-hidden="true" />
            <div className="ps-road" aria-hidden="true" />
            <div className="ps-road-glow" aria-hidden="true" />
            <div className="ps-car-unit" aria-hidden="true">
              <Image src="/pixel-auth/pixel-car.svg" alt="" width={320} height={140} priority />
              <span className="ps-car-plate" />
              <span className="ps-scan-box"><span className="ps-scan-tag">[AI_SCAN: 51K-982.34]</span></span>
            </div>
            <span className="ps-scene-caption" aria-hidden="true">PLATESIGHT // LIVE DETECTION</span>
          </div>

          <ul className="ps-benefits" aria-label="Tính năng">
            <li><span className="ps-benefit-check"><Check size={13} aria-hidden="true" /></span>Tải ảnh và xem kết quả nhận diện tức thì</li>
            <li><span className="ps-benefit-check"><Check size={13} aria-hidden="true" /></span>Tra cứu lịch sử &amp; quản lý dữ liệu an toàn</li>
          </ul>
        </div>
      </section>

      <section className="ps-form-panel" aria-label="Tài khoản">
        <div className="ps-auth-card">
          <nav className="ps-auth-tabs" aria-label="Chọn chế độ tài khoản">
            <Link href="/login" aria-current={!registering ? "page" : undefined} onClick={() => setError("")}>Đăng nhập</Link>
            <Link href="/register" aria-current={registering ? "page" : undefined} onClick={() => setError("")}>Đăng ký</Link>
          </nav>

          <div className="ps-card-heading mt-8">
            <p className="text-[10px] font-bold tracking-[.17em] text-[#35C6D9]">{registering ? "BẮT ĐẦU VỚI PLATESIGHT" : "CHÀO MỪNG BẠN TRỞ LẠI"}</p>
            <h1 className="mt-2 text-[33px] font-bold tracking-[-.035em] text-[#F0F6FC]">{registering ? "Tạo tài khoản" : "Đăng nhập"}</h1>
            <p className="mt-2 text-[13px] leading-[1.7] text-[#8B9CAE]">{registering ? "Tạo không gian riêng để lưu và tra cứu kết quả nhận diện." : "Tiếp tục nhận diện và quản lý các phương tiện đã lưu."}</p>
          </div>

          {error && <div className="ps-auth-error" ref={errorRef} tabIndex={-1} role="alert">{error}</div>}
          <form className="ps-form mt-6" onSubmit={submit} aria-busy={busy}>
            {registering && <div className="ps-auth-field">
              <label className="ps-field-label" htmlFor="name">Họ và tên</label>
              <div className="ps-field-wrap"><ScanLine className="ps-field-icon" size={18} aria-hidden="true" /><input className="ps-field-input" id="name" name="name" type="text" autoComplete="name" placeholder="Tên của bạn" minLength={2} maxLength={60} value={name} onChange={event => setName(event.target.value)} required disabled={busy} /></div>
            </div>}
            <div className="ps-auth-field">
              <label className="ps-field-label" htmlFor="email">Email</label>
              <div className="ps-field-wrap"><Mail className="ps-field-icon" size={18} aria-hidden="true" /><input className="ps-field-input" id="email" name="email" type="email" autoComplete="username" placeholder="ban@example.com" maxLength={254} value={email} onChange={event => { setEmail(event.target.value); setError(""); }} required disabled={busy} /></div>
            </div>
            <div className="ps-auth-field">
              <label className="ps-field-label" htmlFor="password">Mật khẩu</label>
              <div className="ps-field-wrap"><Lock className="ps-field-icon" size={18} aria-hidden="true" /><input className="ps-field-input" id="password" name="password" type={visible ? "text" : "password"} autoComplete={registering ? "new-password" : "current-password"} placeholder={registering ? "Ít nhất 8 ký tự" : "Nhập mật khẩu"} minLength={registering ? 8 : 1} maxLength={128} value={password} onChange={event => { setPassword(event.target.value); setError(""); }} required disabled={busy} /><button className="ps-eye-button" type="button" onClick={() => setVisible(current => !current)} aria-label={visible ? "Ẩn mật khẩu" : "Hiện mật khẩu"} aria-pressed={visible} disabled={busy}>{visible ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}</button></div>
            </div>
            {registering && <div className="ps-auth-field">
              <label className="ps-field-label" htmlFor="confirmation">Nhập lại mật khẩu</label>
              <div className="ps-field-wrap"><Lock className="ps-field-icon" size={18} aria-hidden="true" /><input className="ps-field-input" id="confirmation" name="confirmation" type={visible ? "text" : "password"} autoComplete="new-password" placeholder="Nhập lại mật khẩu" minLength={8} maxLength={128} value={confirmation} onChange={event => setConfirmation(event.target.value)} required disabled={busy} /></div>
            </div>}

            {!registering && <div className="ps-forgot-row mt-3 text-right"><button className="ps-text-link text-[12px] font-semibold text-[#35C6D9]" type="button" onClick={() => setError("Chức năng đặt lại mật khẩu chưa được hỗ trợ. Vui lòng liên hệ quản trị viên.")}>Quên mật khẩu?</button></div>}
            <button className="ps-submit-button" type="submit" disabled={busy}><span>{busy ? registering ? "Đang tạo tài khoản…" : "Đang đăng nhập…" : registering ? "Đăng ký" : "Đăng nhập"}</span><ArrowRight size={18} aria-hidden="true" /></button>
          </form>

          <p className="ps-switch-row mt-5 text-center text-[12px] text-[#8B9CAE]">{registering ? "Đã có tài khoản?" : "Chưa có tài khoản?"} <Link className="ml-1 font-semibold text-[#F4B77D] hover:text-[#ffd0a2]" href={registering ? "/login" : "/register"} onClick={() => setError("")}>{registering ? "Đăng nhập" : "Đăng ký ngay"}</Link></p>
          <div className="ps-privacy-note"><ShieldCheck size={17} aria-hidden="true" /><span>Lịch sử nhận diện được lưu riêng theo tài khoản.</span></div>
        </div>
      </section>
    </div>
  );
}
