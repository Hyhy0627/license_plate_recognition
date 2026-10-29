"use client";

import React, { useState } from "react";
import { Upload, Car, CheckCircle2, Cpu, Zap, ShieldCheck } from "lucide-react";
import type { DetectionResult, PlateDetectionResponse } from "../types/api";

export default function Home() {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // Mock sample detection for Phase 1 preview
  const mockResult: PlateDetectionResponse = {
    success: true,
    message: "Nhận diện biển số thành công (Mock Data Contract)",
    total_detected: 1,
    processing_time_ms: 124.5,
    results: [
      {
        plate_number: "59A1-123.45",
        confidence: 0.9625,
        plate_type: "two_line",
        bbox: [120, 160, 480, 420],
        cropped_image_url: null,
        annotated_image_url: null,
        is_valid_format: true,
      },
    ],
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
    }
  };

  return (
    <div className="space-y-8">
      {/* Top Banner / Hero */}
      <section className="relative overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-b from-slate-900 to-slate-950 p-6 sm:p-10 shadow-2xl">
        <div className="relative z-10 max-w-3xl space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-xs font-semibold text-blue-400">
            <Zap className="h-3.5 w-3.5 text-blue-400" />
            Phase 1: Architecture & Data Contract Ready
          </div>
          <h2 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
            Nhận Diện & Tách Biển Số Xe Việt Nam
          </h2>
          <p className="text-base text-slate-400 leading-relaxed">
            Hệ thống ứng dụng Deep Learning (YOLOv8/v11) kết hợp OpenCV và Engine OCR
            (PaddleOCR / EasyOCR), tự động xử lý biển số dài 1 dòng và biển vuông 2 dòng
            theo tiêu chuẩn giao thông Việt Nam.
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
                const file = e.dataTransfer.files[0];
                setSelectedFile(file);
                setPreviewUrl(URL.createObjectURL(file));
              }
            }}
            className={`relative flex min-h-[340px] flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 text-center transition-all ${
              isDragging
                ? "border-blue-500 bg-blue-500/10 shadow-lg shadow-blue-500/10"
                : "border-slate-800 bg-slate-900/40 hover:border-slate-700 hover:bg-slate-900/60"
            }`}
          >
            {previewUrl ? (
              <div className="relative flex w-full flex-col items-center gap-4">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={previewUrl}
                  alt="Ảnh phương tiện xem trước"
                  className="max-h-[260px] rounded-lg object-contain shadow-md"
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
        </div>

        {/* Right Column: Result Panel (Contract Mock Demonstration) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-white">Kết Quả Nhận Diện</h3>
            <span className="rounded-md bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
              Contract Schema v1.0
            </span>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <p className="text-xs text-slate-400">Biển số phát hiện</p>
                <div className="mt-1 flex items-center gap-3">
                  <span className="rounded-lg bg-amber-400/10 px-3 py-1 font-mono text-2xl font-black tracking-widest text-amber-300 border border-amber-400/20">
                    {mockResult.results[0].plate_number}
                  </span>
                  <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs text-slate-400">Độ tin cậy</p>
                <span className="text-lg font-bold text-emerald-400">
                  {(mockResult.results[0].confidence * 100).toFixed(1)}%
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="rounded-lg bg-slate-950 p-3 border border-slate-800/80">
                <span className="text-slate-500 block">Phân loại biển</span>
                <span className="font-semibold text-slate-200 mt-0.5 block capitalize">
                  {mockResult.results[0].plate_type === "two_line"
                    ? "Biển vuông (2 dòng)"
                    : "Biển dài (1 dòng)"}
                </span>
              </div>
              <div className="rounded-lg bg-slate-950 p-3 border border-slate-800/80">
                <span className="text-slate-500 block">Định dạng Regex VN</span>
                <span className="font-semibold text-emerald-400 mt-0.5 block">
                  Hợp lệ (Chuẩn VN)
                </span>
              </div>
              <div className="rounded-lg bg-slate-950 p-3 border border-slate-800/80">
                <span className="text-slate-500 block">Toạ độ BBox [x1,y1,x2,y2]</span>
                <span className="font-mono text-slate-300 mt-0.5 block text-[11px]">
                  [{mockResult.results[0].bbox.join(", ")}]
                </span>
              </div>
              <div className="rounded-lg bg-slate-950 p-3 border border-slate-800/80">
                <span className="text-slate-500 block">Thời gian xử lý</span>
                <span className="font-semibold text-blue-400 mt-0.5 block">
                  {mockResult.processing_time_ms} ms
                </span>
              </div>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-950 p-3">
              <p className="text-[11px] font-mono text-slate-400">
                Data Contract Status: <span className="text-emerald-400 font-bold">READY</span>
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Frontend đã sẵn sàng cắm kết nối với API <code className="text-slate-300">/api/license-plates/detect</code> trong Phase 4.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
