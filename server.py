"""Local playable integration of the accepted module; each move runs isolated."""

import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tools.verify import RESTRICT, ROOT, RUNNER, admission, bounded

PORT = 3033


def move(payload):
    source = (ROOT / "engine.py").read_text()
    receipt = json.loads((ROOT / "evidence/verification.json").read_text())
    if (
        receipt["passed"] != receipt["total"]
        or receipt["source_sha256"] != hashlib.sha256(source.encode()).hexdigest()
    ):
        raise ValueError("Verified module changed; rerun acceptance before playing.")
    admission(source)
    return bounded(
        [
            "docker",
            "run",
            *RESTRICT,
            "python:3.12-slim",
            "python",
            "-B",
            "-c",
            RUNNER,
            source,
        ],
        [payload],
    )[0]


class Handler(BaseHTTPRequestHandler):
    def send(self, status, value, content_type="application/json"):
        data = (
            json.dumps(value).encode() if content_type == "application/json" else value
        )
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            self.send(
                200, (ROOT / "web/index.html").read_bytes(), "text/html; charset=utf-8"
            )
        elif self.path == "/api/evidence":
            names = [
                "verification.json",
                "holdout.json",
                "provenance.json",
                "delivery.json",
            ]
            self.send(
                200,
                {
                    name.removesuffix(".json"): json.loads(
                        (ROOT / "evidence" / name).read_text()
                    )
                    for name in names
                    if (ROOT / "evidence" / name).exists()
                },
            )
        else:
            self.send(404, {"error": "Not found"})

    def do_POST(self):
        if self.headers.get("Origin") not in {
            f"http://localhost:{PORT}",
            f"http://127.0.0.1:{PORT}",
        }:
            self.send(403, {"error": "Same-origin request required"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 16384:
                raise ValueError("Invalid request length")
            data = json.loads(self.rfile.read(size))
            payload = {
                "kind": "move",
                "board": data["board"],
                "direction": data["direction"],
            }
            actual = move(payload)
            if "error" in actual:
                raise ValueError("Invalid board or direction")
            if self.path == "/api/move":
                self.send(200, actual["value"])
            elif self.path == "/api/compare":
                expected = bounded(
                    [
                        "docker",
                        "run",
                        *RESTRICT,
                        "-v",
                        str(ROOT / "reference") + ":/reference:ro",
                        "-v",
                        str(ROOT / "tools/oracle.py") + ":/oracle.py:ro",
                        "python:3.12-slim",
                        "python",
                        "-B",
                        "/oracle.py",
                    ],
                    [payload],
                )[0]
                self.send(
                    200,
                    {
                        "reference": expected,
                        "recovered": actual["value"],
                        "matches": expected == actual["value"],
                        "reference_kind": "Pinned native ELF shared library, executed now",
                    },
                )
            else:
                self.send(404, {"error": "Not found"})
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self.send(400, {"error": str(exc)})
        except Exception as exc:
            self.send(
                503,
                {"error": "Game execution unavailable", "detail": type(exc).__name__},
            )


if __name__ == "__main__":
    print(f"AYA 2048: http://localhost:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
