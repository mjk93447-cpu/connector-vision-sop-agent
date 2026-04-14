param(
    [Parameter(Mandatory = $true)][string]$GgufUrl,
    [Parameter(Mandatory = $true)][string]$QuantizationManifestUrl,
    [string]$RunnerLabelsJson = '["self-hosted","linux","x64","ollama-large"]',
    [string]$ModelName = "gemma4:26b-a4b-it-q4_K_M",
    [string]$PreparedArtifactName = "connector-agent-llm-prepared",
    [string]$VerificationArtifactName = "connector-agent-llm-verify-report",
    [string]$PublishedArtifactName = "connector-agent-llm-verified-cache"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) is required."
}

Write-Host "[pipeline] Dispatching Prepare Ollama LLM Artifact..."
gh workflow run "Prepare Ollama LLM Artifact" `
  -f runner_labels_json="$RunnerLabelsJson" `
  -f model_name="$ModelName" `
  -f gguf_url="$GgufUrl" `
  -f quantization_manifest_url="$QuantizationManifestUrl" `
  -f prepared_artifact_name="$PreparedArtifactName"

Write-Host "[pipeline] After the prepare job completes, run:"
Write-Host "  gh run list --workflow ""Prepare Ollama LLM Artifact"" --limit 1"
Write-Host ""
Write-Host "[pipeline] Then dispatch Verify Ollama LLM Artifact with the returned run id."
Write-Host "[pipeline] Finally dispatch Publish Verified Ollama LLM Artifact using the verify run id."
Write-Host ""
Write-Host "[pipeline] Expected artifact names:"
Write-Host "  prepared : $PreparedArtifactName"
Write-Host "  verify   : $VerificationArtifactName"
Write-Host "  publish  : $PublishedArtifactName"
