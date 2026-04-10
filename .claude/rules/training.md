# Training Rules

These rules define the product truth for any coding agent. Claude-specific
tooling may enforce them more directly, but the same path and model decisions
also apply in Cursor Codex sidebar and ChatGPT 5.4 medium sessions.

## Active path

- `src/gui/panels/training_panel.py`
- `src/training/dataset_manager.py`
- `src/training/training_manager.py`
- `src/model_artifacts.py`

## Active model priority

1. `assets/models/yolo26x_local_pretrained.pt`
2. `assets/models/yolo26x_pretrain.pt`
3. `assets/models/yolo26x.pt`

## Archived paths

Do not use these for new product work. Unless the user explicitly asks for
legacy pretrain maintenance, agents should avoid even reading these paths:

- `scripts/run_pretrain_local.py`
- `scripts/preflight_cuda_pretrain.py`
- `scripts/preflight_pretrain_runtime.py`
- `src/pretrain_runtime.py`
- `src/training/compact_pretrain_pipeline.py`
- `src/training/pretrain_pipeline.py`
- `legacy/pretrain/`
- `.github/workflows/build-pretrain.yml`
- `pretrain_exe.spec`
- `requirements-pretrain.txt`

## Product focus

- Fine-tuning quality
- Dataset quality gates
- Safe model promotion and rollback
