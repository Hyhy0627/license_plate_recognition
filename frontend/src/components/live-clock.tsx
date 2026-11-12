"use client";

import { useEffect, useState } from "react";
import { Clock } from "lucide-react";

export default function LiveClock() {
  const [timeStr, setTimeStr] = useState<string>("");
  const [dateStr, setDateStr] = useState<string>("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const days = ["Chủ Nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"];
      const dayName = days[now.getDay()];

      const day = String(now.getDate()).padStart(2, "0");
      const month = String(now.getMonth() + 1).padStart(2, "0");
      const year = now.getFullYear();

      const hours = String(now.getHours()).padStart(2, "0");
      const minutes = String(now.getMinutes()).padStart(2, "0");
      const seconds = String(now.getSeconds()).padStart(2, "0");

      setDateStr(`${dayName}, ${day}/${month}/${year}`);
      setTimeStr(`${hours}:${minutes}:${seconds}`);
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  if (!timeStr) {
    return <div className="live-clock-placeholder" aria-hidden="true" />;
  }

  return (
    <div className="live-clock-badge" aria-label={`Thời gian thực: ${dateStr} ${timeStr}`}>
      <span className="live-clock-beacon" aria-hidden="true">
        <span className="live-clock-dot" />
      </span>
      <Clock size={13} className="live-clock-icon" aria-hidden="true" />
      <span className="live-clock-date">{dateStr}</span>
      <span className="live-clock-sep" aria-hidden="true">·</span>
      <strong className="live-clock-time">{timeStr}</strong>
    </div>
  );
}
