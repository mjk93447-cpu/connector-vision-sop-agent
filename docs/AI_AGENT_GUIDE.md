# AI Agent Guide

This repository supports three common assistant environments:

- Claude-based coding agents
- Cursor Codex sidebar
- ChatGPT 5.4 medium used as a coding partner

The product and code rules should stay consistent across all three.

## Shared operating model

- Treat the PyQt6 GUI app as the main product.
- Treat `Tab 1 - Run SOP`, `Tab 4 - SOP Editor`, and `Tab 7 - Training` as
  the active surfaces for feature work and QA.
- Treat archived pretrain code as legacy-only unless the user explicitly asks
  for historical pretrain maintenance.
- Prefer targeted reads, targeted tests, and small patches over broad rewrites.

## Tool-specific interpretation

### Claude

- Follow `.claude/rules/*.md` as direct repository guidance.
- Use `.claudeignore` to avoid archived paths by default.

### Cursor Codex Sidebar

- Apply the same active-path policy even though `.claudeignore` is not native
  to the sidebar experience.
- Start from `docs/ACTIVE_PATHS.md` and this guide before exploring the repo.
- Avoid touching `legacy/pretrain/` and archived pretrain scripts unless the
  task explicitly requires them.

### ChatGPT 5.4 Medium

- Use the same active-path and model-priority rules when answering code or
  architecture questions.
- Prefer concise, high-signal edits and explanations over repo-wide summaries.
- If context is limited, prioritize `README.md`, `docs/ACTIVE_PATHS.md`,
  `docs/MODEL_ARTIFACT_NAMING.md`, and this guide first.

## Model and workflow priorities

- Runtime model priority:
  1. `assets/models/yolo26x_local_pretrained.pt`
  2. `assets/models/yolo26x_pretrain.pt`
  3. `assets/models/yolo26x.pt`
- Fine-tuning writes back into the active runtime slot via checkpoint
  promotion from `runs/detect/train/weights/best.pt`.
- SOP execution must validate against the same runtime slot used by the GUI.

## Documentation entrypoints

- `README.md`
- `README_INSTALL_EN.md`
- `docs/ACTIVE_PATHS.md`
- `docs/MODEL_ARTIFACT_NAMING.md`
- `docs/V5_0_0_FOCUS.md`
