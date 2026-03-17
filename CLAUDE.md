# Connector Vision SOP Agent — CLAUDE.md

> 상세 계획: @ROADMAP.md | 진행 상태: @progress.md

## ⚠️ [MANDATORY] YOLO 모델 규칙 (2026-03-17 확정 — 위반 금지)

```
YOLO 모델: 반드시 yolo26x.pt 단독 사용
YOLOv8 / YOLOv9 / YOLOv10 / YOLOv11 = 절대 금지 (STRICTLY FORBIDDEN)
```

- **Vision 관련 모든 설정·코드·워크플로우·스크립트**는 `yolo26x.pt` 기반으로만 처리.
- `from ultralytics import YOLO; YOLO("yolo26x.pt")` 외 다른 YOLO 아키텍처 호출 금지.
- 프리트레인/파인튜닝 베이스 모델도 반드시 `yolo26x.pt` 사용.
- 외부 GUI 특화 YOLO 모델 통합 시, **반드시 YOLO26x 아키텍처(.pt)로 제공된 것만** 허용.
- 이 규칙은 Claude 및 모든 기여자에게 영구 적용. 예외 없음.

## 스택
- Python 3.11, PyTorch 2.4 CPU, OpenCV 4.9, PyAutoGUI
- YOLO26x (vision), Ollama HTTP (LLM: phi4-mini-reasoning / llama4:scout)
- pytest (커버리지 ≥80%), black + ruff, PyInstaller EXE

## 절대 수정 금지
```
assets/models/   assets/config.json   /data/models/   /config/secrets.yaml
```
LLM 제안 → `assets/config.proposed.json` 만 출력, 수동 적용.

## 핵심 파일
| 파일 | 역할 |
|------|------|
| `src/main.py` | 진입점·콘솔 UI |
| `src/vision_engine.py` | YOLO26x 단일 클래스 |
| `src/control_engine.py` | PyAutoGUI 제어 |
| `src/sop_executor.py` | 12단계 SOP |
| `src/llm_offline.py` | Ollama HTTP 백엔드 |
| `src/sop_advisor.py` | config patch 제안 |
| `src/log_manager.py` | JSONL 로그 |
| `src/config_loader.py` | EXE/소스 경로 해석 |
| `assets/config.json` | v2.0.0 (vision+llm 블록) |
| `tests/unit/` | 163개 테스트, 커버리지 92% |

## 커맨드
```bash
bash run_tests.sh                        # 테스트 + 커버리지
python -m black src/ tests/ && python -m ruff check src/ tests/ --fix
gh workflow run "Build Portable Offline Bundle (Split)" --ref main
```

## 규칙 (코드)
1. 코드 수정 → `bash run_tests.sh` 통과 → black+ruff → 커밋
2. 커밋 형식: `[feat/fix/refactor/chore/test] 한국어 설명`
3. 테스트 실패 시 원인 분석 후 재시도 (동일 커맨드 반복 금지)
4. 새 SOP 단계 → 대응 테스트 필수

## 세션 습관 (매 작업 자동 적용 — 생략 불가)
| 시점 | 행동 |
|------|------|
| **작업 시작** | `@progress.md` 로드하여 현재 상태 파악 |
| **기능 1개 완료** | `/compact` 실행하여 컨텍스트 압축 |
| **다른 기능 전환** | `/clear` 실행하여 컨텍스트 초기화 |
| **파일 참조** | `@src/vision_engine.py` 형식으로 지정 파일만 참조 |
| **요구사항 불명확** | 구현 전 즉시 질문 (추측으로 토큰 낭비 금지) |
| **세션 종료** | `progress.md` 업데이트 후 커밋 |

## config v2.0.0 구조
```json
{
  "version": "2.0.0", "password": "1111", "pin_count_min": null,
  "vision": {"model_path": "assets/models/yolo26x.pt", "confidence_threshold": 0.6},
  "llm": {"enabled": false, "backend": "ollama", "model_path": "llama4:scout",
          "http_url": "http://localhost:11434/v1/chat/completions",
          "ctx_size": 8192, "max_input_tokens": 6144, "max_output_tokens": 1024}
}
```

## 포터블 빌드 (2-part split)
- Part1 `portable-part1-app` : EXE + ollama.exe + launchers
- Part2 `portable-part2-phi4-mini` : phi4-mini-reasoning 모델 블롭
- 조립: Part2 → `connector_agent\ollama_models\` 압축해제 후 `start_agent.bat`
