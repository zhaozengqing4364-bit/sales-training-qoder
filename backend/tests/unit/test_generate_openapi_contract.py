from __future__ import annotations

import yaml
from scripts.generate_openapi_contract import check_contract, render_openapi_yaml


def test_should_render_stable_openapi_yaml() -> None:
    schema = {
        "openapi": "3.1.0",
        "info": {"title": "test", "version": "1"},
        "paths": {"/health": {"get": {"responses": {"200": {"description": "ok"}}}}},
    }

    rendered = render_openapi_yaml(schema)

    assert yaml.safe_load(rendered) == schema
    assert rendered.endswith("\n")


def test_should_detect_semantic_contract_drift(tmp_path) -> None:
    path = tmp_path / "openapi.yaml"
    path.write_text("openapi: 3.1.0\npaths: {}\n", encoding="utf-8")

    assert check_contract(path, {"openapi": "3.1.0", "paths": {}})
    assert not check_contract(
        path,
        {"openapi": "3.1.0", "paths": {"/health": {}}},
    )
