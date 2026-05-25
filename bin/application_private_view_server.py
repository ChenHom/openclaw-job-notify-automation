#!/usr/bin/env python3
"""Serve private 104 application package views from the local profile repo."""

from __future__ import annotations

import argparse
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_notify.application_private_view import handle_package_action, render_health, render_package_view
from job_notify.application_workflow import ApplicationArtifactRepository
from job_notify.config import add_config_args, load_config


class PrivateViewHandler(BaseHTTPRequestHandler):
    artifacts: ApplicationArtifactRepository

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            view = render_health()
        elif parsed.path == "/package":
            application_id = parse_qs(parsed.query).get("applicationId", [""])[0]
            view = render_package_view(application_id=application_id, artifacts=self.artifacts)
        else:
            view = render_health()
            view = type(view)(404, "text/plain; charset=utf-8", "not found")

        body = view.body.encode("utf-8")
        self.send_response(view.status_code)
        self.send_header("Content-Type", view.content_type)
        for key, value in (view.headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        if parsed.path != "/package/action":
            view = type(render_health())(404, "text/plain; charset=utf-8", "not found")
        else:
            application_id = parse_qs(parsed.query).get("applicationId", [""])[0]
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length)
            view = handle_package_action(application_id=application_id, artifacts=self.artifacts, raw_body=raw_body)

        body = view.body.encode("utf-8")
        self.send_response(view.status_code)
        self.send_header("Content-Type", view.content_type)
        for key, value in (view.headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_config_args(parser)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    config = load_config(profile_dir=args.profile_dir, config_file=args.config)
    PrivateViewHandler.artifacts = ApplicationArtifactRepository(config.profile_dir)
    server = ThreadingHTTPServer((args.host, args.port), PrivateViewHandler)
    print(f"PRIVATE_VIEW_URL=http://{args.host}:{args.port}/package?applicationId=<applicationId>")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
