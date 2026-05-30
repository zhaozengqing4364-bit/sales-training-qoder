from __future__ import annotations

import pytest

from common.cos.signing import CosSigningService, _build_public_url


def test_should_build_cos_public_url_with_encoded_object_key() -> None:
    assert _build_public_url(
        "xiaoshouxunlian-1312175157.cos.ap-guangzhou.myqcloud.com",
        "sales-trainer/audio/user/中文 录音.wav",
    ) == (
        "https://xiaoshouxunlian-1312175157.cos.ap-guangzhou.myqcloud.com/"
        "sales-trainer/audio/user/%E4%B8%AD%E6%96%87%20%E5%BD%95%E9%9F%B3.wav"
    )


def test_should_reject_parent_directory_cos_object_key() -> None:
    with pytest.raises(ValueError, match="Invalid COS object key"):
        _build_public_url("https://cos.example.com", "../secret.wav")


def test_should_generate_public_get_url_without_cos_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in (
        "TENCENT_COS_SECRET_ID",
        "TENCENT_COS_SECRET_KEY",
        "TENCENT_COS_BUCKET",
        "TENCENT_COS_REGION",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("TENCENT_COS_DOMAIN", "cos.example.com")
    monkeypatch.setenv("TENCENT_COS_PUBLIC_READ", "true")

    service = CosSigningService()

    assert service.generate_get_url("sales-trainer/audio/a.wav") == (
        "https://cos.example.com/sales-trainer/audio/a.wav"
    )


def test_should_generate_signed_get_url_by_default_when_domain_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    class FakeClient:
        def get_presigned_url(self, **kwargs):
            calls.append(kwargs)
            return "https://signed.example.com/private.wav"

    monkeypatch.setenv("TENCENT_COS_SECRET_ID", "sid")
    monkeypatch.setenv("TENCENT_COS_SECRET_KEY", "skey")
    monkeypatch.setenv("TENCENT_COS_BUCKET", "bucket")
    monkeypatch.setenv("TENCENT_COS_REGION", "ap-guangzhou")
    monkeypatch.setenv("TENCENT_COS_DOMAIN", "cos.example.com")
    monkeypatch.delenv("TENCENT_COS_PUBLIC_READ", raising=False)

    service = CosSigningService()
    service._client = FakeClient()

    assert service.generate_get_url("sales-trainer/audio/a.wav", expires=120) == (
        "https://signed.example.com/private.wav"
    )
    assert calls == [
        {
            "Method": "GET",
            "Bucket": "bucket",
            "Key": "sales-trainer/audio/a.wav",
            "Expired": 120,
        }
    ]


def test_should_upload_cos_object_with_normalized_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    class FakeClient:
        def put_object(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setenv("TENCENT_COS_SECRET_ID", "sid")
    monkeypatch.setenv("TENCENT_COS_SECRET_KEY", "skey")
    monkeypatch.setenv("TENCENT_COS_BUCKET", "bucket")
    monkeypatch.setenv("TENCENT_COS_REGION", "ap-guangzhou")

    service = CosSigningService()
    service._client = FakeClient()

    object_key = service.upload_object(
        "/sales-trainer/audio/user/a.wav",
        b"audio",
        content_type="audio/wav",
    )

    assert object_key == "sales-trainer/audio/user/a.wav"
    assert calls == [
        {
            "Bucket": "bucket",
            "Key": "sales-trainer/audio/user/a.wav",
            "Body": b"audio",
            "ContentType": "audio/wav",
        }
    ]
