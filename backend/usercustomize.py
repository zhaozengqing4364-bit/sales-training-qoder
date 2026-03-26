import os

# Keep repo-local pytest runs stable even when the workspace venv contains
# broken third-party pytest entrypoints. We only need the plugins used by this
# project config; the rest should not block targeted verification commands.
os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")

_required_pytest_plugins = "-p pytest_cov -p pytest_asyncio"
_existing_addopts = os.environ.get("PYTEST_ADDOPTS", "").strip()
if _required_pytest_plugins not in _existing_addopts:
    os.environ["PYTEST_ADDOPTS"] = (
        f"{_required_pytest_plugins} {_existing_addopts}".strip()
    )
