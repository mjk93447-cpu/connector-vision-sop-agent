@echo off
python -m pip install --upgrade --force-reinstall --no-cache-dir -r requirements.txt -f https://download.pytorch.org/whl/torch_stable.html
pyinstaller build_exe.spec
echo EXE: dist/connector_vision_agent.exe
