# connector-vision-sop-agent

Connector Vision SOP Agent **7.0.0** for offline OLED line operation.

## Canonical paths

- `src/gui_app.py`: main GUI entrypoint
- `assets/launchers/start_agent.bat`: packaged launcher
- `src/gui/panels/sop_generate_panel.py`: SOP Generate (document → runtime SOP)
- `src/sop_llm_atomizer.py`: 4-pass LLM atomization engine
- `src/llm_model_registry.py`: Ollama model capability registry
- `docs/V7_0_0_FOCUS.md`: 7.0.0 release focus
- `docs/ACTIVE_PATHS.md`: active vs archived path map

## v7.0.0 highlights

- **SOP Generate AI**: PDF / PPTX / TXT / MD → canonical SOP → compiled runtime steps
- **Dual LLM slots**: `qwen3:8b` (SOP Generate) + `gemma4:9b` (Chat / recovery)
- **Coverage audit**: unmapped document sections block finalize until resolved
- **16GB offline policy**: no cloud-only models (Qwen 3.7 / Kimi 2.6 documented as future)

## Release artifacts

- `connector-agent-app-cpu` — CPU torch runtime
- `connector-agent-app-gpu` — CUDA torch runtime with CPU fallback
- `connector-agent-llm-local-cache` — optional `qwen3:8b` + `gemma4:9b` Ollama blobs

## Build

```bat
build.bat
```

Local release pack (EXE + launcher + optional LLM stage):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_release_artifacts.ps1 -Version 7.0.0
```

## Test

```bash
pytest tests/unit/test_sop_llm_atomizer.py tests/unit/test_sop_generation.py -q
```

## First launch (line PC)

1. Extract app pack + LLM bundle into one folder
2. Run `install_first_time.bat` as Administrator (once)
3. Double-click `start_agent.bat`
