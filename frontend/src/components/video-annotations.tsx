"use client";

import { useEffect, useState, type RefObject } from "react";
import type { VideoFrame, VideoResult } from "../types/video";

type Props = {
  videoRef: RefObject<HTMLVideoElement | null>;
  result: VideoResult;
  frame: VideoFrame | null;
  selectedTrack: number | null;
};

export function VideoAnnotations({ videoRef, result, frame, selectedTrack }: Props) {
  const [hoveredTrack, setHoveredTrack] = useState<number | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    function move(event: PointerEvent) {
      if (event.pointerType !== "mouse" || !video) return;
      const rect = video.getBoundingClientRect();
      // Leave the native playback controls free of annotation interactions.
      if (event.clientY >= rect.bottom - 44) { setHoveredTrack(null); return; }
      const x = (event.clientX - rect.left) / rect.width * result.frame_width;
      const y = (event.clientY - rect.top) / rect.height * result.frame_height;
      const match = frame?.vehicles
        .filter(({ bbox: [left, top, right, bottom] }) => x >= left && x <= right && y >= top && y <= bottom)
        .reduce<(NonNullable<VideoFrame>["vehicles"][number]) | null>((best, vehicle) => {
          const area = ([left, top, right, bottom]: number[]) => (right - left) * (bottom - top);
          return !best || area(vehicle.bbox) < area(best.bbox) ? vehicle : best;
        }, null);
      setHoveredTrack(match?.track_id ?? null);
    }
    function leave() { setHoveredTrack(null); }
    video.addEventListener("pointermove", move);
    video.addEventListener("pointerleave", leave);
    return () => {
      video.removeEventListener("pointermove", move);
      video.removeEventListener("pointerleave", leave);
    };
  }, [videoRef, frame, result.frame_width, result.frame_height]);

  const activeId = frame?.vehicles.some(vehicle => vehicle.track_id === hoveredTrack) ? hoveredTrack : selectedTrack;
  return <div className="video-overlay" aria-hidden="true">
    {frame?.vehicles.map(vehicle => {
      const track = result.tracks.find(item => item.track_id === vehicle.track_id);
      const [x1, y1, x2, y2] = vehicle.bbox;
      const active = activeId === vehicle.track_id;
      return <div key={vehicle.track_id} className={`vehicle-box ${active ? "selected" : ""}`} style={{
        left: `${x1 / result.frame_width * 100}%`, top: `${y1 / result.frame_height * 100}%`,
        width: `${(x2 - x1) / result.frame_width * 100}%`, height: `${(y2 - y1) / result.frame_height * 100}%`,
      }}>
        {active && <span>{track?.plate_number || `#${vehicle.track_id} ${vehicle.vehicle_type}`}</span>}
      </div>;
    })}
  </div>;
}
