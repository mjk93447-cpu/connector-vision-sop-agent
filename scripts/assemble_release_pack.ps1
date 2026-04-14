param(
    [Parameter(Mandatory = $true)]
    [string]$AppRoot,

    [string]$OutputRoot = "connector_agent_pack",

    [string]$LlmArtifactRoot = "",

    [ValidateSet("cpu", "gpu", "unknown")]
    [string]$RuntimeFlavor = "unknown"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Copy-Tree {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Source,
        [Parameter(Mandatory = $true)]
        [string]$Destination
    )

    if (-not (Test-Path $Source)) {
        throw "Missing source folder: $Source"
    }

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null

    Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
        $target = Join-Path $Destination $_.Name
        if ($_.PSIsContainer) {
            Copy-Item -LiteralPath $_.FullName -Destination $target -Recurse -Force
        } else {
            Copy-Item -LiteralPath $_.FullName -Destination $target -Force
        }
    }
}

function New-TextFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Content
    )

    $dir = Split-Path -Parent $Path
    if ($dir) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    Set-Content -LiteralPath $Path -Value $Content -Encoding UTF8
}

function Ensure-PlaceholderDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DirectoryPath,
        [Parameter(Mandatory = $true)]
        [string]$PlaceholderPath,
        [Parameter(Mandatory = $true)]
        [string]$PlaceholderContent
    )

    if (-not (Test-Path $DirectoryPath)) {
        New-Item -ItemType Directory -Path $DirectoryPath -Force | Out-Null
    }
    if (-not (Test-Path $PlaceholderPath)) {
        New-TextFile -Path $PlaceholderPath -Content $PlaceholderContent
    }
}

if (Test-Path $OutputRoot) {
    Remove-Item -LiteralPath $OutputRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null

Copy-Tree -Source $AppRoot -Destination $OutputRoot

New-TextFile -Path (Join-Path $OutputRoot "runtime_flavor.txt") -Content $RuntimeFlavor

if ($LlmArtifactRoot -and (Test-Path $LlmArtifactRoot)) {
    Copy-Tree -Source $LlmArtifactRoot -Destination (Join-Path $OutputRoot "ollama_models")
} else {
    Ensure-PlaceholderDirectory `
        -DirectoryPath (Join-Path $OutputRoot "ollama_models") `
        -PlaceholderPath (Join-Path $OutputRoot "ollama_models\PLACE_LLM_HERE.txt") `
        -PlaceholderContent @"
Drop the connector-agent-llm artifact contents here:
  - blobs\
  - manifests\

This folder is intentionally left as a placeholder until the LLM artifact is merged.
"@
}

New-TextFile -Path (Join-Path $OutputRoot "MERGE_GUIDE.txt") -Content @"
Connector Vision SOP Agent 6.0.0 Deployment Pack

Contents:
  - connector-agent-app-cpu.zip: main app EXE + CPU runtime
  - connector-agent-app-gpu.zip: main app EXE + CUDA-capable runtime
  - connector-agent-llm-local-cache.zip: Ollama model blobs/manifests

Deployment:
  1. Extract exactly one app pack into the final root.
  2. Optional: copy the LLM bundle contents into ollama_models\.

This folder already includes the packaged runtime. No separate runtime merge is required.
Look for PLACE_LLM_HERE.txt for optional content.
"@

New-TextFile -Path (Join-Path $OutputRoot "PLACE_APP_HERE.txt") -Content @"
This folder is the final line deployment root.
Put connector_vision_agent.exe, start_agent.bat, and the asset folders here.
"@

Write-Host "[assemble] pack ready -> $OutputRoot"
