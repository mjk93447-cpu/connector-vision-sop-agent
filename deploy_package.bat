@echo off
setlocal

if not exist dist\connector_vision_agent.exe (
  echo ERROR: dist\connector_vision_agent.exe not found. Run build.bat first.
  exit /b 1
)

rem Ensure deploy directory exists
if not exist deploy (
  mkdir deploy
)

xcopy /Y dist\connector_vision_agent.exe deploy\
copy /Y assets\config.json deploy\
copy /Y README.md deploy\

rem Requires zip CLI to be available in PATH.
zip -r connector_vision_v1.0.zip deploy

echo ✅ deploy/ 완성

endlocal

