# connector-vision-sop-agent

Connector Vision SOP Agent v1.0 scaffold for Samsung OLED line automation.

## Goal

Automate the manual 12-step SOP with YOLOv26n, Tesseract OCR PSM7, and
PyAutoGUI so Mold ROI setup and pin verification can be executed quickly and
consistently on an offline line PC.

## Structure

- `src/main.py`: entry point
- `src/vision_engine.py`: button detection and OCR layer
- `src/control_engine.py`: click/drag automation layer
- `src/sop_executor.py`: 12-step SOP orchestration
- `src/config_loader.py`: JSON configuration loader
- `src/test_sop.py`: smoke test scaffold
- `assets/config.json`: line tuning template