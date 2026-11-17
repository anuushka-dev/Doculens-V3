"""DocuLens application package."""

from __future__ import annotations

import importlib.util
import sys

# Support systems where httpx2 is installed as the drop-in HTTPX package.
if importlib.util.find_spec("httpx") is None and importlib.util.find_spec("httpx2") is not None:
    sys.modules.pop("httpx", None)
    sys.modules.pop("httpcore", None)
    import httpx2 as _httpx2

    _httpx2.alias_httpx()
