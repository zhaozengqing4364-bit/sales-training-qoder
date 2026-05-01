from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from admin.api.admin import _safe_presentation_upload_path


def test_safe_presentation_upload_path_generates_server_owned_filename(tmp_path):
    upload_root = tmp_path / "uploads"

    target, original_name = _safe_presentation_upload_path(
        "Sales-Deck.pptx",
        str(upload_root),
    )

    assert original_name == "Sales-Deck.pptx"
    assert target.parent == upload_root.resolve()
    assert target.suffix == ".pptx"
    assert target.name != "Sales-Deck.pptx"
    assert target.parent.exists()


@pytest.mark.parametrize(
    "filename",
    [
        "../evil.ppt",
        "/tmp/evil.pptx",
        "nested/evil.ppt",
        "evil..pptx",
    ],
)
def test_safe_presentation_upload_path_rejects_traversal_and_nested_paths(
    tmp_path,
    filename,
):
    with pytest.raises(HTTPException, match="not allowed|allowed"):
        _safe_presentation_upload_path(filename, str(tmp_path / "uploads"))
