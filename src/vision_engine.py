"""
YOLOv26n button detection + Tesseract OCR PSM7.

Line UI: left 60% image + right 40% control panel.
Core targets: Mold ROI drag (100,200 -> 800,350) and Pin 40 cluster checks.
"""

from dataclasses import dataclass


@dataclass
class DetectionConfig:
    """Runtime thresholds for object detection and OCR-assisted UI lookup."""

    confidence_threshold: float = 0.6
    ocr_psm: int = 7


class VisionEngine:
    """Stub vision engine for UI element detection and ROI guidance."""

    def __init__(self, config: DetectionConfig | None = None) -> None:
        self.config = config or DetectionConfig()

    def detect_ui_targets(self) -> list[str]:
        """Return placeholder target labels for the SOP automation flow."""

        return [
            "login_button",
            "recipe_button",
            "mold_left_label",
            "mold_right_label",
            "pin_cluster",
        ]
