import yaml
from typer.testing import CliRunner

from devstral_cli import onboarding
import config
import typer
import click


def test_onboard_creates_config(tmp_path, monkeypatch):
    file = tmp_path / "config.yaml"
    monkeypatch.setattr(onboarding, "CONFIG_FILE", file)
    monkeypatch.setattr(config, "CONFIG_FILE", file)
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(
        onboarding.Config,
        "load",
        classmethod(lambda cls: cls(api_key=None, default_model="")),
    )
    orig_save = onboarding.Config.save
    monkeypatch.setattr(onboarding.Config, "save", lambda self: orig_save(self, file))
    if not hasattr(typer, "Choice"):
        monkeypatch.setattr(typer, "Choice", click.Choice, raising=False)

    runner = CliRunner()
    result = runner.invoke(
        onboarding.app,
        input="testkey\ncustom-model\nlight\n",
    )

    assert result.exit_code == 0
    assert file.exists()
    data = yaml.safe_load(file.read_text())
    assert data["api_key"] == "testkey"
    assert data["default_model"] == "custom-model"
    assert data["theme"] == onboarding.THEMES["light"].model_dump()
