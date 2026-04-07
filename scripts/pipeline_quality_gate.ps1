param(
    [ValidateSet("dev-fast", "ci-prebuild", "ci-prepackage")]
    [string]$Stage = "dev-fast",
    [string]$ReportDir = "artifacts/checklists"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Step {
    param(
        [string]$Name,
        [string[]]$CmdArgs
    )

    Write-Host "[gate] $Name"
    $start = Get-Date
    & python @CmdArgs
    $code = $LASTEXITCODE
    $elapsed = [Math]::Round(((Get-Date) - $start).TotalSeconds, 2)
    if ($code -ne 0) {
        throw "[gate] failed: $Name (exit=$code, ${elapsed}s)"
    }
    return [PSCustomObject]@{
        name = $Name
        status = "passed"
        elapsed_seconds = $elapsed
        command = ("python " + ($CmdArgs -join " "))
    }
}

function New-StepSet {
    param([string]$CurrentStage)

    $steps = @()

    $steps += @{ name = "GUI runtime guard"; args = @("scripts/preflight_gui_runtime.py") }
    $steps += @{ name = "Pretrain runtime guard"; args = @("scripts/preflight_pretrain_runtime.py") }
    $steps += @{ name = "CUDA pretrain smoke"; args = @("scripts/preflight_cuda_pretrain.py", "--skip-model-load") }
    $steps += @{ name = "Unit guardrails"; args = @("-m", "pytest", "tests/unit/test_app_runtime_guardrails.py", "tests/unit/test_compact_pretrain_pipeline.py", "-q", "--tb=short", "--no-header") }

    if ($CurrentStage -ne "dev-fast") {
        $steps += @{ name = "Launcher dry-run"; args = @("scripts/run_pretrain_local.py", "--dry-run", "--skip-bundle-prep") }
    }

    return ,$steps
}

New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
$timestamp = (Get-Date).ToString("yyyyMMdd-HHmmss")
$reportPath = Join-Path $ReportDir "quality-gate-$Stage-$timestamp.json"

$results = @()
$startAll = Get-Date

foreach ($step in (New-StepSet -CurrentStage $Stage)) {
    $results += Invoke-Step -Name $step.name -CmdArgs $step.args
}

$total = [Math]::Round(((Get-Date) - $startAll).TotalSeconds, 2)
$report = [PSCustomObject]@{
    stage = $Stage
    created_at = (Get-Date).ToString("s")
    total_seconds = $total
    steps = $results
}
$report | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 -LiteralPath $reportPath

Write-Host "[gate] all checks passed in ${total}s"
Write-Host "[gate] report: $reportPath"
