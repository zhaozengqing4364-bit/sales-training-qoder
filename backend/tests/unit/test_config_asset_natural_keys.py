from __future__ import annotations

import pytest

from admin.config_assets.natural_keys import derive_natural_key, slugify_name, topology_ref


def test_should_slugify_ascii_name_to_natural_key() -> None:
    assert slugify_name("Manufacturing CIO First Visit") == "manufacturing-cio-first-visit"


def test_should_use_situation_pack_code_as_natural_key() -> None:
    assert derive_natural_key("situation_pack", code="first_visit") == "first_visit"


def test_should_build_topology_ref_token() -> None:
    assert topology_ref("persona", "cio-first-visit") == "persona:cio-first-visit"


def test_should_hash_fallback_for_non_ascii_only_name() -> None:
    key = derive_natural_key("persona", name="制造业")
    assert key.startswith("asset-")
