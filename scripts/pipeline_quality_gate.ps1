param(
    [ValidateSet("dev-fast", "ci-smart", "ci-full")]
    [string]$Stage = "dev-fast",
    [ValidateSet("app", "pretrain", "all")]
    [string]$Target = "all",
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

function Get-ChangedFiles {
    try {
        $files = git diff --name-only HEAD~1 HEAD 2>$null
        if (-not $files) {
            return @()
        }
        return @($files | Where-Object { $_ -and $_.Trim().Length -gt 0 })
    } catch {
        return @()
    }
}

function Matches-AnyPrefix {
    param(
        [string[]]$Files,
        [string[]]$Prefixes
    )

    foreach ($file in $Files) {
        foreach ($prefix in $Prefixes) {
            if ($file.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                return $true
            }
        }
    }
    return $false
}

function New-StepSet {
    param(
        [string]$CurrentStage,
        [string]$CurrentTarget
    )

    $changedFiles = Get-ChangedFiles
    $steps = @()

    $dependencyPaths = @(
        "requirements-",
        "requirements.txt",
        ".github/workflows/",
        "build_exe.spec",
        "pretrain_exe.spec",
        "scripts/pyinstaller_support.py",
        "src/runtime_compat.py"
    )

    $appPaths = @(
        "src/main.py",
        "src/gui/",
        "src/training/training_manager.py",
        "scripts/preflight_gui_runtime.py",
        "tests/unit/test_app_runtime_guardrails.py"
    )

    $pretrainPaths = @(
        "src/training/compact_pretrain_pipeline.py",
        "src/pretrain_runtime.py",
        "scripts/run_pretrain_local.py",
        "scripts/preflight_pretrain_runtime.py",
        "tests/unit/test_compact_pretrain_pipeline.py",
        "tests/unit/test_pretrain_runtime_guardrails.py"
    )

    $depsChanged = Matches-AnyPrefix -Files $changedFiles -Prefixes $dependencyPaths
    $appChanged = Matches-AnyPrefix -Files $changedFiles -Prefixes $appPaths
    $pretrainChanged = Matches-AnyPrefix -Files $changedFiles -Prefixes $pretrainPaths

    if ($CurrentStage -eq "dev-fast" -or $CurrentStage -eq "ci-full") {
        $appChanged = $true
        $pretrainChanged = $true
    }
    if ($CurrentTarget -eq "app") {
        $pretrainChanged = $false
    } elseif ($CurrentTarget -eq "pretrain") {
        $appChanged = $false
    }
    if ($depsChanged) {
        if ($CurrentTarget -ne "pretrain") {
            $appChanged = $true
        }
        if ($CurrentTarget -ne "app") {
            $pretrainChanged = $true
        }
    }

    if ($CurrentTarget -eq "app" -or $CurrentTarget -eq "all") {
        $steps += [PSCustomObject]@{ name = "GUI runtime guard"; args = @("scripts/preflight_gui_runtime.py"); reason = "always for app target" }
    }
    if ($CurrentTarget -eq "pretrain" -or $CurrentTarget -eq "all") {
        $steps += [PSCustomObject]@{ name = "Pretrain runtime guard"; args = @("scripts/preflight_pretrain_runtime.py"); reason = "always for pretrain target" }
    }

    if ($appChanged -and ($CurrentTarget -eq "app" -or $CurrentTarget -eq "all")) {
        $smokeArgs = @("scripts/preflight_cuda_app.py")
        if (Test-Path "assets/models/yolo26x.pt") {
            $smokeArgs += @("--model", "assets/models/yolo26x.pt")
        } else {
            $smokeArgs += @("--model", "yolo26x.pt")
        }
        if ($env:CUDA_WHEEL_REQUIRED -eq "1") {
            $smokeArgs += "--require-cuda-wheel"
        }
        $steps += [PSCustomObject]@{ name = "CUDA app smoke"; args = $smokeArgs; reason = "app/runtime changed" }
        $steps += [PSCustomObject]@{ name = "App guardrail tests"; args = @("-m", "pytest", "tests/unit/test_app_runtime_guardrails.py", "-q", "--tb=short", "--no-header"); reason = "app/runtime changed" }
    }

    if ($pretrainChanged -and ($CurrentTarget -eq "pretrain" -or $CurrentTarget -eq "all")) {
        $pretrainSmoke = @("scripts/preflight_cuda_pretrain.py", "--skip-model-load")
        if ($env:CUDA_WHEEL_REQUIRED -eq "1") {
            $pretrainSmoke += "--require-cuda-wheel"
        }
        $steps += [PSCustomObject]@{ name = "CUDA pretrain smoke"; args = $pretrainSmoke; reason = "pretrain/runtime changed" }
        $steps += [PSCustomObject]@{ name = "Pretrain guardrail tests"; args = @("-m", "pytest", "tests/unit/test_compact_pretrain_pipeline.py", "tests/unit/test_pretrain_runtime_guardrails.py", "-q", "--tb=short", "--no-header"); reason = "pretrain/runtime changed" }
        if ($CurrentStage -ne "dev-fast") {
            $steps += [PSCustomObject]@{ name = "Launcher dry-run"; args = @("scripts/run_pretrain_local.py", "--dry-run", "--skip-bundle-prep"); reason = "pretrain runtime path changed" }
        }
    }

    if ($steps.Count -eq 0) {
        $steps += [PSCustomObject]@{ name = "No-op guard"; args = @("-c", "print('No runtime-relevant changes; skipping heavy checks')"); reason = "no relevant changes" }
    }

    Write-Host "[gate] stage=$CurrentStage target=$CurrentTarget changed=$($changedFiles.Count) depsChanged=$depsChanged appChanged=$appChanged pretrainChanged=$pretrainChanged"
    return ,$steps
}

New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
$timestamp = (Get-Date).ToString("yyyyMMdd-HHmmss")
$reportPath = Join-Path $ReportDir "quality-gate-$Stage-$timestamp.json"

$results = @()
$startAll = Get-Date

foreach ($step in (New-StepSet -CurrentStage $Stage -CurrentTarget $Target)) {
    Write-Host ("[gate] reason: " + $step.reason)
    $results += Invoke-Step -Name $step.name -CmdArgs $step.args
}

$total = [Math]::Round(((Get-Date) - $startAll).TotalSeconds, 2)
$report = [PSCustomObject]@{
    stage = $Stage
    target = $Target
    created_at = (Get-Date).ToString("s")
    total_seconds = $total
    steps = $results
}
$report | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 -LiteralPath $reportPath

Write-Host "[gate] all checks passed in ${total}s"
Write-Host "[gate] report: $reportPath"
