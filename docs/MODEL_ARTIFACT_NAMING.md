# Model Artifact Naming

This repository uses three canonical model artifact names:

- `assets/models/yolo26x.pt`
  - COCO base model
  - Used as the starting point when no cloud checkpoint is available
- `assets/models/yolo26x_pretrain.pt`
  - GitHub/cloud pretrain artifact result
  - Preferred seed for Tab 7 fine-tuning
- `assets/models/yolo26x_local_pretrained.pt`
  - Result of local/offline pretrain on the GPU workstation
  - Used when the cloud artifact build times out or local pretrain is needed

Legacy compatibility:

- `assets/models/yolo26x_pretrained.pt` is accepted as a temporary alias for
  `assets/models/yolo26x_pretrain.pt` during the migration window.

Recommended flow:

1. Build or download `yolo26x_pretrain.pt` from GitHub Actions/cloud pretrain.
2. Fine-tune line-specific data in Tab 7 starting from `yolo26x_pretrain.pt`.
3. If cloud pretrain times out, perform local/offline pretrain and use
   `yolo26x_local_pretrained.pt` as the output artifact.
4. The production deployment model remains `assets/models/yolo26x.pt` after
   the training workflow promotes the selected fine-tuned checkpoint.

