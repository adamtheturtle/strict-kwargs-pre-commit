"""Shared fixtures for the ``update.py`` tests.

``update.py`` lives at the repository root rather than in a package, so the
root has to be importable before ``import update`` works.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import update  # noqa: E402

# A cut-down copy of https://pypi.org/pypi/strict-kwargs/json, keeping only the
# keys update.py reads. Trimmed rather than invented: the shapes (including
# `yanked` / `yanked_reason` on each file entry) are PyPI's.
PYPI_FIXTURE: dict[str, object] = {
    "info": {"version": "2026.8.27.post2"},
    "releases": {
        "2026.8.16": [{"filename": "w.whl", "yanked": False, "yanked_reason": None}],
        "2026.8.24": [{"filename": "w.whl", "yanked": False, "yanked_reason": None}],
        "2026.8.27": [{"filename": "w.whl", "yanked": False, "yanked_reason": None}],
        "2026.8.27.post2": [
            {"filename": "w.whl", "yanked": False, "yanked_reason": None},
        ],
    },
}

PYPROJECT_TEMPLATE = """\
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "strict-kwargs-pre-commit"
version = "{version}"
description = "A pre-commit mirror of strict-kwargs."
requires-python = ">=3.11"
dependencies = [
    "strict-kwargs=={version}",
]

[tool.setuptools]
py-modules = []
"""

README_TEMPLATE = """\
# strict-kwargs-pre-commit

```yaml
repos:
  - repo: https://github.com/adamtheturtle/strict-kwargs-pre-commit
    rev: {version}  # pin to the latest release tag
    hooks:
      - id: strict-kwargs
```
"""


@pytest.fixture(name="mirror")
def mirror_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path]:
    """Build a throwaway mirror checkout pinned to 2026.8.16, PyPI stubbed out.

    Returns the ``(pyproject, readme)`` paths. No test touches the network.
    """
    pyproject = tmp_path / "pyproject.toml"
    readme = tmp_path / "README.md"
    pyproject.write_text(PYPROJECT_TEMPLATE.format(version="2026.8.16"))
    readme.write_text(README_TEMPLATE.format(version="2026.8.16"))

    monkeypatch.setattr(update, "PYPROJECT", pyproject)
    monkeypatch.setattr(update, "README", readme)
    monkeypatch.setattr(update, "_pypi", lambda: PYPI_FIXTURE)
    return pyproject, readme
