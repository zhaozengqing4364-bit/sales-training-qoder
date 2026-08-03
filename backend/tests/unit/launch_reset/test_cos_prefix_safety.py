from __future__ import annotations

import pytest

from common.cos.signing import CosSigningService


class _FakeCosClient:
    def __init__(self) -> None:
        self.list_calls: list[dict[str, object]] = []
        self.delete_calls: list[dict[str, object]] = []

    def list_objects(self, **kwargs):
        self.list_calls.append(kwargs)
        if kwargs["Marker"] == "":
            return {
                "Contents": [
                    {"Key": "project/audio/one.webm"},
                    {"Key": "other-project/private.webm"},
                ],
                "IsTruncated": "true",
                "NextMarker": "page-2",
            }
        return {
            "Contents": {"Key": "project/audio/two.webm"},
            "IsTruncated": "false",
        }

    def delete_objects(self, **kwargs) -> None:
        self.delete_calls.append(kwargs)


def _service() -> tuple[CosSigningService, _FakeCosClient]:
    service = CosSigningService()
    service._bucket = "shared-bucket"
    client = _FakeCosClient()
    service._client = client
    return service, client


def test_cos_listing_and_delete_are_confined_to_explicit_project_prefix() -> None:
    service, client = _service()

    keys = service.list_object_keys("project/audio/")
    service.delete_object_keys(keys, prefix="project/audio/")

    assert keys == ["project/audio/one.webm", "project/audio/two.webm"]
    assert [call["Prefix"] for call in client.list_calls] == [
        "project/audio/",
        "project/audio/",
    ]
    assert client.delete_calls == [
        {
            "Bucket": "shared-bucket",
            "Delete": {
                "Object": [
                    {"Key": "project/audio/one.webm"},
                    {"Key": "project/audio/two.webm"},
                ],
                "Quiet": "true",
            },
        }
    ]


def test_cos_delete_rejects_any_key_outside_confirmed_prefix() -> None:
    service, client = _service()

    with pytest.raises(ValueError, match="escaped"):
        service.delete_object_keys(
            ["project/audio/inside.webm", "other-project/private.webm"],
            prefix="project/audio/",
        )

    assert client.delete_calls == []
