# config v2.0.0 구조

```json
{
  "version": "2.0.0", "password": "1111", "pin_count_min": null,
  "vision": {"model_path": "assets/models/yolo26x.pt", "confidence_threshold": 0.6},
  "llm": {"enabled": false, "backend": "ollama", "model_path": "llama4:scout",
          "http_url": "http://localhost:11434/v1/chat/completions",
          "ctx_size": 8192, "max_input_tokens": 6144, "max_output_tokens": 1024}
}
```

- config 변경 제안 → `assets/config.proposed.json` 만 출력, 수동 적용
- `assets/config.json` 직접 수정 금지
