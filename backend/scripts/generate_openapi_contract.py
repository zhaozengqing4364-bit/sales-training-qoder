from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    REPO_ROOT / "specs" / "001-ai-practice-system" / "contracts" / "openapi.yaml"
)
sys.path.insert(0, str(BACKEND_ROOT / "src"))


def build_runtime_schema() -> dict[str, Any]:
    from app_factory import create_app

    return create_app().openapi()


def render_openapi_yaml(schema: dict[str, object]) -> str:
    rendered = yaml.safe_dump(
        schema,
        allow_unicode=True,
        sort_keys=False,
        width=100,
    )
    return rendered if rendered.endswith("\n") else f"{rendered}\n"


def check_contract(path: Path, schema: dict[str, object]) -> bool:
    if not path.exists():
        return False
    committed = yaml.safe_load(path.read_text(encoding="utf-8"))
    return committed == schema


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate the runtime OpenAPI contract")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    schema = build_runtime_schema()
    output = args.output.resolve()
    if args.check:
        if check_contract(output, schema):
            print(f"OpenAPI contract is current: {output}")
            return 0
        print(f"OpenAPI contract is stale: {output}")
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_openapi_yaml(schema), encoding="utf-8")
    print(f"Wrote OpenAPI contract: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
