"""Join trusted JSX templates and safely serialized structured parameters."""

from pathlib import Path
from typing import Any

from .com_client import jsx_literal


class JSXBuilder:
    """No user-controlled source code or template filenames."""

    @staticmethod
    def render_scene(scene: dict[str, Any]) -> str:
        """Invoke the fixed ES3 renderer with literal data, including Unicode escapes."""
        template = (Path(__file__).parent / "jsx" / "render_scene.jsx").read_text(encoding="utf-8")
        return ("(function () {\n" + template + "\ntry { return renderScene(" + jsx_literal(scene)
                + "); } catch (e) { return 'ERROR|line=' + e.line + '|' + e.message; }\n}());")
