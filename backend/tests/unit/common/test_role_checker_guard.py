from common.middleware import auth


def test_role_checker_always_allow_helper_is_not_exported() -> None:
    assert not hasattr(auth, "RoleChecker")
