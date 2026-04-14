# GitHub LLM Pipeline

This repository now separates large Ollama model handling into three workflow stages:

1. `Prepare Ollama LLM Artifact`
   - Pulls the official Ollama model or imports a custom GGUF.
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

The current workflows treat TurboQuant as a documented artifact-chain requirement, not as a stock Ollama pull capability.

- `source_mode=official-pull` is allowed for compatibility testing.
- `source_mode=gguf-import` is required when `require_turboquant=true`.
- `quantization_origin` should contain `turboquant` when a custom GGUF was produced by a TurboQuant toolchain.

This means the verified pipeline can reject an official Ollama pull when the deployment contract says TurboQuant is mandatory for RTX 3070-class local inference.

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
2. If TurboQuant is mandatory, use `source_mode=gguf-import` and provide a TurboQuant GGUF URL.
3. Run or wait for `Verify Ollama LLM Artifact`
4. Run or wait for `Publish Verified Ollama LLM Artifact`
