from __future__ import annotations

from types import SimpleNamespace

from common.auth.service import (
    AUTH_TRANSPORT_MATRIX,
    get_session_cookie_name,
    resolve_bearer_or_cookie_token,
    resolve_websocket_token,
)


def test_auth_transport_matrix_marks_formal_and_compatibility_paths() -> None:
    assert AUTH_TRANSPORT_MATRIX["http_request"]["formal"] == [
        "authorization_bearer",
        "session_cookie",
    ]
    assert AUTH_TRANSPORT_MATRIX["http_request"]["compatibility"] == []
    assert AUTH_TRANSPORT_MATRIX["websocket"]["formal"] == [
        "authorization_bearer",
        "session_cookie",
    ]
    assert AUTH_TRANSPORT_MATRIX["websocket"]["compatibility"] == ["query_token"]
    assert AUTH_TRANSPORT_MATRIX["login_credentials"]["formal"] == [
        "user_hashed_password"
    ]
    assert AUTH_TRANSPORT_MATRIX["login_credentials"]["compatibility"] == [
        "auth_user_passwords_json",
        "auth_shared_password",
    ]


def test_http_auth_prefers_bearer_then_cookie_alias_then_request_cookie() -> None:
    cookie_name = get_session_cookie_name()
    request = SimpleNamespace(cookies={cookie_name: "request-cookie-token"})
    credentials = SimpleNamespace(credentials="bearer-token")

    assert (
        resolve_bearer_or_cookie_token(
            credentials=credentials,
            request=request,
            cookie_token="cookie-alias-token",
        )
        == "bearer-token"
    )

    assert (
        resolve_bearer_or_cookie_token(
            credentials=None,
            request=request,
            cookie_token="cookie-alias-token",
        )
        == "cookie-alias-token"
    )

    assert (
        resolve_bearer_or_cookie_token(
            credentials=None,
            request=request,
            cookie_token=None,
        )
        == "request-cookie-token"
    )


def test_websocket_auth_prefers_header_then_cookie_then_query_compat() -> None:
    cookie_name = get_session_cookie_name()
    cookie_header = f"{cookie_name}=cookie-token"

    assert (
        resolve_websocket_token(
            query_token="query-token",
            authorization_header="Bearer header-token",
            cookie_header=cookie_header,
        )
        == "header-token"
    )

    assert (
        resolve_websocket_token(
            query_token="query-token",
            authorization_header="",
            cookie_header=cookie_header,
        )
        == "cookie-token"
    )

    assert (
        resolve_websocket_token(
            query_token="query-token",
            authorization_header="",
            cookie_header="",
        )
        == "query-token"
    )
