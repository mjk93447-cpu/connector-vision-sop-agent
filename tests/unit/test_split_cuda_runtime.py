from __future__ import annotations

import json
from pathlib import Path

from scripts.split_cuda_runtime import is_cuda_runtime_path, split_cuda_runtime


def test_is_cuda_runtime_path_flags_torch_tree_and_cuda_dlls() -> None:
    assert is_cuda_runtime_path("_internal/torch/__init__.py")
    assert is_cuda_runtime_path("_internal/torchvision/ops.py")
    assert is_cuda_runtime_path("_internal/nvidia/cublas/bin/cublas64_12.dll")
    assert is_cuda_runtime_path("_internal/cudart64_12.dll")
    assert not is_cuda_runtime_path("assets/config.json")
    assert not is_cuda_runtime_path("connector_vision_agent.exe")


def test_split_cuda_runtime_preserves_overlay_layout(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    (source_root / "_internal/torch/lib").mkdir(parents=True, exist_ok=True)
    (source_root / "_internal/torchvision").mkdir(parents=True, exist_ok=True)
    (source_root / "_internal").mkdir(parents=True, exist_ok=True)
    (source_root / "assets").mkdir(parents=True, exist_ok=True)

    (source_root / "connector_vision_agent.exe").write_bytes(b"exe")
    (source_root / "assets/config.json").write_text("{}", encoding="utf-8")
    (source_root / "_internal/torch/__init__.py").write_text("# torch", encoding="utf-8")
    (source_root / "_internal/torch/lib/cublas64_12.dll").write_bytes(b"cuda")
    (source_root / "_internal/torchvision/ops.py").write_text("# vision", encoding="utf-8")
    (source_root / "_internal/cudart64_12.dll").write_bytes(b"cuda-dll")

    core_root = tmp_path / "core"
    cuda_root = tmp_path / "cuda"
    manifest_path = cuda_root / "cuda_runtime_manifest.json"

    summary = split_cuda_runtime(
        source_root, core_root, cuda_root, manifest_path, runtime_flavor="gpu"
    )

    assert (core_root / "connector_vision_agent.exe").exists()
    assert (core_root / "assets/config.json").exists()
    assert not (core_root / "_internal/torch/__init__.py").exists()
    assert (cuda_root / "_internal/torch/__init__.py").exists()
    assert (cuda_root / "_internal/torch/lib/cublas64_12.dll").exists()
    assert (cuda_root / "_internal/torchvision/ops.py").exists()
    assert (cuda_root / "_internal/cudart64_12.dll").exists()
    assert (core_root / "PLACE_RUNTIME_HERE.txt").exists()
    assert (cuda_root / "runtime_gpu.marker").exists()
    assert summary.cuda_file_count == 4

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["runtime_flavor"] == "gpu"
    assert "_internal/torch/__init__.py" in manifest["cuda_files"]
    assert "_internal/cudart64_12.dll" in manifest["cuda_files"]
