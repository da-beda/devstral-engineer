import json
from typing import List, Dict, Any

from config import CONFIG_DIR

HISTORY_FILE = CONFIG_DIR / "conversation_history.json"


def load_history() -> List[Dict[str, Any]]:
    """Load conversation history from disk."""
    if HISTORY_FILE.exists():
        try:
            with HISTORY_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def save_history(history: List[Dict[str, Any]]) -> None:
    """Persist conversation history to disk."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
