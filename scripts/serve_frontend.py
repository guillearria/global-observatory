#!/usr/bin/env python3
"""Serve the static frontend for local preview at http://localhost:8000."""

import functools
import http.server
import socketserver

from pipeline import config

PORT = 8000


def main() -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(config.ROOT / "frontend"))
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"serving frontend at http://localhost:{PORT} (Ctrl-C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")


if __name__ == "__main__":
    main()
