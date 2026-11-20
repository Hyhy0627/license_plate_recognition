"use client";

import { MapPin, Car, ShieldCheck, Tag, Info } from "lucide-react";
import { parseVietnamPlate } from "../lib/vietnam-plates";

interface PlateIntelligenceCardProps {
  plateNumber: string;
  plateType?: string | null;
  isValidFormat?: boolean;
}

export default function PlateIntelligenceCard({
  plateNumber,
  plateType,
  isValidFormat = true,
}: PlateIntelligenceCardProps) {
  const meta = parseVietnamPlate(plateNumber, plateType);

  return (
    <div className="plate-intelligence-card" aria-label="Thông tin tra cứu biển số xe Việt Nam">
      <div className="pi-header">
        <div className="pi-title">
          <Info size={16} aria-hidden="true" />
          <h4>Thông tin biển số</h4>
        </div>
        <span className={`pi-badge-status ${meta.isValidFormat && isValidFormat ? "valid" : "warning"}`}>
          <ShieldCheck size={12} aria-hidden="true" />
          {meta.isValidFormat && isValidFormat ? "Đúng định dạng" : "Cần đối chiếu thêm"}
        </span>
      </div>

      <div className="pi-grid">
        {/* Địa phương */}
        <div className="pi-item">
          <div className="pi-item-icon pi-icon-map">
            <MapPin size={16} aria-hidden="true" />
          </div>
          <div className="pi-item-content">
            <span className="pi-item-label">Tỉnh / thành phố</span>
            <strong className="pi-item-value">{meta.provinceName}</strong>
            <small className="pi-item-sub">Mã đầu số: {meta.provinceCode || "—"} · {meta.regionName}</small>
          </div>
        </div>

        {/* Loại phương tiện */}
        <div className="pi-item">
          <div className="pi-item-icon pi-icon-car">
            <Car size={16} aria-hidden="true" />
          </div>
          <div className="pi-item-content">
            <span className="pi-item-label">Loại phương tiện</span>
            <strong className="pi-item-value">{meta.vehicleCategory}</strong>
            <small className="pi-item-sub">{meta.vehicleDescription}</small>
          </div>
        </div>

        {/* Quy chuẩn & Màu biển */}
        <div className="pi-item pi-item-full">
          <div className="pi-item-icon pi-icon-tag">
            <Tag size={16} aria-hidden="true" />
          </div>
          <div className="pi-item-content">
            <span className="pi-item-label">Màu biển</span>
            <div className="pi-color-pill-row">
              <span className={`pi-color-pill pi-pill-${meta.colorType}`} />
              <strong className="pi-item-value">{meta.colorName}</strong>
            </div>
            <small className="pi-item-sub">{meta.colorDescription}</small>
          </div>
        </div>
      </div>
    </div>
  );
}
