# 테스트 규칙 (tests/ 작업 시 참조)

## 커맨드
```bash
bash run_tests.sh          # 테스트 + 커버리지 (커밋 전 필수)
```

## 현황 (2026-03-19)
- 453 pass, 커버리지 92%
- 주요 테스트 파일: tests/unit/ 아래 13개 모듈

## 커버리지 제외 (.coveragerc)
- main.py, control_engine.py, sop_executor.py, test_sop.py

## 신규 기능 규칙
- 새 SOP 단계 추가 → 대응 테스트 필수
- YOLO/화면 의존 테스트 → monkeypatch/mock으로 헤드리스 환경 지원
