# Active Paths

Use this file as the canonical map for future maintenance and agent exploration.

## Shared agent entrypoint

- `docs/AI_AGENT_GUIDE.md`: common workflow rules for Claude, Cursor Codex
  sidebar, and ChatGPT 5.4 medium

## Active entrypoints

- `src/gui_app.py`: canonical GUI application entrypoint for the packaged app
- `assets/launchers/start_agent.bat`: canonical launcher used in the app bundle
- `build_exe.spec`: PyInstaller spec for the GUI app bundle

## Active product areas

- `src/gui/panels/training_panel.py`: active fine-tuning UX and model reload flow
- `src/gui/panels/sop_editor_panel.py`: active SOP Editor implementation
- `src/gui/panels/sop_panel.py`: active SOP Run panel
- `src/gui/main_window.py`: top-level orchestration of the 7-tab GUI
- `src/model_artifacts.py`: canonical model naming and fine-tune seed resolution

## Archived pretrain paths

These paths are legacy/manual only and must not be used for new product work:

- `legacy/pretrain/README.md`
- `scripts/run_pretrain_local.py`
- `scripts/run_pretrain.py`
- `scripts/run_pretrain_compact.py`
- `scripts/prepare_pretrain_data.py`
- `src/pretrain_runtime.py`
- `src/training/compact_pretrain_pipeline.py`
- `src/training/pretrain_pipeline.py`
- `.github/workflows/build-pretrain.yml`
- `pretrain_exe.spec`
- `requirements-pretrain.txt`

Agent boundary:

- If the user request is about the shipping app, fine-tuning, SOP Editor, SOP Run,
  GUI QA, or release engineering, agents must stay out of the archived pretrain
  paths unless the user explicitly asks for historical pretrain maintenance.
- `.claudeignore` intentionally hides the archived pretrain tree and related tests
  from default agent exploration so they are not edited by accident.

## Artifact policy

- App bundle:
  - GUI EXE
  - launcher
  - config and SOP files
  - `yolo26x.pt`
  - `yolo26x_local_pretrained.pt`
- Archived pretrain bundle:
  - manual rebuild use only
  - never required for standard line deployment
- Pretrain datasets:
  - excluded from active app packaging
  - treated as archived local-only materials
