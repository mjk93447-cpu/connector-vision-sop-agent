# 포터블 빌드 (2-part split)

- Part1 `portable-part1-app` : EXE + ollama.exe + launchers
- Part2 `portable-part2-phi4-mini` : phi4-mini-reasoning 모델 블롭
- 조립: Part2 → `connector_agent\ollama_models\` 압축해제 후 `start_agent.bat`

## CI 트리거
```bash
gh workflow run "Build Portable Offline Bundle (Split)" --ref main
```
