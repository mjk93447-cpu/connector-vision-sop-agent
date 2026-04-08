@echo off
setlocal
cd /d "%~dp0"

rem Repository convenience wrapper. The distributable launcher lives at
rem assets\launchers\start_agent.bat and is the only supported app-bundle entry.
call "%~dp0assets\launchers\start_agent.bat"

endlocal
