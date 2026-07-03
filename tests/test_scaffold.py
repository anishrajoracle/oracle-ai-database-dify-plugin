from __future__ import annotations

import tomllib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_plugin_release_versions_are_consistent():
    manifest = yaml.safe_load((ROOT / "manifest.yaml").read_text())
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    lockfile = tomllib.loads((ROOT / "uv.lock").read_text())
    locked_project = next(package for package in lockfile["package"] if package["name"] == pyproject["project"]["name"])

    assert manifest["version"] == pyproject["project"]["version"]
    assert locked_project["version"] == manifest["version"]


def test_install_requirements_match_project_dependencies():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    requirements = {
        line.strip()
        for line in (ROOT / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert requirements == set(pyproject["project"]["dependencies"])


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
    assert provider["tools"] == [
        "tools/read_only_sql.yaml",
        "tools/write_only_sql.yaml",
        "tools/external_knowledge_search.yaml",
        "tools/external_vector_search.yaml",
        "tools/hybrid_knowledge_search.yaml",
    ]
    for tool_path in provider["tools"]:
        tool_yaml = ROOT / tool_path
        assert tool_yaml.exists(), tool_path
        tool_config = yaml.safe_load(tool_yaml.read_text())
        source = ROOT / tool_config["extra"]["python"]["source"]
        assert source.exists(), source


def test_write_tool_keeps_sql_and_safety_limits_out_of_llm_control():
    provider = yaml.safe_load((ROOT / "provider/oracle.yaml").read_text())
    tool_config = yaml.safe_load((ROOT / "tools/write_only_sql.yaml").read_text())
    parameters = {parameter["name"]: parameter for parameter in tool_config["parameters"]}

    assert parameters["sql"]["form"] == "form"
    assert parameters["allowed_tables"]["form"] == "form"
    assert provider["credentials_for_provider"]["enable_writes"]["type"] == "boolean"
    assert provider["credentials_for_provider"]["enable_writes"]["default"] is False
    assert parameters["allow_delete"]["form"] == "form"
    assert parameters["allow_delete"]["default"] is False
    assert parameters["max_affected_rows"]["form"] == "form"
    assert parameters["max_affected_rows"]["default"] == 1
    assert parameters["max_affected_rows"]["min"] == 1
    assert parameters["max_affected_rows"]["max"] == 100
    assert parameters["bind_parameters"]["form"] == "llm"
    assert parameters["bind_parameters"]["required"] is True
