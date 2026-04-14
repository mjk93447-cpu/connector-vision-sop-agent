# GitHub LLM Pipeline

This repository now separates large Ollama model handling into three workflow stages:

1. `Prepare Ollama LLM Artifact`
   - Imports a TurboQuant GGUF only.
   - Stages `~/.ollama/models` into a chunked transport directory.
   - Uploads the prepared model cache as a GitHub Actions artifact.

2. `Verify Ollama LLM Artifact`
   - Downloads the prepared artifact from the earlier run.
   - Restores split blobs back into a real `OLLAMA_MODELS` directory.
   - Runs metadata checks and a live `ollama show` / smoke chat.
   - Uploads a small verification report artifact.

3. `Publish Verified Ollama LLM Artifact`
   - Downloads the verification report.
   - Resolves the original prepared artifact run id from the report.
   - Repackages the chunked model cache plus verification evidence into a final artifact.

## TurboQuant rule

TurboQuant is mandatory in this pipeline.

- The prepare workflow no longer accepts a stock `ollama pull` path.
- A TurboQuant-built GGUF URL is required.
- A `quantization_manifest.json` URL is also required.
- Verification fails unless:
  - the prepared model was imported through `gguf-import`
  - the quantization manifest identifies `turboquant`
  - `ollama show` reports the imported model as `gguf`

This is intentional because the deployment contract says RTX 3070-class local inference is not acceptable without a TurboQuant path.

## Recommended runner setup

- Prepare: self-hosted Linux runner with at least 150 GB SSD.
- Verify: self-hosted Linux runner with the same or larger disk profile.
- Publish: standard GitHub-hosted runner is enough.

The default model tag is the official Ollama name:

- `gemma4:26b-a4b-it-q4_K_M`

## Artifact layout

- Prepared artifact: `connector-agent-llm-prepared`
- Verification report: `connector-agent-llm-verify-report`
- Published bundle: `connector-agent-llm-verified-cache`

The prepared and published bundles both carry `ollama_split_manifest.json`, so large blob parts can be restored locally with:

```powershell
python scripts/package_ollama_models.py restore --root ollama_artifact_stage --remove-parts
```

## Typical flow

1. Run `Prepare Ollama LLM Artifact`
2. Provide a TurboQuant GGUF URL and a matching quantization manifest URL.
3. Run or wait for `Verify Ollama LLM Artifact`
4. Run or wait for `Publish Verified Ollama LLM Artifact`

## Dispatch helper

You can start the first stage locally with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dispatch_turboquant_pipeline.ps1 `
  -GgufUrl "https://example.invalid/gemma4-turboquant.gguf" `
  -QuantizationManifestUrl "https://example.invalid/quantization_manifest.json"
```

Or run the full 3-stage chain sequentially:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_turboquant_pipeline.ps1 `
  -GgufUrl "https://example.invalid/gemma4-turboquant.gguf" `
  -QuantizationManifestUrl "https://example.invalid/quantization_manifest.json"
```
