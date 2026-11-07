"""Geometric plate candidates for scenes missed by the learned detector.

These are hypotheses, not detections: callers must validate the OCR observation.
The returned box is measured from the image and the crop is perspective-aligned.
"""
import cv2
import numpy as np


def quadrilateral_plate_regions(image, max_candidates=4):
    if image is None or image.size == 0:
        return []
    height, width = image.shape[:2]
    # Bound CPU/memory on large uploads; warp the final crop from original pixels.
    scale = min(1.0, 1280 / max(height, width))
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else image
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    smooth = cv2.medianBlur(gray, 5)
    residual = gray.astype(np.float32) - cv2.GaussianBlur(gray, (0, 0), 1).astype(np.float32)
    if float(residual.std()) > 25:
        # Find the outline on a noise-reduced image, but crop original pixels.
        smooth = cv2.GaussianBlur(gray, (0, 0), 3)
    mask = cv2.threshold(smooth, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    regions = []
    total_area = small.shape[0] * small.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:32]:
        area = cv2.contourArea(contour)
        if not 0.008 * total_area <= area <= 0.65 * total_area:
            continue
        rect = cv2.minAreaRect(contour)
        rw, rh = rect[1]
        if min(rw, rh) < 20 or area / max(1, rw * rh) < 0.80:
            continue
        quad = cv2.boxPoints(rect).astype(np.float32) / scale
        sums, diffs = quad.sum(axis=1), np.diff(quad, axis=1).ravel()
        corners = np.float32([quad[np.argmin(sums)], quad[np.argmin(diffs)], quad[np.argmax(sums)], quad[np.argmax(diffs)]])
        if len(np.unique(corners, axis=0)) != 4:
            continue
        w = int(max(np.linalg.norm(corners[1] - corners[0]), np.linalg.norm(corners[2] - corners[3])))
        h = int(max(np.linalg.norm(corners[3] - corners[0]), np.linalg.norm(corners[2] - corners[1])))
        if h < 15 or not 0.90 <= w / h <= 6:
            continue
        bbox = [max(0, int(corners[:, 0].min())), max(0, int(corners[:, 1].min())),
                min(width, int(np.ceil(corners[:, 0].max()))), min(height, int(np.ceil(corners[:, 1].max())))]
        if any(sum(abs(a - b) for a, b in zip(bbox, old['bbox'])) < 12 / scale for old in regions):
            continue
        target = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
        crop = cv2.warpPerspective(image, cv2.getPerspectiveTransform(corners, target), (w, h))
        regions.append({'bbox': bbox, 'crop': crop})
        if len(regions) >= max_candidates:
            break
    return regions
