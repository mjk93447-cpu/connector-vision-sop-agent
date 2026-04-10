# 5.0.0 Focus

Version 5.0.0 is the release where the product baseline moves from
transition cleanup into a stable operating model for the shipping app.

## Product center

- The packaged PyQt6 GUI is the canonical user entrypoint.
- `Tab 1 - Run SOP`, `Tab 4 - SOP Editor`, and `Tab 7 - Training` are the
  active surfaces for field work.
- `assets/models/yolo26x_local_pretrained.pt` is the runtime model slot that
  ties fine-tuning output back into SOP execution.

## Engineering priorities

- Preserve stable GUI-first packaging and Windows launch behavior.
- Keep GPU-first fine-tuning behavior clear on NVIDIA-equipped PCs.
- Promote `runs/detect/train/weights/best.pt` into the active runtime slot
  automatically after fine-tuning.
- Keep archived pretrain code isolated from active app work and release flows.

## Release expectations

5.0.0 should be considered healthy only if:

- `start_agent.bat` opens the PyQt6 GUI instead of the historical console app.
- Fine-tuning output is visible in the runtime slot used by SOP execution.
- SOP Editor save operations reload cleanly into Run SOP.
- The app bundle and CUDA overlay can be assembled offline on deployment PCs.
- Agent instructions are usable from Claude, Cursor Codex sidebar, and
  ChatGPT 5.4 medium without depending on Claude-only wording.
