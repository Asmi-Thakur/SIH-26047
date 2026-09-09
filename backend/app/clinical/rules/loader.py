"""Loads and validates the triage rule content (rules.json)."""
import json
from functools import lru_cache
from pathlib import Path

from app.clinical.schemas.rule import RuleBank

_RULES_FILE = Path(__file__).parent / "rules.json"


@lru_cache(maxsize=1)
def load_rules() -> RuleBank:
    if not _RULES_FILE.exists():
        raise FileNotFoundError(f"Rule bank not found: {_RULES_FILE}")
    raw = json.loads(_RULES_FILE.read_text(encoding="utf-8"))
    return RuleBank.model_validate(raw)


def clear_rules_cache() -> None:
    load_rules.cache_clear()
