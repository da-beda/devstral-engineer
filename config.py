import os
from pathlib import Path
from typing import Optional, Dict, Any

import yaml
from pydantic import BaseModel

CONFIG_DIR = Path.home() / ".config" / "devstral-engineer"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


class EmbeddingConfig(BaseModel):
    """Settings for the embedding provider used by the indexing engine."""

    provider: str = "local"
    model: Optional[str] = None
    api_key: Optional[str] = None

    # Provide compatibility with pydantic v1
    def model_dump(self, *args, **kwargs):  # type: ignore[override]
        if hasattr(BaseModel, "model_dump"):
            return super().model_dump(*args, **kwargs)
        return self.dict(*args, **kwargs)


class ThemeConfig(BaseModel):
    """Color configuration for terminal output."""

    success: str = "bold blue"
    error: str = "bold red"
    warning: str = "bold yellow"
    panel: str = "green"


class Config(BaseModel):
    """Application configuration loaded from YAML or environment variables."""

    api_key: Optional[str] = None
    default_model: str = "mistralai/devstral-small:free"
    indexing_enabled: bool = False
    index_engine_path: Optional[str] = None
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None
    embedding: EmbeddingConfig = EmbeddingConfig()
    theme: ThemeConfig = ThemeConfig()

    # Provide compatibility with pydantic v1
    def model_dump(self, *args, **kwargs):  # type: ignore[override]
        if hasattr(BaseModel, "model_dump"):
            return super().model_dump(*args, **kwargs)
        return self.dict(*args, **kwargs)

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> "Config":
        data = {}
        if path.exists():
            with path.open("r") as f:
                data = yaml.safe_load(f) or {}
        # fall back to env vars if values missing
        if "api_key" not in data:
            env_key = os.getenv("OPENROUTER_API_KEY")
            if env_key:
                data["api_key"] = env_key
        if "default_model" not in data:
            env_model = os.getenv("DEFAULT_MODEL")
            if env_model:
                data["default_model"] = env_model
        if "indexing_enabled" not in data:
            env_index = os.getenv("INDEXING_ENABLED")
            if env_index is not None:
                data["indexing_enabled"] = env_index.lower() in ("1", "true", "yes")
        if "index_engine_path" not in data:
            env_path = os.getenv("INDEX_ENGINE_PATH")
            if env_path:
                data["index_engine_path"] = env_path
        if "qdrant_url" not in data:
            env_url = os.getenv("QDRANT_URL")
            if env_url:
                data["qdrant_url"] = env_url
        if "qdrant_api_key" not in data:
            env_qk = os.getenv("QDRANT_API_KEY")
            if env_qk:
                data["qdrant_api_key"] = env_qk
        if "embedding" not in data:
            env_provider = os.getenv("EMBEDDING_PROVIDER")
            env_model = os.getenv("EMBEDDING_MODEL")
            env_api = os.getenv("EMBEDDING_API_KEY")
            if any([env_provider, env_model, env_api]):
                emb: Dict[str, Any] = {}
                if env_provider:
                    emb["provider"] = env_provider
                if env_model:
                    emb["model"] = env_model
                if env_api:
                    emb["api_key"] = env_api
                data["embedding"] = emb
        if "theme" not in data:
            env_success = os.getenv("THEME_SUCCESS")
            env_error = os.getenv("THEME_ERROR")
            env_warning = os.getenv("THEME_WARNING")
            env_panel = os.getenv("THEME_PANEL")
            if any([env_success, env_error, env_warning, env_panel]):
                theme: Dict[str, Any] = {}
                if env_success:
                    theme["success"] = env_success
                if env_error:
                    theme["error"] = env_error
                if env_warning:
                    theme["warning"] = env_warning
                if env_panel:
                    theme["panel"] = env_panel
                data["theme"] = theme
        return cls(**data)

    def save(self, path: Path = CONFIG_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            if hasattr(self, "model_dump"):
                yaml.safe_dump(self.model_dump(), f)
            else:
                yaml.safe_dump(self.dict(), f)
