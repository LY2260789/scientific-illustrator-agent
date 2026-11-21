"""Run the FigureSpec renderer in desktop Illustrator on macOS."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from string import Template
from tempfile import TemporaryDirectory
from typing import Any, Optional
from uuid import uuid4

from .com_client import IllustratorError, create_document_jsx, jsx_literal, save_new_document

LOGGER = logging.getLogger(__name__)

# Keep the file path in argv, separate from both AppleScript and JSX source.
RUN_JSX = """\
on run argv
    with timeout of 120 seconds
        tell application id "com.adobe.illustrator"
            do javascript "$.evalFile(arguments[0])" with arguments {item 1 of argv}
        end tell
    end timeout
end run
"""


class AppleScriptIllustratorClient:
    """Use Apple events synchronously and leave Illustrator documents open."""

    def __init__(self) -> None:
        self._version: Optional[str] = None
        self._document_marker: Optional[str] = None
        self._original_artboard_name = ""
        self._saved_path: Optional[Path] = None

    @staticmethod
    def _run_jsx(script: str) -> str:
        # Use an explicit result file because Illustrator versions differ in how
        # they pass an ExtendScript return value back through AppleScript.
        with TemporaryDirectory(prefix="illustrator-jsx-") as directory:
            source = Path(directory) / "command.jsx"
            reply = Path(directory) / "result.txt"
            program = Template(r"""
(function () {
    var response;
    try {
        response = "OK\n" + String(eval($script));
    } catch (error) {
        response = "ERROR\n" + String(error) + " (JSX line " + error.line + ")";
    }
    var reply = new File($reply);
    reply.encoding = "UTF-8";
    if (reply.open("w")) {
        try { reply.write(response); }
        finally { reply.close(); }
    }
}());
""").substitute(script=jsx_literal(script), reply=jsx_literal(reply.as_posix()))
            source.write_text(program, encoding="ascii")
            LOGGER.debug("Generated JSX:\n%s", script)
            try:
                result = subprocess.run(
                    ["/usr/bin/osascript", "-", str(source)],
                    input=RUN_JSX,
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                    timeout=130,
                )
            except subprocess.TimeoutExpired as exc:
                raise IllustratorError("Illustrator timed out. Check open dialogs and the new document before retrying.") from exc
            except OSError as exc:
                raise IllustratorError(f"Cannot run macOS osascript: {exc}") from exc
            if result.returncode:
                raise IllustratorError(
                    f"AppleScript could not run Illustrator JSX: {result.stderr.strip() or result.returncode}. "
                    "Open Illustrator, close modal dialogs, and check macOS Privacy & Security > Automation."
                )
            if not reply.is_file():
                raise IllustratorError("Illustrator returned no JSX result. Check its scripting support and open dialogs.")
            status, _, message = reply.read_text(encoding="utf-8-sig").partition("\n")
            if status == "ERROR":
                raise IllustratorError(message)
            if status != "OK":
                raise IllustratorError("Illustrator did not return a valid JSX response.")
            return message

    def __enter__(self) -> AppleScriptIllustratorClient:
        if sys.platform != "darwin":
            raise IllustratorError("The --mac option requires macOS and desktop Illustrator.")
        self._version = self._run_jsx("app.version;")
        return self

    def __exit__(self, *args: Any) -> None:
        self._version = None
        self._document_marker = None
        self._original_artboard_name = ""
        self._saved_path = None

    def get_version(self) -> str:
        if self._version is None:
            raise IllustratorError("Use the Illustrator client inside a with block.")
        return self._version

    def health_check(self) -> dict[str, str]:
        version = self.get_version()
        return {"version": version, "jsx_version": version}

    def create_document(self, width: float = 520, height: float = 300) -> None:
        creation = create_document_jsx(width, height)
        marker = "SCI_ARTBOARD_" + uuid4().hex
        script = (
            "(function () { var board = " + creation + ".artboards[0];"
            "var originalName = board.name;"
            "board.name = " + jsx_literal(marker) + "; return originalName; }());"
        )
        self._original_artboard_name = self.execute_jsx(script, owned_document=False)
        self._document_marker = marker
        self._saved_path = None

    def execute_jsx(self, script: str, *, owned_document: bool = True) -> str:
        """Identify and activate the new document in the same call as the script."""
        self.get_version()
        if not script.strip():
            raise ValueError("JSX cannot be empty")
        if not owned_document:
            return self._run_jsx(script)
        if self._document_marker is None:
            raise IllustratorError("Create a new owned document before drawing or saving.")
        if self._saved_path is None:
            match = "doc.artboards[0].name === " + jsx_literal(self._document_marker)
        else:
            match = "doc.fullName.fsName === new File(" + jsx_literal(self._saved_path.as_posix()) + ").fsName"
        return self._run_jsx(
            "(function () {"
            "for (var i = 0; i < app.documents.length; i++) {"
            "var doc = app.documents[i], matches = false;"
            "try { matches = " + match + "; } catch (unavailable) {}"
            "if (matches) { doc.activate(); return eval(" + jsx_literal(script) + "); }"
            "}"
            "throw new Error('The document created for this drawing is no longer available');"
            "}());"
        )

    def save_document(self, path: Path) -> Path:
        saved_path = save_new_document(path, self._save_jsx)
        self._saved_path = saved_path
        return saved_path

    def _save_jsx(self, script: str) -> str:
        if self._saved_path is not None:
            return self.execute_jsx(script)
        # Restore the default artboard name in the output. If saveAs fails, the
        # marker still identifies the partially rendered document on inspection.
        return self.execute_jsx(
            "(function () {"
            "var board = app.activeDocument.artboards[0], marker = board.name;"
            "board.name = " + jsx_literal(self._original_artboard_name) + ";"
            "try { return eval(" + jsx_literal(script) + "); }"
            "catch (error) { board.name = marker; throw error; }"
            "}());"
        )
