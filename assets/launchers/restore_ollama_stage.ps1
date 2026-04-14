param(
    [string]$ModelsRoot = "",
    [switch]$DeleteParts = $true
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-LauncherRoot {
    return Split-Path -Parent $MyInvocation.MyCommand.Path
}

if (-not $ModelsRoot) {
    $ModelsRoot = Join-Path (Get-LauncherRoot) "ollama_models"
}

$modelsPath = [System.IO.Path]::GetFullPath($ModelsRoot)
$manifestPath = Join-Path $modelsPath "ollama_split_manifest.json"

if (-not (Test-Path $manifestPath)) {
    Write-Host "[restore] No split manifest found at $manifestPath"
    exit 0
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$restored = 0

foreach ($entry in @($manifest.split_files)) {
    $relativePath = [string]$entry.path
    $targetPath = Join-Path $modelsPath $relativePath
    $targetDir = Split-Path -Parent $targetPath
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

    $expectedSize = 0
    try {
        $expectedSize = [int64]$entry.size
    } catch {
        $expectedSize = 0
    }

    $needsRestore = $true
    if (Test-Path $targetPath) {
        try {
            $existing = Get-Item -LiteralPath $targetPath
            if ($expectedSize -gt 0 -and $existing.Length -eq $expectedSize) {
                $needsRestore = $false
            }
        } catch {
            $needsRestore = $true
        }
    }

    if ($needsRestore) {
        if (Test-Path $targetPath) {
            Remove-Item -LiteralPath $targetPath -Force
        }

        $targetStream = [System.IO.File]::Open(
            $targetPath,
            [System.IO.FileMode]::Create,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None
        )
        try {
            foreach ($partRel in @($entry.parts)) {
                $partPath = Join-Path $modelsPath ([string]$partRel)
                if (-not (Test-Path $partPath)) {
                    throw "Missing split part: $partPath"
                }
                $partStream = [System.IO.File]::OpenRead($partPath)
                try {
                    $partStream.CopyTo($targetStream)
                } finally {
                    $partStream.Dispose()
                }
                if ($DeleteParts) {
                    Remove-Item -LiteralPath $partPath -Force
                }
            }
        } finally {
            $targetStream.Dispose()
        }
        $restored += 1
        Write-Host "[restore] rebuilt $relativePath"
    } elseif ($DeleteParts) {
        foreach ($partRel in @($entry.parts)) {
            $partPath = Join-Path $modelsPath ([string]$partRel)
            if (Test-Path $partPath) {
                Remove-Item -LiteralPath $partPath -Force
            }
        }
    }
}

Write-Host "[restore] completed. Restored $restored split file(s) in $modelsPath"
