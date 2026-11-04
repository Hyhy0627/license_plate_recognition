"use client";

import React, { useState, useEffect } from "react";
import { Upload, Car, CheckCircle2, Cpu, Zap, ShieldCheck, Loader2, AlertCircle, Search, RefreshCw, Clock } from "lucide-react";
import type { DetectionResult, PlateDetectionResponse, DetectionHistoryItem } from "../types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [detectionResponse, setDetectionResponse] = useState<PlateDetectionResponse | null>(null);

  // Quản lý lịch sử và tìm kiếm
  const [historyItems, setHistoryItems] = useState<DetectionHistoryItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);

  // Quản lý kết quả nhận diện (Chỉ hiển thị khi người dùng tải ảnh thật)
  const activeResult: DetectionResult | undefined = detectionResponse?.results?.[0];

  const fetchHistory = async (query = "") => {
    setIsHistoryLoading(true);
    try {
      const endpoint = query.trim()
        ? `${API_BASE_URL}/api/license-plates/search?plate=${encodeURIComponent(query.trim())}`
        : `${API_BASE_URL}/api/license-plates/history?page=1&page_size=20`;
      const response = await fetch(endpoint);
      if (response.ok) {
        const data = await response.json();
        setHistoryItems(query.trim() ? data.results || [] : data.items || []);
      }
    } catch {
      // Backend có thể chưa chạy
    } finally {
      setIsHistoryLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleProcessImage = async (file: File) => {
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setErrorMessage(null);
    setIsLoading(true);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_BASE_URL}/api/license-plates/detect`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Lỗi máy chủ (${response.status})`);
      }

      const data: PlateDetectionResponse = await response.json();
      setDetectionResponse(data);
      // Cập nhật lại danh sách lịch sử sau khi nhận diện thành công
      fetchHistory(searchQuery);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Không thể kết nối đến máy chủ Backend";
      setErrorMessage(
        message.includes("Failed to fetch")
          ? "Không thể kết nối tới Backend (http://localhost:8000). Hãy đảm bảo bạn đã khởi chạy uvicorn main:app!"
          : message
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleProcessImage(e.target.files[0]);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchHistory(searchQuery);
  };

  const getFullImageUrl = (url?: string | null) => {
    if (!url) return null;
    if (url.startsWith("http")) return url;
    return `${API_BASE_URL}${url}`;
  };

  return (
    <div className="space-y-8">
      {/* Top Banner / Hero */}
      <section className="relative overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-b from-slate-900 to-slate-950 p-6 sm:p-10 shadow-2xl">
        <div className="relative z-10 max-w-3xl space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-xs font-semibold text-blue-400">
            <Zap className="h-3.5 w-3.5 text-blue-400" />
            Hệ Thống Trực Tuyến Thời Gian Thực
          </div>
          <h2 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
            Nhận Diện & Tách Biển Số Xe Việt Nam
          </h2>
          <p className="text-base text-slate-400 leading-relaxed">
            Hệ thống ứng dụng Deep Learning (YOLOv8) kết hợp tiền xử lý OpenCV và Engine OCR,
            tự động nắn góc nghiêng và nhận diện chuẩn xác biển số 1 dòng và 2 dòng.
          </p>

          <div className="grid grid-cols-2 gap-4 pt-4 sm:grid-cols-4">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3.5">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
                <Cpu className="h-4 w-4 text-blue-400" /> Model YOLO
              </div>
              <div className="mt-1 text-lg font-bold text-white">mAP ≥ 93%</div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3.5">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
                <ShieldCheck className="h-4 w-4 text-emerald-400" /> OCR Accuracy
              </div>
              <div className="mt-1 text-lg font-bold text-white">CAR ≥ 95%</div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3.5">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
                <Zap className="h-4 w-4 text-amber-400" /> Latency
              </div>
              <div className="mt-1 text-lg font-bold text-white">≤ 1.2s / ảnh</div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3.5">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
                <Car className="h-4 w-4 text-purple-400" /> Biển Số VN
              </div>
              <div className="mt-1 text-lg font-bold text-white">1 & 2 Dòng</div>
            </div>
          </div>
        </div>
      </section>

      {/* Main Workspace: Upload & Preview */}
      <section className="grid grid-cols-1 gap-8 lg:grid-cols-12">
        {/* Left Column: Upload Area */}
        <div className="lg:col-span-7 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-white">Tải Lên Hình Ảnh Phương Tiện</h3>
            <span className="text-xs text-slate-400">Hỗ trợ JPG, PNG, WEBP</span>
          </div>

          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragging(false);
              if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                handleProcessImage(e.dataTransfer.files[0]);
              }
            }}
            className={`relative flex min-h-[340px] flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 text-center transition-all ${
              isDragging
                ? "border-blue-500 bg-blue-500/10 shadow-lg shadow-blue-500/10"
                : "border-slate-800 bg-slate-900/40 hover:border-slate-700 hover:bg-slate-900/60"
            }`}
          >
            {isLoading ? (
              <div className="flex flex-col items-center gap-3 py-10">
                <Loader2 className="h-10 w-10 animate-spin text-blue-500" />
                <p className="text-sm font-semibold text-slate-200">Đang chạy mô hình AI (YOLO + OCR)...</p>
                <p className="text-xs text-slate-500">Đang phát hiện vị trí, cắt ảnh và giải mã ký tự</p>
              </div>
            ) : previewUrl ? (
              <div className="relative flex w-full flex-col items-center gap-4">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={
                    activeResult?.annotated_image_url
                      ? getFullImageUrl(activeResult.annotated_image_url) || previewUrl
                      : previewUrl
                  }
                  alt="Ảnh phương tiện xem trước"
                  className="max-h-[280px] rounded-lg object-contain shadow-md border border-slate-800"
                />
                <label className="cursor-pointer rounded-lg bg-slate-800 px-4 py-2 text-xs font-medium text-slate-200 hover:bg-slate-700 transition">
                  Chọn ảnh khác
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                </label>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-600/10 text-blue-400 border border-blue-500/20">
                  <Upload className="h-6 w-6" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-200">
                    Kéo và thả ảnh phương tiện vào đây
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    hoặc nhấp chuột để duyệt file từ máy tính
                  </p>
                </div>
                <label className="cursor-pointer mt-2 rounded-xl bg-blue-600 px-5 py-2.5 text-xs font-semibold text-white shadow-lg shadow-blue-600/30 hover:bg-blue-500 transition">
                  Chọn tệp ảnh
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                </label>
              </div>
            )}
          </div>

          {errorMessage && (
            <div className="flex items-start gap-2.5 rounded-xl border border-red-500/20 bg-red-500/10 p-3.5 text-xs text-red-400">
              <AlertCircle className="h-4 w-4 shrink-0 text-red-400 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}
        </div>

        {/* Right Column: Result Panel */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-white">Kết Quả Nhận Diện</h3>
            <span
              className={`rounded-md px-2 py-0.5 text-xs font-medium ${
                detectionResponse
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  : "bg-slate-800 text-slate-400"
              }`}
            >
              {detectionResponse ? "Live API Result" : "Chờ tải ảnh"}
            </span>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <p className="text-xs text-slate-400">Biển số phát hiện</p>
                <div className="mt-1 flex items-center gap-3">
                  <span
                    className={`rounded-lg px-3 py-1 font-mono text-2xl font-black tracking-widest border ${
                      !detectionResponse
                        ? "bg-slate-800/40 text-slate-500 border-slate-700/50 text-xl font-normal"
                        : detectionResponse.total_detected === 0
                        ? "bg-red-500/10 text-red-400 border-red-500/30 text-xl"
                        : "bg-amber-400/10 text-amber-300 border-amber-400/20"
                    }`}
                  >
                    {!detectionResponse
                      ? "CHƯA CÓ ẢNH"
                      : detectionResponse.total_detected === 0
                      ? "KHÔNG TÌM THẤY"
                      : activeResult
                      ? activeResult.plate_number
                      : "---"}
                  </span>
                  {activeResult?.is_valid_format && (
                    <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                  )}
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs text-slate-400">Độ tin cậy</p>
                <span className="text-lg font-bold text-emerald-400">
                  {!detectionResponse
                    ? "--"
                    : detectionResponse.total_detected === 0
                    ? "0%"
                    : activeResult
                    ? (activeResult.confidence * 100).toFixed(1) + "%"
                    : "0%"}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="rounded-lg bg-slate-950 p-3 border border-slate-800/80">
                <span className="text-slate-500 block">Phân loại biển</span>
                <span className="font-semibold text-slate-200 mt-0.5 block capitalize">
                  {!detectionResponse || detectionResponse.total_detected === 0
                    ? "---"
                    : activeResult?.plate_type === "two_line"
                    ? "Biển vuông (2 dòng)"
                    : activeResult?.plate_type === "one_line"
                    ? "Biển dài (1 dòng)"
                    : "---"}
                </span>
              </div>

              <div className="rounded-lg bg-slate-950 p-3 border border-slate-800/80">
                <span className="text-slate-500 block">Định dạng Regex VN</span>
                <span className="font-semibold mt-0.5 block">
                  {!detectionResponse || detectionResponse.total_detected === 0 ? (
                    <span className="text-slate-500">---</span>
                  ) : activeResult?.is_valid_format ? (
                    <span className="text-emerald-400">Hợp lệ (Chuẩn VN)</span>
                  ) : (
                    <span className="text-amber-400">Không chuẩn VN</span>
                  )}
                </span>
              </div>

              {/* Ô Hiển thị Ảnh cắt biển số (Cropped Plate Image) */}
              <div className="rounded-lg bg-slate-950 p-3 border border-slate-800/80 flex flex-col justify-between">
                <span className="text-slate-500 block mb-1">Ảnh cắt biển số (Crop)</span>
                <div className="flex h-14 w-full items-center justify-center overflow-hidden rounded-md bg-slate-900 border border-slate-800/80">
                  {activeResult?.cropped_image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={getFullImageUrl(activeResult.cropped_image_url) || ""}
                      alt="Ảnh cắt biển số"
                      className="max-h-full max-w-full object-contain p-1 rounded"
                    />
                  ) : (
                    <span className="text-[11px] text-slate-500 font-mono">Chưa có ảnh crop</span>
                  )}
                </div>
              </div>

              <div className="rounded-lg bg-slate-950 p-3 border border-slate-800/80">
                <span className="text-slate-500 block">Thời gian xử lý</span>
                <span className="font-semibold text-blue-400 mt-0.5 block">
                  {detectionResponse ? `${detectionResponse.processing_time_ms} ms` : "--"}
                </span>
              </div>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-950 p-3 space-y-1.5">
              <div className="flex items-center justify-between text-[11px] font-mono">
                <span className="text-slate-400">Trạng thái:</span>
                <span
                  className={
                    !detectionResponse
                      ? "text-slate-400 font-semibold"
                      : detectionResponse.total_detected > 0
                      ? "text-emerald-400 font-bold"
                      : "text-amber-400 font-bold"
                  }
                >
                  {!detectionResponse
                    ? "SẴN SÀNG"
                    : detectionResponse.total_detected > 0
                    ? "ĐÃ KẾT NỐI API THỰC TẾ"
                    : "KHÔNG TÌM THẤY BIỂN SỐ"}
                </span>
              </div>
              {detectionResponse && detectionResponse.total_detected > 0 && activeResult && (
                <div className="flex items-center justify-between text-[11px] font-mono">
                  <span className="text-slate-400">Mô hình AI:</span>
                  <span
                    className={
                      activeResult.engine_used === "9router_vision"
                        ? "text-purple-400 font-semibold bg-purple-500/10 px-1.5 py-0.5 rounded border border-purple-500/20"
                        : "text-emerald-400 font-semibold bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20"
                    }
                  >
                    {activeResult.engine_used === "9router_vision"
                      ? "☁️ Cloud Vision AI (Fallback)"
                      : "⚡ Local YOLO AI (Cục bộ)"}
                  </span>
                </div>
              )}
              <p className="text-[11px] text-slate-500 mt-0.5">
                {!detectionResponse
                  ? "Vui lòng chọn hoặc kéo thả ảnh phương tiện ở khung bên trái để nhận diện."
                  : detectionResponse.total_detected > 0
                  ? `Nhận diện xong lúc ${new Date().toLocaleTimeString("vi-VN")}`
                  : "Không tìm thấy biển số trên xe trong ảnh này. Vui lòng thử ảnh chụp rõ góc hoặc chụp gần hơn."}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Section 3: History & Search Management */}
      <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 sm:p-8 space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xl font-bold text-white">Lịch Sử Nhận Diện Phương Tiện</h3>
              <span className="rounded-full bg-blue-500/10 border border-blue-500/20 px-2.5 py-0.5 text-xs font-semibold text-blue-400">
                {historyItems.length} lượt
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Danh sách các lượt phương tiện đã được hệ thống ALPR ghi nhận thời gian thực.
            </p>
          </div>

          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Tìm biển số (VD: 30A, 59G2)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-64 rounded-xl border border-slate-800 bg-slate-950 pl-9 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:border-blue-500 focus:outline-none"
              />
            </div>
            <button
              type="submit"
              className="rounded-xl bg-slate-800 hover:bg-slate-700 px-3 py-2 text-xs font-medium text-slate-200 transition"
            >
              Tìm
            </button>
            <button
              type="button"
              onClick={() => {
                setSearchQuery("");
                fetchHistory("");
              }}
              className="rounded-xl border border-slate-800 bg-slate-950 p-2 text-slate-400 hover:text-white transition"
              title="Làm mới danh sách"
            >
              <RefreshCw className={`h-4 w-4 ${isHistoryLoading ? "animate-spin" : ""}`} />
            </button>
          </form>
        </div>

        {/* Table */}
        <div className="overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 bg-slate-950/80 text-slate-400">
              <tr>
                <th className="py-3 px-4 font-semibold"># ID</th>
                <th className="py-3 px-4 font-semibold">Biển Số Nhận Diện</th>
                <th className="py-3 px-4 font-semibold">Ảnh Cắt (Crop)</th>
                <th className="py-3 px-4 font-semibold">Phân Loại</th>
                <th className="py-3 px-4 font-semibold">Độ Tin Cậy</th>
                <th className="py-3 px-4 font-semibold">Thời Gian Ghi Nhận</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-900/40">
              {historyItems.length > 0 ? (
                historyItems.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-800/40 transition">
                    <td className="py-3 px-4 font-mono text-slate-400">#{item.id}</td>
                    <td className="py-3 px-4 font-mono font-bold text-amber-300">
                      <span className="rounded bg-amber-400/10 px-2 py-0.5 border border-amber-400/20">
                        {item.plate_number}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {item.cropped_plate_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={getFullImageUrl(item.cropped_plate_url) || ""}
                          alt="Biển số"
                          className="h-8 w-auto max-w-[80px] rounded object-contain bg-slate-950 p-0.5 border border-slate-800"
                        />
                      ) : (
                        <span className="text-slate-500">---</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-slate-300">
                      {item.plate_type === "two_line" ? "Biển vuông (2 dòng)" : "Biển dài (1 dòng)"}
                    </td>
                    <td className="py-3 px-4 font-semibold text-emerald-400">
                      {(item.confidence * 100).toFixed(1)}%
                    </td>
                    <td className="py-3 px-4 text-slate-400">
                      <div className="flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5 text-slate-500 shrink-0" />
                        <span>{item.created_at ? item.created_at.replace("T", " ") : "---"}</span>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-500">
                    {isHistoryLoading ? "Đang tải danh sách..." : "Chưa có lượt nhận diện nào được ghi nhận."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
