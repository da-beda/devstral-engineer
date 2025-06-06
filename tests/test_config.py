from config import Config, EmbeddingConfig


def test_config_roundtrip(tmp_path):
    cfg = Config(
        api_key="key",
        default_model="model",
        indexing_enabled=True,
        index_engine_path="/path/bin",
        qdrant_url="http://localhost:6333",
        qdrant_api_key="qkey",
        embedding=EmbeddingConfig(provider="openai", model="test", api_key="e"),
    )
    path = tmp_path / "config.yaml"
    cfg.save(path)
    loaded = Config.load(path)
    assert loaded.model_dump() == cfg.model_dump()
