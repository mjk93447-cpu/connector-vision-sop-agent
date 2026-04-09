"""
YOLOv26x button detection + Tesseract OCR PSM7.

Line UI: left 60% image + right 40% control panel.
Core targets: Mold ROI drag (100,200 -> 800,350) and Pin 40 cluster checks.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher

import cv2
import numpy as np
import pytesseract
from ultralytics import YOLO

try:
    import pyautogui
except Exception as exc:  # pragma: no cover - depends on display availability.
    pyautogui = None
    PYAUTOGUI_IMPORT_ERROR = exc
else:  # pragma: no cover - environment dependent branch.
    PYAUTOGUI_IMPORT_ERROR = None


DEFAULT_TARGET_LABELS = [
    "login_button",
    "recipe_button",
    "register_button",
    "open_icon",
    "image_source",
    "mold_left_label",
    "mold_right_label",
    "pin_cluster",
]

DEFAULT_MOLD_ROI = ((100, 200), (800, 350))


@dataclass
class DetectionConfig:
    """Runtime thresholds for object detection and OCR-assisted UI lookup."""
    model_path: str = "assets/models/yolo26x.pt"

    confidence_threshold: float = 0.6
    ocr_psm: int = 7


@dataclass
class UiDetection:
    """Normalized UI detection record from YOLO inference."""

    label: str
    confidence: float
    bbox: tuple[int, int, int, int]


class VisionAgent:
    """YOLO + OCR helper for Samsung OLED line UI automation."""

    def __init__(
        self,
        model_path: str | None = None,
        confidence_threshold: float = 0.6,
        ocr_psm: int = 7,
    ) -> None:
        resolved_model_path = model_path or "assets/models/yolo26x.pt"
        self.model_path = self._resolve_runtime_path(resolved_model_path)
        self.confidence_threshold = confidence_threshold
        self.ocr_psm = ocr_psm
        self.model = self._load_model(self.model_path)

    def _resolve_runtime_path(self, relative_path: str) -> str:
        """Resolve file paths for both source runs and PyInstaller EXE runs."""

        if os.path.isabs(relative_path):
            return relative_path

        if getattr(sys, "frozen", False):
            base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        else:
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        return os.path.abspath(os.path.join(base_path, relative_path))

    def _load_model(self, model_path: str) -> YOLO | None:
        """
        Load YOLO weights when available without breaking scaffold runs.

        Priority:
        1. Use a local .pt file if it exists (offline line PC, assets/models/yolo26x.pt).
        2. If the local file is missing, fall back to the Ultralytics hub name
           (e.g. 'yolo26x.pt') so that CI or online dev machines can auto-download.
        """

        if os.path.exists(model_path):
            return YOLO(model_path)

        # Fall back to model name only (Ultralytics will download if possible).
        name = os.path.basename(model_path)
        try:
            return YOLO(name)
        except Exception:
            return None

    def reload_model(self, model_path: str | None = None) -> bool:
        """Reload YOLO weights at runtime.

        Parameters
        ----------
        model_path:
            Optional explicit path. When omitted, reloads from the currently
            configured ``self.model_path``.

        Returns
        -------
        bool
            ``True`` when a model instance was loaded successfully,
            otherwise ``False``.
        """

        if model_path is not None:
            self.model_path = self._resolve_runtime_path(model_path)

        self.model = self._load_model(self.model_path)
        return self.model is not None

    def capture_screen(
        self, region: tuple[int, int, int, int] | None = None
    ) -> np.ndarray:
        """Capture the current screen and return a BGR image for OpenCV."""

        if pyautogui is None:
            raise RuntimeError(
                "pyautogui is unavailable in this environment."
            ) from PYAUTOGUI_IMPORT_ERROR

        screenshot = pyautogui.screenshot(region=region)
        rgb_image = np.array(screenshot)
        return cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)

    @staticmethod
    def _to_gray(image: np.ndarray) -> np.ndarray:
        """Convert an image to grayscale while preserving existing grayscale."""

        if image.ndim == 2:
            return image.copy()
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    def preprocess_for_ocr(self, image: np.ndarray) -> np.ndarray:
        """Sharpen OCR targets for English button labels such as Mold Left."""

        gray = self._to_gray(image)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        _, binary = cv2.threshold(
            blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        return binary

    def read_text(self, image: np.ndarray) -> str:
        """Read a text string from the supplied ROI using Tesseract PSM 7."""

        processed = self.preprocess_for_ocr(image)
        config = f"--psm {self.ocr_psm}"
        return pytesseract.image_to_string(processed, config=config).strip()

    @staticmethod
    def similarity(left: str, right: str) -> float:
        """Measure fuzzy similarity between OCR output and target labels."""

        return SequenceMatcher(None, left.lower(), right.lower()).ratio()

    def locate_text(
        self, image: np.ndarray, target_text: str, min_score: float = 0.65
    ) -> dict[str, object] | None:
        """Locate the best OCR text match and return its box and score."""

        processed = self.preprocess_for_ocr(image)
        ocr_data = pytesseract.image_to_data(
            processed,
            config=f"--psm {self.ocr_psm}",
            output_type=pytesseract.Output.DICT,
        )

        best_match: dict[str, object] | None = None
        for index, raw_text in enumerate(ocr_data["text"]):
            text = raw_text.strip()
            if not text:
                continue

            score = self.similarity(text, target_text)
            if best_match is None or score > float(best_match["score"]):
                left = int(ocr_data["left"][index])
                top = int(ocr_data["top"][index])
                width = int(ocr_data["width"][index])
                height = int(ocr_data["height"][index])
                best_match = {
                    "text": text,
                    "score": score,
                    "bbox": (left, top, left + width, top + height),
                }

        if best_match and float(best_match["score"]) >= min_score:
            return best_match
        return None

    def detect_objects(
        self, image: np.ndarray, conf_threshold: float | None = None
    ) -> list[UiDetection]:
        """Run YOLO inference and return normalized UI detections."""

        if self.model is None:
            return []

        confidence = conf_threshold or self.confidence_threshold
        results = self.model.predict(source=image, conf=confidence, verbose=False)
        detections: list[UiDetection] = []

        for result in results:
            names = result.names
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue

            for box in boxes:
                coords = box.xyxy[0].cpu().numpy().astype(int).tolist()
                class_id = int(box.cls[0].item())
                label = names.get(class_id, str(class_id))
                score = float(box.conf[0].item())
                detections.append(
                    UiDetection(label=label, confidence=score, bbox=tuple(coords))
                )

        return detections

    def detect_roi(
        self,
        image: np.ndarray,
        roi: tuple[int, int, int, int],
        conf_threshold: float | None = None,
    ) -> list[UiDetection]:
        """Run detection inside a cropped region of interest."""

        x1, y1, x2, y2 = roi
        cropped = image[y1:y2, x1:x2]
        detections = self.detect_objects(cropped, conf_threshold=conf_threshold)

        adjusted: list[UiDetection] = []
        for detection in detections:
            dx1, dy1, dx2, dy2 = detection.bbox
            adjusted.append(
                UiDetection(
                    label=detection.label,
                    confidence=detection.confidence,
                    bbox=(dx1 + x1, dy1 + y1, dx2 + x1, dy2 + y1),
                )
            )
        return adjusted

    def find_detection(
        self,
        image: np.ndarray,
        label: str,
        min_score: float | None = None,
        roi: tuple[int, int, int, int] | None = None,
    ) -> UiDetection | None:
        """Return the highest-confidence detection for the requested label."""

        score_threshold = min_score or self.confidence_threshold
        if roi is None:
            candidates = self.detect_objects(image, conf_threshold=score_threshold)
        else:
            candidates = self.detect_roi(
                image, roi=roi, conf_threshold=score_threshold
            )
        matches = [
            detection
            for detection in candidates
            if detection.label == label
        ]
        if not matches:
            return None
        return max(matches, key=lambda detection: detection.confidence)

    @staticmethod
    def normalize_roi(
        start: tuple[int, int] = DEFAULT_MOLD_ROI[0],
        end: tuple[int, int] = DEFAULT_MOLD_ROI[1],
    ) -> tuple[tuple[int, int], tuple[int, int]]:
        """Normalize drag points into top-left and bottom-right corners."""

        x1, y1 = start
        x2, y2 = end
        return (min(x1, x2), min(y1, y2)), (max(x1, x2), max(y1, y2))

    def extract_pin_centers(self, image: np.ndarray) -> list[tuple[int, int]]:
        """Extract blob centers that approximate connector pin locations."""

        gray = self._to_gray(image)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, binary = cv2.threshold(
            blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        pin_centers: list[tuple[int, int]] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 8:
                continue
            x, y, width, height = cv2.boundingRect(contour)
            pin_centers.append((x + width // 2, y + height // 2))

        return sorted(pin_centers, key=lambda point: (point[1], point[0]))

    def validate_pin_count(
        self, image: np.ndarray, pin_count_min: int = 20
    ) -> dict[str, object]:
        """Validate whether the detected pin count satisfies the SOP minimum."""

        centers = self.extract_pin_centers(image)
        return {
            "count": len(centers),
            "pin_count_min": pin_count_min,
            "valid": len(centers) >= pin_count_min,
            "centers": centers,
        }

    def detect_ui_targets(self, image: np.ndarray | None = None) -> list[str]:
        """Return detected labels when possible, otherwise use SOP defaults."""

        if image is None:
            return DEFAULT_TARGET_LABELS.copy()

        detections = self.detect_objects(image)
        if not detections:
            return DEFAULT_TARGET_LABELS.copy()

        ordered_labels: list[str] = []
        for detection in detections:
            if detection.label not in ordered_labels:
                ordered_labels.append(detection.label)
        return ordered_labels


class VisionEngine(VisionAgent):
    """Compatibility wrapper used by the scaffold main execution path."""

    def __init__(
        self,
        config: DetectionConfig | None = None,
        model_path: str | None = None,
    ) -> None:
        self.config = config or DetectionConfig()
        resolved_model_path = model_path or self.config.model_path
        super().__init__(
            model_path=resolved_model_path,
            confidence_threshold=self.config.confidence_threshold,
            ocr_psm=self.config.ocr_psm,
        )

    def reload_model(self, model_path: str | None = None) -> bool:
        """Reload model using explicit path, config path, or current path."""

        effective_path = model_path or self.config.model_path
        return super().reload_model(effective_path)
