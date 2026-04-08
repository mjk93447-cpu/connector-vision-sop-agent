# Changelog

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
