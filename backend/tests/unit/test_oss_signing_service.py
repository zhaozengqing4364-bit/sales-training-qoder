"""Unit tests for OssSigningService."""

from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock, patch

import pytest

from common.oss.signing import OssSigningService

# Ensure env vars exist before importing the service module
_VALID_ENV = {
    "ALI_OSS_ACCESS_KEY_ID": "test-ak",
    "ALI_OSS_ACCESS_KEY_SECRET": "test-sk",
    "ALI_OSS_BUCKET": "test-bucket",
    "ALI_OSS_ENDPOINT": "oss-cn-hangzhou.aliyuncs.com",
}


# ---------------------------------------------------------------------------
# OssConfigError
# ---------------------------------------------------------------------------


class TestOssConfigError:
    def test_missing_env_vars_raises(self):
        """Missing env vars → OssConfigError with actionable message."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove all ALI_OSS vars
            for k in list(os.environ):
                if k.startswith("ALI_OSS_"):
                    del os.environ[k]
            from common.oss.signing import OssConfigError, OssSigningService

            with pytest.raises(OssConfigError, match="OSS credentials not configured"):
                OssSigningService()

    def test_partial_env_vars_raises(self):
        """Only some vars set → still raises."""
        env = {"ALI_OSS_ACCESS_KEY_ID": "ak", "ALI_OSS_BUCKET": "b"}
        with patch.dict(os.environ, env, clear=True):
            from common.oss.signing import OssConfigError, OssSigningService

            with pytest.raises(OssConfigError, match="ALI_OSS_ACCESS_KEY_SECRET"):
                OssSigningService()


# ---------------------------------------------------------------------------
# Signing behaviour (mocked oss2)
# ---------------------------------------------------------------------------


def _make_service():
    """Create an OssSigningService with valid env + mocked oss2 internals."""
    with patch.dict(os.environ, _VALID_ENV, clear=False):
        # Force re-import to pick up env
        import common.oss.signing as mod

        mod._instance = None  # reset singleton

        mock_bucket = MagicMock()
        mock_bucket.sign_url.return_value = "https://signed-url.example.com/obj"

        with patch.object(mod, "oss2") as mock_oss2:
            mock_auth = MagicMock()
            mock_oss2.Auth.return_value = mock_auth
            mock_oss2.Bucket.return_value = mock_bucket

            svc = mod.OssSigningService()
            return svc, mock_bucket


class TestGeneratePutUrl:
    def test_returns_presigned_result(self):
        svc, mock_bucket = _make_service()
        result = svc.generate_put_url("audio/abc/seg_0001.webm")

        assert result.url == "https://signed-url.example.com/obj"
        assert result.object_key == "audio/abc/seg_0001.webm"
        assert result.expires_at  # ISO-8601 string

    def test_sign_url_called_with_put(self):
        svc, mock_bucket = _make_service()
        svc.generate_put_url("audio/abc/seg_0000.webm", content_type="audio/ogg", expires=300)

        mock_bucket.sign_url.assert_called_once_with(
            "PUT",
            "audio/abc/seg_0000.webm",
            expires=300,
            headers={"Content-Type": "audio/ogg"},
        )


class TestGenerateGetUrl:
    def test_returns_signed_url_string(self):
        svc, mock_bucket = _make_service()
        url = svc.generate_get_url("audio/abc/seg_0001.webm")
        assert url == "https://signed-url.example.com/obj"
        mock_bucket.sign_url.assert_called_once_with("GET", "audio/abc/seg_0001.webm", expires=3600)


class TestBuildObjectKey:
    def test_format(self):
        sid = str(uuid.uuid4())
        key = OssSigningService.build_object_key(sid, 3)
        assert key == f"audio/{sid}/seg_0003.webm"

    def test_sequence_zero(self):
        key = OssSigningService.build_object_key("sid", 0)
        assert key == "audio/sid/seg_0000.webm"

    def test_large_sequence(self):
        key = OssSigningService.build_object_key("sid", 9999)
        assert key == "audio/sid/seg_9999.webm"


class TestGetOssSigningServiceSingleton:
    def test_singleton_returns_same_instance(self):
        with patch.dict(os.environ, _VALID_ENV, clear=False):
            import common.oss.signing as mod

            mod._instance = None
            with patch.object(mod, "oss2"):
                a = mod.get_oss_signing_service()
                b = mod.get_oss_signing_service()
                assert a is b
