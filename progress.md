# Progress — Connector Vision SOP Agent

_최종 갱신: 2026-03-16_

## 현재 브랜치
`main` (CP-0~CP-4 전체 머지 완료)

## 완료 체크포인트
| CP | 내용 | 테스트 | 커버리지 |
|----|------|--------|----------|
| CP-0 | pytest 인프라, conftest, 4개 모듈 테스트 | 72 pass | 60%+ |
| CP-1 | Ollama LLM 백엔드, llm_offline.py 재작성 | 115 pass | 93% |
| CP-2 | YOLO26x, VisionEngine 단일 클래스 통합 | 163 pass | 87% |
| CP-3 | Tesseract/pytesseract 완전 제거 | 157 pass | 92% |
| CP-4 | config v2.0.0, TEST_REPORT.md | 157 pass | 92% |
| fix | config_loader EXE 경로 해석, 포터블 번들 구조 수정 | 163 pass | 92% |

## 현재 스택 (v2.0.0)
- YOLO: yolo26x (`assets/models/yolo26x.pt`)
- LLM: phi4-mini-reasoning via Ollama (`http://localhost:11434`)
- OCR: 완전 제거
- 테스트: 163개, 92% 커버리지

## 진행 중
- GitHub Actions 포터블 번들 빌드 (run: 23136160146)
  - Part1: EXE + Ollama binary → `portable-part1-app`
  - Part2: phi4-mini-reasoning → `portable-part2-phi4-mini`

## 다음 작업 후보
- [ ] YOLO26x 실제 가중치 학습 및 교체
- [ ] VisionAgent 별칭 제거 (deprecated)
- [ ] main.py, sop_executor.py 레거시 OCR 레퍼런스 정리
- [ ] Checkpoint 4 로컬 검증 완결 (TEST_REPORT.md 업데이트)

## 알려진 이슈
- `assets/models/yolo26x.pt`: CI에서는 yolo26n.pt 플레이스홀더 사용 중
- `llama_cpp` 백엔드: deprecated 상태, 코드 미삭제
- `.coveragerc` 제외: main.py, control_engine.py, sop_executor.py, test_sop.py

## 핵심 커맨드
```bash
bash run_tests.sh          # 테스트 실행
gh run view 23136160146    # 현재 빌드 상태
```
