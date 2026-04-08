# Windows GUI QA Runbook

This runbook defines the practical 4.5.0 QA flow for the current lab PC.

## Environment baseline

- OS: Windows 10 Pro 10.0.19045
- Display: 1920x1080
- GPU/CUDA: CPU-only fallback validation
- GUI launch target: packaged EXE plus `start_agent.bat`

## QA objectives

1. Verify the packaged app opens the PyQt6 GUI window.
2. Verify `SOP Editor -> Save -> Run SOP` continuity.
3. Verify the SOP execution core can navigate common Windows Settings flows.

## Repository QA assets

- `qa/scenarios/windows_settings_smoke.json`
- `qa/scenarios/windows_settings_colors_toggle.json`
- `qa/scenarios/windows_settings_navigation_deep.json`
- `scripts/run_gui_bundle_smoke.ps1`
- `scripts/run_windows_scenario_qa.py`

## Recommended execution order

1. Build the GUI EXE.
2. Assemble a local bundle with launcher, EXE, and assets.
3. Run `scripts/run_gui_bundle_smoke.ps1`.
4. Run `python scripts/run_windows_scenario_qa.py --scenario qa/scenarios/windows_settings_smoke.json`
5. If stable, run the colors toggle scenario.
6. If still stable, run the deep navigation scenario.

## Evidence to collect

- GUI smoke JSON report
- Scenario JSON report(s)
- Any SOP log or audit output
- Notes on manual intervention, if any

## Interpretation

- Pass:
  - GUI window detected
  - smoke scenario completes without failure
- Conditional pass:
  - GUI opens but one scenario fails in a reproducible way
- Fail:
  - GUI window not detected
  - scenario chain breaks before completing the basic navigation path
