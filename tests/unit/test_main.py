from __future__ import annotations

from unittest.mock import patch


class TestResolveConfidenceThreshold:
    def test_prefers_flat_ocr_threshold_when_present(self) -> None:
        from src.main import _resolve_confidence_threshold

        cfg = {"ocr_threshold": 0.42, "vision": {"confidence_threshold": 0.75}}
        assert _resolve_confidence_threshold(cfg) == 0.42

    def test_falls_back_to_nested_vision_threshold(self) -> None:
        from src.main import _resolve_confidence_threshold

        cfg = {"vision": {"confidence_threshold": "0.8"}}
        assert _resolve_confidence_threshold(cfg) == 0.8

    def test_uses_default_when_missing(self) -> None:
        from src.main import _resolve_confidence_threshold

        assert _resolve_confidence_threshold({}) == 0.6


class TestResolveOcrPsm:
    def test_reads_nested_ocr_psm(self) -> None:
        from src.main import _resolve_ocr_psm

        assert _resolve_ocr_psm({"vision": {"ocr_psm": 11}}) == 11

    def test_defaults_to_7(self) -> None:
        from src.main import _resolve_ocr_psm

        assert _resolve_ocr_psm({}) == 7


class TestResolveRuntimeModelPath:
    def test_delegates_to_runtime_model_resolver(self) -> None:
        import src.main as app_main

        with patch.object(
            app_main,
            "resolve_runtime_model",
            return_value="C:/bundle/assets/models/yolo26x_local_pretrained.pt",
        ) as mock_resolve:
            result = app_main._resolve_runtime_model_path(
                {"vision": {"model_path": "assets/models/yolo26x.pt"}}
            )

        mock_resolve.assert_called_once_with("assets/models/yolo26x.pt")
        assert result.replace("\\", "/").endswith(
            "assets/models/yolo26x_local_pretrained.pt"
        )


class TestResolveRetries:
    def test_reads_retries_from_control_block(self) -> None:
        from src.main import _resolve_retries

        assert _resolve_retries({"control": {"retries": 8}}) == 8

    def test_defaults_to_3(self) -> None:
        from src.main import _resolve_retries

        assert _resolve_retries({}) == 3


class TestBuildServices:
    def test_returns_three_services(self) -> None:
        from src.main import _build_services
        from src.vision_engine import VisionEngine
        from src.control_engine import ControlEngine
        from src.sop_executor import SopExecutor

        cfg = {
            "vision": {
                "model_path": "assets/models/yolo26x_local_pretrained.pt",
                "confidence_threshold": 0.6,
                "ocr_psm": 7,
            },
            "control": {"retries": 5},
        }

        with (
            patch("src.main.load_config", return_value=cfg),
            patch.object(VisionEngine, "_load_model", return_value=None),
        ):
            vision, control, executor = _build_services(speed="normal")

        assert isinstance(vision, VisionEngine)
        assert isinstance(control, ControlEngine)
        assert isinstance(executor, SopExecutor)
        assert control.retries == 5

    def test_speed_preset_fast_uses_shorter_delays(self) -> None:
        import src.main as app_main

        cfg = {
            "vision": {
                "model_path": "assets/models/yolo26x_local_pretrained.pt",
                "confidence_threshold": 0.6,
                "ocr_psm": 7,
            },
            "control": {"retries": 3},
        }

        with (
            patch.object(app_main, "load_config", return_value=cfg),
            patch.object(app_main.VisionEngine, "_load_model", return_value=None),
        ):
            _, control, _ = app_main._build_services(speed="fast")

        assert control.move_duration == 0.05
        assert control.click_pause == 0.01


class TestMainFunction:
    def test_main_runs_executor_once_and_returns_trace(self) -> None:
        import src.main as app_main

        fake_trace = ["step1:OK: login", "step2:OK: save"]

        class _FakeExecutor:
            def run(self):
                return fake_trace

        with patch.object(
            app_main, "_build_services", return_value=(object(), object(), _FakeExecutor())
        ):
            result = app_main.main()

        assert result == fake_trace
