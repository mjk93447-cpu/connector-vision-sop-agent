# v3.9.0 Test Report

**Test date:** 2026-03-26
**Environment:** Windows 10, CPU-only, phi4-mini-reasoning (Ollama), YOLO26x
**Baseline:** 599 pass (v3.9.0 — ROI Picker fix + 40-step SOP expansion)

## Issues Found

| # | Issue | Severity | File | Status |
|---|-------|----------|------|--------|
| 1 | ROI drag-and-drop awkward + coordinate mismatch | 🔴 High | sop_editor_panel.py | ✅ Fixed (v3.6.0) |
| 2 | "LOG IN" button not detected (large font, uppercase, space) | 🔴 High | ocr_engine.py | ✅ Fixed (v3.6.0) |
| 3 | Think tokens invisible (color contrast too low) | 🟡 Medium | llm_panel.py | ✅ Fixed (v3.6.0) |
| 4 | Poor color contrast in some Windows display setups | 🟡 Medium | multiple panels | ✅ Fixed (v3.6.0) |
| 5 | LLM answer delay — burst output when next prompt entered | 🔴 High | llm_panel.py | ✅ Fixed (v3.6.0) |
| 6 | New prompt during generation causes collision/stop | 🔴 High | llm_panel.py | ✅ Fixed (v3.6.0) |
| 7 | Training crash: tqdm NoneType + CPU OOM | 🔴 High | training_manager.py | ✅ Fixed (v3.6.0) |

## Root Causes

### Issue 1: ROI UX
- **Symptom:** Drag-and-drop is awkward on touchpad; selected canvas area does not match red rectangle shown on screen
- **Cause:** After `KeepAspectRatio` scaling, the displayed pixmap is smaller than the QLabel container. Centering offsets `ox`, `oy` were not subtracted before coordinate conversion, so selections are shifted
- **Fix:** Click-move-click state machine (1st click = start, hover = live preview, 2nd click = confirm) + `ox`/`oy` offset correction in `_compute_roi()`

### Issue 2: "LOG IN" button not detected
- **Symptom:** Button not recognized even at confidence 0.5 with ROI set; large uppercase text with space between words
- **Cause:** Only 4 preprocessing variants exist — none uses 2× upscaling for large-font text. Also, query "LOG IN" vs OCR result "LOGIN" fails exact/fuzzy match when space is ignored
- **Fix:** Add 5th preprocessing variant (2× bicubic upscale + OTSU threshold); add space-normalized comparison path in fuzzy matching

### Issues 3 + 5: Think tokens invisible + burst output
- **Symptom 3:** Think token section barely visible (effectively invisible on most displays)
- **Symptom 5:** Previous answer text appears all at once when the next prompt is sent
- **Cause 3:** `color: #bdbdbd` / `#9e9e9e` on `background: #fafafa` → contrast ratio ~1.5:1 (WCAG AA minimum is 4.5:1)
- **Cause 5:** `on_streaming_done()` stops the flush timer before calling `_flush_token_buf()`, leaving tokens in the buffer. They are flushed on the next timer tick, which fires after the next prompt is entered
- **Fix 3:** Update colors to `#444444` / `#555555`; think panel background to `#f0f0f0`
- **Fix 5:** Add `_stop_flush_and_finalize()` that drains the buffer first, then stops the timer

### Issue 4: Poor color contrast across panels
- **Symptom:** Gray text on white/light backgrounds is nearly illegible on some Windows display profiles (e.g., high-brightness, sRGB)
- **Affected areas:** `llm_panel.py` elapsed label, think panel; `sop_editor_panel.py` hint labels, disabled fields
- **Fix:** Replace all low-contrast hardcoded colors with WCAG AA-compliant values (`#333333`–`#555555` on white/light gray)

### Issue 6: Prompt queue collision
- **Symptom:** Typing a new prompt while the model is generating triggers "⏹ Generation stopped by user" and discards the current output
- **Cause:** `_on_send()` unconditionally stops the running worker when a new prompt arrives
- **Fix:** Add `_pending_prompt` queue — if worker is active, store new prompt silently, show `⏳ Queued` indicator, auto-send when generation completes

### Issue 7: Training crash (two failure modes)
- **Symptom A:** `AttributeError: 'NoneType' object has no attribute 'write'` — crash inside `tqdm.close()`
- **Symptom B:** `RuntimeError: DefaultCPUAllocator: not enough memory` — crash during YOLO26x model initialization
- **Cause A:** `_TeeWriter` wraps `sys.stdout` before `_apply_ultralytics_tqdm_patch()` is called. The patch captures the raw (possibly `None`) pre-wrap reference instead of the live `_TeeWriter`
- **Cause B:** YOLO26x requires ~1.5 GB free RAM for a single forward pass during model init; systems with <1.5 GB available crash without a friendly message
- **Fix A:** Swap order — apply tqdm patch first, then wrap `sys.stdout` with `_TeeWriter`; also update `_safe_close()` to re-read `sys.stdout` at close time
- **Fix B:** Pre-flight RAM check using `psutil`; wrap `model.train()` with OOM catch that emits actionable English error; reduce default `batch` from 4 to 2

## Expected Results After Fixes

| Metric | Before | After |
|--------|--------|-------|
| Test count | 458 pass | 476+ pass |
| ROI accuracy | Coordinate mismatch | Pixel-accurate mapping |
| OCR "LOG IN" | Not detected | Detected via upscaled variant |
| LLM think tokens | Invisible (~1.5:1 contrast) | Visible (#444 on #f0f0f0, 6.6:1) |
| LLM streaming | Burst / delay | Immediate, 60 fps flush |
| Prompt queue | Collision / stop | Queue + auto-send |
| Training tqdm | NoneType crash | No crash |
| Training OOM | Unhandled crash | Friendly English error + batch=2 default |
| App version | 3.5.1 | 3.9.0 |
