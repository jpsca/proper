"""File-based tracking of installed Proper addons.

Stores a JSON document at ``app.root_path / ".proper"``:

    {
      "addons": {
        "storage": {"version": "0.10.0", "installed_at": "2026-05-20T10:00:00Z"}
      }
    }

The file lives with the code in version control, so cloning the app yields
an accurate view of which addons are installed without requiring the
database to be available.
"""
import json
import typing as t
from datetime import datetime, timezone
from importlib.metadata import version as _pkg_version
from pathlib import Path


if t.TYPE_CHECKING:
    from ..app import App


METADATA_FILENAME = ".proper"


def _current_version() -> str:
    return _pkg_version("proper")


def metadata_path(app: "App") -> Path:
    return app.root_path / METADATA_FILENAME


def load_metadata(app: "App") -> dict:
    """Return the parsed metadata dict, or an empty schema if no file exists."""
    path = metadata_path(app)
    if not path.exists():
        return {"addons": {}}
    return json.loads(path.read_text())


def is_installed(app: "App", addon: str) -> bool:
    """True if the addon has been recorded as installed in this app."""
    data = load_metadata(app)
    return addon in data.get("addons", {})


def record_install(
    app: "App",
    addon: str,
    version: str | None = None,
    config: dict | None = None,
) -> None:
    """Upsert the addon's install record in the metadata file.

    Re-recording the same addon updates its entry rather than duplicating.
    If ``version`` is not provided, the current Proper version is used.
    """
    if version is None:
        version = _current_version()
    data = load_metadata(app)
    addons = data.setdefault("addons", {})
    entry: dict[str, t.Any] = {
        "version": version,
        "installed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if config is not None:
        entry["config"] = config
    addons[addon] = entry
    _atomic_write(metadata_path(app), data)


def _atomic_write(path: Path, data: dict) -> None:
    tmp = path.parent / (path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)
