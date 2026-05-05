
import pytest
from fastapi import HTTPException

from admin.api.admin import _safe_presentation_upload_path


@pytest.mark.parametrize(
    "filename",
    ["../evil.py", "/tmp/evil.pptx", "nested/evil.pptx", "nested\\evil.pptx", "evil.py"],
)
def test_presentation_upload_path_rejects_traversal_absolute_nested_and_wrong_extension(tmp_path, filename):
    with pytest.raises(HTTPException) as exc_info:
        _safe_presentation_upload_path(filename, str(tmp_path))

    assert exc_info.value.status_code == 400


@pytest.mark.parametrize("filename,extension", [("deck.ppt", ".ppt"), ("deck.pptx", ".pptx")])
def test_presentation_upload_path_uses_server_generated_name_under_root(tmp_path, filename, extension):
    target, original = _safe_presentation_upload_path(filename, str(tmp_path))

    assert original == filename
    assert target.parent == tmp_path.resolve()
    assert target.suffix == extension
    assert target.name != filename
    assert not target.exists()
