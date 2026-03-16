# Progress — Connector Vision SOP Agent

_최종 갱신: 2026-03-16 (세션 종료)_

## 현재 브랜치
`main` (CP-0~CP-4 + 포터블 번들 fix 완료)

## 완료 체크포인트
| CP | 내용 | 테스트 | 커버리지 |
|----|------|--------|----------|
| CP-0 | pytest 인프라, conftest | 72 pass | 60%+ |
| CP-1 | Ollama LLM 백엔드 | 115 pass | 93% |
| CP-2 | YOLO26x, VisionEngine 단일 클래스 | 163 pass | 87% |
| CP-3 | Tesseract 완전 제거 | 157 pass | 92% |
| CP-4 | config v2.0.0, TEST_REPORT.md | 157 pass | 92% |
| fix | config_loader EXE 경로, 포터블 번들 구조 | 163 pass | 92% |
| **chore** | **토큰 최적화 세팅 완료** | — | — |
| **docs** | **라인 PC 영어 매뉴얼 작성 완료** | — | — |

## 현재 스택 (v2.0.0)
- YOLO: yolo26x (`assets/models/yolo26x.pt`, CI는 yolo26n.pt 플레이스홀더)
- LLM: phi4-mini-reasoning via Ollama (`http://localhost:11434`)
- OCR: 완전 제거 / 테스트: 163개, 92% 커버리지

## ✅ 포터블 번들 빌드 완료 (run: 23136160146)
| Artifact | 크기 | 상태 |
|----------|------|------|
| `portable-part1-app` | **440 MB** | ✅ 완료 |
| `portable-part2-phi4-mini` | **2,749 MB (~2.7 GB)** | ✅ 완료 |

다운로드:
https://github.com/mjk93447-cpu/connector-vision-sop-agent/actions/runs/23136160146

## 다음 작업 후보
- [ ] YOLO26x 실제 가중치 학습 및 교체 (`assets/models/yolo26x.pt`)
- [ ] VisionAgent 별칭 제거 (deprecated since CP-2)
- [ ] main.py, sop_executor.py 레거시 OCR 레퍼런스 정리
- [ ] llama_cpp 백엔드 코드 삭제 (deprecated since CP-1)
- [ ] Checkpoint 4 로컬 검증 완결 (TEST_REPORT.md 업데이트)
- [ ] actions/upload-artifact@v4 → v4 Node.js 24 호환 버전 업그레이드 (2026-06 전)

## 알려진 이슈
- `assets/models/yolo26x.pt`: CI 플레이스홀더 (yolo26n.pt 복사본)
- `llama_cpp` 백엔드: deprecated, 코드 미삭제
- `.coveragerc` 제외: main.py, control_engine.py, sop_executor.py, test_sop.py

## 핵심 커맨드
```bash
bash run_tests.sh                                          # 테스트+lint
gh workflow run "Build Portable Offline Bundle (Split)"    # 포터블 빌드
gh run view 23136160146                                    # 마지막 빌드 상태
```
