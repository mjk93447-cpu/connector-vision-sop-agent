# Connector Vision SOP Agent Installation Guide

Version 4.5.0

## Canonical paths

- Main GUI entry: `src/gui_app.py`
- Packaged launcher: `assets/launchers/start_agent.bat`
- Active path map: `docs/ACTIVE_PATHS.md`
- Model naming: `docs/MODEL_ARTIFACT_NAMING.md`
- 4.5.0 focus: `docs/V4_5_0_FOCUS.md`

## Important policy

- The packaged app is GUI-first.
- Fine-tuning is the active training workflow.
- `yolo26x_local_pretrained.pt` is the preferred seed model.
- Pretrain generation scripts and datasets are archived and not part of normal
  line deployment.

## Bundle contents

The standard app bundle should contain:

- `connector_vision_agent.exe`
- `start_agent.bat`
- `stop_ollama.bat`
- `assets/config.json`
- `assets/sop_steps.json`
- `assets/models/yolo26x.pt`
- `assets/models/yolo26x_local_pretrained.pt`

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

- `scripts/run_pretrain_local.py`
- `scripts/run_pretrain.py`
- `scripts/run_pretrain_compact.py`
- `scripts/prepare_pretrain_data.py`
- `src/pretrain_runtime.py`
- `src/training/compact_pretrain_pipeline.py`
- `src/training/pretrain_pipeline.py`
