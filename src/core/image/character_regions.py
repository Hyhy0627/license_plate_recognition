"""Character-box proposals used when plate detection misses a region."""

from src.utils.logger import logger


def _ocr_character_regions(image, ocr_engine):
    """Propose plate crops from grouped character detections when plate YOLO misses."""
    character_model = getattr(ocr_engine, "yolo_ocr", None)
    if character_model is None:
        return []

    try:
        # Preserve small characters in full-scene images, including additional
        # plates that the detector missed. Crop OCR still runs at normal size.
        prediction = character_model.predict(image, conf=0.15, imgsz=1280, agnostic_nms=True, verbose=False)[0]
        boxes = []
        for box in prediction.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().tolist()
            confidence = float(box.conf[0].cpu().numpy())
            if x2 > x1 and y2 > y1:
                boxes.append({"bbox": [x1, y1, x2, y2], "confidence": confidence})
    except Exception as exc:
        logger.warning(f"OCR character fallback failed: {exc}")
        return []

    # OCR can return multiple classes for the same glyph. Keep the best box.
    boxes.sort(key=lambda item: item["confidence"], reverse=True)
    unique = []
    for candidate in boxes:
        x1, y1, x2, y2 = candidate["bbox"]
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        height = y2 - y1
        if any(
            abs(cx - (b["bbox"][0] + b["bbox"][2]) / 2) < 0.3 * height
            and abs(cy - (b["bbox"][1] + b["bbox"][3]) / 2) < 0.3 * height
            for b in unique
        ):
            continue
        unique.append(candidate)

    # Nearby glyphs on one or two lines form a connected plate candidate.
    parent = list(range(len(unique)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for i, first in enumerate(unique):
        ax1, ay1, ax2, ay2 = first["bbox"]
        acx, acy = (ax1 + ax2) / 2, (ay1 + ay2) / 2
        ah = ay2 - ay1
        for j in range(i + 1, len(unique)):
            bx1, by1, bx2, by2 = unique[j]["bbox"]
            bcx, bcy = (bx1 + bx2) / 2, (by1 + by2) / 2
            bh = by2 - by1
            threshold = 2.2 * max(ah, bh)
            if abs(acx - bcx) <= threshold and abs(acy - bcy) <= threshold:
                root_i, root_j = find(i), find(j)
                if root_i != root_j:
                    parent[root_j] = root_i

    clusters = {}
    for index, item in enumerate(unique):
        clusters.setdefault(find(index), []).append(item)

    height, width = image.shape[:2]
    proposals = []
    for cluster in clusters.values():
        if len(cluster) < 6:
            continue
        x1 = min(item["bbox"][0] for item in cluster)
        y1 = min(item["bbox"][1] for item in cluster)
        x2 = max(item["bbox"][2] for item in cluster)
        y2 = max(item["bbox"][3] for item in cluster)
        pad_x, pad_y = (x2 - x1) * 0.12, (y2 - y1) * 0.12
        bbox = [
            max(0, int(x1 - pad_x)), max(0, int(y1 - pad_y)),
            min(width, int(x2 + pad_x)), min(height, int(y2 + pad_y)),
        ]
        area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        if area <= 0 or area > width * height * 0.50:
            continue
        proposals.append({"bbox": bbox, "confidence": sum(item["confidence"] for item in cluster) / len(cluster)})

    return sorted(proposals, key=lambda item: item["confidence"], reverse=True)[:4]
