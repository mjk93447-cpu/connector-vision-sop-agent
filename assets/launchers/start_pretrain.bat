@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Connector Vision SOP Agent v4.2.0 [Local Pretrain]

set OLLAMA_MODELS=%~dp0ollama_models
set NO_PROXY=localhost,127.0.0.1,::1
set no_proxy=localhost,127.0.0.1,::1

echo ================================================================
echo  Connector Vision SOP Agent v4.2.0  [Local Pretrain]
echo  Data : pretrain_data (bundled)
echo  Model: yolo26x_pretrained.pt
echo ================================================================
echo.

if exist "%~dp0connector_pretrain.exe" (
    echo [1/1] Launching local pretrain EXE...
    "%~dp0connector_pretrain.exe" --source local_bundle
) else (
    echo [ERROR] connector_pretrain.exe not found.
    echo         Rebuild the local pretrain bundle or restore the EXE next to this BAT.
)

echo.
echo Pretrain finished. Press any key to close.
pause >nul
