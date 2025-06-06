import os
from pathlib import Path
from config import Config

def test_config_roundtrip(tmp_path):
    cfg = Config(api_key="key", default_model="model")
    path = tmp_path / "config.yaml"
    cfg.save(path)
    loaded = Config.load(path)
    assert loaded.model_dump() == cfg.model_dump()
