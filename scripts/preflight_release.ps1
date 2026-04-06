param(
    [string[]]$UnitTests = @(
        "tests/unit/test_config_loader.py",
        "tests/unit/test_training_manager.py",
        "tests/unit/test_annotation_queue.py",
        "tests/unit/test_sop_document_ingest.py",
        "tests/unit/test_llm_offline.py",
        "tests/unit/test_check_local_runtime.py",
        "tests/unit/test_pretrain_runtime.py",
        "tests/unit/test_run_pretrain_local.py",
        "tests/unit/test_legacy_pretrain_entrypoints.py",
        "tests/unit/test_pyinstaller_support.py",
        "tests/unit/test_start_pretrain_bat.py"
    ),
    [string[]]$IntegrationTests = @(
        "tests/integration/test_no_yolo_sop_run.py"
    )
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Pytest {
    param(
        [string[]]$Tests,
        [int]$TimeoutSec
    )

    if (-not $Tests -or $Tests.Count -eq 0) {
        return
    }

    $args = @(
        "-m", "pytest"
    ) + $Tests + @(
        "-q",
        "--tb=short",
        "--no-header",
        "--timeout=$TimeoutSec"
    )
    & python @args
    if ($LASTEXITCODE -ne 0) {
        throw "pytest failed for: $($Tests -join ', ')"
    }
}

function Test-RequiredFiles {
    function Test-AnyPathExists {
        param([string[]]$Paths)

        foreach ($path in $Paths) {
            if (Test-Path $path) {
                return $true
            }
        }
        return $false
    }

    $required = @(
        "assets\config.json",
        "assets\sop_steps.json",
        "assets\launchers\start_agent.bat",
        "assets\launchers\start_pretrain.bat",
        "build_exe.spec",
        "pretrain_exe.spec"
    )
    foreach ($item in $required) {
        if (-not (Test-Path $item)) {
            throw "Required file not found: $item"
        }
    }

    if (-not (Test-AnyPathExists @(
        "assets\models\yolo26x_pretrain.pt",
        "assets\models\yolo26x_pretrained.pt"
    ))) {
        throw "Required cloud pretrain checkpoint not found: assets\models\yolo26x_pretrain.pt (legacy alias assets\models\yolo26x_pretrained.pt)"
    }
}

Write-Host "[preflight] verifying required files..."
Test-RequiredFiles

Write-Host "[preflight] running unit tests..."
Invoke-Pytest -Tests $UnitTests -TimeoutSec 60

if ((Test-Path "pretrain_data") -or (Test-Path "pretrain_data_test")) {
    Write-Host "[preflight] verifying pretrain launcher dry-run..."
    & python scripts/run_pretrain_local.py --dry-run
    if ($LASTEXITCODE -ne 0) {
        throw "Pretrain dry-run failed"
    }
}

if ($IntegrationTests.Count -gt 0) {
    Write-Host "[preflight] running integration smoke tests..."
    Invoke-Pytest -Tests $IntegrationTests -TimeoutSec 300
}

Write-Host "[preflight] release checks passed."
