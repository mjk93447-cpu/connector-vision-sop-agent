# v7.0.0 Focus — SOP Generate Ollama AI

Release date: 2026-06-09

## Summary

v7.0.0 integrates role-split local Ollama models and a four-pass LLM atomizer
for document-to-SOP generation. PDF, PPTX, TXT, and MD work instructions are
parsed into canonical workflow steps with coverage audit, then compiled into
runtime `sop_steps.json` for PyQt6 execution.

## Model policy (offline 16GB line PC)

| Role | Config path | Default tag | Purpose |
|------|-------------|-------------|---------|
| SOP Generate | `llm.sop_generation.model_path` | `qwen3:8b` | 4-pass atomize, JSON repair, long-doc chunking |
| Chat / Recovery | `llm.model_path` | `gemma4:9b` | LLM Chat, `recovery_action`, multimodal screenshots |

Unavailable offline (documented in `src/llm_model_registry.py`):

- Qwen 3.7 — weights not published for local Ollama
- Kimi K2.6 — `kimi-k2.6:cloud` only

Lite fallback for low RAM: `qwen3:4b` via `llm.sop_generation.model_path`.

## New / updated modules

- `src/llm_model_registry.py` — capability table and 16GB recommendations
- `src/sop_llm_atomizer.py` — outline → extract → merge → audit pipeline
- `src/sop_generation.py` — atomizer wired into `generate_from_document()`
- `src/llm_offline.py` — `SOPGenerationLLMConfig`, `chat_sop_generation()`, `check_sop_generation_health()`
- `src/gui/panels/sop_generate_panel.py` — coverage panel, progress, Stop, dry-run

## Deployment pack layout

```
connector_agent/
  connector_vision_agent.exe
  start_agent.bat
  ollama.exe                    (optional, colocated)
  ollama_models/                or llm_stage/
    blobs/
    manifests/
  assets/
    config.json                 (v7.0.0, dual LLM slots)
    sop_steps.json
    models/
      yolo26x.pt
      yolo26x_local_pretrained.pt
```

Required Ollama models in the local cache:

```text
ollama pull qwen3:8b
ollama pull gemma4:9b
```

Stage with `scripts/build_release_artifacts.ps1` or merge a verified LLM bundle
into `ollama_models/` before first launch.

## Operator workflow (Tab 3 — SOP Generate)

1. Upload PDF / PPTX / TXT / MD
2. Review coverage panel (target 100% mapped source refs)
3. Answer audit-driven questions
4. Dry-run compile → Finalize → Apply now

Finalize is blocked while unmapped source sections remain.

## Verification

```bash
pytest tests/unit/test_sop_llm_atomizer.py tests/unit/test_sop_generation.py -q
```
