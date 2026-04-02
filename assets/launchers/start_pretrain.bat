@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Connector Vision SOP Agent v4.4.0 [Local Pretrain]
setlocal EnableExtensions EnableDelayedExpansion

set OLLAMA_MODELS=%~dp0ollama_models
set NO_PROXY=localhost,127.0.0.1,::1
set no_proxy=localhost,127.0.0.1,::1
set "DEFAULT_EPOCHS=40"
set "DEFAULT_BATCH=16"

echo ================================================================
echo  Connector Vision SOP Agent v4.4.0  [Local Pretrain]
echo  Data : pretrain_data (pcb_inspection + pcb_component_detection + pcb_defect_detection + rf100_smd_components + rf100_deeppcb)
echo  Model: yolo26x_local_pretrained.pt
echo ================================================================
echo.

if exist "%~dp0connector_pretrain.exe" (
    set "EPOCHS=%DEFAULT_EPOCHS%"
    set "BATCH=%DEFAULT_BATCH%"
    set /p "USER_EPOCHS=Enter epochs [%DEFAULT_EPOCHS%]: "
    if defined USER_EPOCHS set "EPOCHS=!USER_EPOCHS!"
    set /p "USER_BATCH=Enter batch [%DEFAULT_BATCH%]: "
    if defined USER_BATCH set "BATCH=!USER_BATCH!"

    for /f "tokens=* delims= " %%A in ("!EPOCHS!") do set "EPOCHS=%%A"
    for /f "tokens=* delims= " %%A in ("!BATCH!") do set "BATCH=%%A"
    echo(!EPOCHS!| findstr /r "^[0-9][0-9]*$" >nul || set "EPOCHS="
    echo(!BATCH!| findstr /r "^[0-9][0-9]*$" >nul || set "BATCH="

    echo.
    set "PRETRAIN_ARGS="
    if defined EPOCHS set "PRETRAIN_ARGS=!PRETRAIN_ARGS! --epochs !EPOCHS!"
    if defined BATCH set "PRETRAIN_ARGS=!PRETRAIN_ARGS! --batch !BATCH!"
    if not "!PRETRAIN_ARGS!"=="" (
        echo [1/1] Launching local pretrain EXE with!PRETRAIN_ARGS!...
        "%~dp0connector_pretrain.exe" !PRETRAIN_ARGS!
    ) else (
        echo [1/1] Launching local pretrain EXE with auto profile...
        "%~dp0connector_pretrain.exe"
    )
) else (
    echo [ERROR] connector_pretrain.exe not found.
    echo         Rebuild the local pretrain bundle or restore the EXE next to this BAT.
)

echo.
echo Pretrain finished. Press any key to close.
pause >nul
