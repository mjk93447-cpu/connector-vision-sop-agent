# QUICK START — Connector Vision SOP Agent

> Full instructions: `README_INSTALL_EN.md`

---

## Daily Operation (5 steps)

| Step | Action |
|------|--------|
| **1. START** | Double-click `C:\connector_agent\start_agent.bat` |
| **2. RUN SOP** | Tab 1 → click **▶ Run SOP** |
| **3. CHECK RESULTS** | Tab 1 log panel — each step shows ✅ or ❌ |
| **4. VIEW DETAILS** | Tab 6 (Audit Panel) for full run history |
| **5. STOP** | Close the window (Ollama stops automatically) |

---

## When Something Goes Wrong

| Problem | Where to fix |
|---------|-------------|
| Button not detected | Tab 5 → lower OCR Threshold (0.80 → 0.70) |
| New Windows popup blocking | Tab 5 → add keyword to "Windows Popup Keywords" |
| Wrong button names | Tab 4 → edit "button_text" field |
| Pin count wrong | Tab 7 → upload new photos → Train → Reload |
| LLM not responding | Close & restart `start_agent.bat` |
| Any crash | Restart `start_agent.bat`; if repeated → reinstall |

---

## Teaching New Connector Pins

1. Tab 7 → click **📁 Add Images** (upload 30+ connector photos)
2. Select each image → draw bbox or polygon around pin area
3. Set label: **connector_pin** or **mold_left** / **mold_right**
4. Click **▶ Start Training** (5-30 min on CPU)
5. Click **🔄 Reload Model** when "Training complete" appears
6. Tab 1 → **▶ Run SOP** to verify

---

## Key Tabs

| Tab | Purpose |
|-----|---------|
| **Tab 1** — SOP Runner | Run the SOP, see step-by-step results |
| **Tab 2** — Vision | Live camera view with YOLO detection overlay |
| **Tab 3** — LLM Chat | Ask questions about run results (AI assistant) |
| **Tab 4** — SOP Editor | Edit button names and step order |
| **Tab 5** — Config | Adjust OCR sensitivity, popup keywords, timing |
| **Tab 6** — Audit | Full run history and log viewer |
| **Tab 7** — Training | Annotate connector photos and retrain model |

---

## Contact for Escalation

> *(Fill in local contact details here)*

---

*Connector Vision SOP Agent v3.2.7 — Line Automation System*
