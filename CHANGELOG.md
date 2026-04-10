# Changelog

## [5.1.0] - 2026-04-10

### Changed

- Simplified the shipping release into `connector-agent-app-cpu` and
  `connector-agent-app-gpu` full packs.
- Physically isolated archived pretrain code, launchers, specs, and tests under
  `legacy/pretrain/`.
- Reworked release helper and guard scripts so active app validation no longer
  traverses legacy pretrain paths.

### Fixed

- Updated the active test suite to match the current `src/main.py` helper API
  and restored the shared `config_file` fixture for config loader coverage.

### Docs

- Added `docs/V5_1_0_FOCUS.md` for the new release baseline.
- Updated install and deployment guides for CPU/GPU full-pack delivery.
- Updated active-path guidance so agents see `legacy/pretrain/` as the only
  archived pretrain boundary.

## [5.0.0] - 2026-04-10

### Changed

- Promoted the product baseline from `4.5.0` to `5.0.0`.
- Reframed the shipping package as `cpu` and `gpu` full app packs built from
  the same shared GUI codebase.
- Standardized fine-tuning so the active runtime slot is
  `assets/models/yolo26x_local_pretrained.pt`.
- Expanded agent workflow documentation so the same guidance works for Claude,
  Cursor Codex sidebar, and ChatGPT 5.4 medium.

### Fixed

- Added automatic promotion of `runs/detect/train/weights/best.pt` into the
  active local pretrained runtime slot after fine-tuning.
- Tightened GPU-first handling for fine-tuning and related offline runtime
  paths so NVIDIA-capable PCs do not silently drift into the wrong path.

### Docs

- Added the initial 5.x release-focus document for the new baseline.
- Added `docs/AI_AGENT_GUIDE.md` for cross-agent development workflow.
- Updated deployment, install, and QA documents for the `5.0.0` CPU/GPU full-pack release.

## [4.5.0] - 2026-04-08

### Changed

- Switched the packaged app entrypoint to `src/gui_app.py`.
- Updated `build_exe.spec` to build the GUI app with `console=False`.
- Re-centered the Training tab around `yolo26x_local_pretrained.pt`.
- Removed archived pretrain dataset placeholders from the active app bundle.

### Fixed

- Fixed the app-bundle launch bug where `start_agent.bat` started the old
  console program instead of the PyQt6 GUI.

### Docs

- Rewrote active-path guidance to separate active product work from archived
  pretrain code.
- Added `docs/V4_5_0_FOCUS.md` covering fine-tuning, SOP Editor, and SOP Run
  improvements.

## [4.4.0]

- Previous GUI app baseline.

## [1.0.0]

- Initial console-oriented release.
