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

## Free storage options

### 1. Hugging Face public model repo

Best option for a very large single GGUF.

- Free public storage is best-effort for free users.
- Large public repos are supported.
- `hf upload-large-folder` is designed for very large uploads.

Helpers:

```powershell
python scripts/generate_quantization_manifest.py `
  --gguf-path model.gguf `
  --output quantization_manifest.json `
  --model-name gemma4:26b-a4b-it-q4_K_M `
  --base-model gemma4

python scripts/publish_turboquant_to_hf.py `
  --repo-id your-name/gemma4-turboquant `
  --gguf-path model.gguf `
  --quantization-manifest-path quantization_manifest.json
```

Auth required:

- one Hugging Face write token in `HF_TOKEN`

### 2. GitHub Release split parts

Best no-new-account fallback when you already have GitHub repo write access.

- Split the GGUF into sub-2GB parts
- Upload the parts plus provenance manifest to a GitHub Release
- Use the generated `gguf_download_manifest.public.json` URL as `gguf_manifest_url`

Helper:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/publish_turboquant_to_github_release.ps1 `
  -GgufPath model.gguf `
  -QuantizationManifestPath quantization_manifest.json
```

Auth required:

- existing `gh` login with release upload permission

### 3. GitHub Actions cloud mirror from a public TurboQuant source

Best fully cloud-based no-extra-account path.

- Source file stays public on the original host
- GitHub Actions downloads it in HTTP range chunks
- Each chunk is uploaded directly as a GitHub Release asset
- The workflow also emits:
  - `gguf_download_manifest.public.json`
  - `quantization_manifest.json`

Workflow:

- [mirror-public-turboquant-to-release.yml](/c:/connector-vision-sop-agent/.github/workflows/mirror-public-turboquant-to-release.yml:1)

Default source:

- `BugTraceAI-Apex-G4-26B-Q4.gguf`
- Public source URL supports range downloads and is about 16.8 GB

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
