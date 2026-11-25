"""Port for optional cloud vision used by recognition workflows."""

from typing import Any, Protocol

import numpy as np


class ICloudVisionClient(Protocol):
    def is_available(self) -> bool:
        ...

    def recognize_plate(self, plate_img: np.ndarray, timeout: float | None = None) -> dict[str, Any]:
        ...

    def detect_and_recognize_plate(self, image: np.ndarray, timeout: float | None = None) -> dict[str, Any]:
        ...
