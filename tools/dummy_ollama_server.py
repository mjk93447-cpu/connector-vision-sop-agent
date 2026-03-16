"""
Dummy Ollama server — CP-1 개발 유틸리티.

실제 Ollama 서버 없이 OfflineLLM의 HTTP 통신을 수동으로 검증할 수 있는
최소 Mock HTTP 서버. 단위 테스트에서는 requests.post를 직접 mock하므로
이 서버는 수동 E2E 확인 전용이다.

사용법:
    python tools/dummy_ollama_server.py          # 기본 포트 11434
    python tools/dummy_ollama_server.py --port 8080

요청 예:
    POST http://localhost:11434/v1/chat/completions
    {"model": "llama4:scout", "messages": [...], "stream": false}

응답:
    {"choices": [{"message": {"role": "assistant", "content": "Mock response from dummy_ollama_server"}}]}
"""

from __future__ import annotations

import argparse
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

MOCK_RESPONSE = {
    "id": "chatcmpl-dummy-001",
    "object": "chat.completion",
    "model": "llama4:scout",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": (
                    '{"config_patch": {}, "sop_recommendations": ["dummy_ollama_server 응답 — 실제 모델 없음"], '
                    '"raw_text": "Mock response from dummy_ollama_server. 실제 Ollama를 사용하세요."}'
                ),
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
}


class OllamaHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:  # noqa: D102
        logger.info(fmt, *args)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            req = json.loads(body)
            model = req.get("model", "?")
            msgs = req.get("messages", [])
            logger.info("Request: model=%s, messages=%d", model, len(msgs))
        except Exception:
            logger.warning("Could not parse request body")

        payload = json.dumps(MOCK_RESPONSE, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dummy Ollama-compatible HTTP server for CP-1 dev testing"
    )
    parser.add_argument(
        "--port", type=int, default=11434, help="Listen port (default: 11434)"
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Listen host (default: 127.0.0.1)"
    )
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), OllamaHandler)
    logger.info(
        "Dummy Ollama server listening on http://%s:%d/v1/chat/completions",
        args.host,
        args.port,
    )
    logger.info("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopped.")


if __name__ == "__main__":
    main()
