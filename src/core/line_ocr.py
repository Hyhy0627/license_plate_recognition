"""Optional local line OCR for geometrically located crops YOLO cannot read."""
from pathlib import Path
import cv2

from src.core.postprocessor import PlatePostprocessor
from src.utils.logger import logger


class LocalLineOCR:
    def __init__(self, model_directory):
        self.model_directory = Path(model_directory)
        self.reader = None
        self.attempted = False

    def _load(self):
        if self.attempted:
            return self.reader
        self.attempted = True
        if not (self.model_directory / 'english_g2.pth').is_file():
            return None
        try:
            import easyocr
            self.reader = easyocr.Reader(
                ['en'], gpu=False, detector=False, download_enabled=False,
                model_storage_directory=str(self.model_directory),
                user_network_directory=str(self.model_directory / 'user_network'), verbose=False,
            )
        except Exception as exc:
            logger.warning(f'Local line OCR unavailable: {type(exc).__name__}')
        return self.reader

    def recognize(self, crop):
        empty = {'raw_text': '', 'text_lines': [], 'plate_type': 'unknown', 'avg_conf': 0.0,
                 'chars_count': 0, 'engine_used': 'local_easyocr'}
        if crop is None or crop.size == 0:
            return empty
        reader = self._load()
        if reader is None:
            return empty
        height, width = crop.shape[:2]
        two_line = width / max(1, height) < 2.2
        parts = [crop[:height // 2], crop[height // 2:]] if two_line else [crop]
        lines, scores = [], []
        try:
            for part in parts:
                readings = reader.recognize(part, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.',
                                            detail=1, paragraph=False, workers=0)
                if len(readings) != 1:
                    return empty
                lines.append(PlatePostprocessor.clean_text(readings[0][1]))
                scores.append(float(readings[0][2]))
        except Exception as exc:
            logger.warning(f'Local line OCR failed: {type(exc).__name__}')
            return empty
        text = ''.join(lines)
        plate_type = 'two_line' if two_line else 'one_line'
        formatted = PlatePostprocessor.format_vietnamese_plate(text, plate_type, lines)
        if not scores or min(scores) < 0.50 or sum(scores) / len(scores) < 0.70 or not PlatePostprocessor.validate_plate(formatted):
            return empty
        return {'raw_text': text, 'text_lines': lines, 'plate_type': plate_type,
                'avg_conf': sum(scores) / len(scores), 'chars_count': len(text), 'engine_used': 'local_easyocr'}
