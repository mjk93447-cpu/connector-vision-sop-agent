"""Quick local runtime diagnostic for Ollama + CUDA workstation setup.

Run:
  python scripts/check_local_runtime.py

What it checks:
  - Proxy-related environment variables that can break localhost Ollama calls
  - Ollama context length / host / origin settings
  - CUDA / VRAM detection and NVIDIA fallback visibility
  - Whether the local machine looks ready for GPU-assisted training
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config_loader import detect_local_accelerator


@dataclass
class RuntimeCheck:
    name: str
    ok: bool
    detail: str


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return None
    return value


def collect_proxy_checks() -> list[RuntimeCheck]:
    checks: list[RuntimeCheck] = []

    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        value = _env(key)
        if value is None:
            checks.append(RuntimeCheck(key, True, "unset"))
        else:
            checks.append(RuntimeCheck(key, False, value))

    no_proxy = _env("NO_PROXY") or _env("no_proxy")
    if no_proxy is None:
        checks.append(RuntimeCheck("NO_PROXY", False, "unset"))
    else:
        required = {"localhost", "127.0.0.1", "::1"}
        parts = {part.strip() for part in no_proxy.split(",") if part.strip()}
        missing = sorted(required - parts)
        if missing:
            checks.append(
                RuntimeCheck("NO_PROXY", False, f"missing {', '.join(missing)}")
            )
        else:
            checks.append(RuntimeCheck("NO_PROXY", True, no_proxy))

    return checks


def collect_ollama_checks() -> list[RuntimeCheck]:
    checks: list[RuntimeCheck] = []

    host = _env("OLLAMA_HOST")
    checks.append(
        RuntimeCheck(
            "OLLAMA_HOST",
            bool(host and host.startswith("127.0.0.1")),
            host or "unset",
        )
    )

    origins = _env("OLLAMA_ORIGINS")
    checks.append(
        RuntimeCheck(
            "OLLAMA_ORIGINS",
            bool(origins == "*" or origins is None),
            origins or "unset",
        )
    )

    ctx = _env("OLLAMA_CONTEXT_LENGTH")
    if ctx is None:
        checks.append(RuntimeCheck("OLLAMA_CONTEXT_LENGTH", False, "unset"))
    else:
        checks.append(
            RuntimeCheck(
                "OLLAMA_CONTEXT_LENGTH",
                ctx != "0",
                ctx,
            )
        )

    return checks


def collect_cuda_checks() -> list[RuntimeCheck]:
    checks: list[RuntimeCheck] = []
    accel = detect_local_accelerator()

    gpu_present = bool(accel.get("gpu_present"))
    cuda_usable = bool(accel.get("cuda_usable"))
    name = accel.get("name") or "unknown"
    memory_gb = accel.get("memory_gb")

    checks.append(RuntimeCheck("GPU detected", gpu_present, str(name)))
    checks.append(RuntimeCheck("CUDA usable", cuda_usable, str(accel.get("device"))))
    checks.append(
        RuntimeCheck(
            "VRAM",
            memory_gb is not None and float(memory_gb) > 0,
            f"{memory_gb:.2f} GB" if isinstance(memory_gb, (int, float)) else "unavailable",
        )
    )

    return checks


def render_report() -> tuple[str, int]:
    sections: list[str] = []
    failures = 0

    def add_section(title: str, checks: list[RuntimeCheck]) -> None:
        nonlocal failures
        lines = [f"== {title} =="]
        for check in checks:
            status = "OK" if check.ok else "WARN"
            if not check.ok:
                failures += 1
            lines.append(f"[{status}] {check.name}: {check.detail}")
        sections.append("\n".join(lines))

    add_section("Proxy", collect_proxy_checks())
    add_section("Ollama", collect_ollama_checks())
    add_section("CUDA", collect_cuda_checks())

    summary = [
        "Local Runtime Diagnostic",
        f"Python: {sys.version.split()[0]}",
        "",
        *sections,
    ]
    if failures:
        summary.append("")
        summary.append(
            f"Result: {failures} warning(s) found. Check proxy and Ollama startup settings."
        )
    else:
        summary.append("")
        summary.append("Result: no obvious runtime issues detected.")

    return "\n".join(summary), failures


def main() -> int:
    report, failures = render_report()
    print(report)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
