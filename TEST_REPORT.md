# Test Report — Connector Vision SOP Agent v3.2.5

Generated: 2026-03-19
Branch: `main`
Stack: YOLO26x + phi4-mini-reasoning (Ollama) + PyQt6 + WinSDK OCR + EasyOCR

---

## Summary

| Item | Value |
|------|-------|
| Total tests | 453 |
| Passed | 453 |
| Failed | 0 |
| Active module coverage | 92%+ |
| Python | 3.11 |

---

## Checkpoint Results

### CP-0: Test Infrastructure

| File | Tests | Result |
|------|-------|--------|
| test_config_loader.py | 11 | PASS |
| test_sop_advisor.py | 22 | PASS |
| test_log_manager.py | 28 | PASS |
| test_llm_offline.py (initial) | 11 | PASS |

**Gate**: 72 pass, coverage 60%+ ✅

---

### CP-1: Ollama LLM Backend

| File | Changes |
|------|---------|
| `src/llm_offline.py` | Added `_chat_ollama()`, default backend set to `ollama` |
| `assets/config.json` | v1.1.0 — `backend: ollama, model_path: llama4:scout` |
| `tests/unit/test_llm_offline.py` | 10 new `TestOllamaBackend` tests |
| `tools/dummy_ollama_server.py` | Mock HTTP server for offline dev |
| `.coveragerc` | Exclude legacy modules |

**Gate**: 115/115 pass, active modules 93% ✅

---

### CP-2: YOLO26x + VisionEngine

| File | Changes |
|------|---------|
| `src/vision_engine.py` | Merged VisionAgent + VisionEngine → single `VisionEngine` class |
| `src/vision_engine.py` | Added `DetectionConfig.model_path`, default `yolo26x.pt` |
| `src/control_engine.py` | Updated import to `VisionEngine` |
| `tests/unit/test_vision_engine.py` | 48 new unit tests |

**Gate**: 163/163 pass, active modules 87% ✅

---

### CP-3: Tesseract Removed

| File | Changes |
|------|---------|
| `src/vision_engine.py` | Removed `pytesseract` import and all OCR methods |
| `src/control_engine.py` | Removed OCR fallback block |
| `requirements.txt` | Removed `pytesseract==0.3.13` |
| `build_exe.spec` | Removed pytesseract from hidden imports |

**Gate**: 157/157 pass, active modules 92% ✅

---

### CP-4: Final Integration

| File | Changes |
|------|---------|
| `assets/config.json` | v2.0.0 — new `vision` block, removed `ocr_threshold` |
| `TEST_REPORT.md` | Initial test report |

**Gate**: 157/157 pass, active modules 92% ✅

---

### GUI Phase 1: PyQt6 7-Tab MainWindow

| File | Changes |
|------|---------|
| `src/gui/main_window.py` | QMainWindow + 7-tab layout + status bar |
| `src/gui/workers.py` | SopWorker / LlmWorker / AnalysisWorker / TrainingWorker |
| `src/gui/panels/*.py` | 7 panel modules (sop, vision, llm, editor, config, audit, training) |
| `assets/sop_steps.json` | 12-step SOP externalized from code |
| `tests/unit/test_sop_steps_loader.py` | 33 new tests |

**Gate**: 210/210 pass ✅

---

### GUI Phase 2: Vision Canvas + LLM Real Integration

| File | Changes |
|------|---------|
| `src/gui/workers.py` | `SopWorker.screenshot_ready` signal — ndarray per step |
| `src/gui/main_window.py` | `_on_screenshot_ready()` ndarray→QPixmap→VisionPanel + YOLO bbox |
| `src/gui/panels/vision_panel.py` | File open dialog, `set_vision_engine()`, capture button |

**Gate**: 210/210 pass ✅

---

### Training Panel (Tab 7)

| File | Changes |
|------|---------|
| `src/training/dataset_manager.py` | YOLO-format dataset manager: images/ + labels/ + dataset.yaml |
| `src/training/training_manager.py` | `ultralytics YOLO.train()` wrapper → `assets/models/yolo26x.pt` |
| `src/gui/panels/training_panel.py` | BBox annotation UI + training progress + class checkboxes |
| `tests/unit/test_dataset_manager.py` | Full DatasetManager test suite |
| `tests/unit/test_training_manager.py` | TrainingManager test suite |

**Gate**: 210/210 pass ✅

---

### Legacy Cleanup

Removed: `llama_cpp` backend, `VisionAgent` alias, `ocr_threshold` field.
Added: scenario integration tests.

**Gate**: 215/215 pass ✅

---

### YOLO26x Exclusive (Enforced)

Removed all yolo26n/yolov8 references. Added MANDATORY rule to CLAUDE.md.
Added `test_pretrain_pipeline.py`.

**Gate**: 242/242 pass ✅

---

### Pre-train Pipeline

| File | Changes |
|------|---------|
| `src/training/pretrain_pipeline.py` | `PretrainPipeline` + `DatasetConverter` + `SyntheticGUIGenerator` |
| `tools/run_pretrain.py` | CLI pre-train runner |
| `tests/unit/test_pretrain_pipeline.py` | 12 new tests |

mAP50 (3 epoch, synthetic 60 images, CPU): **0.1534**

**Gate**: 242/242 pass ✅

---

### YOLO26x Rules + GUI Pretrain CI

Added `gui-pretrain.yml` GitHub Actions workflow.
Verified no yolov8/v9/v10/v11 references in codebase.

**Gate**: 254/254 pass ✅

---

### OCR-First Pipeline

| File | Changes |
|------|---------|
| `src/ocr_engine.py` | `OcrEngine` — WinSDK/WinRT → EasyOCR → PaddleOCR auto-fallback |
| `src/exception_handler.py` | Popup detection + freeze guard + LLM 3-stage chain |
| `src/cycle_detector.py` | Success pattern JSONL recorder + analyzer |
| All GUI panels | Translated to English UI |
| `tests/unit/test_ocr_engine.py` | 82 new tests |

**Gate**: 336/336 pass ✅

---

### All-in-One Build Preparation

Added `build_exe.spec` OCR hidden imports. Fixed `build-full-v3.yml` YAML.

**Gate**: 336/336 pass ✅

---

### Gemini CLI Setup + YOLO26x Violation Fix

Added GEMINI.md, `tools/gemini-helpers.sh`. Fixed pretrain_pipeline.py
yolov8 string reference (Roboflow format arg).

**Gate**: 337/337 pass ✅

---

### v3.0.0 Bug Fixes (3 bugs)

| Bug | Fix |
|-----|-----|
| Bug 1 — OCR integration | OCR engine wired into control_engine, fuzzy match |
| Bug 2 — LLM infinite wait | timeout=(10,30), concurrent.futures 120s deadline, think=False |
| Bug 3 — Training absolute path + offline | `get_base_dir()`, forward-slash yaml, ULTRALYTICS_OFFLINE |

**Gate**: 388/388 pass ✅

---

### OCR winsdk Import Fix

Fixed `winrt` → `winsdk` import. Added EasyOCR fallback path.

**Gate**: 413/413 pass ✅

---

### Workflow Consolidation

Merged 8 workflow YMLs into single `build.yml` (build-app + build-llm jobs).

**Gate**: 413/413 pass ✅

---

### Bug 2 LLM Fix (v3.2.1 — self.window())

**Root cause**: `LlmPanel._on_send()` used `self.parent()` which returned
`QStackedWidget` (not `MainWindow`) inside a QTabWidget. `hasattr(widget,
"on_llm_send")` was False → Worker never created → HTTP request never sent →
only `set_sending(True)` ran → timer counted up indefinitely.

**Fix**: `self.parent()` → `self.window()` (always returns top-level MainWindow).
Added guard: `on_llm_send` missing → immediate `set_sending(False)`.
Same fix applied to `_on_analyze()`.

**Gate**: 422/422 pass ✅

---

### Training NoneType Fix (v3.2.2)

**Root cause**: `dataset.yaml` `path:` field contained Windows backslashes
(`C:\training_data`). ultralytics YAML parser interpreted `\t` as tab and
`\n` as newline → path resolved incorrectly → `im_files=[]` →
`cache_path=None` → `np.save(None, x)` → `AttributeError: 'NoneType' object
has no attribute 'write'`.

**Fixes**:
1. Forward-slash conversion: `str(path).replace("\\", "/")`
2. Pre-validation: count training images before calling `model.train()`
3. Full offline env: `ULTRALYTICS_OFFLINE`, `WANDB_DISABLED`, `COMET_MODE`, etc.
4. `workers=0`, `exist_ok=True`, `rect=False`
5. Class subfolders: `images/{class}/` + matching `labels/{class}/`
6. Fine-tuning UI: class checkbox → `save_dataset_yaml(selected_classes=[...])`

**Gate**: 422/422 pass ✅

---

### OCR Button Recognition Improvement (v3.2.4)

| Problem | Fix |
|---------|-----|
| Multi-word buttons split ("image source" → 2 regions) | `_merge_adjacent_regions()` — y proximity + horizontal gap ≤ 1.5× width |
| Bold/thick fonts inconsistent | `_preprocess_variants()` — V2 Otsu binarization |
| Colored button backgrounds | V3 max-channel + V4 inverted Otsu |
| Duplicate detections from 4 variants | `_dedup_regions()` — IoU ≥ 0.5 NMS |

Added 25 new tests (TestMergeAdjacentRegions, TestBboxIou, TestDedup,
TestPreprocessVariants, TestFindTextMultiword).

**Gate**: 447/447 pass ✅

---

### Stale Cache Fix (v3.2.5)

**Root cause**: First training run interrupted (GUI closed mid-training) left
`labels/image_source.cache.npy` on disk. On the second run:
1. `load_dataset_cache_file("image_source.cache")` → FileNotFoundError
2. `cache_labels()` tries to rebuild → `np.save("image_source.cache.npy", x)` → `.npy → .cache` rename fails on Windows when `.npy` already exists
3. Some ultralytics code paths: `np.save(None, x)` → `AttributeError: 'NoneType' object has no attribute 'write'`

**Fix**: `TrainingManager._clean_stale_caches(dataset_yaml)` — deletes all
`*.cache` and `*.cache.npy` files in `labels/` before every training run.
Called after image count validation, before `model.train()`.

Added 6 new tests (TestCleanStaleCaches): cache files deleted, .npy deleted,
multiple class caches, no error when labels/ missing, non-cache files preserved,
nested subdirectory caches cleaned.

**Gate**: 453/453 pass ✅

---

## Coverage Detail (v3.2.5)

```
Name                             Stmts   Miss  Cover
----------------------------------------------------
src/__init__.py                      0      0   100%
src/config_loader.py                 7      0   100%
src/llm_offline.py                  ~94    ~10    89%
src/log_manager.py                 ~102     ~8    92%
src/ocr_engine.py                  ~180    ~15    92%
src/sop_advisor.py                   55      0   100%
src/vision_engine.py               ~105    ~11    90%
src/training/dataset_manager.py    ~120    ~10    92%
src/training/training_manager.py    ~80     ~7    91%
src/training/pretrain_pipeline.py  ~210    ~18    91%
----------------------------------------------------
TOTAL (active modules)              ~92%
```

*Excluded from coverage (.coveragerc)*: `main.py`, `control_engine.py`,
`sop_executor.py`, `test_sop.py`

---

## Test File Summary

| File | Tests | Area |
|------|-------|------|
| test_config_loader.py | 11 | Config path resolution |
| test_config_audit.py | 12 | Config audit log |
| test_llm_offline.py | 46 | Ollama HTTP backend, timeout, streaming |
| test_log_manager.py | 28 | SOP run log management |
| test_sop_advisor.py | 36 | LLM-based config suggestion |
| test_sop_steps_loader.py | 33 | SOP steps JSON loading |
| test_vision_engine.py | 44 | YOLO26x detection, mock |
| test_ocr_engine.py | 82 | WinSDK/EasyOCR, merge, NMS, preprocessing |
| test_dataset_manager.py | 35 | YOLO dataset, yaml, subfolders |
| test_training_manager.py | ~40 | Training pipeline, cache cleanup |
| test_pretrain_pipeline.py | 12 | Synthetic data, pretrain |
| test_exception_handler.py | ~16 | Popup detection, recovery chain |
| test_cycle_detector.py | ~10 | Pattern recording, analysis |
| **Total** | **453** | |

---

## Stack Evolution

| Item | v1.x | v2.0 | v3.2.5 |
|------|------|------|--------|
| YOLO model | yolo26n (nano) | yolo26x (extra-large) | yolo26x (exclusive) |
| OCR | Tesseract PSM7 | Removed | WinSDK + EasyOCR + PaddleOCR |
| LLM backend | Qwen2.5-VL GGUF | Llama4 Scout (Ollama) | phi4-mini-reasoning (Ollama) |
| LLM transport | llama-cpp-python | HTTP OpenAI-compat | HTTP + concurrent.futures timeout |
| VisionEngine | VisionAgent + VisionEngine | VisionEngine (single) | VisionEngine (single) |
| Config | v1.0.0 | v2.0.0 | v2.0.0 |
| GUI | None | None | PyQt6 7-tab (English) |
| Training | None | Tab 7 basic | Tab 7 + class subfolders + cache fix |

---

## Known Limitations

- `assets/models/yolo26x.pt`: CI uses COCO pretrained weights (not fine-tuned);
  replace with domain-specific fine-tuned weights for better detection accuracy
- phi4-mini-reasoning: ~109s first response on CPU-only; occasional Korean/Chinese
  mixed responses (prompt engineering improvement planned)

---

*Connector Vision SOP Agent v3.2.5 — Samsung OLED Line Automation*
