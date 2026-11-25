"use client";

import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { AlertCircle, CheckCircle2, Film, LoaderCircle, Play, ScanLine, Upload, Video } from "lucide-react";
import { RequireAuth } from "../../components/auth-provider";
import { VideoAnnotations } from "../../components/video-annotations";
import { API_BASE_URL, apiError, apiFetch } from "../../lib/api";
import type { VehicleTrack, VideoFrame, VideoJob, VideoResult } from "../../types/video";

const MAX_BYTES = 100 * 1024 * 1024;
const ALLOWED = new Set(["mp4", "mov", "avi", "webm"]);

function tracksWithPlates(result: VideoResult): VideoResult {
  const tracks = result.tracks.filter(track => track.plate_number?.trim());
  const ids = new Set(tracks.map(track => track.track_id));
  return {
    ...result,
    tracks,
    frames: result.frames.map(frame => ({
      ...frame,
      vehicles: frame.vehicles.filter(vehicle => ids.has(vehicle.track_id)),
    })),
  };
}

function nearestFrame(result: VideoResult, time: number): VideoFrame | null {
  const index = Math.round(time * result.sample_fps);
  const candidates = result.frames.slice(Math.max(0, index - 2), index + 3);
  const nearest = candidates.reduce<VideoFrame | null>((best, frame) =>
    !best || Math.abs(frame.time - time) < Math.abs(best.time - time) ? frame : best, null);
  return nearest && Math.abs(nearest.time - time) <= 0.5 / result.sample_fps + 0.05 ? nearest : null;
}

function formatTime(seconds: number) {
  return `${Math.floor(seconds / 60).toString().padStart(2, "0")}:${Math.floor(seconds % 60).toString().padStart(2, "0")}`;
}

export default function VideoPage() {
  return <RequireAuth><VideoWorkspace /></RequireAuth>;
}

function VideoWorkspace() {
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<"fast" | "detailed" | "combined">("fast");
  const [showAllTracks, setShowAllTracks] = useState(false);
  const [pastJobs, setPastJobs] = useState<Array<{ id: string; filename: string; mode: string; status: string }>>([]);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [videoDimensions, setVideoDimensions] = useState<{ width: number; height: number } | null>(null);
  const [job, setJob] = useState<VideoJob | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [playbackError, setPlaybackError] = useState("");
  const [currentTime, setCurrentTime] = useState(0);
  const [selectedTrack, setSelectedTrack] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const pendingSeek = useRef<number | null>(null);
  const jobResult = job?.result;
  const result = useMemo(() => jobResult && (showAllTracks ? jobResult : tracksWithPlates(jobResult)), [jobResult, showAllTracks]);
  const dimensions = result ? { width: result.frame_width, height: result.frame_height } : videoDimensions;
  const playerStyle = dimensions ? { aspectRatio: `${dimensions.width} / ${dimensions.height}`, maxWidth: `${70 * dimensions.width / dimensions.height}vh` } : undefined;
  const sourceUrl = job?.id ? `${API_BASE_URL}/api/video-tracking/jobs/${job.id}/media` : videoUrl;
  const frame = result ? nearestFrame(result, currentTime) : null;

  useEffect(() => () => { if (videoUrl) URL.revokeObjectURL(videoUrl); }, [videoUrl]);
  useEffect(() => {
    void apiFetch("/api/video-tracking/jobs?page_size=20").then(async response => {
      if (response.ok) setPastJobs((await response.json()).items ?? []);
    }).catch(() => {});
  }, [job?.status]);
  useEffect(() => {
    if (!job?.id || !["queued", "running"].includes(job.status)) return;
    let cancelled = false;
    let pending = false;
    const timer = window.setInterval(async () => {
      if (pending) return;
      pending = true;
      try {
        const response = await apiFetch(`/api/video-tracking/jobs/${job.id}`);
        if (!response.ok) throw new Error(await apiError(response, "Không lấy được trạng thái video."));
        const update: VideoJob = await response.json();
        if (!cancelled) setJob(update);
      } catch (reason) {
        if (!cancelled) { setError(reason instanceof Error ? reason.message : "Mất kết nối với máy chủ."); setJob(previous => previous ? { ...previous, status: "failed" } : previous); }
      } finally { pending = false; }
    }, 1200);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [job?.id, job?.status]);

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const chosen = event.target.files?.[0];
    event.target.value = "";
    if (!chosen) return;
    if (uploading || job?.status === "queued" || job?.status === "running") return;
    const extension = chosen.name.split(".").pop()?.toLowerCase() || "";
    if (!ALLOWED.has(extension)) { setError("Hãy chọn video MP4, MOV, AVI hoặc WEBM."); return; }
    if (chosen.size > MAX_BYTES) { setError("Video vượt quá 100 MB."); return; }
    setError(""); setPlaybackError(""); setJob(null); setVideoDimensions(null); setCurrentTime(0); setSelectedTrack(null); pendingSeek.current = null;
    setFile(chosen); setVideoUrl(URL.createObjectURL(chosen));
    void analyze(chosen);
  }

  async function analyze(videoFile: File | null = file) {
    if (!videoFile || uploading || job?.status === "queued" || job?.status === "running") return;
    setUploading(true); setError(""); setJob(null);
    try {
      const form = new FormData(); form.append("file", videoFile);
      const response = await apiFetch(`/api/video-tracking/jobs?mode=${mode}`, { method: "POST", body: form });
      if (!response.ok) throw new Error(await apiError(response, "Không tải được video lên máy chủ."));
      setJob(await response.json());
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Không kết nối được máy chủ."); }
    finally { setUploading(false); }
  }

  function seekTo(seconds: number, trackId: number) {
    if (videoRef.current) {
      const video = videoRef.current;
      const target = Math.min(seconds, Number.isFinite(video.duration) ? Math.max(0, video.duration - 0.05) : seconds);
      if (video.readyState === 0) pendingSeek.current = target;
      else { video.currentTime = target; video.pause(); }
    }
    setCurrentTime(seconds); setSelectedTrack(trackId);
  }

  function trackButton(track: VehicleTrack) {
    return <button key={track.track_id} type="button" className={`video-track ${selectedTrack === track.track_id ? "selected" : ""}`} onClick={() => seekTo(track.first_seen, track.track_id)}>
      <span className="video-track-id">#{track.track_id}</span>
      <span className="video-track-main"><strong>{track.plate_number}</strong><small>{track.vehicle_type} · {formatTime(track.first_seen)}–{formatTime(track.last_seen)}</small>
        {track.plate_status === "confirmed" && <small className="video-plate-state">Nhiều lượt đọc khớp</small>}
        {track.plate_status === "tentative" && <small className="video-plate-state">Cần đối chiếu hình ảnh</small>}
        {track.plate_status === "needs_review" && <small className="video-plate-state warning">Các lượt đọc khác nhau: {track.plate_candidates?.join(" / ")}</small>}
      </span>{track.plate_status === "confirmed" && <CheckCircle2 size={17} aria-hidden="true" />}
    </button>;
  }

  return <div className="video-page">
    <header className="video-hero">
      <span className="video-kicker"><Video size={15} aria-hidden="true" /> PHÂN TÍCH VIDEO GIAO THÔNG</span>
      <h1>Theo vết phương tiện<br /><span>và nhận diện biển số</span></h1>
      <p>Tải video lên để theo dõi từng xe qua các khung hình. Hệ thống gắn ID, đọc biển số và tổng hợp kết quả theo từng phương tiện.</p>
    </header>

    <div className="video-grid">
      <section className="video-card" aria-labelledby="video-upload-title">
        <div className="video-card-head"><div><Film size={18} aria-hidden="true" /><h2 id="video-upload-title">Video đầu vào</h2></div><span>MP4, MOV, AVI, WEBM</span></div>
        <div className="video-stage">
          {sourceUrl ? <div className="video-player" style={playerStyle}>
            <video key={sourceUrl} ref={videoRef} src={sourceUrl} crossOrigin="use-credentials" controls playsInline preload="metadata"
              onLoadedMetadata={event => { setPlaybackError(""); setVideoDimensions({ width: event.currentTarget.videoWidth, height: event.currentTarget.videoHeight }); if (pendingSeek.current !== null) { event.currentTarget.currentTime = pendingSeek.current; pendingSeek.current = null; } }}
              onError={() => setPlaybackError("Không phát được video. Hãy chọn lại tệp hoặc tải lại trang.")}
              onTimeUpdate={event => setCurrentTime(event.currentTarget.currentTime)} onSeeked={event => setCurrentTime(event.currentTarget.currentTime)} aria-label="Video giao thông đang phân tích" />
            {result && <VideoAnnotations videoRef={videoRef} result={result} frame={frame} selectedTrack={selectedTrack} />}
          </div> : <div className="video-empty"><div className="video-empty-icon"><Play size={34} aria-hidden="true" /></div><strong>Chưa chọn video</strong><p>Chọn video để tự động bắt đầu phân tích.</p></div>}
        </div>
        <label className="video-combined-note" htmlFor="video-mode">Chế độ xử lý</label>
        <select id="video-mode" value={mode} onChange={event => setMode(event.target.value as typeof mode)} disabled={uploading || job?.status === "running" || job?.status === "queued"} className="mb-3 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-cyan-500">
          <option value="fast">Nhanh · OCR cục bộ</option><option value="detailed">Chi tiết</option><option value="combined">Kết hợp</option>
        </select>
        <div className="video-actions">
          <input ref={inputRef} type="file" accept=".mp4,.mov,.avi,.webm,video/*" className="sr-only" onChange={chooseFile} aria-label="Chọn video giao thông" />
          <button type="button" className="video-select" onClick={() => inputRef.current?.click()} disabled={uploading || job?.status === "running" || job?.status === "queued"}><Upload size={17} aria-hidden="true" /> {file ? "Đổi video" : "Chọn video"}</button>
          <button type="button" className="video-analyze" onClick={() => void analyze()} disabled={!file || uploading || job?.status === "running" || job?.status === "queued"}><ScanLine size={17} aria-hidden="true" /> {uploading ? "Đang tải lên…" : "Phân tích lại"}</button>
        </div>
        <p className="video-file-note">{file ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB` : "Video tối đa 100 MB, dài tối đa 45 giây, độ phân giải tối đa Full HD."}</p>
        {error && <div className="video-alert" role="alert"><AlertCircle size={18} aria-hidden="true" />{error}</div>}
        {playbackError && <div className="video-alert" role="alert"><AlertCircle size={18} aria-hidden="true" />{playbackError}</div>}
        {job?.status === "failed" && job.error && <div className="video-alert" role="alert"><AlertCircle size={18} aria-hidden="true" />{job.error}</div>}
        {(uploading || job?.status === "queued" || job?.status === "running") && <div className="video-progress" role="status"><span><LoaderCircle size={16} className="animate-spin" aria-hidden="true" />{uploading ? "Đang tải video lên" : job?.status === "queued" ? "Đang chờ xử lý" : "Đang theo vết và đọc biển số"}</span><strong>{job?.progress ?? 0}%</strong><div className="video-progress-track"><span style={{ width: `${job?.progress ?? 0}%` }} /></div></div>}
      </section>

      <aside className="video-card video-results" aria-labelledby="video-results-title">
        <div className="video-card-head"><div><ScanLine size={18} aria-hidden="true" /><h2 id="video-results-title">Kết quả nhận diện biển số</h2></div></div>
        <label className="video-result-note"><input type="checkbox" checked={showAllTracks} onChange={event => setShowAllTracks(event.target.checked)} /> Hiện cả xe chưa đọc được biển</label>
        {result ? <>
          {result.processing_seconds !== undefined && <p className="video-result-note">Hoàn tất phân tích trong {result.processing_seconds.toFixed(1)} giây.</p>}
          <div className="video-stats"><div><strong>{result.tracks.length}</strong><span>{showAllTracks ? "ID theo vết" : "ID có biển số"}</span></div><div><strong>{formatTime(result.duration)}</strong><span>Thời lượng</span></div></div>
          {result.tracks.length ? <div className="video-track-list">{result.tracks.map(trackButton)}</div>
            : <p className="video-results-empty">Chưa đọc được biển số nào trong video này. Hãy thử video có biển số rõ hơn.</p>}
          {result.ninerouter?.status === "available" && <p className="video-result-note">9Router đã kiểm tra {result.ninerouter.attempts} ID chưa đọc được và đọc thêm {result.ninerouter.recognized} biển.</p>}
          {result.ninerouter?.status === "unavailable" && <p className="video-result-note">9Router chưa kết nối; video chỉ dùng OCR cục bộ.</p>}
          {result.ninerouter?.status === "disabled" && <p className="video-result-note">9Router chưa được bật trong cấu hình OCR.</p>}
          {result.ninerouter?.status === "error" && <p className="video-result-note">9Router đã thử {result.ninerouter.attempts} ID nhưng gặp lỗi kết nối hoặc hết thời gian chờ.</p>}
          <p className="video-result-note">Một xe có thể mang nhiều ID khi camera di chuyển. Biển đọc được cần đối chiếu với hình ảnh gốc trước khi sử dụng.</p>
        </> : <div className="video-results-empty"><ScanLine size={36} aria-hidden="true" /><strong>Kết quả sẽ xuất hiện ở đây</strong><p>Sau khi phân tích, chọn một xe trong danh sách để chuyển đến thời điểm xe xuất hiện.</p></div>}
        {pastJobs.length > 0 && <section aria-label="Lịch sử video" className="video-result-note"><strong>Video đã xử lý</strong><div className="mt-2 flex flex-wrap gap-2">{pastJobs.map(past => <button key={past.id} type="button" className="rounded-lg border border-slate-300 px-3 py-2 text-left text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500" onClick={async () => { const response = await apiFetch(`/api/video-tracking/jobs/${past.id}`); if (response.ok) setJob(await response.json()); }} >{past.filename} · {past.status}</button>)}</div></section>}
      </aside>
    </div>
  </div>;
}
