# 5.1.0 Focus

Version 5.1.0 is the release where the shipping baseline is simplified around
two complete app packs and the archived pretrain stack is physically isolated
from day-to-day product work.

## Product center

- The packaged PyQt6 GUI remains the canonical user entrypoint.
- `Tab 1 - Run SOP`, `Tab 4 - SOP Editor`, and `Tab 7 - Training` remain the
  active surfaces for field work.
- `assets/models/yolo26x_local_pretrained.pt` remains the runtime model slot
  shared by fine-tuning and SOP execution.

## Packaging direction

- `connector-agent-app-cpu` is the standard full pack for broad compatibility.
- `connector-agent-app-gpu` is the CUDA-preferred full pack.
- Both packs share the same application code and feature set.
- The runtime difference is limited to the packaged torch stack.

## Engineering priorities

- Keep GUI, fine-tuning, SOP Run, SOP Editor, Config, Audit, and LLM flow
  behavior identical across CPU and GPU packs.
- Keep GPU-first fine-tuning behavior clear on NVIDIA-equipped PCs while
  preserving CPU fallback where the runtime flavor allows it.
- Keep archived pretrain code isolated under `legacy/pretrain/` so active app
  work and release flows do not drift into it by accident.

## Release expectations

5.1.0 should be considered healthy only if:

- `start_agent.bat` opens the PyQt6 GUI instead of the historical console app.
- CPU runtime validation passes on the current lab PC.
- GPU pack configuration points to a CUDA-enabled torch wheel in CI.
- Fine-tuning output is visible in the runtime slot used by SOP execution.
- SOP Editor save operations reload cleanly into Run SOP.
- Agent instructions remain usable from Claude, Cursor Codex sidebar, and
  ChatGPT 5.4 medium without Claude-only assumptions.
