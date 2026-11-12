"use client";
/* eslint-disable @next/next/no-img-element -- Uploaded images and API crops use their original local URLs. */

import { useEffect, useRef, useState, type ChangeEvent, type CSSProperties, type DragEvent } from "react";
import { AlertCircle, ArrowUpRight, Check, FileImage, ImagePlus, ScanLine, ShieldCheck, Upload, X, Layers, History, Focus, ArrowRight } from "lucide-react";
import Link from "next/link";
import type { PlateDetectionResponse } from "../types/api";
import { apiFetch } from "../lib/api";
import { RequireAuth } from "../components/auth-provider";
import VietnamPlate from "../components/vietnam-plate";
import PlateIntelligenceCard from "../components/plate-intelligence-card";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
function imageUrl(url?: string | null) { return url ? url.startsWith("http") ? url : `${API_BASE_URL}${url}` : null; }
const pixelCometCount = 2;
const pixelCometDuration = 7.7;
const pixelComets = Array.from({ length: pixelCometCount }, (_, index) => ({
  x: 5 + index * 100 / (pixelCometCount - 1),
  drift: -(125 + (index % 3) * 10),
  duration: pixelCometDuration,
  // Interleave launch lanes while keeping the same spacing on every loop.
  delay: -((index * 3) % pixelCometCount) * pixelCometDuration / pixelCometCount,
  opacity: index === 0 || index === 4 ? .9 : index % 3 === 0 ? .62 : index % 3 === 1 ? .48 : .38,
}));

const SCAN_STEPS = [
  "YOLOv8 đang phát hiện tọa độ biển số xe…",
  "Đang nắn góc nghiêng & tối ưu ảnh cắt…",
  "OCR đang đọc ký tự & đối chiếu quy chuẩn Việt Nam…",
];

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
  const [annotated, setAnnotated] = useState(true);
  const [scanStepIndex, setScanStepIndex] = useState(0);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const requestRef = useRef<AbortController | null>(null);
  const results = detectionResponse?.results ?? [];
  const activeResult = results[activeIndex];
  const cropUrl = imageUrl(activeResult?.cropped_image_url);
  const annotatedUrl = imageUrl(activeResult?.annotated_image_url);
  const confidence = activeResult ? Math.max(0, Math.min(100, activeResult.confidence * 100)) : 0;

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);
  useEffect(() => () => { requestRef.current?.abort(); }, []);

  // Tiến trình các bước AI giả lập mượt mà khi đang xử lý
  useEffect(() => {
    if (!isLoading) return;
    const timer = setInterval(() => {
      setScanStepIndex(prev => (prev + 1) % SCAN_STEPS.length);
    }, 1800);
    return () => clearInterval(timer);
  }, [isLoading]);

  // Hỗ trợ phím tắt Ctrl + V dán ảnh từ clipboard
  useEffect(() => {
    const handlePaste = (event: ClipboardEvent) => {
      const items = event.clipboardData?.items;
      if (!items) return;
      for (const item of items) {
        if (item.type.startsWith("image/")) {
          const file = item.getAsFile();
          if (file) {
            void processImage(file);
            break;
          }
        }
      }
    };
    window.addEventListener("paste", handlePaste);
    return () => window.removeEventListener("paste", handlePaste);
  }, []);

  async function processImage(file: File) {
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) { setErrorMessage("Hãy chọn ảnh JPG, PNG hoặc WEBP."); return; }
    if (file.size > 10 * 1024 * 1024) { setErrorMessage("Ảnh quá lớn. Vui lòng chọn ảnh dưới 10 MB."); return; }
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setSelectedFile(file); setPreviewUrl(URL.createObjectURL(file)); setDetectionResponse(null);
    setActiveIndex(0); setAnnotated(true); setErrorMessage(null); setIsLoading(true);
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
  function reset() { requestRef.current?.abort(); setPreviewUrl(null); setSelectedFile(null); setDetectionResponse(null); setIsLoading(false); setErrorMessage(null); }

  return <div className="recognition-page">
    <section className="page-heading">
      <div><span className="eyebrow"><span /> NHẬN DIỆN THÔNG MINH</span><h1>Mỗi biển số.<br className="mobile-break" /> <span className="heading-accent">Một cái nhìn rõ ràng.</span></h1><p>Tải ảnh phương tiện, nhận diện biển số và lưu lại kết quả trong một không gian.</p></div>
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
            <img className="vehicle-image" src={annotated && annotatedUrl && !isLoading ? annotatedUrl : previewUrl} alt="Ảnh phương tiện được chọn để nhận diện biển số" />

            {!isLoading && <div className="image-actions">
              <button onClick={() => fileInputRef.current?.click()}><ImagePlus size={14} aria-hidden="true" /> Thay ảnh</button>
              <button onClick={reset} aria-label="Xóa ảnh và bắt đầu lại"><X size={16} aria-hidden="true" /></button>
            </div>}

            {annotatedUrl && !isLoading && <button className="annotation-toggle" onClick={() => setAnnotated(!annotated)} aria-pressed={annotated}><Focus size={14} aria-hidden="true" /> {annotated ? "Đang hiện vùng nhận diện" : "Đang xem ảnh gốc"}</button>}

            {/* Phương án C: Tia Laser quét trên ảnh rõ nét & HUD AI động khi đang xử lý */}
            {isLoading && (
              <div className="pixel-laser-scan-overlay" role="status" aria-label="AI đang quét biển số">
                <div className="pixel-scan-beam" />
                <div className="pixel-scan-grid" />
                <span className="pixel-target-bracket tl" />
                <span className="pixel-target-bracket tr" />
                <span className="pixel-target-bracket bl" />
                <span className="pixel-target-bracket br" />
                <div className="pixel-scan-hud">
                  <span className="pixel-hud-pill">
                    <span className="pixel-pulse-dot" /> AI LIVE SCANNING // PLATESIGHT
                  </span>
                  <p className="pixel-hud-step">{SCAN_STEPS[scanStepIndex]}</p>
                </div>
              </div>
            )}
          </> : <div className="upload-empty">
            <div className="pixel-upload-scene" aria-hidden="true">
              <div className="pixel-upload-world">
                <span className="pixel-starfield" />
                <span className="pixel-upload-sun" />
                <span className="pixel-upload-city" />
                <span className="pixel-upload-sidewalk" />
                <span className="pixel-upload-campus">
                  {[0, 1].map(copy => <span key={copy} className="pixel-campus-block">
                    <span className="pixel-campus-tree pixel-campus-tree--left" />
                    <span className="pixel-campus-tree pixel-campus-tree--right" />
                    <span className="pixel-campus-bench" />
                    <span className="pixel-campus-lamp pixel-campus-lamp--left" />
                    <span className="pixel-campus-lamp pixel-campus-lamp--right" />
                  </span>)}
                </span>
                <span className="pixel-upload-road" />
                <span className={`pixel-upload-car ${isLoading ? "is-scanning" : ""}`} />
                <span className="pixel-upload-focus"><ScanLine size={28} /></span>
                <span className="pixel-comets">{pixelComets.map(comet => <i key={comet.x} className="pixel-comet" style={{ left: `${comet.x}%`, animationDuration: `${comet.duration}s`, animationDelay: `${comet.delay}s`, "--drift": `${comet.drift}px`, "--comet-opacity": comet.opacity } as CSSProperties} />)}</span>
              </div>
            </div>
            <h3>Tải ảnh phương tiện</h3>
            <p>Kéo thả tệp vào đây hoặc bấm <strong>Ctrl + V</strong> để nhận diện ngay</p>
            <button className="primary-button upload-cta" onClick={() => fileInputRef.current?.click()}><Upload size={17} aria-hidden="true" /> Chọn hình ảnh <ArrowRight size={16} aria-hidden="true" /></button><span className="upload-limit">JPG, PNG hoặc WEBP · Tối đa 10 MB</span>
          </div>}

          {isDragging && <div className="drop-overlay"><Upload size={36} aria-hidden="true" /><strong>Thả ảnh để bắt đầu nhận diện</strong></div>}
        </div>
        <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp" onChange={onFileChange} className="sr-only" aria-label="Chọn ảnh phương tiện" />
        <div className="upload-footer"><span><ShieldCheck size={14} aria-hidden="true" />{selectedFile ? selectedFile.name : "Dán Ctrl+V hoặc kéo thả ảnh để nhận diện"}</span><span>{detectionResponse ? `${results.length} biển được nhận diện` : "Tự động phân tích sau khi tải"}</span></div>
      </div>

      <aside className="results-panel" aria-label="Kết quả nhận diện">
        <div className="panel-heading"><div><ScanLine size={17} aria-hidden="true" /><h3>Kết quả nhận diện</h3></div><span className={`result-status ${activeResult ? "done" : ""}`}><span />{isLoading ? "Đang phân tích…" : detectionResponse ? "Hoàn tất" : "Chờ hình ảnh"}</span></div>
        <div className="result-content" aria-live="polite" aria-busy={isLoading}>
          {results.length > 1 && <div className="result-tabs" aria-label="Chọn biển số">{results.map((result, index) => <button key={`${result.plate_number}-${index}`} className={activeIndex === index ? "active" : ""} aria-pressed={activeIndex === index} onClick={() => { setActiveIndex(index); }}>Biển {String(index + 1).padStart(2, "0")}</button>)}</div>}

          {activeResult ? <>
            {/* 1. MÔ PHỎNG BIỂN SỐ DẬP NỔI CHUẨN QUY CÁCH (1 DÒNG HOẶC 2 DÒNG VUÔNG) */}
            <VietnamPlate
              plateNumber={activeResult.plate_number}
              plateType={activeResult.plate_type}
            />

            {/* 2. THẺ TRA CỨU THÔNG MINH BIỂN SỐ VIỆT NAM (PLATE INTELLIGENCE) */}
            <PlateIntelligenceCard
              plateNumber={activeResult.plate_number}
              plateType={activeResult.plate_type}
              isValidFormat={activeResult.is_valid_format}
            />

            {/* 3. ĐỘ TIN CẬY & THÔNG SỐ PHÂN TÍCH */}
            <div className="confidence-section">
              <div>
                <span>Độ tin cậy nhận diện</span>
                <strong>{confidence.toFixed(1)}<small>%</small></strong>
              </div>
              <div className="confidence-track">
                <span style={{ width: `${confidence}%` }} />
              </div>
            </div>

            <div className="result-details">
              <div>
                <span>Thời gian xử lý</span>
                <strong>{((detectionResponse?.processing_time_ms ?? 0) / 1000).toFixed(2)} giây</strong>
              </div>
              <div>
                <span>Phân loại biển</span>
                <strong>{activeResult.plate_type === "two_line" ? "Biển 2 dòng (Vuông)" : "Biển 1 dòng (Dài)"}</strong>
              </div>
            </div>

            {/* 4. ĐỐI CHIẾU ẢNH CẮT BIỂN SỐ THỰC TẾ TỪ YOLO (KHÔNG LẶP LẠI CHỮ) */}
            <div className="crop-heading">
              <span>Ảnh cắt vùng biển số thực tế</span>
              {cropUrl && <a href={cropUrl} target="_blank" rel="noreferrer">Mở ảnh đầy đủ <ArrowUpRight size={13} aria-hidden="true" /></a>}
            </div>
            <div className="crop-preview-clean">
              {cropUrl ? <img src={cropUrl} alt={`Vùng biển số ${activeResult.plate_number}`} /> : <span>Không có ảnh biển số</span>}
            </div>

            <Link href="/history" className="saved-note"><Check size={14} aria-hidden="true" /> Kết quả đã được lưu tự động trong lịch sử <ArrowUpRight size={13} aria-hidden="true" /></Link>
          </> : <div className="result-empty"><div className="empty-result-symbol"><ScanLine size={30} aria-hidden="true" /><span className="empty-result-line" /></div><h3>{isLoading ? "Kết quả đang được chuẩn bị" : detectionResponse ? "Chưa đọc được biển số" : "Sẵn sàng cho ảnh đầu tiên"}</h3><p>{isLoading ? "Hệ thống đang truy quét vùng biển số, nhận dạng ký tự và giải mã tỉnh thành." : detectionResponse ? "Hãy thử ảnh chụp gần hơn, đủ sáng và nhìn rõ toàn bộ biển số." : "Tải ảnh phương tiện hoặc bấm Ctrl+V để xem biển số mô phỏng, tra cứu địa phương và thông số phân tích."}</p><div className="empty-data-rows"><span>Biển số nhận diện <i>—</i></span><span>Độ tin cậy <i>—</i></span><span>Thời gian xử lý <i>—</i></span></div>{detectionResponse && <button className="secondary-button" onClick={() => fileInputRef.current?.click()}><ImagePlus size={16} aria-hidden="true" /> Chọn ảnh khác</button>}</div>}
        </div>
      </aside>
    </section>

    <section className="how-it-works" aria-label="Hướng dẫn nhận diện"><div className="guide-intro"><span className="eyebrow">ĐƠN GIẢN TRONG 3 BƯỚC</span><h2>Từ hình ảnh<br /> đến thông tin.</h2></div>{[{ number: "01", icon: Upload, title: "Tải ảnh phương tiện", text: "Chọn ảnh rõ nét, nhìn thấy toàn bộ biển số hoặc dán Ctrl+V." }, { number: "02", icon: Focus, title: "Tự động nhận diện", text: "Hệ thống tìm vùng biển, đọc ký tự và giải mã tỉnh thành." }, { number: "03", icon: History, title: "Xem và lưu kết quả", text: "Đối chiếu biển số thực tế và tra cứu lại trong lịch sử." }].map(({ number, icon: Icon, title, text }) => <div className="guide-step" key={number}><div><Icon size={20} aria-hidden="true" /><span>{number}</span></div><h3>{title}</h3><p>{text}</p></div>)}</section>
    <div className="quality-tip"><ShieldCheck size={17} aria-hidden="true" /><p><strong>Mẹo cho kết quả tốt hơn</strong> Dùng ảnh đủ sáng, hạn chế rung mờ và tránh che khuất ký tự trên biển số.</p></div>
  </div>;
}
