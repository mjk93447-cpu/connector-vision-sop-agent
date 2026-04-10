# connector-vision-sop-agent

Connector Vision SOP Agent 5.0.0 for offline OLED line operation.

## Canonical paths

- `src/gui_app.py`: main GUI entrypoint
- `assets/launchers/start_agent.bat`: packaged launcher
- `src/gui/panels/training_panel.py`: active fine-tuning flow
- `src/gui/panels/sop_editor_panel.py`: active SOP Editor flow
- `src/gui/panels/sop_panel.py`: active SOP Run flow
- `docs/ACTIVE_PATHS.md`: active vs archived path map
- `docs/MODEL_ARTIFACT_NAMING.md`: model naming rules
- `docs/V5_0_0_FOCUS.md`: 5.0.0 release focus
- `docs/AI_AGENT_GUIDE.md`: shared workflow guidance for Claude, Cursor Codex sidebar, and ChatGPT 5.4 medium

## Current product direction

Pretraining is complete. `assets/models/yolo26x_local_pretrained.pt` is the
active seed for Tab 7 fine-tuning, and `runs/detect/train/weights/best.pt`
is promoted back into that runtime slot after fine-tuning.

Archived pretrain code and dataset-prep paths remain in the repository only
for historical/manual rebuilds. Do not use them for new feature work, SOP
development, release engineering, or standard line deployment.

## Release highlights

- `5.0.0` standardizes the shipping app around the PyQt6 GUI bundle.
- Fine-tuning, SOP Editor, and SOP Run are the active product surfaces.
- CUDA runtime is packaged as a split overlay for faster app assembly while
  keeping NVIDIA acceleration available in offline deployments.
- Agent workflow guidance now covers Claude, Cursor Codex sidebar, and
  ChatGPT 5.4 medium instead of a Claude-only operating model.

## Build

```bat
build.bat
```

This builds the GUI app bundle EXE from `build_exe.spec`.

## Test

```bash
pytest -q
```

## Packaging policy

- App bundle includes:
  - `connector_vision_agent.exe`
  - `start_agent.bat`
  - `assets/config.json`
  - `assets/sop_steps.json`
  - `assets/models/yolo26x.pt`
  - `assets/models/yolo26x_local_pretrained.pt`
- Pretrain datasets are archived local-only materials and are excluded from the
  active app bundle.
