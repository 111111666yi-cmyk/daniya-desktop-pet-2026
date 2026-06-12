from __future__ import annotations

import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class _QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


class StoryWebServer:
    """Serve the bundled story site on a loopback-only random port."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def url(self) -> str:
        index = self.root / "index.html"
        if not index.is_file():
            raise FileNotFoundError(index)
        if self._server is None:
            handler = partial(_QuietStaticHandler, directory=str(self.root))
            self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            self._server.daemon_threads = True
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                name="daniya-story-web",
                daemon=True,
            )
            self._thread.start()
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}/index.html"

    def close(self) -> None:
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is None:
            return
        server.shutdown()
        server.server_close()
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
