"""Local Adobe Illustrator automation bridge."""

from typing import Union

from .applescript_client import AppleScriptIllustratorClient
from .com_client import IllustratorClient, IllustratorError

__all__ = ["IllustratorClient", "IllustratorError", "desktop_client"]


def desktop_client(*, mac: bool = False) -> Union[IllustratorClient, AppleScriptIllustratorClient]:
    """Use the existing COM bridge unless the macOS preview is requested."""
    if mac:
        return AppleScriptIllustratorClient()
    return IllustratorClient()
