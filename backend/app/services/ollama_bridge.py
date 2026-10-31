"""HTTP reverse proxy bridging 127.0.0.1:11434 to WSL2 Ollama on 172.18.109.88:11434."""
from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
import httpx

TARGET = "http://172.18.109.88:11434"
WSL_SRC = "172.18.96.1"

_transport = httpx.HTTPTransport(local_address=WSL_SRC)
_http_client = httpx.Client(transport=_transport, timeout=120.0)


class OllamaProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._forward("GET")

    def do_POST(self) -> None:
        self._forward("POST")

    def do_HEAD(self) -> None:
        self._forward("HEAD")

    def _forward(self, method: str) -> None:
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len > 0 else None

        fwd_headers = {
            k: v
            for k, v in self.headers.items()
            if k.lower() not in ("host", "content-length", "transfer-encoding")
        }

        try:
            resp = _http_client.request(
                method,
                f"{TARGET}{self.path}",
                content=body,
                headers=fwd_headers,
            )
            self.send_response(resp.status_code)
            for k, v in resp.headers.items():
                if k.lower() not in ("content-length", "transfer-encoding", "connection"):
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(resp.content)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(resp.content)
        except Exception as e:
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            err_body = f'{{"error": "Bridge error: {e}"}}'.encode("utf-8")
            self.send_header("Content-Length", str(len(err_body)))
            self.end_headers()
            self.wfile.write(err_body)

    def log_message(self, format: str, *args) -> None:
        pass


def main() -> None:
    server = HTTPServer(("127.0.0.1", 11434), OllamaProxyHandler)
    print("HTTP Ollama Bridge listening on 127.0.0.1:11434 -> 172.18.109.88:11434")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
