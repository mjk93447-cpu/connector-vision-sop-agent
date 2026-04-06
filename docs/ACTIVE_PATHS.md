# Active Paths

Use this as the canonical map for future maintenance and agent exploration.

## Active entrypoints

- `src/main.py`: main SOP agent EXE entrypoint
- `scripts/run_pretrain_local.py`: canonical local pretrain runner
- `scripts/preflight_release.ps1`: release sanity gate

## Manual-only or legacy helpers

- `legacy/pretrain/prepare_pretrain_data.py`: optional manual dataset builder for dev use
- `legacy/pretrain/run_pretrain.py`: legacy pretrain runner, deprecated
- `legacy/pretrain/run_pretrain_compact.py`: legacy compact pretrain runner, deprecated
- `src/training/pretrain_pipeline.py`: legacy/manual pretrain pipeline, not the default runner

## Compatibility wrappers

- `scripts/prepare_pretrain_data.py`
- `scripts/run_pretrain.py`
- `scripts/run_pretrain_compact.py`

## Generated or pending paths

- `.claude/worktrees/`
- `.coverage`
- `build/`
- `dist/`
- `dist-ci/`
- `runs/`
- `pretrain_data_test/`
- `node_modules/`

## Artifact policy

- App artifact: EXE + launcher + config/models
- Pretrain artifact: EXE + launcher + model files only
- Pretrain datasets are excluded from GitHub artifacts and must be supplied locally if needed
