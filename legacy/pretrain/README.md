# Legacy Pretrain Archive

Pretraining is complete. The resulting checkpoint `assets/models/yolo26x_local_pretrained.pt`
is now the active fine-tuning seed for the product.

Everything in this folder is archived for historical rebuilds, audits, or
emergency seed regeneration only:

- `run_pretrain.py`
- `run_pretrain_compact.py`
- `prepare_pretrain_data.py`
- `scripts/`
- `src/`
- `tests/`
- `assets/launchers/`

Rules for future work:

1. Do not use this folder for normal feature development.
2. Do not add new product behavior here.
3. AI code agents should ignore this folder by default unless the user explicitly
   requests legacy pretrain maintenance.
4. Focus active improvements on:
   - Tab 7 fine-tuning quality
   - Tab 4 SOP Editor safety and validation
   - Tab 1 SOP Run stability and recovery
