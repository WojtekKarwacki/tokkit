"""Background watcher that polls for file changes and triggers re-indexing."""
import threading


class Watcher:
    def __init__(self, poll_interval: float = 5.0) -> None:
        self._poll_interval = poll_interval
        self._project_path: str | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def set_project(self, path: str) -> None:
        self._project_path = path

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="tokkit-watcher")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._poll_interval + 1)
            self._thread = None

    def _run(self) -> None:
        while not self._stop_event.wait(timeout=self._poll_interval):
            self._check_and_reindex()

    def _check_and_reindex(self) -> None:
        if self._project_path is None:
            return
        try:
            from tokkit_server.tools import handle_tool_call  # noqa: PLC0415
            result = handle_tool_call("detect_changes", {})
            content = result.get("content", [{}])
            text = content[0].get("text", "") if content else ""
            if text and text != "[]" and text != "None":
                handle_tool_call("index_repository", {"path": self._project_path})
        except Exception:  # noqa: BLE001
            pass
