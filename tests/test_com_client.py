"""Offline checks for parameter safety and document ownership guards."""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from illustrator.com_client import IllustratorClient, IllustratorError, jsx_literal


class ClientSafetyTests(unittest.TestCase):
    """Verify guards before real COM calls are possible."""

    def test_unicode_escaping(self) -> None:
        value = '中文 "quote" C:\\研究\\new.ai\n\u2028'
        encoded = jsx_literal(value)
        self.assertEqual(json.loads(encoded), value)
        self.assertTrue(encoded.isascii())

    def test_owned_document_required(self) -> None:
        client = IllustratorClient()
        client._app = Mock()
        with self.assertRaises(IllustratorError):
            client.execute_jsx("app.activeDocument.close();")
        client._app.DoJavaScript.assert_not_called()

    def test_invalid_dimensions(self) -> None:
        for value in (0, -1, float("nan"), float("inf"), 20000):
            with self.assertRaises(ValueError):
                IllustratorClient().create_document(width=value)

    def test_existing_path_refused(self) -> None:
        with self.assertRaises(FileExistsError):
            # Existing directory with .ai suffix also must never be overwritten.
            import tempfile
            with tempfile.TemporaryDirectory(suffix=".ai") as directory:
                IllustratorClient().save_document(Path(directory))


if __name__ == "__main__":
    unittest.main()
