from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.vision_engine import DetectionConfig, VisionEngine


def test_vision_engine_reload_model_uses_config_path() -> None:
    cfg = DetectionConfig(model_path="assets/models/yolo26x_local_pretrained.pt")
    mocked_model = object()
    with patch.object(VisionEngine, "_load_model", return_value=mocked_model) as loader:
        engine = VisionEngine(config=cfg)
        ok = engine.reload_model()
    assert ok is True
    assert engine.model is mocked_model
    # __init__ load + reload load
    assert loader.call_count == 2
    assert "yolo26x_local_pretrained.pt" in loader.call_args_list[-1].args[0]


def test_main_build_services_respects_config_model_path() -> None:
    config = {
        "vision": {
            "model_path": "assets/models/yolo26x_local_pretrained.pt",
            "confidence_threshold": 0.55,
            "ocr_psm": 8,
        },
        "control": {"retries": 2},
    }
    with patch("src.main.load_config", return_value=config), patch(
        "src.main.VisionEngine"
    ) as vision_cls, patch("src.main.ControlEngine"), patch("src.main.SopExecutor"):
        from src.main import _build_services

        _build_services()

    vision_cfg = vision_cls.call_args.args[0]
    assert vision_cfg.model_path == "assets/models/yolo26x_local_pretrained.pt"
    assert vision_cfg.confidence_threshold == 0.55
    assert vision_cfg.ocr_psm == 8


def test_gui_build_runtime_respects_config_model_path() -> None:
    config = {
        "line_id": "LINE-A3",
        "vision": {
            "model_path": "assets/models/yolo26x_local_pretrained.pt",
            "confidence_threshold": 0.5,
            "ocr_psm": 6,
        },
        "ocr": {"threshold": 0.77},
        "llm": {"enabled": False},
    }
    vision_instance = MagicMock()
    with patch("src.gui_app.VisionEngine", return_value=vision_instance) as vision_cls, patch(
        "src.gui_app.OCREngine"
    ), patch("src.gui_app.ControlEngine"), patch("src.gui_app.SopExecutor"):
        from src.gui_app import _build_runtime

        _build_runtime(config)

    vision_cfg = vision_cls.call_args.args[0]
    assert vision_cfg.model_path == "assets/models/yolo26x_local_pretrained.pt"
    assert vision_cfg.confidence_threshold == 0.5
    assert vision_cfg.ocr_psm == 6
