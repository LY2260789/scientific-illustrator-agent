"""Offline checks for the opt-in macOS bridge."""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from illustrator import IllustratorClient, IllustratorError, desktop_client
from illustrator.applescript_client import AppleScriptIllustratorClient


class AppleScriptClientTests(unittest.TestCase):
    def test_mac_bridge_is_opt_in(self) -> None:
        self.assertIsInstance(desktop_client(), IllustratorClient)
        self.assertIsInstance(desktop_client(mac=True), AppleScriptIllustratorClient)

    def test_owned_document_required(self) -> None:
        client = desktop_client(mac=True)
        with patch("illustrator.applescript_client.sys.platform", "darwin"):
            with patch.object(client, "_run_jsx", return_value="29.0") as run:
                with client:
                    with self.assertRaisesRegex(IllustratorError, "new owned document"):
                        client.execute_jsx("app.activeDocument.close();")
                run.assert_called_once_with("app.version;")

    def test_temp_file_transport_handles_unicode_and_multiline_results(self) -> None:
        value = '中文 "quote"\nnext line'
        script = json.dumps(value) + ";"

        def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
            self.assertEqual(command[:2], ["/usr/bin/osascript", "-"])
            self.assertNotIn(script, kwargs["input"])
            source = Path(command[2])
            self.assertIn("eval(" + json.dumps(script) + ")", source.read_text(encoding="ascii"))
            source.with_name("result.txt").write_text("OK\n" + value, encoding="utf-8-sig")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with patch("illustrator.applescript_client.subprocess.run", side_effect=run):
            self.assertEqual(AppleScriptIllustratorClient._run_jsx(script), value)

    def test_permission_failure_preserves_osascript_error(self) -> None:
        result = subprocess.CompletedProcess([], 1, stdout="", stderr="Not authorized (-1743)")
        with patch("illustrator.applescript_client.subprocess.run", return_value=result):
            with self.assertRaisesRegex(IllustratorError, r"-1743.*Automation"):
                AppleScriptIllustratorClient._run_jsx("app.version;")


if __name__ == "__main__":
    unittest.main()
