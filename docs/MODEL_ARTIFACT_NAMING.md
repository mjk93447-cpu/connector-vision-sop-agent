# Model Artifact Naming

This repository uses these canonical model files:

- `assets/models/yolo26x.pt`
  - base detector fallback
- `assets/models/yolo26x_local_pretrained.pt`
  - active fine-tuning seed
  - produced by the completed archived pretrain program
- `assets/models/yolo26x_pretrain.pt`
  - archived cloud pretrain checkpoint
  - compatibility fallback only

Legacy compatibility:

- `assets/models/yolo26x_pretrained.pt` is tolerated only as an alias for the
  archived cloud checkpoint during migration.

Recommended runtime order:

1. Fine-tuning starts from `yolo26x_local_pretrained.pt`.
2. If that file is unavailable, use archived `yolo26x_pretrain.pt`.
3. If no pretrained seed exists, fall back to `yolo26x.pt`.

Deployment rule:

- Standard app bundles ship `yolo26x.pt` and `yolo26x_local_pretrained.pt`.
- Pretrain generation artifacts and datasets are not part of the active app path.
