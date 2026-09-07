"""Small, synchronous COM bridge compatible with Python 3.9 and legacy JSX.

Use one client on one thread. Disconnect releases COM references; it never quits
Illustrator. Mutations target the document created by this client, not selection.
"""

from __future__ import annotations

import json
import logging
import math
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)


class IllustratorError(RuntimeError):
    """Actionable failure in the local Illustrator bridge."""


def jsx_literal(value: Any) -> str:
    """Encode data as ES3-compatible literals, including Unicode and paths."""
    return json.dumps(value, ensure_ascii=True, allow_nan=False)


def describe_com_error(exc: Exception) -> str:
    """Explain common HRESULTs without guessing that Illustrator is absent."""
    code = getattr(exc, "hresult", 0) & 0xFFFFFFFF
    hints = {
        0x80040154: "COM class not registered: Illustrator may be missing or its COM registration is damaged. Check installation/repair.",
        0x800401F3: "Invalid COM ProgID: Illustrator.Application is not registered. Check Illustrator installation/repair.",
        0x80080005: "Illustrator startup failed. Launch Illustrator manually and resolve startup/sign-in dialogs.",
        0x80010001: "Illustrator rejected the call. Close modal dialogs and wait until Illustrator is idle.",
        0x8001010A: "Illustrator is busy. Close dialogs and retry when idle.",
        0x800706BA: "Illustrator COM server is unavailable. Check whether Illustrator exited or crashed.",
        0x80010105: "Illustrator reported a server-side exception. Inspect JSX diagnostics and application state before retrying.",
        0x80020003: "Requested COM member is unavailable. Check Illustrator version and scripting support.",
    }
    return f"{hints.get(code, 'Check Illustrator startup, modal dialogs, COM registration and scripting support.')} HRESULT=0x{code:08X}; {exc}"


class IllustratorClient:
    """Dispatch Illustrator.Application and execute scripts on an owned document."""

    def __init__(self) -> None:
        self._app: Any = None
        self._document: Any = None
        self._pythoncom: Any = None
        self._thread_id: Optional[int] = None

    def _check_thread(self) -> None:
        if self._thread_id is not None and self._thread_id != threading.get_ident():
            raise IllustratorError("Use IllustratorClient only on the thread that connected it.")

    def connect(self) -> IllustratorClient:
        """Connect or launch Illustrator without opening or modifying documents."""
        self._check_thread()
        if self._app is not None:
            return self
        if sys.platform != "win32":
            raise IllustratorError("Illustrator COM requires Windows and a local desktop session.")
        try:
            import pythoncom
            import win32com.client
        except ImportError as exc:
            raise IllustratorError("pywin32 is missing: run python -m pip install -r requirements.txt") from exc
        try:
            pythoncom.CoInitialize()
            self._pythoncom = pythoncom
            self._thread_id = threading.get_ident()
            self._app = win32com.client.Dispatch("Illustrator.Application")
            LOGGER.info("Connected to Illustrator %s", self.get_version())
        except Exception as exc:
            self.disconnect()
            raise IllustratorError(f"Cannot connect to Illustrator: {describe_com_error(exc)}") from exc
        return self

    def disconnect(self) -> None:
        """Release this client's references; leave Illustrator and documents open."""
        self._check_thread()
        self._document = None
        self._app = None
        if self._pythoncom is not None:
            self._pythoncom.CoUninitialize()
        self._pythoncom = None
        self._thread_id = None

    def _require_app(self) -> Any:
        self._check_thread()
        if self._app is None:
            raise IllustratorError("Not connected. Call connect() first.")
        return self._app

    def get_version(self) -> str:
        """Read the actual installed application version."""
        try:
            return str(self._require_app().Version)
        except IllustratorError:
            raise
        except Exception as exc:
            raise IllustratorError(f"Cannot read Illustrator version: {describe_com_error(exc)}") from exc

    def execute_jsx(self, script: str, *, owned_document: bool = True) -> str:
        """Execute trusted internal JSX, with errors and timings in the log.

        This is a developer escape hatch, not an agent-facing arbitrary-JS tool.
        Scripts are not retried: a failed COM call may already have made changes.
        """
        app = self._require_app()
        if not script.strip():
            raise ValueError("JSX cannot be empty")
        started = time.perf_counter()
        LOGGER.debug("Generated JSX:\n%s", script)
        try:
            if owned_document:
                if self._document is None:
                    raise IllustratorError("Create a new owned document before drawing or saving.")
                self._document.Activate()
            result = str(app.DoJavaScript(script))
            LOGGER.info("DoJavaScript succeeded in %.3fs; result=%s", time.perf_counter() - started, result)
            return result
        except IllustratorError:
            raise
        except Exception as exc:
            LOGGER.exception("DoJavaScript failed after %.3fs", time.perf_counter() - started)
            raise IllustratorError(
                "DoJavaScript unavailable or execution failed. Check scripting support, JSX syntax/API and modal dialogs. "
                + describe_com_error(exc)
            ) from exc

    def create_document(self, width: float = 520, height: float = 300) -> Any:
        """Create a fresh RGB document in points and retain its COM reference."""
        if not all(math.isfinite(v) and 1 <= v <= 16383 for v in (width, height)):
            raise ValueError("Document dimensions must be finite and between 1 and 16383 pt")
        self.execute_jsx(
            f"app.documents.add(DocumentColorSpace.RGB, {jsx_literal(width)}, {jsx_literal(height)}); app.activeDocument.name;",
            owned_document=False,
        )
        try:
            self._document = self._require_app().ActiveDocument
            return self._document
        except Exception as exc:
            raise IllustratorError(f"Document created but reference retrieval failed: {describe_com_error(exc)}") from exc

    def get_active_document(self) -> Any:
        """Return a read-only caller reference or None; does not adopt ownership."""
        app = self._require_app()
        try:
            return app.ActiveDocument if app.Documents.Count else None
        except Exception as exc:
            raise IllustratorError(f"Cannot inspect active document: {describe_com_error(exc)}") from exc

    def save_document(self, path: Path) -> Path:
        """Save owned artwork to a new .ai path; refuse existing destinations."""
        destination = Path(path).expanduser().resolve()
        if destination.suffix.lower() != ".ai":
            raise ValueError("Save destination must have an .ai extension")
        if destination.exists():
            raise FileExistsError(f"Refusing to overwrite: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.execute_jsx(
            "(function () { var target = new File(" + jsx_literal(destination.as_posix()) + ");"
            "if (target.exists) throw new Error('Destination already exists');"
            "var options = new IllustratorSaveOptions(); options.pdfCompatible = true;"
            "app.activeDocument.saveAs(target, options); return target.fsName; }());"
        )
        if not destination.is_file() or destination.stat().st_size == 0:
            raise IllustratorError(f"saveAs returned but output is absent/empty: {destination}")
        return destination

    def health_check(self) -> dict[str, Any]:
        """Check version and read-only scripting connectivity."""
        return {"version": self.get_version(), "jsx_version": self.execute_jsx("app.version;", owned_document=False)}

    def __enter__(self) -> IllustratorClient:
        return self.connect()

    def __exit__(self, *args: Any) -> None:
        self.disconnect()
