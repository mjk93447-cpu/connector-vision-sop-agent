# Connector Vision SOP Agent

> **v4.0.0** | OLED Line PC Automation | Offline-First | Windows 10/11

Automates the 40-step atomic connector inspection SOP using YOLO26x vision detection,
WinSDK OCR, and an offline LLM assistant — no internet required after
installation.

---

## Key Features

| Feature | Details |
|---------|---------|
| **Vision** | YOLO26x (NMS-free, highest mAP in the YOLO26 family) |
| **OCR** | WinSDK/WinRT (primary) → EasyOCR → PaddleOCR auto-fallback |
| **LLM** | IBM Granite Vision 3.2-2b via Ollama — multimodal, fully offline |
| **GUI** | PyQt6 — 7 tabs (SOP Runner, Vision, LLM Chat, SOP Editor, Config, Audit, Training) |
| **SOP Editor** | Edit type_text / press_key / wait_ms steps directly in GUI (Tab 4) |
| **Training** | In-app YOLO fine-tuning with bbox annotation (Tab 7) |
| **OS** | Windows 10 Pro 1803+ / Windows 11 (64-bit only) |
| **Tests** | 733 pass, 92%+ coverage |

---

## Quick Start (Deployed Line PC)

1. Copy the `connector_agent\` folder to `C:\connector_agent\`
2. Run `install_first_time.bat` **once** as Administrator
3. Double-click `start_agent.bat` — the 7-tab GUI opens
4. **Tab 1 → ▶ Run SOP** to execute the full 40-step sequence

See **`README_INSTALL_EN.md`** for complete installation and operation guide.
See **`QUICK_START_EN.md`** for a one-page daily reference card.

---

## Architecture

```
src/
  main.py               Entry point + OCR health-check + --console flag
  vision_engine.py      YOLO26x single-class detector (yolo26x.pt)
  ocr_engine.py         WinSDK/WinRT OCR + EasyOCR/PaddleOCR fallback
  control_engine.py     PyAutoGUI click/drag/type automation
  sop_executor.py       40-step atomic SOP orchestration
  llm_offline.py        Ollama HTTP backend (IBM Granite Vision 3.2-2b)
  config_loader.py      JSON config loader (EXE-safe path resolution)
  exception_handler.py  Pop-up detection, freeze guard, LLM 3-stage chain
  cycle_detector.py     Success pattern recording (JSONL)
  gui/
    main_window.py      QMainWindow + 7-tab layout + status bar
    workers.py          QThread workers: SopWorker/LlmWorker/TrainingWorker
    panels/
      sop_panel.py      Tab 1 — SOP step list + run log
      vision_panel.py   Tab 2 — Screenshot + YOLO bbox overlay
      llm_panel.py      Tab 3 — LLM chat (ROI screenshot, Stop button, token counter)
      sop_editor_panel.py  Tab 4 — Add/delete/reorder/edit SOP steps
      config_panel.py   Tab 5 — Config editor (spinbox/checkbox UI)
      audit_panel.py    Tab 6 — Config change audit log viewer
      training_panel.py Tab 7 — BBox annotation + local YOLO fine-tuning
  training/
    dataset_manager.py  YOLO-format dataset (images/ + labels/ + dataset.yaml)
    training_manager.py ultralytics YOLO.train() wrapper → assets/models/yolo26x.pt
    pretrain_pipeline.py Synthetic data pre-training (CI use)
assets/
  config.json           v4.0.0 — vision/LLM/control settings
  sop_steps.json        40-step atomic SOP definition v2.0 (editable via Tab 4)
  models/
    yolo26x.pt          YOLO26x weights (COCO pretrained baseline)
```

---

## MANDATORY: YOLO26x Only

```
Model: yolo26x.pt — ONLY
YOLOv8 / YOLOv9 / YOLOv10 / YOLOv11 — ABSOLUTELY FORBIDDEN
```

---

## Build (CI / GitHub Actions)

Trigger the all-in-one build to produce two downloadable artifacts:

```bash
gh workflow run "Build Connector Vision Agent (All-in-One)" --ref main
```

| Artifact | Size | Contents |
|----------|------|----------|
| `connector-agent-app` | ~500 MB | EXE + Ollama + YOLO26x + OCR + launchers |
| `connector-agent-llm` | ~2.0 GB | IBM Granite Vision 3.2-2b model blobs |

**Assembly on line PC:**
1. Extract `connector-agent-app.zip` → `connector_agent\`
2. Extract `connector-agent-llm.zip` → copy `blobs\` and `manifests\` into `connector_agent\ollama_models\`
3. Double-click `start_agent.bat`

See `.github/workflows/build.yml` for full pipeline details.

---

## Development

### Requirements

- Python 3.11 (Python 3.12 not supported — PyTorch CPU wheel unavailable)
- `pip install -r requirements.txt`
- Ollama installed locally (for LLM features)

### Run Tests

```bash
bash run_tests.sh          # pytest + coverage (required before every commit)
bash scripts/ci_check.sh   # local CI simulation (mirrors build.yml exactly)
```

### Lint

```bash
python -m black src/ tests/ && python -m ruff check src/ tests/ --fix
```

### Run the GUI

```bash
python src/main.py           # GUI mode (PyQt6)
python src/main.py --console # CLI/headless mode
```

### Mock Ollama Server (offline LLM testing)

```bash
python tools/dummy_ollama_server.py
```

---

## Config (assets/config.json)

> **NEVER edit directly.** Propose changes via Tab 5 → saves to `assets/config.proposed.json` → review → manually apply.

```json
{
  "version": "4.0.0",
  "password": "LINE_PASSWORD",
  "vision": {
    "model_path": "assets/models/yolo26x.pt",
    "confidence_threshold": 0.6
  },
  "llm": {
    "enabled": true,
    "backend": "ollama",
    "model_path": "granite3.2-vision:2b",
    "http_url": "http://localhost:11434/api/chat"
  }
}
```

---

## LLM Config Proposal Workflow

The agent never auto-modifies `config.json`. The LLM suggests changes to
`config.proposed.json` only. An engineer reviews and manually applies approved
changes.

1. Tab 3 (LLM Chat) → ask for a config suggestion
2. LLM writes `assets/config.proposed.json`
3. Open both files in a text editor, review the diff
4. Copy approved changes into `config.json`

---

## SOP Editor — Editing Keyboard Input (Tab 4)

To change a password or typed value in the SOP:

1. Tab 4 → select `login_type_password` step → **✏ Edit**
2. Type combo shows `type_text` → **Text** field appears
3. Enter the new password in the **Text** field
4. **Clear First** checkbox controls whether the field is cleared before typing
5. Click **OK** → **💾 Save**

Other editable types:
- `press_key` → **Key** field (e.g. `Return`, `Tab`, `ctrl+a`)
- `wait_ms` → **Duration** spinbox (milliseconds)

---

## Training (Tab 7)

Fine-tune YOLO26x on new connector types directly in the GUI:

1. Tab 7 → **Add Images** (30+ photos of the new connector)
2. Draw bounding boxes and assign labels
3. Select which classes to include → **Start Training & Save**
4. Training runs locally (5-30 min CPU); best weights saved to `assets/models/yolo26x.pt`
5. **Reload Model** — detection updates immediately, no restart needed

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| **4.0.0** | 2026-03-27 | SOP Editor 타입별 편집 UI (type_text PW/press_key/wait_ms) + LLM Chat UX 대폭 개선 (ROI 드래그, Stop 버튼, 600s timeout) + CI 빌드 수정 + 733 pass |
| 3.10.2 | 2026-03-27 | LLM Chat: ROI 드래그 스크린샷 + ChatGPT-like UI + Stop 버튼 실제 취소 + 600s timeout |
| 3.10.1 | 2026-03-27 | image_b64 TypeError 수정 + Granite Vision 체인 통합 테스트 18개 |
| 3.10.0 | 2026-03-27 | Granite Vision 3.2-2b 전환 (multimodal, DocVQA 89%) + Screenshot 전송 + dry-run |
| 3.9.0 | 2026-03-26 | ROI Picker crash fix (exec→open) + SOP atomic 40-step expansion (v2.0) |
| 3.8.0 | 2026-03-26 | SOP field 100%: auth_sequence/input_text/mold_setup, axis_y/verify_left/right |
| 3.2.5 | 2026-03-19 | Fix: stale ultralytics label-cache NoneType on 2nd training run |
| 3.2.4 | 2026-03-19 | OCR: multi-word merge, 4-variant preprocessing, IoU NMS dedup |
| 3.2.3 | 2026-03-19 | Fix: LLM requests never sent (self.parent() → self.window()) |
| 3.0.0 | 2026-03-17 | GUI 7-tab, Training panel, YOLO26x pretrain CI |
| 2.0.0 | 2026-02 | SmolLM3 LLM, Ollama backend, config v2.0.0 |
| 1.0.0 | 2025-12 | Initial release |

---

## Rules

- Code change → `bash run_tests.sh` passes → black+ruff → commit
- Commit format: `[feat/fix/refactor/chore/test] description`
- Test failures → root-cause analysis, then fix (never repeat same command blindly)
- `assets/models/` — **never modify directly**
- Config changes → `assets/config.proposed.json` only

---

*Connector Vision SOP Agent v4.0.0 — Samsung OLED Line Automation*
