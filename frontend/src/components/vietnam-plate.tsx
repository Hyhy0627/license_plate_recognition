"use client";

import { useState, useRef } from "react";
import { CheckCheck, Copy } from "lucide-react";
import { parseVietnamPlate, type PlateMetadata } from "../lib/vietnam-plates";

interface VietnamPlateProps {
  plateNumber: string;
  plateType?: string | null;
  className?: string;
  onCopy?: () => void;
}

export default function VietnamPlate({ plateNumber, plateType, className = "", onCopy }: VietnamPlateProps) {
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const meta: PlateMetadata = parseVietnamPlate(plateNumber, plateType);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(plateNumber);
      setCopied(true);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setCopied(false), 2000);
      onCopy?.();
    } catch {
      // ignore
    }
  };

  // Color classes
  const colorTheme = meta.colorType === "blue"
    ? "plate-theme-blue"
    : meta.colorType === "yellow"
    ? "plate-theme-yellow"
    : meta.colorType === "red"
    ? "plate-theme-red"
    : "plate-theme-white";

  return (
    <div className={`vn-plate-wrapper ${className}`}>
      <div className="vn-plate-toolbar">
        <span className="vn-plate-badge-type">
          {meta.isTwoLine ? "BIỂN 2 DÒNG (XE MÁY / MÔ TÔ)" : "BIỂN 1 DÒNG (Ô TÔ / XE CON)"}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="vn-plate-copy-btn"
          aria-label={copied ? "Đã sao chép" : "Sao chép biển số"}
          title={copied ? "Đã sao chép" : "Sao chép biển số"}
        >
          {copied ? <CheckCheck size={14} className="text-emerald-400" /> : <Copy size={14} />}
          <span>{copied ? "Đã chép" : "Sao chép"}</span>
        </button>
      </div>

      {meta.isTwoLine ? (
        /* BIỂN 2 DÒNG VUÔNG CHUẨN XE MÁY */
        <div className={`vn-plate-box vn-plate-square ${colorTheme}`} role="img" aria-label={`Biển số xe máy: ${meta.line1} ${meta.line2}`}>
          {/* Đinh vít gắn biển 2 bên trên */}
          <span className="vn-plate-bolt vn-plate-bolt-tl" aria-hidden="true" />
          <span className="vn-plate-bolt vn-plate-bolt-tr" aria-hidden="true" />

          <div className="vn-plate-inner">
            <div className="vn-plate-row vn-plate-top">
              <span>{meta.line1}</span>
            </div>
            <div className="vn-plate-divider" aria-hidden="true" />
            <div className="vn-plate-row vn-plate-bottom">
              <span>{meta.line2}</span>
            </div>
          </div>
        </div>
      ) : (
        /* BIỂN 1 DÒNG DÀI CHUẨN Ô TÔ */
        <div className={`vn-plate-box vn-plate-long ${colorTheme}`} role="img" aria-label={`Biển số ô tô: ${meta.line1}`}>
          {/* Đinh vít gắn biển 2 bên mép */}
          <span className="vn-plate-bolt vn-plate-bolt-ml" aria-hidden="true" />
          <span className="vn-plate-bolt vn-plate-bolt-mr" aria-hidden="true" />

          <div className="vn-plate-inner">
            <div className="vn-plate-row vn-plate-single">
              <span>{meta.line1}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
