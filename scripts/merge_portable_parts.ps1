# merge_portable_parts.ps1
# Assembles the split GitHub Actions artifacts into one portable folder
#
# Prerequisites: Download both artifacts from GitHub Actions:
#   - portable-part1-app-exe-ollama.zip      (~500MB)
#   - portable-part2-llm-phi4-mini-rsn.zip   (~2.5GB)
#
# Usage (place this script next to both zip files, then run):
#   .\merge_portable_parts.ps1
#
# Custom model artifact:
#   .\merge_portable_parts.ps1 -Part2Zip "portable-part2-llm-mistral-7b.zip"

param(
    [string]$Part1Zip  = "portable-part1-app-exe-ollama.zip",
    [string]$Part2Zip  = "portable-part2-llm-phi4-mini-rsn.zip",
    [string]$OutputDir = "connector_agent"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  Connector Vision SOP Agent - Portable Bundle Merge" -ForegroundColor Cyan
Write-Host "  LLM: phi4-mini-reasoning (Microsoft / USA)" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Input file check ────────────────────────────────────
$missing = @()
if (-not (Test-Path $Part1Zip)) { $missing += $Part1Zip }

# Auto-detect Part2 zip if default name not found
if (-not (Test-Path $Part2Zip)) {
    Write-Host "[i] '$Part2Zip' not found — searching for portable-part2-llm-*.zip..." -ForegroundColor Yellow
    $found = Get-ChildItem . -Filter "portable-part2-llm-*.zip" | Select-Object -First 1
    if ($found) {
        $Part2Zip = $found.Name
        Write-Host "    -> Using '$Part2Zip' automatically." -ForegroundColor Green
    } else {
        $missing += "portable-part2-llm-*.zip"
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "[ERROR] Missing files:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host ""
    Write-Host "Download from: GitHub Actions -> Build Portable Offline Bundle -> Artifacts" -ForegroundColor Yellow
    exit 1
}

Write-Host "  Part 1 : $Part1Zip" -ForegroundColor White
Write-Host "  Part 2 : $Part2Zip" -ForegroundColor White
Write-Host "  Output : $OutputDir\" -ForegroundColor White
Write-Host ""

# ── 2. Prepare output directory ────────────────────────────
if (Test-Path $OutputDir) {
    Write-Host "[!] '$OutputDir' already exists — removing..." -ForegroundColor Yellow
    Remove-Item $OutputDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path "$OutputDir\ollama_models" | Out-Null

# ── 3. Extract Part 1 (EXE + Ollama + scripts) ────────────
Write-Host "[1/3] Extracting Part 1 (EXE + Ollama + scripts)..." -ForegroundColor Green
Expand-Archive -Path $Part1Zip -DestinationPath $OutputDir -Force
Write-Host "      Done. ✅"

# ── 4. Extract Part 2 (LLM model blobs) ───────────────────
Write-Host "[2/3] Extracting Part 2 (LLM model blobs, ~2.5GB)..." -ForegroundColor Green
Write-Host "      This may take a few minutes..."
Expand-Archive -Path $Part2Zip -DestinationPath "$OutputDir\ollama_models" -Force
Write-Host "      Done. ✅"

# ── 5. Validate final structure ────────────────────────────
Write-Host "[3/3] Validating package..." -ForegroundColor Green
Write-Host ""

$checks = @(
    @{ Path = "$OutputDir\connector_vision_agent.exe"; Label = "SOP Agent EXE" },
    @{ Path = "$OutputDir\ollama.exe";                  Label = "Ollama binary" },
    @{ Path = "$OutputDir\config.json";                 Label = "Config file" },
    @{ Path = "$OutputDir\start_agent.bat";             Label = "Launcher script" },
    @{ Path = "$OutputDir\stop_ollama.bat";             Label = "Stop script" },
    @{ Path = "$OutputDir\ollama_models\blobs";         Label = "Model blobs dir" },
    @{ Path = "$OutputDir\ollama_models\manifests";     Label = "Model manifests" }
)

$allOk = $true
foreach ($chk in $checks) {
    if (Test-Path $chk.Path) {
        $item = Get-Item $chk.Path
        if ($item.PSIsContainer) {
            $count = (Get-ChildItem $chk.Path -File -Recurse).Count
            Write-Host ("  ✅ {0,-32} ({1} files)" -f $chk.Label, $count) -ForegroundColor Green
        } else {
            $mb = [math]::Round($item.Length / 1MB, 1)
            Write-Host ("  ✅ {0,-32} ({1} MB)" -f $chk.Label, $mb) -ForegroundColor Green
        }
    } else {
        Write-Host ("  ❌ {0,-32} MISSING" -f $chk.Label) -ForegroundColor Red
        $allOk = $false
    }
}

$totalGB = (Get-ChildItem $OutputDir -Recurse -File | Measure-Object Length -Sum).Sum / 1GB
Write-Host ""
Write-Host ("  Total package size: {0:F2} GB" -f $totalGB) -ForegroundColor Cyan

Write-Host ""
if ($allOk) {
    $absPath = (Resolve-Path $OutputDir).Path
    Write-Host "=====================================================" -ForegroundColor Green
    Write-Host "  Merge complete! ✅" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Run: $absPath\start_agent.bat" -ForegroundColor Green
    Write-Host "=====================================================" -ForegroundColor Green
} else {
    Write-Host "=====================================================" -ForegroundColor Red
    Write-Host "  [ERROR] Some files are missing." -ForegroundColor Red
    Write-Host "  Re-download artifacts and retry." -ForegroundColor Red
    Write-Host "=====================================================" -ForegroundColor Red
    exit 1
}
