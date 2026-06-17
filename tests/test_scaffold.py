from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_manifest_declares_only_tool_plugin_provider():
    manifest = yaml.safe_load((ROOT / "manifest.yaml").read_text())

    assert manifest["type"] == "plugin"
    assert manifest["plugins"] == {"tools": ["provider/oracle.yaml"]}
    assert "models" not in manifest["plugins"]
    assert "endpoints" not in manifest["plugins"]
    assert "datasources" not in manifest["plugins"]


def test_provider_and_tool_yaml_sources_exist():
    provider = yaml.safe_load((ROOT / "provider/oracle.yaml").read_text())

    assert provider["extra"]["python"]["source"] == "provider/oracle.py"
    for tool_path in provider["tools"]:
        tool_yaml = ROOT / tool_path
        assert tool_yaml.exists(), tool_path
        tool_config = yaml.safe_load(tool_yaml.read_text())
        source = ROOT / tool_config["extra"]["python"]["source"]
        assert source.exists(), source

