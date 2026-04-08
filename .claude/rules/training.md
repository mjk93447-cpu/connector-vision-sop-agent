# Training Rules

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

Do not use these for new product work:

- `scripts/run_pretrain_local.py`
- `src/pretrain_runtime.py`
- `src/training/compact_pretrain_pipeline.py`
- `src/training/pretrain_pipeline.py`
- `legacy/pretrain/`

## Product focus

- Fine-tuning quality
- Dataset quality gates
- Safe model promotion and rollback
