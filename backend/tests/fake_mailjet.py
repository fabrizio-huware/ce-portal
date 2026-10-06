"""Un finto Mailjet: server HTTP locale che risponde nel formato della Send API v3.1.

Il client reale (requests) lo chiama davvero via rete locale: si prova l'intero percorso HTTP,
compresi autenticazione, intestazioni, timeout e connessione rifiutata.
"""

import base64
import json
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

Body = dict[str, Any] | str | Callable[[dict[str, Any]], dict[str, Any]]


def success_for(message: dict[str, Any], n: int, sandbox: bool = False) -> dict[str, Any]:
    recipient = {"Email": message["To"][0]["Email"]}
    if not sandbox:  # in sandbox Mailjet omette MessageID e MessageUUID
        recipient |= {
            "MessageUUID": f"uuid-{n}",
            "MessageID": 1000 + n,
            "MessageHref": f"https://x/{n}",
        }
    return {"Status": "success", "CustomID": message.get("CustomID", ""), "To": [recipient]}


class FakeMailjet:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.script: list[
            tuple[int, Body] | tuple[int, Body, float]
        ] = []  # (status, corpo[, ritardo])
        self._counter = 0
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                try:
                    data = json.loads(raw)
                except ValueError:
                    data = None
                outer.requests.append(
                    {
                        "path": self.path,
                        "headers": dict(self.headers.items()),
                        "json": data,
                        "raw": raw,
                    }
                )
                status, body, delay = outer._next(data)
                if delay:
                    time.sleep(delay)
                payload = body if isinstance(body, str) else json.dumps(body)
                encoded = payload.encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, *args: Any) -> None:  # silenzioso
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def _next(self, data: Any) -> tuple[int, Any, float]:
        if self.script:
            entry = self.script.pop(0)
            status, body = entry[0], entry[1]
            delay = entry[2] if len(entry) > 2 else 0.0
            return status, (body(data) if callable(body) else body), delay
        sandbox = bool(data and data.get("SandboxMode"))
        messages = []
        for message in (data or {}).get("Messages", []):
            self._counter += 1
            messages.append(success_for(message, self._counter, sandbox))
        return 200, {"Messages": messages}, 0.0

    # ------------------------------------------------------------------ uso
    def start(self) -> "FakeMailjet":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}/v3.1/send"

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @staticmethod
    def basic_auth(request: dict[str, Any]) -> str:
        header = request["headers"].get("Authorization", "")
        return base64.b64decode(header.removeprefix("Basic ")).decode() if header else ""
