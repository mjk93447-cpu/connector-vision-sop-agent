# Connector Vision SOP Agent Installation Guide

Version 5.1.0

## Canonical paths

- Main GUI entry: `src/gui_app.py`
- Packaged launcher: `assets/launchers/start_agent.bat`
- Active path map: `docs/ACTIVE_PATHS.md`
- Model naming: `docs/MODEL_ARTIFACT_NAMING.md`
- 5.1.0 focus: `docs/V5_1_0_FOCUS.md`
- Shared AI agent workflow: `docs/AI_AGENT_GUIDE.md`

## Important policy

- The packaged app is GUI-first.
- Fine-tuning is the active training workflow.
- `yolo26x_local_pretrained.pt` is the preferred seed model.
- `runs/detect/train/weights/best.pt` is promoted into the active runtime slot
  after fine-tuning completes.
- Pretrain generation scripts and datasets are archived and not part of normal
  line deployment.
- Claude-specific guidance has been generalized so the same operational rules
  also work in Cursor Codex sidebar and ChatGPT 5.4 medium sessions.

## Bundle contents

The standard app bundle should be either:

- `connector-agent-app-cpu`
- `connector-agent-app-gpu`

Both full packs include:

- `connector_vision_agent.exe`
- `start_agent.bat`
- `stop_ollama.bat`
- `assets/config.json`
- `assets/sop_steps.json`
- `assets/models/yolo26x.pt`
- `assets/models/yolo26x_local_pretrained.pt`

The Python runtime and packaged dependencies are embedded into
`connector_vision_agent.exe`, so deployment no longer depends on an external
`_internal` runtime folder.

## First launch

1. Copy the extracted app bundle to the target Windows PC.
2. Double-click `start_agent.bat`.
3. Confirm the PyQt6 GUI opens.
4. If the GUI does not open, treat that as a packaging defect.

## Daily operation

1. Use `Tab 1 - Run SOP` for production execution.
2. Use `Tab 4 - SOP Editor` for controlled SOP changes.
3. Use `Tab 7 - Training` for fine-tuning and model reload.

## Fine-tuning workflow

1. Collect annotated images for the target connector family.
2. Open `Tab 7 - Training`.
3. Confirm the base model is `yolo26x_local_pretrained.pt`.
4. Run fine-tuning.
5. Reload the new model.
6. Validate with `Tab 1 - Run SOP`.

## Archived material

Do not use these for new work unless you are intentionally rebuilding the
historical pretrain seed:

- `legacy/pretrain/`
