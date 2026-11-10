import hashlib
import json
from typing import Any, Optional

class ToolResultCache:
    """
    In-memory and hash-keyed cache for deterministic tool executions.
    Avoids re-parsing, re-extracting, or re-normalizing identical files.
    """
    def __init__(self):
        self._cache: dict[str, Any] = {}
        self.hits: int = 0
        self.misses: int = 0

    def _make_key(self, tool_name: str, identifier: str, kwargs_dict: Optional[dict] = None) -> str:
        key_raw = f"{tool_name}:{identifier}"
        if kwargs_dict:
            # Sort keys for deterministic hash
            kwargs_str = json.dumps(kwargs_dict, sort_keys=True, default=str)
            extra_hash = hashlib.sha256(kwargs_str.encode("utf-8")).hexdigest()[:12]
            key_raw += f":{extra_hash}"
        return key_raw

    def get(self, tool_name: str, identifier: str, kwargs_dict: Optional[dict] = None) -> Optional[Any]:
        key = self._make_key(tool_name, identifier, kwargs_dict)
        if key in self._cache:
            self.hits += 1
            return self._cache[key]
        self.misses += 1
        return None

    def set(self, tool_name: str, identifier: str, value: Any, kwargs_dict: Optional[dict] = None):
        key = self._make_key(tool_name, identifier, kwargs_dict)
        self._cache[key] = value

    def clear(self):
        self._cache.clear()
        self.hits = 0
        self.misses = 0

# Global instance
tool_cache = ToolResultCache()
