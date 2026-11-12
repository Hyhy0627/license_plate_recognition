"use client";
/* eslint-disable @next/next/no-img-element -- Uploaded images and API crops use their original local URLs. */

import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { AlertCircle, ArrowDown, ArrowUpRight, Check, CheckCheck, Copy, FileImage, ImagePlus, LoaderCircle, ScanLine, ShieldCheck, Upload, X, Layers, History, Focus, ArrowRight } from "lucide-react";
import Link from "next/link";
import type { PlateDetectionResponse } from "../types/api";
import { apiFetch } from "../lib/api";
import { RequireAuth } from "../components/auth-provider";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
function imageUrl(url?: string | null) { return url ? url.startsWith("http") ? url : `${API_BASE_URL}${url}` : null; }

export default function Home() {
  return <RequireAuth><RecognitionWorkspace /></RequireAuth>;
}

function RecognitionWorkspace() {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [detectionResponse, setDetectionResponse] = useState<PlateDetectionResponse | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [copied, setCopied] = useState(false);
  const [annotated, setAnnotated] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const requestRef = useRef<AbortController | null>(null);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const results = detectionResponse?.results ?? [];
  const activeResult = results[activeIndex];
  const cropUrl = imageUrl(activeResult?.cropped_image_url);
  const annotatedUrl = imageUrl(activeResult?.annotated_image_url);
  const confidence = activeResult ? Math.max(0, Math.min(100, activeResult.confidence * 100)) : 0;

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);
  useEffect(() => () => { requestRef.current?.abort(); if (copyTimer.current) clearTimeout(copyTimer.current); }, []);

  async function processImage(file: File) {
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) { setErrorMessage("Hãy chọn ảnh JPG, PNG hoặc WEBP."); return; }
    if (file.size > 10 * 1024 * 1024) { setErrorMessage("Ảnh quá lớn. Vui lòng chọn ảnh dưới 10 MB."); return; }
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setSelectedFile(file); setPreviewUrl(URL.createObjectURL(file)); setDetectionResponse(null);
    setActiveIndex(0); setCopied(false); setAnnotated(true); setErrorMessage(null); setIsLoading(true);
    try {
      const form = new FormData(); form.append("file", file);
      const response = await apiFetch("/api/license-plates/detect", { method: "POST", body: form, signal: controller.signal });
      if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(typeof data.detail === "string" ? data.detail : "Chưa thể phân tích ảnh. Vui lòng thử lại."); }
      const data: PlateDetectionResponse = await response.json();
      if (!controller.signal.aborted) setDetectionResponse(data);
    } catch (error) {
      if (!controller.signal.aborted) setErrorMessage(error instanceof TypeError ? "Không thể kết nối máy chủ nhận diện. Hãy kiểm tra kết nối và thử lại." : error instanceof Error ? error.message : "Không thể phân tích ảnh.");
    } finally { if (!controller.signal.aborted) setIsLoading(false); }
  }
  function onFileChange(event: ChangeEvent<HTMLInputElement>) { const file = event.target.files?.[0]; if (file) void processImage(file); event.target.value = ""; }
  function onDrop(event: DragEvent<HTMLDivElement>) { event.preventDefault(); setIsDragging(false); const file = event.dataTransfer.files?.[0]; if (file) void processImage(file); }
  async function copyPlate() {
    if (!activeResult) return;
    try { await navigator.clipboard.writeText(activeResult.plate_number); setCopied(true); if (copyTimer.current) clearTimeout(copyTimer.current); copyTimer.current = setTimeout(() => setCopied(false), 2000); }
    catch { setErrorMessage("Không thể sao chép tự động. Bạn có thể chọn và sao chép trực tiếp biển số."); }
  }
  function reset() { requestRef.current?.abort(); setPreviewUrl(null); setSelectedFile(null); setDetectionResponse(null); setIsLoading(false); setErrorMessage(null); }

  return <div className="recognition-page">
    <section className="page-heading">
      <div><span className="eyebrow"><span /> NHẬN DIỆN THÔNG MINH</span><h1>Mỗi biển số.<br className="mobile-break" /> Một cái nhìn rõ ràng.</h1><p>Tải ảnh phương tiện, nhận diện biển số và lưu lại kết quả trong một không gian.</p></div>
      <Link href="/history" className="history-shortcut"><History size={16} aria-hidden="true" /> Xem lịch sử <ArrowUpRight size={15} aria-hidden="true" /></Link>
    </section>

    <div className="workflow-heading"><div><span className="step-number">01</span><h2>Không gian nhận diện</h2><span className="desktop-label">Ảnh đầu vào → Kết quả phân tích</span></div><span className="supported-label"><Layers size={14} aria-hidden="true" /> Hỗ trợ biển 1 & 2 dòng</span></div>
    {errorMessage && <div className="error-notice" role="alert"><AlertCircle size={19} aria-hidden="true" /><span>{errorMessage}</span>{selectedFile && !isLoading && <button onClick={() => void processImage(selectedFile)}>Thử lại</button>}<button onClick={() => setErrorMessage(null)} aria-label="Đóng thông báo lỗi"><X size={16} aria-hidden="true" /></button></div>}
    {detectionResponse?.warnings?.map(warning => <div key={warning} className="error-notice" role="status"><AlertCircle size={19} aria-hidden="true" /><span>{warning}</span></div>)}
    {detectionResponse && results.length === 0 && <p className="mb-4 text-xs text-slate-500">Đã xử lý trong {(detectionResponse.processing_time_ms / 1000).toFixed(2)} giây. Chưa đọc được biển số đủ tin cậy.</p>}
    <section className="recognition-grid">
      <div className="upload-panel">
        <div className="panel-heading"><div><FileImage size={17} aria-hidden="true" /><h3>Ảnh phương tiện</h3></div><span className="panel-meta">{selectedFile ? `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB` : "JPG, PNG, WEBP"}</span></div>
        <div className={`image-stage ${previewUrl ? "has-image" : ""} ${isDragging ? "is-dragging" : ""}`} onDragOver={event => { event.preventDefault(); setIsDragging(true); }} onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setIsDragging(false); }} onDrop={onDrop}>
          {previewUrl ? <>
            <img className="vehicle-image" src={annotated && annotatedUrl ? annotatedUrl : previewUrl} alt="Ảnh phương tiện được chọn để nhận diện biển số" />
            <div className="image-actions"><button disabled={isLoading} onClick={() => fileInputRef.current?.click()}><ImagePlus size={14} aria-hidden="true" /> Thay ảnh</button><button onClick={reset} aria-label="Xóa ảnh và bắt đầu lại"><X size={16} aria-hidden="true" /></button></div>
            {annotatedUrl && !isLoading && <button className="annotation-toggle" onClick={() => setAnnotated(!annotated)} aria-pressed={annotated}><Focus size={14} aria-hidden="true" /> {annotated ? "Đang hiện vùng nhận diện" : "Đang xem ảnh gốc"}</button>}
          </> : <div className="upload-empty">
            <div className="scan-illustration" aria-hidden="true"><span className="corner top-left" /><span className="corner top-right" /><span className="corner bottom-left" /><span className="corner bottom-right" /><div className="illustrated-plate"><ScanLine size={32} /><div><i /><i /><i /></div></div><span className="scan-beam" /></div>
            <span className="canvas-tag">IMAGE RECOGNITION</span><h3>Bắt đầu từ một hình ảnh</h3><p>Kéo thả ảnh phương tiện vào đây<br />hoặc chọn ảnh từ thiết bị của bạn.</p>
            <button className="primary-button upload-cta" onClick={() => fileInputRef.current?.click()}><Upload size={17} aria-hidden="true" /> Chọn hình ảnh <ArrowRight size={16} aria-hidden="true" /></button><span className="upload-limit">JPG, PNG hoặc WEBP · Tối đa 10 MB</span>
          </div>}
          {isLoading && <div className="analysis-overlay" role="status"><div className="analysis-spinner"><LoaderCircle size={30} aria-hidden="true" /></div><h3>Đang đọc biển số…</h3><p>Hệ thống đang phát hiện vùng biển và phân tích ký tự.</p><span className="loading-track"><span /></span></div>}
          {isDragging && <div className="drop-overlay"><Upload size={36} aria-hidden="true" /><strong>Thả ảnh để bắt đầu nhận diện</strong></div>}
        </div>
        <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp" onChange={onFileChange} className="sr-only" aria-label="Chọn ảnh phương tiện" />
        <div className="upload-footer"><span><ShieldCheck size={14} aria-hidden="true" />{selectedFile ? selectedFile.name : "Ảnh rõ nét giúp kết quả chính xác hơn"}</span><span>{detectionResponse ? `${results.length} biển được nhận diện` : "Tự động phân tích sau khi tải"}</span></div>
      </div>

      <aside className="results-panel" aria-label="Kết quả nhận diện">
        <div className="panel-heading"><div><ScanLine size={17} aria-hidden="true" /><h3>Kết quả nhận diện</h3></div><span className={`result-status ${activeResult ? "done" : ""}`}><span />{isLoading ? "Đang phân tích" : detectionResponse ? "Hoàn tất" : "Chờ hình ảnh"}</span></div>
        <div className="result-content" aria-live="polite" aria-busy={isLoading}>
          {results.length > 1 && <div className="result-tabs" aria-label="Chọn biển số">{results.map((result, index) => <button key={`${result.plate_number}-${index}`} className={activeIndex === index ? "active" : ""} aria-pressed={activeIndex === index} onClick={() => { setActiveIndex(index); setCopied(false); }}>Biển {String(index + 1).padStart(2, "0")}</button>)}</div>}
          {activeResult ? <>
            <div className="plate-label"><span>BIỂN SỐ NHẬN DIỆN</span><button className="icon-button" onClick={copyPlate} aria-label={copied ? "Đã sao chép biển số" : "Sao chép biển số"}>{copied ? <CheckCheck size={16} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />}</button></div>
            <div className="license-plate">{activeResult.plate_number}</div>
            <span className={`validation-label ${activeResult.is_valid_format ? "valid" : ""}`}><ShieldCheck size={14} aria-hidden="true" />{activeResult.is_valid_format ? "Khớp cấu trúc biển số · Cần đối chiếu ảnh" : "Cần kiểm tra lại kết quả"}</span>
            <div className="confidence-section"><div><span>Độ tin cậy nhận diện</span><strong>{confidence.toFixed(1)}<small>%</small></strong></div><div className="confidence-track"><span style={{ width: `${confidence}%` }} /></div></div>
            <div className="result-details"><div><span>Thời gian xử lý</span><strong>{((detectionResponse?.processing_time_ms ?? 0) / 1000).toFixed(2)} giây</strong></div><div><span>Loại biển số</span><strong>{activeResult.plate_type === "two_line" ? "Biển 2 dòng" : activeResult.plate_type === "one_line" ? "Biển 1 dòng" : "Chưa xác định"}</strong></div></div>
            <div className="crop-heading"><span>Vùng biển số đã tách</span>{cropUrl && <a href={cropUrl} target="_blank" rel="noreferrer">Mở ảnh <ArrowUpRight size={13} aria-hidden="true" /></a>}</div><div className="crop-preview">{cropUrl ? <img src={cropUrl} alt={`Vùng biển số ${activeResult.plate_number}`} /> : <span>Không có ảnh biển số</span>}</div>
            <Link href="/history" className="saved-note"><Check size={14} aria-hidden="true" /> Kết quả đã được lưu trong lịch sử <ArrowUpRight size={13} aria-hidden="true" /></Link>
          </> : <div className="result-empty"><div className="empty-result-symbol"><ScanLine size={30} aria-hidden="true" /><span className="empty-result-line" /></div><h3>{isLoading ? "Kết quả đang được chuẩn bị" : detectionResponse ? "Chưa đọc được biển số" : "Sẵn sàng cho ảnh đầu tiên"}</h3><p>{isLoading ? "Biển số, độ tin cậy và ảnh đã tách sẽ xuất hiện ngay tại đây." : detectionResponse ? "Hãy thử ảnh chụp gần hơn, đủ sáng và nhìn rõ toàn bộ biển số." : "Tải một ảnh phương tiện để xem biển số, độ tin cậy và thông tin phân tích."}</p><div className="empty-data-rows"><span>Biển số nhận diện <i>—</i></span><span>Độ tin cậy <i>—</i></span><span>Thời gian xử lý <i>—</i></span></div>{detectionResponse && <button className="secondary-button" onClick={() => fileInputRef.current?.click()}><ImagePlus size={16} aria-hidden="true" /> Chọn ảnh khác</button>}</div>}
        </div>
      </aside>
    </section>
    <section className="how-it-works" aria-label="Hướng dẫn nhận diện"><div className="guide-intro"><span className="eyebrow">ĐƠN GIẢN TRONG 3 BƯỚC</span><h2>Từ hình ảnh<br />đến thông tin.</h2></div>{[{ number: "01", icon: Upload, title: "Tải ảnh phương tiện", text: "Chọn ảnh rõ nét, nhìn thấy toàn bộ biển số." }, { number: "02", icon: Focus, title: "Tự động nhận diện", text: "Hệ thống tìm vùng biển và đọc các ký tự." }, { number: "03", icon: History, title: "Xem và lưu kết quả", text: "Đối chiếu biển số và tra cứu lại trong lịch sử." }].map(({ number, icon: Icon, title, text }) => <div className="guide-step" key={number}><div><Icon size={20} aria-hidden="true" /><span>{number}</span></div><h3>{title}</h3><p>{text}</p></div>)}</section>
    <div className="quality-tip"><ShieldCheck size={17} aria-hidden="true" /><p><strong>Mẹo cho kết quả tốt hơn</strong> Dùng ảnh đủ sáng, hạn chế rung mờ và tránh che khuất ký tự trên biển số.</p><ArrowDown size={16} aria-hidden="true" /></div>
  </div>;
}
