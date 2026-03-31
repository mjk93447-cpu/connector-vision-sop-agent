"""
Automated offline environment verification script.
Run: python tests/manual_offline_check.py
"""

import os
import tempfile
import pathlib
from unittest.mock import patch


def check_llm_offline_config():
    print("\n=== LLM Offline Config ===")
    from src.llm_offline import OfflineLLM, _HEALTH_TIMEOUT
    import inspect
    import src.llm_offline as m

    llm = OfflineLLM.from_config(
        {"backend": "ollama", "model_path": "pedrolucas/smollm3:3b-q4_k_m"}
    )
    sess = llm._get_session()
    assert sess.trust_env is False
    print("[OK] trust_env=False (proxy bypass)")

    assert _HEALTH_TIMEOUT >= 30
    print(f"[OK] _HEALTH_TIMEOUT={_HEALTH_TIMEOUT}s")

    src_stream = inspect.getsource(m.OfflineLLM._stream_ollama)
    assert "timeout=(10, 180)" in src_stream
    print("[OK] _stream_ollama timeout=(10, 180)")

    src_chat = inspect.getsource(m.OfflineLLM._chat_ollama)
    assert 'payload["think"]' not in src_chat
    print("[OK] think=False removed from _chat_ollama")

    assert 'payload["think"]' not in src_stream
    print("[OK] think=False removed from _stream_ollama")

    from src.gui.workers import LLMStreamWorker

    assert LLMStreamWorker._STREAM_TIMEOUT_SECS >= 180
    print(
        f"[OK] LLMStreamWorker._STREAM_TIMEOUT_SECS={LLMStreamWorker._STREAM_TIMEOUT_SECS}s"
    )


def check_training_offline_env():
    print("\n=== Training Offline Env Vars ===")
    from src.training.training_manager import TrainingManager

    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        model = td / "yolo26x.pt"
        model.touch()
        imgs = td / "images"
        imgs.mkdir()
        for i in range(3):
            (imgs / f"img{i}.jpg").touch()
        (td / "labels").mkdir()
        dyaml = td / "dataset.yaml"
        td_fwd = str(td).replace("\\", "/")
        dyaml.write_text(f"path: {td_fwd}\ntrain: images\nnc: 1\nnames: [pin]\n")

        captured_env = {}

        class FakeModel:
            def train(self, **kw):
                captured_env.update(
                    {
                        "YOLO_OFFLINE": os.environ.get("YOLO_OFFLINE"),
                        "ULTRALYTICS_OFFLINE": os.environ.get("ULTRALYTICS_OFFLINE"),
                        "WANDB_DISABLED": os.environ.get("WANDB_DISABLED"),
                        "COMET_MODE": os.environ.get("COMET_MODE"),
                        "NEPTUNE_MODE": os.environ.get("NEPTUNE_MODE"),
                    }
                )
                raise SystemExit(0)

        with patch("ultralytics.YOLO", return_value=FakeModel()):
            try:
                tm = TrainingManager(str(model))
                tm.train(dataset_yaml=str(dyaml), epochs=1)
            except SystemExit:
                pass

        checks = [
            ("YOLO_OFFLINE", "1"),
            ("ULTRALYTICS_OFFLINE", "1"),
            ("WANDB_DISABLED", "true"),
            ("COMET_MODE", "disabled"),
            ("NEPTUNE_MODE", "offline"),
        ]
        for key, expected in checks:
            val = captured_env.get(key)
            status = "OK" if val == expected else "FAIL"
            print(f"[{status}] {key}={val!r}")


def check_tqdm_patch():
    print("\n=== ultralytics TQDM Patch ===")
    from src.training.training_manager import TrainingManager

    TrainingManager._apply_ultralytics_tqdm_patch()

    try:
        import ultralytics.utils as u

        assert u.VERBOSE is True
        print("[OK] ultralytics.utils.VERBOSE=True")
    except ImportError:
        print("[SKIP] ultralytics not installed")

    try:
        from ultralytics.utils.tqdm import TQDM

        assert getattr(TQDM, "_safe_close_patched", False)
        print("[OK] TQDM._safe_close_patched=True")
    except ImportError:
        print("[SKIP] ultralytics.utils.tqdm not available")


def check_install_bat():
    print("\n=== install_first_time.bat Offline Checks ===")
    bat_path = pathlib.Path("install_first_time.bat")
    if not bat_path.exists():
        print("[SKIP] install_first_time.bat not found")
        return
    content = bat_path.read_text(encoding="utf-8", errors="replace")
    checks = [
        ("manifests", "manifests/ folder check"),
        ("ollama list", "pre-check before pull"),
        ("smollm3", "correct model name"),
        ("OLLAMA_MODELS", "OLLAMA_MODELS env var set"),
    ]
    for keyword, desc in checks:
        status = "OK" if keyword in content else "FAIL"
        print(f"[{status}] {desc} ({keyword!r})")


if __name__ == "__main__":
    check_llm_offline_config()
    check_training_offline_env()
    check_tqdm_patch()
    check_install_bat()
    print("\n[DONE] All automated checks complete.")
