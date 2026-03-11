"""
Main entry point for Connector Vision SOP Agent v1.0.

Priority path: src/main.py -> EXE build -> test validation for Samsung OLED
line deployment with YOLO, OCR, PyAutoGUI, JSON logging, and retry handling.
"""

from src.config_loader import load_config
from src.control_engine import ControlEngine
from src.sop_executor import SopExecutor
from src.vision_engine import DetectionConfig, VisionEngine


def main() -> list[str]:
    """Build core services and execute the placeholder SOP sequence."""

    config = load_config()
    vision = VisionEngine(
        DetectionConfig(
            confidence_threshold=config["vision"]["confidence_threshold"],
            ocr_psm=config["vision"]["ocr_psm"],
        )
    )
    control = ControlEngine(retries=config["control"]["retries"])
    executor = SopExecutor(vision=vision, control=control)
    return executor.run()


if __name__ == "__main__":
    for log_line in main():
        print(log_line)
