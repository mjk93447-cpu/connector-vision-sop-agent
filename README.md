# connector-vision-sop-agent

Connector Vision SOP Agent for offline OLED line operation.

## Canonical paths

- `src/gui_app.py`: main GUI entrypoint
- `assets/launchers/start_agent.bat`: packaged launcher
- `src/gui/panels/training_panel.py`: active fine-tuning flow
- `src/gui/panels/sop_editor_panel.py`: active SOP Editor flow
- `src/gui/panels/sop_panel.py`: active SOP Run flow
- `docs/ACTIVE_PATHS.md`: active vs archived path map
- `docs/MODEL_ARTIFACT_NAMING.md`: model naming rules
- `docs/V4_5_0_FOCUS.md`: 4.5.0 development focus

## Current product direction

Pretraining is complete. `assets/models/yolo26x_local_pretrained.pt` is the
active seed for Tab 7 fine-tuning.

Archived pretrain code and dataset-prep paths remain in the repository only
for historical/manual rebuilds. Do not use them for new feature work.

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
