/**
 * Data Contract định nghĩa kiểu dữ liệu đồng bộ giữa Frontend và Backend FastAPI
 * Phụ trách bởi: Người 5 (Frontend) & Người 4 (Backend)
 */

export interface DetectionResult {
  plate_number: string;
  confidence: number;
  plate_type: "one_line" | "two_line" | "unknown" | string;
  bbox: [number, number, number, number]; // [x1, y1, x2, y2]
  cropped_image_url?: string | null;
  annotated_image_url?: string | null;
  is_valid_format: boolean;
}

export interface PlateDetectionResponse {
  success: boolean;
  message: string;
  total_detected: number;
  processing_time_ms: number;
  results: DetectionResult[];
}

export interface DetectionHistoryItem {
  id: number;
  plate_number: string;
  confidence: number;
  plate_type: string;
  created_at: string;
  image_url?: string | null;
  cropped_plate_url?: string | null;
}

export interface DetectionHistoryResponse {
  total: number;
  page: number;
  page_size: number;
  items: DetectionHistoryItem[];
}

export interface SearchPlatesResponse {
  total: number;
  query: string;
  results: DetectionHistoryItem[];
}
