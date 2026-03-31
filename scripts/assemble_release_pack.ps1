param(
    [Parameter(Mandatory = $true)]
    [string]$AppRoot,

    [Parameter(Mandatory = $true)]
    [string]$PretrainRoot,

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

if (Test-Path $OutputRoot) {
    Remove-Item -LiteralPath $OutputRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null

Copy-Tree -Source $AppRoot -Destination $OutputRoot
Copy-Tree -Source $PretrainRoot -Destination $OutputRoot

if ($LlmArtifactRoot -and (Test-Path $LlmArtifactRoot)) {
    Copy-Tree -Source $LlmArtifactRoot -Destination (Join-Path $OutputRoot "ollama_models")
} else {
    New-TextFile -Path (Join-Path $OutputRoot "ollama_models\PLACE_LLM_HERE.txt") -Content @"
Drop the connector-agent-llm artifact contents here:
  - blobs\
  - manifests\

This folder is intentionally left as a placeholder until the LLM artifact is merged.
"@
}

if (-not (Test-Path (Join-Path $OutputRoot "pretrain_data"))) {
    New-Item -ItemType Directory -Path (Join-Path $OutputRoot "pretrain_data") -Force | Out-Null
    New-TextFile -Path (Join-Path $OutputRoot "pretrain_data\PLACE_PRETRAIN_DATA_HERE.txt") -Content @"
This folder should contain the bundled local pretraining dataset.
Extract connector-agent-pretrain.zip here if the dataset is distributed separately.
"@
}

New-TextFile -Path (Join-Path $OutputRoot "MERGE_GUIDE.txt") -Content @"
Connector Vision SOP Agent 4.2.0 Deployment Pack

Contents:
  - Root: connector_vision_agent.exe, connector_pretrain.exe, start_agent.bat
  - pretrain_data\: bundled dataset for local YOLO26x training
  - ollama_models\: LLM blobs and manifests from connector-agent-llm

If you only received part of the artifacts:
  1. Copy the app bundle into this folder first.
  2. Copy the pretrain bundle into the same root so connector_pretrain.exe
     and pretrain_data\ sit next to the main EXE.
  3. Copy the LLM bundle contents into ollama_models\.

Look for PLACE_PRETRAIN_DATA_HERE.txt and PLACE_LLM_HERE.txt for drop locations.
"@

New-TextFile -Path (Join-Path $OutputRoot "PLACE_APP_HERE.txt") -Content @"
This folder is the final line deployment root.
Put connector_vision_agent.exe, connector_pretrain.exe, and the launchers here.
"@

Write-Host "[assemble] pack ready -> $OutputRoot"
