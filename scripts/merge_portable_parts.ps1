param(
    [string]$Part1Zip = "connector-agent-app-local.zip",
    [string]$Part2Zip = "connector-agent-llm-local-cache.zip",
    [string]$OutputDir = "connector_agent"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  Connector Vision SOP Agent - Portable Bundle Merge" -ForegroundColor Cyan
Write-Host "  Optional LLM cache: Ollama models (chunked blobs supported)" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""

$missing = @()
if (-not (Test-Path $Part1Zip)) {
    $missing += $Part1Zip
}

if (-not (Test-Path $Part2Zip)) {
    Write-Host "[i] '$Part2Zip' not found - searching for connector-agent-llm-*.zip..." -ForegroundColor Yellow
    $found = Get-ChildItem . -Filter "connector-agent-llm-*.zip" | Select-Object -First 1
    if ($found) {
        $Part2Zip = $found.Name
        Write-Host "    -> Using '$Part2Zip' automatically." -ForegroundColor Green
    } else {
        $partFound = Get-ChildItem . -Filter "connector-agent-llm-*.zip.001" | Select-Object -First 1
        if ($partFound) {
            $Part2Zip = $partFound.Name
            Write-Host "    -> Using split archive '$Part2Zip' automatically." -ForegroundColor Green
        } else {
            $missing += "connector-agent-llm-*.zip or .zip.001"
        }
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "[ERROR] Missing files:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host ""
    Write-Host "Download the app artifact and optional LLM artifact from GitHub Actions first." -ForegroundColor Yellow
    exit 1
}

Write-Host "  Part 1 : $Part1Zip" -ForegroundColor White
Write-Host "  Part 2 : $Part2Zip" -ForegroundColor White
Write-Host "  Output : $OutputDir\" -ForegroundColor White
Write-Host ""

if (Test-Path $OutputDir) {
    Write-Host "[i] Removing existing output directory '$OutputDir'..." -ForegroundColor Yellow
    Remove-Item -LiteralPath $OutputDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path "$OutputDir\ollama_models" | Out-Null

Write-Host "[1/3] Extracting app artifact..." -ForegroundColor Green
Expand-Archive -Path $Part1Zip -DestinationPath $OutputDir -Force

Write-Host "[2/3] Extracting optional Ollama model cache..." -ForegroundColor Green
$repoRoot = Split-Path -Parent $PSScriptRoot
$restoreScript = Join-Path $repoRoot "scripts\package_ollama_models.py"
$resolvedPart2 = (Resolve-Path $Part2Zip).Path
$extractZip = $resolvedPart2
if ($resolvedPart2 -match "\.zip\.[0-9]{3}$") {
    if (-not (Test-Path $restoreScript)) {
        throw "Missing restore helper: $restoreScript"
    }
    Write-Host "      Joining split LLM zip parts..." -ForegroundColor Green
    python $restoreScript join-file --first-part $resolvedPart2 *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to join split LLM zip parts."
    }
    $extractZip = $resolvedPart2 -replace "\.[0-9]{3}$", ""
}
Expand-Archive -Path $extractZip -DestinationPath "$OutputDir\ollama_models" -Force

$splitManifest = Join-Path $OutputDir "ollama_models\ollama_split_manifest.json"
if ((Test-Path $splitManifest) -and (Test-Path $restoreScript)) {
    Write-Host "      Restoring chunked Ollama blobs..." -ForegroundColor Green
    python $restoreScript restore --root "$OutputDir\ollama_models" --remove-parts
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to restore split Ollama model blobs."
    }
}

Write-Host "[3/3] Validating merged package..." -ForegroundColor Green
Write-Host ""

$checks = @(
    @{ Path = "$OutputDir\connector_vision_agent.exe"; Label = "SOP Agent EXE" },
    @{ Path = "$OutputDir\start_agent.bat"; Label = "Launcher script" },
    @{ Path = "$OutputDir\stop_ollama.bat"; Label = "Stop script" },
    @{ Path = "$OutputDir\assets\config.json"; Label = "Config file" },
    @{ Path = "$OutputDir\assets\sop_steps.json"; Label = "Runtime SOP JSON" },
    @{ Path = "$OutputDir\ollama_models\blobs"; Label = "Model blobs dir" },
    @{ Path = "$OutputDir\ollama_models\manifests"; Label = "Model manifests" }
)

$allOk = $true
foreach ($chk in $checks) {
    if (Test-Path $chk.Path) {
        $item = Get-Item $chk.Path
        if ($item.PSIsContainer) {
            $count = (Get-ChildItem $chk.Path -File -Recurse | Measure-Object).Count
            Write-Host ("  [OK] {0,-24} ({1} files)" -f $chk.Label, $count) -ForegroundColor Green
        } else {
            $mb = [math]::Round($item.Length / 1MB, 1)
            Write-Host ("  [OK] {0,-24} ({1} MB)" -f $chk.Label, $mb) -ForegroundColor Green
        }
    } else {
        Write-Host ("  [MISS] {0,-24} missing" -f $chk.Label) -ForegroundColor Red
        $allOk = $false
    }
}

$totalGB = (Get-ChildItem $OutputDir -Recurse -File | Measure-Object Length -Sum).Sum / 1GB
Write-Host ""
Write-Host ("  Total package size: {0:F2} GB" -f $totalGB) -ForegroundColor Cyan
Write-Host ""

if (-not $allOk) {
    Write-Host "=====================================================" -ForegroundColor Red
    Write-Host "  Merge failed validation." -ForegroundColor Red
    Write-Host "=====================================================" -ForegroundColor Red
    exit 1
}

$absPath = (Resolve-Path $OutputDir).Path
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "  Merge complete." -ForegroundColor Green
Write-Host "  Run: $absPath\start_agent.bat" -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
