param(
    [string]$BundleDir = ".",
    [int]$TimeoutSeconds = 45
)

$ErrorActionPreference = "Stop"

$bundle = (Resolve-Path $BundleDir).Path
$launcher = Join-Path $bundle "start_agent.bat"
$exe = Join-Path $bundle "connector_vision_agent.exe"

if (-not (Test-Path $launcher)) {
    throw "Missing launcher: $launcher"
}
if (-not (Test-Path $exe)) {
    throw "Missing exe: $exe"
}

$proc = Start-Process -FilePath $launcher -WorkingDirectory $bundle -PassThru
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$windowProc = $null
$launcherWindow = $null
$connectorProc = $null

while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    $launcherWindow = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
    $connectorProc = Get-Process | Where-Object {
        $_.ProcessName -like "connector_vision_agent*"
    } | Select-Object -First 1
    $candidates = Get-Process | Where-Object {
        $_.ProcessName -like "connector_vision_agent*" -and $_.MainWindowHandle -ne 0
    }
    if ($candidates) {
        $windowProc = $candidates | Select-Object -First 1
        break
    }
}

$result = [ordered]@{
    bundle_dir = $bundle
    launcher = $launcher
    exe = $exe
    started_process_id = $proc.Id
    launcher_window_detected = ($null -ne $launcherWindow -and $launcherWindow.MainWindowHandle -ne 0)
    launcher_window_title = if ($launcherWindow) { $launcherWindow.MainWindowTitle } else { "" }
    connector_process_running = ($null -ne $connectorProc)
    connector_process_id = if ($connectorProc) { $connectorProc.Id } else { 0 }
    connector_has_window = ($null -ne $connectorProc -and $connectorProc.MainWindowHandle -ne 0)
    connector_window_title = if ($connectorProc) { $connectorProc.MainWindowTitle } else { "" }
    gui_window_detected = ($null -ne $windowProc)
    main_window_title = if ($windowProc) { $windowProc.MainWindowTitle } else { "" }
    main_window_handle = if ($windowProc) { $windowProc.MainWindowHandle } else { 0 }
    timestamp = (Get-Date).ToString("s")
}

$artifacts = Join-Path $PWD "artifacts\qa"
New-Item -ItemType Directory -Force -Path $artifacts | Out-Null
$outFile = Join-Path $artifacts ("gui-smoke-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".json")
$result | ConvertTo-Json -Depth 4 | Set-Content -Path $outFile -Encoding UTF8

Write-Host "[gui-smoke] wrote report: $outFile"
Write-Host "[gui-smoke] gui_window_detected=$($result.gui_window_detected)"
Write-Host "[gui-smoke] launcher_window_detected=$($result.launcher_window_detected)"
Write-Host "[gui-smoke] connector_process_running=$($result.connector_process_running)"
Write-Host "[gui-smoke] connector_has_window=$($result.connector_has_window)"
if ($result.main_window_title) {
    Write-Host "[gui-smoke] title=$($result.main_window_title)"
}

Get-Process | Where-Object { $_.ProcessName -like "connector_vision_agent*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process | Where-Object { $_.ProcessName -like "ollama*" } | Stop-Process -Force -ErrorAction SilentlyContinue

if (-not $result.gui_window_detected) {
    throw "GUI smoke failed: no main window detected"
}
