from __future__ import annotations

import argparse
import fnmatch
import json
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path, PurePosixPath

CUDA_PACKAGE_ROOTS = {
    "torch",
    "torchvision",
    "torchgen",
    "functorch",
    "torchvision.libs",
    "nvidia",
}

CUDA_FILENAME_PATTERNS = (
    "c10_cuda*.dll",
    "cublas*.dll",
    "cudart64*.dll",
    "cudnn*.dll",
    "cufft*.dll",
    "cupti*.dll",
    "curand*.dll",
    "cusolver*.dll",
    "cusparse*.dll",
    "nvjitlink*.dll",
    "nvrtc*.dll",
    "nvtx*.dll",
    "torch_cuda*.dll",
)

PLACEHOLDER_TEXT = """Drop the connector-agent-cuda-runtime artifact contents here:
  - _internal\\torch\\
  - _internal\\torchvision\\
  - _internal\\nvidia\\
  - CUDA-related DLLs listed in cuda_runtime_manifest.json

Merge order:
  1. Extract connector-agent-app-core.zip first.
  2. Extract connector-agent-cuda-runtime.zip into the same root folder.
  3. Keep the relative folder structure unchanged.
"""


@dataclass
class SplitSummary:
    source_root: str
    core_root: str
    cuda_root: str
    core_file_count: int
    cuda_file_count: int
    core_total_bytes: int
    cuda_total_bytes: int
    cuda_files: list[str]


def _normalize_relpath(path: Path, root: Path) -> PurePosixPath:
    return PurePosixPath(path.relative_to(root).as_posix())


def _package_root(parts: tuple[str, ...]) -> str | None:
    if not parts:
        return None
    if parts[0].lower() == "_internal" and len(parts) >= 2:
        return parts[1].lower()
    return parts[0].lower()


def is_cuda_runtime_path(relative_path: str | PurePosixPath) -> bool:
    rel = PurePosixPath(relative_path)
    package_root = _package_root(rel.parts)
    if package_root in CUDA_PACKAGE_ROOTS:
        return True

    filename = rel.name.lower()
    return any(fnmatch.fnmatch(filename, pattern) for pattern in CUDA_FILENAME_PATTERNS)


def _copy_file(source_file: Path, source_root: Path, target_root: Path) -> int:
    rel = source_file.relative_to(source_root)
    destination = target_root / rel
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_file, destination)
    return source_file.stat().st_size


def split_cuda_runtime(
    source_root: Path,
    core_root: Path,
    cuda_root: Path,
    manifest_path: Path | None = None,
) -> SplitSummary:
    if not source_root.exists():
        raise FileNotFoundError(f"Source root not found: {source_root}")

    if core_root.exists():
        shutil.rmtree(core_root)
    if cuda_root.exists():
        shutil.rmtree(cuda_root)

    core_root.mkdir(parents=True, exist_ok=True)
    cuda_root.mkdir(parents=True, exist_ok=True)

    core_file_count = 0
    cuda_file_count = 0
    core_total_bytes = 0
    cuda_total_bytes = 0
    cuda_files: list[str] = []

    for source_file in sorted(p for p in source_root.rglob("*") if p.is_file()):
        rel = _normalize_relpath(source_file, source_root)
        if is_cuda_runtime_path(rel):
            cuda_total_bytes += _copy_file(source_file, source_root, cuda_root)
            cuda_file_count += 1
            cuda_files.append(rel.as_posix())
        else:
            core_total_bytes += _copy_file(source_file, source_root, core_root)
            core_file_count += 1

    placeholder = core_root / "PLACE_CUDA_RUNTIME_HERE.txt"
    placeholder.write_text(PLACEHOLDER_TEXT, encoding="utf-8")

    summary = SplitSummary(
        source_root=str(source_root),
        core_root=str(core_root),
        cuda_root=str(cuda_root),
        core_file_count=core_file_count,
        cuda_file_count=cuda_file_count,
        core_total_bytes=core_total_bytes,
        cuda_total_bytes=cuda_total_bytes,
        cuda_files=cuda_files,
    )

    if manifest_path is not None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(asdict(summary), indent=2), encoding="utf-8")

    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split a PyInstaller one-folder app into core and CUDA overlay artifacts."
    )
    parser.add_argument("--source", required=True, help="Full assembled app folder to split.")
    parser.add_argument("--core-out", required=True, help="Output folder for the core app artifact.")
    parser.add_argument(
        "--cuda-out",
        required=True,
        help="Output folder for the CUDA runtime overlay artifact.",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Optional JSON manifest path listing files placed into the CUDA overlay.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    summary = split_cuda_runtime(
        source_root=Path(args.source),
        core_root=Path(args.core_out),
        cuda_root=Path(args.cuda_out),
        manifest_path=Path(args.manifest) if args.manifest else None,
    )
    print(
        "[split_cuda_runtime] "
        f"core_files={summary.core_file_count} cuda_files={summary.cuda_file_count} "
        f"core_bytes={summary.core_total_bytes} cuda_bytes={summary.cuda_total_bytes}"
    )


if __name__ == "__main__":
    main()
