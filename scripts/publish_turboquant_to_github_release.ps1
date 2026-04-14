param(
    [Parameter(Mandatory = $true)][string]$GgufPath,
    [Parameter(Mandatory = $true)][string]$QuantizationManifestPath,
    [string]$Tag = "turboquant-gemma4",
    [string]$ReleaseName = "TurboQuant Gemma4 GGUF",
    [string]$Repo = "",
    [int64]$ChunkSizeBytes = 1900000000
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) is required."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not $Repo) {
    $Repo = gh repo view --json nameWithOwner --jq .nameWithOwner
}

$gguf = [System.IO.Path]::GetFullPath($GgufPath)
$manifest = [System.IO.Path]::GetFullPath($QuantizationManifestPath)
if (-not (Test-Path $gguf)) { throw "GGUF not found: $gguf" }
if (-not (Test-Path $manifest)) { throw "Quantization manifest not found: $manifest" }

$releaseRoot = Join-Path $repoRoot ".tmp_release_upload"
if (Test-Path $releaseRoot) {
    Remove-Item -LiteralPath $releaseRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
Copy-Item $gguf (Join-Path $releaseRoot ([IO.Path]::GetFileName($gguf))) -Force

python scripts/package_ollama_models.py split-file --source (Join-Path $releaseRoot ([IO.Path]::GetFileName($gguf))) --chunk-size $ChunkSizeBytes --delete-source *> $null

@'
import hashlib
import json
from pathlib import Path
root = Path(r"$releaseRoot")
parts = []
for path in sorted(root.glob("*.gguf.[0-9][0-9][0-9]")):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    parts.append({"name": path.name, "sha256": digest, "size_bytes": path.stat().st_size})
manifest = {"schema_version":"1","merge_strategy":"concat","parts":parts}
(root / "gguf_download_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
'@ | python -

$releaseExists = $true
try {
    gh release view $Tag --repo $Repo *> $null
} catch {
    $releaseExists = $false
}
if (-not $releaseExists) {
    gh release create $Tag --repo $Repo --title $ReleaseName --notes "TurboQuant GGUF split parts and provenance manifest"
}

$assets = Get-ChildItem $releaseRoot
foreach ($asset in $assets) {
    gh release upload $Tag $asset.FullName --repo $Repo --clobber
}
gh release upload $Tag $manifest --repo $Repo --clobber

$downloadManifestPath = Join-Path $releaseRoot "gguf_download_manifest.json"
$downloadManifest = Get-Content $downloadManifestPath | ConvertFrom-Json
$parts = @()
foreach ($part in $downloadManifest.parts) {
    $name = $part.name
    $parts += @{
        name = $name
        url = "https://github.com/$Repo/releases/download/$Tag/$name"
        sha256 = $part.sha256
        size_bytes = $part.size_bytes
    }
}
$outManifest = @{
    schema_version = "1"
    merge_strategy = "concat"
    parts = $parts
}
$outManifestPath = Join-Path $releaseRoot "gguf_download_manifest.public.json"
$outManifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $outManifestPath -Encoding UTF8
gh release upload $Tag $outManifestPath --repo $Repo --clobber

Write-Host "GGUF manifest URL:"
Write-Host "https://github.com/$Repo/releases/download/$Tag/gguf_download_manifest.public.json"
Write-Host "Quantization manifest URL:"
Write-Host "https://github.com/$Repo/releases/download/$Tag/$([IO.Path]::GetFileName($manifest))"
