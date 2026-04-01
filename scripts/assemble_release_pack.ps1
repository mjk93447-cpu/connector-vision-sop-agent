param(
    [Parameter(Mandatory = $true)]
    [string]$AppRoot,

    [string]$PretrainRoot = "",

    [string]$OutputRoot = "connector_agent_pack",

    [string]$LlmArtifactRoot = ""
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

if ($PretrainRoot -and (Test-Path $PretrainRoot)) {
    $pretrainExe = Join-Path $PretrainRoot "connector_pretrain.exe"
    if (Test-Path $pretrainExe) {
        Copy-Item -LiteralPath $pretrainExe -Destination (Join-Path $OutputRoot "connector_pretrain.exe") -Force
    }

    $pretrainDataRoot = Join-Path $PretrainRoot "pretrain_data"
    if (-not (Test-Path $pretrainDataRoot)) {
        $pretrainDataRoot = $PretrainRoot
    }

    Copy-Tree -Source $pretrainDataRoot -Destination (Join-Path $OutputRoot "pretrain_data")
} else {
    Ensure-PlaceholderDirectory `
        -DirectoryPath (Join-Path $OutputRoot "pretrain_data") `
        -PlaceholderPath (Join-Path $OutputRoot "pretrain_data\PLACE_PRETRAIN_DATA_HERE.txt") `
        -PlaceholderContent @"
Drop the connector-agent-pretrain artifact contents here:
  - connector_pretrain.exe
  - pretrain_data\

This folder is intentionally left as a placeholder until the pretrain artifact is merged.
"@
}

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
Connector Vision SOP Agent 4.2.0 Deployment Pack

Contents:
  - connector-agent-app.zip: main app EXE + launchers + config/models
  - connector-agent-pretrain.zip: connector_pretrain.exe + pretrain_data tree
  - connector-agent-llm.zip: Ollama model blobs/manifests

If you only received part of the artifacts:
  1. Copy the app bundle into this folder first.
  2. Copy the pretrain bundle into the same root so connector_pretrain.exe
     and pretrain_data\ sit next to the main EXE.
  3. Copy the LLM bundle contents into ollama_models\.

Look for PLACE_PRETRAIN_DATA_HERE.txt and PLACE_LLM_HERE.txt for drop locations.
"@

New-TextFile -Path (Join-Path $OutputRoot "PLACE_APP_HERE.txt") -Content @"
This folder is the final line deployment root.
Put connector_vision_agent.exe, connector_pretrain.exe, start_agent.bat,
start_pretrain.bat, and the asset folders here.
"@

Write-Host "[assemble] pack ready -> $OutputRoot"
