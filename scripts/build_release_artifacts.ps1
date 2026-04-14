param(
    [string]$Version = "6.0.0",
    [string]$DistDir = "dist",
    [string]$WorkDir = "build-release",
    [string]$OutputRoot = "",
    [string]$OllamaExe = "",
    [string]$OllamaModelsRoot = "",
    [switch]$SkipPyInstaller
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not $OutputRoot) {
    $OutputRoot = Join-Path $repoRoot ("artifacts\release\v" + $Version)
}

if (-not $OllamaExe) {
    $cmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($cmd) {
        $OllamaExe = $cmd.Source
    }
}

if (-not $OllamaModelsRoot) {
    $candidates = @(
        (Join-Path $env:USERPROFILE ".ollama\models"),
        (Join-Path $env:LOCALAPPDATA "Ollama\models"),
        (Join-Path $env:ProgramData "Ollama\models")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            $OllamaModelsRoot = $candidate
            break
        }
    }
}

$distDirPath = Join-Path $repoRoot $DistDir
$workDirPath = Join-Path $repoRoot $WorkDir
$outputRootPath = [System.IO.Path]::GetFullPath($OutputRoot)
$appStage = Join-Path $outputRootPath "app"
$llmStage = Join-Path $outputRootPath "llm_stage"
$appZip = Join-Path $outputRootPath "connector-agent-app-local.zip"
$llmZip = Join-Path $outputRootPath "connector-agent-llm-local-cache.zip"

if (Test-Path $outputRootPath) {
    Remove-Item -LiteralPath $outputRootPath -Recurse -Force
}
New-Item -ItemType Directory -Path $outputRootPath -Force | Out-Null

if (-not $SkipPyInstaller) {
    if (Test-Path $distDirPath) {
        Remove-Item -LiteralPath $distDirPath -Recurse -Force
    }
    if (Test-Path $workDirPath) {
        Remove-Item -LiteralPath $workDirPath -Recurse -Force
    }
    pyinstaller build_exe.spec --distpath $distDirPath --workpath $workDirPath --clean
}

$exePath = Join-Path $distDirPath "connector_vision_agent.exe"
if (-not (Test-Path $exePath)) {
    throw "Missing built EXE: $exePath"
}

New-Item -ItemType Directory -Path $appStage -Force | Out-Null
Copy-Item $exePath (Join-Path $appStage "connector_vision_agent.exe") -Force
Copy-Item "assets\launchers\start_agent.bat" (Join-Path $appStage "start_agent.bat") -Force
Copy-Item "assets\launchers\stop_ollama.bat" (Join-Path $appStage "stop_ollama.bat") -Force
Copy-Item "assets\launchers\restore_ollama_stage.ps1" (Join-Path $appStage "restore_ollama_stage.ps1") -Force
Copy-Item "assets\launchers\INSTALL_GUIDE.txt" (Join-Path $appStage "INSTALL_GUIDE.txt") -Force
Copy-Item "assets\launchers\MERGE_GUIDE.txt" (Join-Path $appStage "MERGE_GUIDE.txt") -Force
Copy-Item "assets\launchers\PLACE_APP_HERE.txt" (Join-Path $appStage "PLACE_APP_HERE.txt") -Force
Copy-Item "assets\launchers\PLACE_LLM_HERE.txt" (Join-Path $appStage "PLACE_LLM_HERE.txt") -Force

New-Item -ItemType Directory -Path (Join-Path $appStage "assets") -Force | Out-Null
Copy-Item "assets\config.json" (Join-Path $appStage "assets\config.json") -Force
Copy-Item "assets\config.schema.json" (Join-Path $appStage "assets\config.schema.json") -Force
Copy-Item "assets\class_registry.json" (Join-Path $appStage "assets\class_registry.json") -Force
Copy-Item "assets\sop_steps.json" (Join-Path $appStage "assets\sop_steps.json") -Force
Copy-Item "assets\models" (Join-Path $appStage "assets\models") -Recurse -Force

if (Test-Path "README.md") { Copy-Item "README.md" (Join-Path $appStage "README.md") -Force }
if (Test-Path "README_INSTALL_EN.md") { Copy-Item "README_INSTALL_EN.md" (Join-Path $appStage "README_INSTALL_EN.md") -Force }
if ($OllamaExe -and (Test-Path $OllamaExe)) {
    Copy-Item $OllamaExe (Join-Path $appStage "ollama.exe") -Force
}

Set-Content -LiteralPath (Join-Path $appStage "runtime_flavor.txt") -Value "local" -Encoding UTF8

python scripts/package_ollama_models.py zipdir --source $appStage --output $appZip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to build app zip artifact."
}

if ($OllamaModelsRoot -and (Test-Path $OllamaModelsRoot)) {
    python scripts/package_ollama_models.py stage --source $OllamaModelsRoot --output $llmStage --chunk-size 2147483648 *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to stage Ollama model cache."
    }
    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        $listPath = Join-Path $llmStage "ollama_models_list.txt"
        & ollama list | Out-File -FilePath $listPath -Encoding utf8
    }
    python scripts/package_ollama_models.py zipdir --source $llmStage --output $llmZip
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build Ollama model cache zip artifact."
    }
    python scripts/package_ollama_models.py split-file --source $llmZip --chunk-size 2147483648 --delete-source *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to split Ollama model cache zip artifact."
    }
}

Write-Host "[release] output root: $outputRootPath"
Write-Host "[release] app zip     : $appZip"
if (Test-Path $llmZip) {
    Write-Host "[release] llm zip     : $llmZip"
} elseif (Test-Path ($llmZip + ".001")) {
    Write-Host "[release] llm zip     : $llmZip.001 (+ split parts)"
} else {
    Write-Host "[release] llm zip     : skipped (no local Ollama models root found)"
}
