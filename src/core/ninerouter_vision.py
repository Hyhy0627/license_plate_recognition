import base64
import json
import time
import re
import cv2
import requests
import numpy as np
from typing import Dict, Any, Optional

from src.config import settings
from src.utils.logger import logger


class NineRouterVisionClient:
    """
    Client kết nối tới 9Router AI Gateway để nhận diện ký tự biển số xe
    bằng mô hình Vision-Language Model (VLM: GPT-4o, Claude 3.5/Sonnet, Gemini, Qwen-VL...).
    Tương thích chuẩn OpenAI API: {base_url}/chat/completions
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.base_url = (base_url or getattr(settings, "NINEROUTER_BASE_URL", "http://localhost:20128/v1")).rstrip("/")
        self.api_key = api_key or getattr(settings, "NINEROUTER_API_KEY", "sk-61f55deb9d48b9e9-nh78ky-98700cc2")
        self.model = model or getattr(settings, "NINEROUTER_MODEL", "ag/gemini-3.8-flash")
        self.timeout = timeout or getattr(settings, "NINEROUTER_TIMEOUT", 20.0)
        # Sử dụng requests.Session để tái sử dụng HTTP connection pooling (giảm độ trễ kết nối)
        self.session = requests.Session()
        self._last_check = 0.0
        self._cached_available = False

    def is_available(self) -> bool:
        """Kiểm tra xem 9Router service có đang phản hồi hay không (cache 30s để tránh làm chậm hệ thống)."""
        now = time.time()
        if now - self._last_check < 30.0:
            return self._cached_available
        self._last_check = now
        try:
            url = f"{self.base_url}/models"
            resp = self.session.get(url, timeout=1.0)
            self._cached_available = (resp.status_code == 200)
        except Exception:
            self._cached_available = False
        return self._cached_available

    def _encode_image_to_base64(self, image: np.ndarray, max_dim: int = 512, quality: int = 85) -> Optional[str]:
        """
        Tối ưu hóa dung lượng: Resize ảnh về kích thước tối ưu và nén JPEG chất lượng 85%.
        Giúp giảm 70-80% dung lượng payload, tăng tốc độ truyền mạng và giảm thời gian inference của VLM.
        """
        if image is None or image.size == 0:
            return None

        h, w = image.shape[:2]
        if max(h, w) > max_dim:
            scale = max_dim / float(max(h, w))
            new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
            image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        success, buffer = cv2.imencode(".jpg", image, encode_param)
        if not success:
            return None
        return base64.b64encode(buffer).decode("utf-8")

    def recognize_plate(self, plate_img: np.ndarray) -> Dict[str, Any]:
        """
        Gửi ảnh biển số xe (crop) tới 9Router Vision API để nhận dạng ký tự.
        Tự động nắn nghiêng và tăng nét viền trước khi gửi để tránh nhầm ký tự G và C.
        """
        if plate_img is None or plate_img.size == 0:
            return {"raw_text": "", "plate_type": "unknown", "confidence": 0.0}

        if not self.is_available():
            return {"raw_text": "", "plate_type": "unknown", "confidence": 0.0, "error": "offline"}

        # Áp dụng tiền xử lý nắn thẳng và làm nét ký tự
        try:
            from src.core.preprocessor import PlatePreprocessor
            deskewed = PlatePreprocessor.deskew_plate(plate_img)
            enhanced = PlatePreprocessor.sharpen_image(deskewed, strength=1.3)
        except Exception:
            enhanced = plate_img

        base64_img = self._encode_image_to_base64(enhanced, max_dim=400, quality=90)
        if not base64_img:
            logger.error("9Router Vision: Không thể mã hóa ảnh sang base64.")
            return {"raw_text": "", "plate_type": "unknown", "confidence": 0.0}

        system_prompt = (
            "Bạn là chuyên gia thị giác máy tính nhận dạng biển số xe Việt Nam.\n"
            "Nhiệm vụ: Đọc chính xác toàn bộ chữ cái và chữ số trên biển số xe trong ảnh.\n"
            "QUY TẮC PHÂN BIỆT KÝ TỰ DỄ NHẦM LẪN:\n"
            "- Phân biệt cực kỳ cẩn thận giữa chữ 'G' và 'C':\n"
            "  + 'G': Có nét gạch ngang (thanh ngang) hướng vào trong ở phía bên phải.\n"
            "  + 'C': Là hình vòng cung hở, hoàn toàn KHÔNG có thanh ngang bên trong.\n"
            "- Phân biệt giữa số '8' (hai vòng tròn kín đối xứng) và chữ cái 'B' (có thanh đứng thẳng bên trái).\n"
            "- Phân biệt giữa số '0' và chữ 'D' / 'O'.\n"
            "Đặc điểm biển số Việt Nam:\n"
            "- Biển 1 dòng: ví dụ 30A-123.45 hoặc 51G-888.88\n"
            "- Biển 2 dòng: dòng trên gồm mã tỉnh và sê-ri (ví dụ: 88-G1, 29-X1), dòng dưới gồm dãy số (ví dụ: 333.43).\n"
            "Yêu cầu xuất kết quả theo định dạng JSON chuẩn duy nhất:\n"
            "{\n"
            '  "raw_text": "chuỗi ký tự không dấu cách (vd: 88G133343)",\n'
            '  "plate_type": "one_line" hoặc "two_line",\n'
            '  "confidence": số thập phân từ 0.0 đến 1.0\n'
            "}"
        )

        user_content = [
            {
                "type": "text",
                "text": "Hãy nhận diện và trích xuất ký tự trên biển số xe này. Lưu ý phân biệt rõ chữ G và C. Trả về đúng JSON.",
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_img}"
                },
            },
        ]

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
            "max_tokens": 120,
        }

        try:
            logger.info(f"9Router Vision: Đang gửi request tới {self.base_url} (model: {self.model})...")
            resp = self.session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )

            if resp.status_code != 200:
                logger.warning(
                    f"9Router Vision API trả về mã lỗi {resp.status_code}: {resp.text}"
                )
                return {"raw_text": "", "plate_type": "unknown", "confidence": 0.0, "error": resp.text}

            content = ""
            raw_body = resp.text.strip()

            # Trường hợp 1: Phản hồi SSE streaming
            if "text/event-stream" in resp.headers.get("content-type", "") or raw_body.startswith("data:"):
                for line in raw_body.splitlines():
                    line = line.strip()
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            chunk = json.loads(line[6:])
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content += delta.get("content", "")
                        except Exception:
                            pass
            else:
                try:
                    resp_json = resp.json()
                    content = resp_json["choices"][0]["message"]["content"].strip()
                except Exception as je:
                    content = raw_body

            logger.info(f"9Router Vision Raw Content: {content}")
            return self._parse_model_output(content)

        except requests.exceptions.Timeout:
            logger.error(f"9Router Vision: Quá thời gian chờ phản hồi ({self.timeout}s).")
            return {"raw_text": "", "plate_type": "unknown", "confidence": 0.0, "error": "timeout"}
        except requests.exceptions.ConnectionError:
            logger.error(f"9Router Vision: Không thể kết nối tới {self.base_url}. Hãy chắc chắn 9Router đang chạy.")
            return {"raw_text": "", "plate_type": "unknown", "confidence": 0.0, "error": "connection_error"}
        except Exception as e:
            logger.error(f"9Router Vision lỗi ngoại lệ: {e}")
            return {"raw_text": "", "plate_type": "unknown", "confidence": 0.0, "error": str(e)}

    def detect_and_recognize_plate(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Nhận diện vị trí tấm biển số (bounding box [x1, y1, x2, y2]) và ký tự trên ảnh gốc
        khi mô hình YOLO cục bộ không phát hiện được (ví dụ ảnh chụp góc nghiêng, khoảng cách xa).
        Tối ưu kích thước 720px và có cơ chế Thoát Sớm (Early Exit) nếu ảnh không có xe.
        """
        if image is None or image.size == 0:
            return {"raw_text": "", "plate_type": "unknown", "bbox": None, "confidence": 0.0}

        if not self.is_available():
            return {"raw_text": "", "plate_type": "unknown", "bbox": None, "confidence": 0.0, "error": "offline"}

        h, w = image.shape[:2]
        # Resize ảnh về max 720px để truyền nhanh hơn và suy luận dưới 2-3s
        base64_img = self._encode_image_to_base64(image, max_dim=720, quality=80)
        if not base64_img:
            return {"raw_text": "", "plate_type": "unknown", "bbox": None, "confidence": 0.0}

        system_prompt = (
            "Bạn là chuyên gia thị giác máy tính nhận diện biển số xe Việt Nam.\n"
            "Nhiệm vụ: Hãy tìm chính xác vị trí của tấm biển số xe trong ảnh và đọc toàn bộ ký tự trên biển.\n"
            "QUY TẮC THOÁT SỚM (EARLY EXIT): Nếu bức ảnh là phong cảnh, động vật, tài liệu hoặc HOÀN TOÀN KHÔNG CÓ BIỂN SỐ XE, "
            "hãy trả về ngay JSON:\n"
            '{"bbox_normalized": null, "raw_text": "", "plate_type": "unknown", "confidence": 0.0}\n'
            "Tuyệt đối không suy nghĩ hay giải thích dài dòng.\n\n"
            "Nếu có biển số xe, tọa độ bounding box chuẩn hóa theo thang đo 0 đến 1000: [ymin, xmin, ymax, xmax] "
            "(trong đó 0, 0 là góc trên bên trái, 1000, 1000 là góc dưới bên phải tấm ảnh).\n"
            "Yêu cầu trả về định dạng JSON thuần túy:\n"
            "{\n"
            '  "bbox_normalized": [ymin, xmin, ymax, xmax],\n'
            '  "raw_text": "chuỗi ký tự viết hoa không dấu cách (vd: 29AC88688)",\n'
            '  "plate_type": "one_line" hoặc "two_line",\n'
            '  "confidence": số thập phân từ 0.0 đến 1.0\n'
            "}"
        )

        user_content = [
            {
                "type": "text",
                "text": "Tìm vị trí biển số xe và đọc ký tự. Nếu không có xe, trả về bbox_normalized: null. Trả về đúng JSON.",
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_img}"
                },
            },
        ]

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
            "max_tokens": 120,
        }

        try:
            logger.info(f"9Router Vision: Đang tìm vị trí biển số & đọc ký tự trên toàn ảnh ({self.model})...")
            resp = self.session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )

            if resp.status_code != 200:
                logger.warning(f"9Router Vision detect trả về lỗi {resp.status_code}: {resp.text}")
                return {"raw_text": "", "plate_type": "unknown", "bbox": None, "confidence": 0.0}

            content = ""
            raw_body = resp.text.strip()
            if "text/event-stream" in resp.headers.get("content-type", "") or raw_body.startswith("data:"):
                for line in raw_body.splitlines():
                    line = line.strip()
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            chunk = json.loads(line[6:])
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content += delta.get("content", "")
                        except Exception:
                            pass
            else:
                try:
                    resp_json = resp.json()
                    content = resp_json["choices"][0]["message"]["content"].strip()
                except Exception:
                    content = raw_body

            logger.info(f"9Router Vision detect response: {content}")
            parsed_res = self._parse_model_output(content)

            # Trích xuất bounding box chuẩn hóa
            bbox_pixel = None
            clean_text = content.strip()
            clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r"\s*```$", "", clean_text).strip()
            try:
                parsed_json = json.loads(clean_text)
                bbox_norm = parsed_json.get("bbox_normalized")
                if bbox_norm and len(bbox_norm) == 4:
                    ymin, xmin, ymax, xmax = [float(v) for v in bbox_norm]
                    x1 = max(0, min(w, int(xmin * w / 1000.0)))
                    y1 = max(0, min(h, int(ymin * h / 1000.0)))
                    x2 = max(0, min(w, int(xmax * w / 1000.0)))
                    y2 = max(0, min(h, int(ymax * h / 1000.0)))
                    if x2 > x1 and y2 > y1:
                        bbox_pixel = [x1, y1, x2, y2]
            except Exception as e:
                logger.warning(f"Không thể trích xuất bbox từ 9Router: {e}")

            parsed_res["bbox"] = bbox_pixel
            return parsed_res

        except Exception as e:
            logger.error(f"Lỗi 9Router Vision detect_and_recognize_plate: {e}")
            return {"raw_text": "", "plate_type": "unknown", "bbox": None, "confidence": 0.0}

    def _parse_model_output(self, text: str) -> Dict[str, Any]:
        """Xử lý và parse JSON từ chuỗi văn bản của LLM (loại bỏ markdown block nếu có)."""
        clean_text = text.strip()
        # Loại bỏ ```json ... ``` nếu LLM bọc markdown
        clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"\s*```$", "", clean_text)
        clean_text = clean_text.strip()

        try:
            parsed = json.loads(clean_text)
            raw_text = str(parsed.get("raw_text", "")).strip()
            # Giữ lại chỉ ký tự chữ và số
            raw_text = re.sub(r"[^A-Za-z0-9]", "", raw_text).upper()
            plate_type = parsed.get("plate_type", "one_line")
            if plate_type not in ["one_line", "two_line"]:
                plate_type = "one_line"
            conf = float(parsed.get("confidence", 0.95))
            return {
                "raw_text": raw_text,
                "plate_type": plate_type,
                "confidence": conf,
            }
        except Exception:
            # Fallback nếu model trả văn bản thuần không phải JSON
            match = re.search(r"([0-9]{2}[A-Z0-9]{1,3}[0-9]{4,6})", re.sub(r"[^A-Za-z0-9]", "", clean_text.upper()))
            raw_text = match.group(1) if match else re.sub(r"[^A-Za-z0-9]", "", clean_text.upper())
            return {
                "raw_text": raw_text,
                "plate_type": "two_line" if len(raw_text) > 8 else "one_line",
                "confidence": 0.85,
            }

