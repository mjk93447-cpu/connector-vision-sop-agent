param(
    [Parameter(Mandatory = $true)][string]$GgufUrl,
    [Parameter(Mandatory = $true)][string]$QuantizationManifestUrl,
    [string]$RunnerLabelsJson = '["self-hosted","linux","x64","ollama-large"]',
    [string]$ModelName = "gemma4:26b-a4b-it-q4_K_M",
    [string]$PreparedArtifactName = "connector-agent-llm-prepared",
    [string]$VerificationArtifactName = "connector-agent-llm-verify-report",
    [string]$PublishedArtifactName = "connector-agent-llm-verified-cache",
    [string]$ReleaseTag = "llm-bundle-turboquant-gemma4-26b-q4",
    [string]$ReleaseTitle = "Verified LLM Bundle - TurboQuant Gemma4 26B Q4_K_M",
    [string]$ReleaseAssetPrefix = "connector-agent-llm-verified-cache",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) is required."
}

function Get-LatestWorkflowRunId {
    param(
        [Parameter(Mandatory = $true)][string]$WorkflowName,
        [Parameter(Mandatory = $true)][string]$BranchName
    )

    $json = gh run list --workflow $WorkflowName --branch $BranchName --limit 1 --json databaseId,status,conclusion
    if (-not $json) {
        throw "No workflow runs found for '$WorkflowName' on branch '$BranchName'."
    }
    $runs = $json | ConvertFrom-Json
    if (-not $runs -or $runs.Count -lt 1) {
        throw "Unable to resolve workflow run id for '$WorkflowName'."
    }
    return [string]$runs[0].databaseId
}

Write-Host "[pipeline] Dispatching prepare stage..."
gh workflow run "Prepare Ollama LLM Artifact" `
  -f runner_labels_json="$RunnerLabelsJson" `
  -f model_name="$ModelName" `
  -f gguf_url="$GgufUrl" `
  -f quantization_manifest_url="$QuantizationManifestUrl" `
  -f prepared_artifact_name="$PreparedArtifactName"

Start-Sleep -Seconds 5
$prepareRunId = Get-LatestWorkflowRunId -WorkflowName "Prepare Ollama LLM Artifact" -BranchName $Branch
Write-Host "[pipeline] Watching prepare run $prepareRunId"
gh run watch $prepareRunId --exit-status

Write-Host "[pipeline] Dispatching verify stage..."
gh workflow run "Verify Ollama LLM Artifact" `
  -f runner_labels_json="$RunnerLabelsJson" `
  -f source_run_id="$prepareRunId" `
  -f prepared_artifact_name="$PreparedArtifactName" `
  -f expected_model_name="$ModelName" `
  -f require_turboquant=true `
  -f verification_artifact_name="$VerificationArtifactName"

Start-Sleep -Seconds 5
$verifyRunId = Get-LatestWorkflowRunId -WorkflowName "Verify Ollama LLM Artifact" -BranchName $Branch
Write-Host "[pipeline] Watching verify run $verifyRunId"
gh run watch $verifyRunId --exit-status

Write-Host "[pipeline] Dispatching publish stage..."
gh workflow run "Publish Verified Ollama LLM Artifact" `
  -f verify_run_id="$verifyRunId" `
  -f verify_artifact_name="$VerificationArtifactName" `
  -f published_artifact_name="$PublishedArtifactName"

Start-Sleep -Seconds 5
$publishRunId = Get-LatestWorkflowRunId -WorkflowName "Publish Verified Ollama LLM Artifact" -BranchName $Branch
Write-Host "[pipeline] Watching publish run $publishRunId"
gh run watch $publishRunId --exit-status

Write-Host "[pipeline] Dispatching deploy stage..."
gh workflow run "Deploy Verified Ollama LLM Bundle Release" `
  -f publish_run_id="$publishRunId" `
  -f published_artifact_name="$PublishedArtifactName" `
  -f release_tag="$ReleaseTag" `
  -f release_title="$ReleaseTitle" `
  -f asset_prefix="$ReleaseAssetPrefix"

Start-Sleep -Seconds 5
$deployRunId = Get-LatestWorkflowRunId -WorkflowName "Deploy Verified Ollama LLM Bundle Release" -BranchName $Branch
Write-Host "[pipeline] Watching deploy run $deployRunId"
gh run watch $deployRunId --exit-status

Write-Host "[pipeline] Completed."
Write-Host "  prepare run : $prepareRunId"
Write-Host "  verify run  : $verifyRunId"
Write-Host "  publish run : $publishRunId"
Write-Host "  deploy run  : $deployRunId"
