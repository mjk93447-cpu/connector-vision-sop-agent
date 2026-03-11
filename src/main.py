"""
Main entry point for Connector Vision SOP Agent v1.0.

Priority path: src/main.py -> EXE build -> test validation for Samsung OLED
line deployment with YOLO, OCR, PyAutoGUI, JSON logging, and retry handling.
"""

from src.config_loader import load_config
from src.control_engine import ControlEngine
from src.sop_executor import SopExecutor
from src.vision_engine import DetectionConfig, VisionEngine


def _resolve_confidence_threshold(config: dict) -> float:
    """Support both flat and nested config layouts during scaffold evolution."""

    if "ocr_threshold" in config:
        return float(config["ocr_threshold"])
    return float(config.get("vision", {}).get("confidence_threshold", 0.6))


def _resolve_ocr_psm(config: dict) -> int:
    """Read OCR page segmentation mode with a sensible scaffold default."""

    return int(config.get("vision", {}).get("ocr_psm", 7))


def _resolve_retries(config: dict) -> int:
    """Read retry count from config or fall back to the default."""

    return int(config.get("control", {}).get("retries", 3))


def main() -> list[str]:
    """Build core services and execute the placeholder SOP sequence."""

    config = load_config()
    vision = VisionEngine(
        DetectionConfig(
            confidence_threshold=_resolve_confidence_threshold(config),
            ocr_psm=_resolve_ocr_psm(config),
        )
    )
    control = ControlEngine(retries=_resolve_retries(config))
    executor = SopExecutor(vision=vision, control=control)
    return executor.run()


if __name__ == "__main__":
    for log_line in main():
        print(log_line)
