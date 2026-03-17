"""
YOLO26x button detection for Samsung OLED line UI automation.

Line UI: left 60% image + right 40% control panel.
Core targets: Mold ROI drag (100,200 -> 800,350) and Pin 40 cluster checks.

CP-3 변경사항:
  - Tesseract / pytesseract 완전 제거.
  - DetectionConfig에서 ocr_psm 필드 제거.
  - preprocess_for_ocr / read_text / locate_text / similarity 메서드 제거.
  - YOLO26x 단독 검출 방식으로 완전 전환.
"""

from __future__ import annotations

import os
import pathlib
import sys
from dataclasses import dataclass

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Redirect ultralytics config directory BEFORE importing YOLO.
# This avoids "Error decoding json from persistent_cache.json" crashes that
# occur on fresh line-PC installs where the default AppData path is missing
# or contains a corrupted file from a previous installation attempt.
# ---------------------------------------------------------------------------
_YOLO_CFG_DIR = str(pathlib.Path.home() / ".connector_vision_agent")
pathlib.Path(_YOLO_CFG_DIR).mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", _YOLO_CFG_DIR)

from ultralytics import YOLO  # noqa: E402

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
    "apply_button",
    "save_button",
    "axis_mark",
    "connector_pin",
]

DEFAULT_MOLD_ROI = ((100, 200), (800, 350))


@dataclass
class DetectionConfig:
    """Runtime thresholds and paths for YOLO26x detection.

    CP-3: ocr_psm 필드 제거 (Tesseract 완전 삭제).
    """

    model_path: str = "assets/models/yolo26x.pt"
    confidence_threshold: float = 0.6


@dataclass
class UiDetection:
    """Normalized UI detection record from YOLO inference."""

    label: str
    confidence: float
    bbox: tuple[int, int, int, int]


class VisionEngine:
    """YOLO26x helper for Samsung OLED line UI automation.

    CP-2: VisionAgent / VisionEngine 이중 계층 통합.
    CP-3: Tesseract / OCR 완전 제거, YOLO26x 단독 검출로 전환.
    """

    def __init__(
        self,
        config: DetectionConfig | None = None,
    ) -> None:
        self.config = config or DetectionConfig()
        self.model_path = self._resolve_runtime_path(self.config.model_path)
        self.model = self._load_model(self.model_path)

    # ------------------------------------------------------------------ #
    # 경로 해석 / 모델 로드
    # ------------------------------------------------------------------ #

    def _resolve_runtime_path(self, relative_path: str) -> str:
        """Resolve file paths for both source runs and PyInstaller EXE runs.

        Search order when frozen (PyInstaller EXE):
          1. Next to the EXE — assets/models/yolo26x.pt  (user-editable, deployed by bat)
          2. Inside _MEIPASS  — bundled copy inside the EXE's extracted temp dir
        Source-run: project root (parent of src/).
        """

        if os.path.isabs(relative_path):
            return relative_path

        if getattr(sys, "frozen", False):
            # 1st priority: alongside the EXE (Part1 package layout)
            exe_dir = os.path.dirname(sys.executable)
            candidate_exe = os.path.abspath(os.path.join(exe_dir, relative_path))
            if os.path.exists(candidate_exe):
                return candidate_exe
            # 2nd priority: inside _MEIPASS (bundled via PyInstaller datas)
            base_path = getattr(sys, "_MEIPASS", exe_dir)
        else:
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        return os.path.abspath(os.path.join(base_path, relative_path))

    def _load_model(self, model_path: str) -> YOLO | None:
        """Load YOLO weights when available without breaking scaffold runs.

        Priority:
        1. Local .pt file (offline line PC, assets/models/yolo26x.pt).
        2. yolo26x.pt base model auto-download (ultralytics >= 8.4.0).

        Model choice rationale — YOLO26x (released 2026-01-14):
          yolo26x (highest mAP in YOLO26 family) is the preferred base:
          - NMS-free end-to-end inference (DFL 제거)
          - YOLO26 계열 최고 정확도 → SOP 12단계 UI 검출 안정성 최우선
          - 속도보다 정확성/안정성 중시 (라인 PC SOP 자동화 특성)
          - 파인튜닝 후 12개 OLED UI 클래스에 특화
          ultralytics 버전 요구사항: >= 8.4.0
        """

        if os.path.exists(model_path):
            try:
                model = YOLO(model_path)
                model.overrides["verbose"] = False
                return model
            except Exception:
                return None

        # Local .pt not found — use yolo26x.pt as COCO-pretrained base model.
        # YOLO26x: highest mAP in the YOLO26 family, preferred for SOP accuracy.
        # Requires ultralytics >= 8.4.0 (YOLO26 support added 2026-01-14).
        try:
            model = YOLO("yolo26x.pt")  # auto-downloads from ultralytics hub
            model.overrides["verbose"] = False
            return model
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # 화면 캡처
    # ------------------------------------------------------------------ #

    def capture_screen(
        self, region: tuple[int, int, int, int] | None = None
    ) -> np.ndarray:
        """Capture the current screen and return a BGR image for OpenCV."""

        if pyautogui is None:
            raise RuntimeError(
                "pyautogui is unavailable in this environment."
            ) from PYAUTOGUI_IMPORT_ERROR

        screenshot = pyautogui.screenshot(region=region)  # pragma: no cover
        rgb_image = np.array(screenshot)  # pragma: no cover
        return cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)  # pragma: no cover

    # ------------------------------------------------------------------ #
    # 공통 이미지 헬퍼
    # ------------------------------------------------------------------ #

    @staticmethod
    def _to_gray(image: np.ndarray) -> np.ndarray:
        """Convert an image to grayscale while preserving existing grayscale."""

        if image.ndim == 2:
            return image.copy()
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # ------------------------------------------------------------------ #
    # YOLO 검출
    # ------------------------------------------------------------------ #

    def detect_objects(
        self, image: np.ndarray, conf_threshold: float | None = None
    ) -> list[UiDetection]:
        """Run YOLO inference and return normalized UI detections."""

        if self.model is None:
            return []

        confidence = conf_threshold or self.config.confidence_threshold
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

    def find_detection(
        self, image: np.ndarray, label: str, min_score: float | None = None
    ) -> UiDetection | None:
        """Return the highest-confidence detection for the requested label."""

        score_threshold = min_score or self.config.confidence_threshold
        matches = [
            detection
            for detection in self.detect_objects(image, conf_threshold=score_threshold)
            if detection.label == label
        ]
        if not matches:
            return None
        return max(matches, key=lambda detection: detection.confidence)

    # ------------------------------------------------------------------ #
    # ROI / 핀 헬퍼
    # ------------------------------------------------------------------ #

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

    #: Convenience alias — vision_panel and workers use the shorter name.
    detect = detect_objects

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


# ---------------------------------------------------------------------------
# 하위 호환 별칭 (CP-3 이후 제거 예정)
# ---------------------------------------------------------------------------

#: .. deprecated:: CP-2
#:    ``VisionEngine`` 을 직접 사용하세요.
VisionAgent = VisionEngine
