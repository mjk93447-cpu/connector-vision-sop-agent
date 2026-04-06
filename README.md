# connector-vision-sop-agent

Connector Vision SOP Agent v1.0 scaffold for OLED line automation.

## Goal

Automate the manual 12-step SOP with YOLO26n, Tesseract OCR PSM7, and
PyAutoGUI so Mold ROI setup and pin verification can be executed quickly and
consistently on an offline line PC.

## Structure

- `src/main.py`: entry point and dependency wiring
- `src/vision_engine.py`: YOLO26n + OpenCV + Tesseract vision layer
- `src/control_engine.py`: PyAutoGUI-based click/drag automation layer
- `src/sop_executor.py`: 12-step SOP orchestration (login → recipe → mold ROI → axis → pins → save/apply)
- `src/config_loader.py`: JSON configuration loader
- `src/test_sop.py`: pytest suite for SOP/vision smoke tests
- `assets/config.json`: line tuning template

## Canonical Paths

Use these first when exploring or extending the project:

- `src/main.py` for the main agent
- `scripts/run_pretrain_local.py` for local pretrain
- `docs/ACTIVE_PATHS.md` for active vs legacy path guidance
- `docs/MODEL_ARTIFACT_NAMING.md` for `yolo26x.pt` / `yolo26x_pretrain.pt` / `yolo26x_local_pretrained.pt`

Legacy pretrain scripts are kept only as compatibility shims and should not be used for new work.

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

## LLM & config.proposed.json 수동 적용 가이드

LLM 기반 SOP/비전 튜닝은 **항상 사람이 최종 승인**한다는 원칙을 따른다. 에이전트는 `assets/config.json`을 자동으로 덮어쓰지 않고, 대신 제안만 별도 파일로 남긴다.

### 1. LLM 분석 실행 (콘솔 [L])

1. `connector_vision_agent.exe`를 실행한다.
2. `[1] / [2] / [3]` 중 하나를 선택해 SOP를 한 번 실행한다.
3. 실행이 끝난 뒤, 콘솔에서 `[L]` 키를 눌러 **Offline LLM 분석**을 수행한다.
4. LLM이 활성화되어 있고 설정이 올바르면:
   - 콘솔에 `Suggested config_patch keys`, `SOP recommendations`, `Proposed actions` 리스트가 출력된다.
   - `assets/config.proposed.json` 파일이 생성되거나 갱신된다.

### 2. config.proposed.json 검토

1. 에이전트를 종료하거나 일시 중지한 상태에서:
   - `assets/config.json`
   - `assets/config.proposed.json`
   두 파일을 텍스트 에디터로 연다.
2. `config.proposed.json`에서 변경된 키와 값을 확인한다.
3. 변경 내용이 라인 환경에 적절한지, 안전 범위(예: `ocr_threshold`, `confidence_threshold`)를 벗어나지 않는지 검토한다.

### 3. 승인된 변경 수동 적용

1. 필요하다면 `assets/config.json`을 백업한다. 예:

   - `config.backup-2026-03-12.json`

2. 승인된 변경만 `config.proposed.json`에서 `config.json`으로 **수동으로 복사**한다.
3. 저장 후, 다음 SOP 실행부터는 업데이트된 `config.json`이 사용된다.
4. 적용이 끝난 `config.proposed.json`은:
   - 보관이 필요하면 리네임하여 기록용으로 남기고,
   - 그렇지 않으면 삭제해도 된다 (다음 [L] 실행 시 다시 생성 가능).

> 중요: 현재 버전에서는 어떠한 경우에도 EXE가 `config.json`을 자동으로 수정하지 않는다.  
> 항상 엔지니어가 `config.proposed.json`을 검토한 뒤 필요한 변경만 수동으로 반영해야 한다.

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
