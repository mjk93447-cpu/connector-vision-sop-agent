# Vision Rules

## Mandatory model family

- Use YOLO26x only for the packaged vision path.

## Active artifacts

- `assets/models/yolo26x.pt`
- `assets/models/yolo26x_local_pretrained.pt`

## Compatibility-only artifacts

- `assets/models/yolo26x_pretrain.pt`
- `assets/models/yolo26x_pretrained.pt`

## Active files

- `src/vision_engine.py`
- `src/model_artifacts.py`
- `src/gui/panels/training_panel.py`

## Guidance

- Treat `yolo26x_local_pretrained.pt` as the preferred fine-tuning seed.
- Do not route new work through archived pretrain pipelines.
