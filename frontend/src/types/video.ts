export type TrackedVehicle = {
  track_id: number;
  vehicle_type: string;
  bbox: [number, number, number, number];
};

export type VideoFrame = { time: number; vehicles: TrackedVehicle[] };

export type VehicleTrack = {
  track_id: number;
  vehicle_type: string;
  first_seen: number;
  last_seen: number;
  plate_number: string | null;
  plate_confidence: number | null;
  plate_observations: number;
  plate_candidates?: string[];
  plate_status?: "confirmed" | "tentative" | "needs_review" | "unreadable";
};

export type VideoResult = {
  duration: number;
  fps: number;
  frame_width: number;
  frame_height: number;
  sample_fps: number;
  processing_seconds?: number;
  mode: "combined" | "fast" | "detailed";
  ninerouter?: {
    status: "available" | "unavailable" | "disabled" | "error" | "skipped";
    attempts: number;
    recognized: number;
  };
  frames: VideoFrame[];
  tracks: VehicleTrack[];
};

export type VideoJob = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  error: string | null;
  result: VideoResult | null;
};
