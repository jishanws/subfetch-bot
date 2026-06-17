"""Deterministic title alias resolution."""

import re


class AliasService:
    """Resolve common title abbreviations before external lookups."""

    ALIASES = {
        "got": "game of thrones",
        "hotd": "house of the dragon",
        "bb": "breaking bad",
        "tbbt": "the big bang theory",
        "lotr": "lord of the rings",
        "gotg": "guardians of the galaxy",
        "twd": "the walking dead",
    }

    def resolve(self, query: str) -> str:
        """Return the aliased title when the whole query is a known alias."""
        normalized = self._normalize(query)
        return self.ALIASES.get(normalized, query)

    def _normalize(self, query: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", " ", query.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        parts = normalized.split()
        if parts and all(len(part) == 1 for part in parts):
            return "".join(parts)
        return normalized
