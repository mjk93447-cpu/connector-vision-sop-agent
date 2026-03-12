# connector-vision-sop-agent

Connector Vision SOP Agent v1.0 scaffold for OLED line automation.

## Goal

Automate the manual 12-step SOP with YOLOv26n, Tesseract OCR PSM7, and
PyAutoGUI so Mold ROI setup and pin verification can be executed quickly and
consistently on an offline line PC.

## Structure

- `src/main.py`: entry point and dependency wiring
- `src/vision_engine.py`: YOLOv26n + OpenCV + Tesseract vision layer
- `src/control_engine.py`: PyAutoGUI-based click/drag automation layer
- `src/sop_executor.py`: 12-step SOP orchestration (login → recipe → mold ROI → axis → pins → save/apply)
- `src/config_loader.py`: JSON configuration loader
- `src/test_sop.py`: pytest suite for SOP/vision smoke tests
- `assets/config.json`: line tuning template

## Build (PyInstaller EXE)

Offline EXE for the line PC can be produced with:

```bat
build.bat
```

This will:

- Install `requirements.txt`
- Run `pyinstaller build_exe.spec`
- Emit `dist\connector_vision_agent.exe`

> Note: In environments with Python 3.12, the pinned `torch==2.3.0+cpu`
> wheel may not be available. For local testing you can either use Python
> 3.11 or adjust the Torch version to a compatible one (e.g. `2.3.1`).

## Testing

Run the smoke tests with:

```bash
pytest -q
```

The tests use monkeypatching so they **do not require** a real display or YOLO
weights; they only validate that the 12-step SOP sequence and vision wiring are
intact.

## Line PC Deployment (5 minutes)

1. Copy `connector_vision_agent.exe` to the line PC (e.g. `C:\tools\connector`).
2. Place `assets\config.json` next to the EXE and edit as needed, including:
   - `password`: `"라인비번"`
3. Double-click the EXE.
4. Within ~30 seconds the 12-step SOP automation will execute end-to-end using
   the configured password and thresholds.

## Release & Packaging

- To create a deployable package directory and zip:

  ```bat
  deploy_package.bat
  ```

  This script will:

  - Copy `dist\connector_vision_agent.exe` into `deploy\`
  - Copy `assets\config.json` and `README.md` into `deploy\`
  - Create `connector_vision_v1.0.zip` from the `deploy\` directory

- To publish a GitHub Release (run after tagging `v1.0.0`):

  ```bash
  gh release create v1.0.0 \
    dist/connector_vision_agent.exe \
    assets/config.json \
    README.md \
    --title "v1.0.0 Production" \
    --notes "12-step SOP automation complete"
  ```

## 🎯 라인 PC 배포 (3분)

1. 브라우저에서 프로젝트 릴리스 페이지로 이동합니다. 예:
   - `https://github.com/[USERNAME]/connector-vision-sop-agent/releases/tag/v1.0.0`
2. Assets 섹션에서 `connector_vision_agent.exe`를 다운로드합니다.
3. 같은 위치에 `config.json`을 두고 `"password"` 값을 실제 라인 비밀번호(`"라인비번"`)로 설정합니다.
4. `connector_vision_agent.exe`를 더블 클릭하여 실행합니다.
5. 약 30초 내에 12-step SOP 자동화가 완료되며, 콘솔에서는 다음과 유사한 로그를 확인할 수 있습니다:

   ```text
   🎯 v1.0 Starting...
   Step 1/12: login ✓
   ...
   Step 12/12: apply ✓ (28.4s)
   ✅ SOP Complete!
   ```


