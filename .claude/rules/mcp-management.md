# MCP 서버 관리 (토큰 절약)

## 현황
이 프로젝트의 settings.local.json에서 허용된 MCP는 HuggingFace 2개뿐.
나머지(Claude_Preview, Claude_in_Chrome, scheduled-tasks 등)는 요청당 15K+ 토큰 overhead.

## 세션 시작 시 확인
```
/mcp
```
불필요한 서버가 활성화되어 있으면 비활성화.

## 이 프로젝트에서 불필요한 MCP
- Claude_Preview (웹 미리보기 — Python 개발에 불필요)
- Claude_in_Chrome (브라우저 자동화 — 불필요)
- mcp__b4d8e858 (HuggingFace — 모델 검색 시에만 필요)

## 필요 시에만 사용
- mcp__scheduled-tasks: 자동화 스케줄 설정 시
- mcp__mcp-registry: 새 MCP 서버 탐색 시
