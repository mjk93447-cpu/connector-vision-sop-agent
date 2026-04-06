# Connector Vision SOP Agent — Complete Guide for Line Engineers

> Version 4.2.0 | For Indian Line Engineers | English Only

---

## Canonical Paths

- Main agent: `src/main.py`
- Local pretrain: `scripts/run_pretrain_local.py`
- Active path map: `docs/ACTIVE_PATHS.md`
- Model naming reference: `docs/MODEL_ARTIFACT_NAMING.md`

Legacy pretrain scripts are compatibility-only and should not be used for new work.

## Table of Contents

1. [System Requirements](#1-system-requirements)
2. [Installation (One Time Only)](#2-installation-one-time-only)
3. [Daily Operation](#3-daily-operation)
4. [Adjusting OCR Sensitivity](#4-adjusting-ocr-sensitivity)
5. [Teaching New Connector Pins (Training)](#5-teaching-new-connector-pins-training)
6. [Editing SOP Steps](#6-editing-sop-steps)
7. [LLM AI Assistant](#7-llm-ai-assistant)
8. [Troubleshooting](#8-troubleshooting)
9. [File Structure Reference](#9-file-structure-reference)

---

## 1. System Requirements

| Item | Requirement |
|------|-------------|
| **Operating System** | Windows 10 Pro version 1803 or later (Windows 11 supported) |
| **CPU** | Intel Core i7 (any generation), 4+ cores |
| **RAM** | 16 GB minimum (32 GB recommended for LLM features) |
| **Storage** | 15 GB free space minimum |
| **Display** | **1920×1080 Full HD — REQUIRED** (other resolutions will cause detection errors) |
| **Internet** | NOT needed after installation |

---

## 2. Installation (One Time Only)

### 2.1 Copy the Installation Files

Copy the **entire** `connector_agent` folder to exactly this location:

```
C:\connector_agent\
```

**Important:** Do not place it in Program Files, Desktop, or any other location. The exact path `C:\connector_agent\` is required.

### 2.2 Verify the File Layout

After copying, your folder should look like this:

```
C:\connector_agent\
  ├── connector_agent.exe      ← Main program
  ├── start_agent.bat          ← START HERE (double-click to launch)
  ├── install_first_time.bat   ← Run ONCE as Administrator (first setup)
  ├── ollama.exe               ← LLM AI server
  ├── ollama_models\           ← AI model files — DO NOT DELETE
  │   ├── blobs\
  │   └── manifests\
  └── assets\
      ├── config.json          ← Settings file (editable via Tab 5)
      ├── sop_steps.json       ← SOP steps (editable via Tab 4)
      └── models\
          └── yolo26x.pt       ← Vision AI model
```

If any of these are missing, contact your IT team.

### 2.3 Run First-Time Setup

1. Right-click `install_first_time.bat`
2. Select **"Run as administrator"**
3. Wait for the message: **"Setup Complete!"** (takes 2-5 minutes)
4. Press any key to close the setup window

This step only needs to be done **once** per PC.

### 2.4 Verify Setup

Double-click `start_agent.bat`. The main window should open with 7 tabs.

If you see a screen resolution warning, change display settings to **1920×1080** before continuing.

---

## 3. Daily Operation

### 3.1 Starting the Agent

1. Double-click `start_agent.bat`
2. Wait for the main window to open (5-10 seconds)
3. The status bar at the bottom shows: **"Ready"**

### 3.2 Running the SOP

1. Click **Tab 1 (SOP Runner)**
2. Click the **▶ Run SOP** button
3. Watch the step list — each step shows:
   - ✅ Green: Success
   - ❌ Red: Failed (check the log below)
   - 🔄 Spinning: In progress

### 3.3 Understanding the Results

After each run:
- **Step log** (Tab 1): Shows pass/fail for each of the 12 SOP steps
- **Audit log** (Tab 6): Full history of all runs with timestamps
- **Vision view** (Tab 2): Shows what the camera captured with AI detection overlays

### 3.4 When a Step Fails

The system automatically tries to recover:

1. **Known Windows popup** → Auto-dismissed (Windows Update, Activation, etc.)
2. **Screen freeze** → Auto-wait 5 seconds, then retry
3. **Unknown situation** → LLM AI analyzes and suggests action (if LLM is enabled)

If the step still fails after recovery, it is marked ❌ and the reason is shown in the log.

---

## 4. Adjusting OCR Sensitivity

OCR (Optical Character Recognition) is how the agent reads button text on screen.

### When to Adjust

- Buttons are detected inconsistently
- "Button not found" errors appear frequently
- New factory software version installed

### How to Adjust

1. Click **Tab 5 (Config)**
2. Scroll to the **"OCR Settings"** section
3. Adjust the **"Match Threshold"** slider:
   - **0.70** = More permissive (catches buttons even with OCR errors; more false positives)
   - **0.80** = Default (recommended for standard factory UI)
   - **0.90** = Stricter (safer, may miss buttons if OCR reads text slightly wrong)
4. Click **💾 Save to config.proposed.json**
5. Review the proposed file and apply manually if correct

### Adding Windows Popup Keywords

If a new Windows dialog is blocking SOP execution and is not auto-dismissed:

1. Tab 5 → **"Windows Popup Keywords"** text box
2. Add the exact text that appears in the popup title or buttons (one per line)
3. Click **💾 Save to config.proposed.json**

---

## 5. Teaching New Connector Pins (Training)

When a new connector model is introduced on the line, the AI needs to be retrained.

### Required Materials

- **30 or more photos** of the new connector (taken from the camera)
- Photos should show different positions and lighting conditions
- Image format: JPG or PNG, any resolution

### Training Steps

1. Click **Tab 7 (Training)**

2. Click **📁 Add Images** and select your connector photos

3. For each image:
   - Select the image from the list
   - Choose annotation mode:
     - **BBox Rect** — draw a rectangle around the pin area (simpler)
     - **Polygon Mask** — click to trace around irregular shapes (more precise)
   - Select the correct label from the dropdown:
     - `connector_pin` — individual connector pins
     - `mold_left` — left mold boundary
     - `mold_right` — right mold boundary
     - `pin_cluster` — entire pin group area
   - Draw the annotation on the image

4. Click **▶ Start Training**
   - Training time: 5-30 minutes on CPU (faster with GPU)
   - Progress bar shows completion percentage
   - Log shows epoch-by-epoch results

5. When "Training complete" appears:
   - Click **🔄 Reload Model** to apply immediately
   - No restart needed

6. Test: Tab 1 → **▶ Run SOP** to verify the new connector is detected correctly

### Dataset Readiness Guide

| Images | Status | Notes |
|--------|--------|-------|
| < 10 | ⚠️ Too few | Need more photos for reliable detection |
| 10-30 | 🔶 Minimum | Acceptable, but more photos = better accuracy |
| 30+ | ✅ Good | Sufficient for reliable detection |
| 100+ | ✅ Excellent | Best accuracy |

---

## 6. Editing SOP Steps

If button names change in the factory software or step order needs adjustment:

### Changing a Button Name

1. Click **Tab 4 (SOP Editor)**
2. Click on the step you want to edit
3. Update the **"button_text"** field with the exact text shown on the button
   - Example: "LOGIN" → "LOG IN" (if the button label changed)
4. Click **💾 Save**

### Reordering Steps

1. Tab 4 → select a step
2. Use **↑ Up** / **↓ Down** arrows to change position
3. Click **💾 Save**

### Enabling/Disabling Steps

- Check/uncheck the **"Enabled"** checkbox next to each step
- Disabled steps are skipped during SOP execution

---

## 7. LLM AI Assistant

The AI assistant (SmolLM3-3B) helps analyze failures and answer questions.

### Using LLM Chat (Tab 3)

1. Click **Tab 3 (LLM Chat)**
2. Type your question in the input box
3. Press **Enter** or click **▶ Send**

**Example questions:**
- "Why did the login step fail 3 times?"
- "What should I check for pin count failures?"
- "Suggest a fix for button not found errors"

### Brief Mode

Check the **⚡ Brief mode** checkbox for faster, shorter answers (useful for quick questions).

### LLM Response Speed

- First response after startup: ~60-120 seconds (model loading)
- Subsequent responses: ~30-60 seconds
- Brief mode responses: ~15-30 seconds

This is normal for CPU-only operation. The AI runs fully offline.

---

## 8. Troubleshooting

| Problem | What to Check | Solution |
|---------|--------------|----------|
| **"Button not found"** | Display resolution | Check: 1920×1080 in Windows Display Settings |
| **"Button not found"** | OCR threshold too high | Tab 5: Lower threshold from 0.80 to 0.70 |
| **New popup blocking SOP** | popup_keywords list | Tab 5: Add the popup title text |
| **Wrong pin count** | Model not trained for new connector | Tab 7: Add photos → Train → Reload |
| **Program won't start** | Ollama server issue | Delete `start_agent.bat` temp files, re-run |
| **Very slow AI response** | Normal for first call | Wait up to 2 minutes for first LLM response |
| **LLM gives Korean/Chinese** | Language setting | Ignore — answer is still correct, will be fixed |
| **App crashed** | Any issue | Restart `start_agent.bat`; check Tab 6 logs |
| **"Model file not found"** | yolo26x.pt missing | Contact IT to restore `assets\models\yolo26x.pt` |
| **Training failed** | Insufficient images | Add at least 30 labeled images in Tab 7 |
| **"NoneType write" on 2nd training** | Stale cache file | Fixed automatically in v3.2.5+ — just retry training |
| **Config change not applied** | proposed.json | Open `assets\config.proposed.json`, verify, copy to `config.json` manually |

### Restarting Properly

1. Close the main window
2. Wait 5 seconds
3. Double-click `start_agent.bat`

If the problem persists after 3 restarts, reinstall by re-running `install_first_time.bat`.

### Collecting Logs for Support

1. Tab 6 (Audit Panel) → click **📋 Export Logs**
2. Send the exported file to your IT contact

---

## 9. File Structure Reference

| File | Purpose | Can I Edit? |
|------|---------|-------------|
| `connector_agent.exe` | Main program | ❌ No |
| `start_agent.bat` | Launch script | ❌ No |
| `install_first_time.bat` | Setup script | ❌ No |
| `assets\config.json` | Settings | ✅ Via Tab 5 only |
| `assets\sop_steps.json` | SOP steps | ✅ Via Tab 4 only |
| `assets\models\yolo26x.pt` | Vision AI | ✅ Via Tab 7 Training |
| `ollama_models\` | LLM model files | ❌ No |
| `logs\` | Run logs | ✅ View via Tab 6 |

**Important:** Always use the GUI tabs to make changes. Do not edit JSON files directly — use the proposed.json workflow to review changes before applying.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| **3.10.0** | 2026-03-27 | Granite Vision 3.3-2b (multimodal) + Screenshot send + dry-run mode + 638 pass |
| 3.9.1 | 2026-03-26 | GitHub Actions Node.js 24 fix |
| 3.9.0 | 2026-03-26 | ROI Picker app-crash fix + SOP 40-step atomic expansion (wait_ms/type_text/press_key) |
| 3.8.0 | 2026-03-26 | SOP field 100%: login/mold/axis/pin/verify all wired to keyboard+mouse |
| 3.2.8 | 2026-03-19 | Fix: Training tqdm NoneType crash (verbose=True) + Reload Model wired to VisionEngine |
| 3.2.7 | 2026-03-19 | Fix: bypass corporate HTTP proxy (trust_env=False, NO_PROXY) + health-check timeout → 30s |
| 3.2.6 | 2026-03-19 | Fix: LLM health check non-fatal + timeout 1.5s → 5s (network-drive/RAM-limited envs) |
| 3.2.5 | 2026-03-19 | Fix: stale label-cache crash on 2nd training run ("NoneType write") |
| 3.2.4 | 2026-03-19 | OCR: multi-word button detection, 4-variant preprocessing, IoU dedup |
| 3.2.3 | 2026-03-19 | Fix: LLM chat requests never sent (self.parent() → self.window()) |
| 3.2.2 | 2026-03-18 | Fix: Training dataset.yaml path, offline env, class subfolders |
| 3.2.0 | 2026-03-18 | OCR winsdk import fix, EasyOCR fallback, workflow consolidation |
| 3.1.0 | 2026-03-17 | OCR-first detection, LLM streaming, exception handler, English UI |
| 3.0.0 | 2026-03-17 | GUI 7-tab, Training panel, YOLO26x pretrain CI |
| 2.1 | 2026-03 | YOLO26x exclusive, GUI 7-tab layout, TrainingPanel |
| 2.0 | 2026-02 | SmolLM3-3B LLM, Ollama backend |
| 1.0 | 2025-12 | Initial release |

---

*For technical support, contact your local IT team or line supervisor.*
*Connector Vision SOP Agent v3.10.0 — Samsung OLED Line Automation*
