# Windows-MCP PyQt6 GUI 자동 테스트 가이드

Windows-MCP의 computer-use를 활용한 7탭 GUI 시나리오 테스트.
Claude Code 세션에서 Windows-MCP 도구를 직접 호출하여 사용한다.

---

## 사용 방법

Claude Code 채팅에서 아래 지시문을 그대로 입력하면 된다.

---

## 시나리오 1 — Bug2 LLM 응답 검증 (v3.2.3 수정 확인)

```
[Windows-MCP GUI 테스트 - Bug2]
1. python src/main.py 를 background로 실행
2. 앱 창이 뜨면 스크린샷 캡처
3. "LLM Chat" 탭 클릭
4. 입력창에 "테스트 메시지" 입력 후 Send 버튼 클릭
5. 120초 이내에 응답이 오면 성공, "Thinking..." 고착이면 Bug2 재발
6. 결과 스크린샷 저장
```

---

## 시나리오 2 — Training tqdm 진행바 검증 (v3.2.8 수정 확인)

```
[Windows-MCP GUI 테스트 - Training tqdm]
1. "Training" 탭 (Tab7) 클릭
2. Start Training 버튼 클릭
3. tqdm 진행바가 표시되는지 확인 (NoneType 오류 없어야 함)
4. 콘솔 에러 없이 진행되면 성공
5. 결과 스크린샷 저장
```

---

## 시나리오 3 — Vision Canvas YOLO 검출 검증

```
[Windows-MCP GUI 테스트 - Vision]
1. "Vision" 탭 클릭
2. "Open File" 버튼 클릭 → tests/fixtures/ 에서 테스트 이미지 선택
3. YOLO bbox overlay가 캔버스에 표시되는지 확인
4. confidence threshold 0.6 이상 검출 결과 확인
5. 결과 스크린샷 저장
```

---

## 시나리오 4 — OCR 버튼 인식 검증 (v3.2.4 다단어 병합)

```
[Windows-MCP GUI 테스트 - OCR]
1. "SOP" 탭 클릭
2. Run SOP 버튼 클릭
3. 로그 패널에 OCR 감지 결과 확인 ("image source" 등 다단어 버튼 인식)
4. 로그 스크린샷 저장
```

---

## Windows-MCP 권한 (settings.local.json에 등록됨)

- `mcp__Windows_MCP__screenshot` — 화면 캡처
- `mcp__Windows_MCP__click` — 클릭
- `mcp__Windows_MCP__type_text` — 텍스트 입력
- `mcp__Windows_MCP__find_element` — UI 요소 탐색

---

## 주의사항

- GUI 앱 실행 전 `python src/main.py` 프로세스가 없는지 확인
- 테스트 실행 중 마우스/키보드 조작 금지
- Ollama 미실행 상태에서 LLM 테스트 시 "Ollama not running" 메시지 정상 출력 확인
