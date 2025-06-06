import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel

CONFIG_DIR = Path.home() / '.config' / 'devstral-engineer'
CONFIG_FILE = CONFIG_DIR / 'config.yaml'

class Config(BaseModel):
    """Application configuration loaded from YAML or environment variables."""
    api_key: Optional[str] = None
    default_model: str = 'mistralai/devstral-small:free'

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> 'Config':
        data = {}
        if path.exists():
            with path.open('r') as f:
                data = yaml.safe_load(f) or {}
        # fall back to env vars if values missing
        if 'api_key' not in data:
            env_key = os.getenv('OPENROUTER_API_KEY')
            if env_key:
                data['api_key'] = env_key
        if 'default_model' not in data:
            env_model = os.getenv('DEFAULT_MODEL')
            if env_model:
                data['default_model'] = env_model
        return cls(**data)

    def save(self, path: Path = CONFIG_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w') as f:
            yaml.safe_dump(self.model_dump(), f)
