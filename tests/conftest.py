"""Shared fixtures for the ``update.py`` tests."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, TypedDict

import karva

import update


class CapturedOutput(Protocol):
    """Text returned by the output capture fixture."""

    @property
    def out(self) -> str:
        """Captured standard output."""
        ...

    @property
    def err(self) -> str:
        """Captured standard error."""
        ...


class CaptureFixture(Protocol):
    """The output capture operations used by the suite."""

    def readouterr(self) -> CapturedOutput:
        """Return captured output and reset the buffers."""
        ...


class PypiFile(TypedDict):
    """The PyPI file fields used by the updater tests."""

    filename: str
    yanked: bool
    yanked_reason: str | None


class PypiFixture(TypedDict):
    """The part of the PyPI JSON response used by the updater."""

    info: dict[str, str]
    releases: dict[str, list[PypiFile]]


# A cut-down copy of https://pypi.org/pypi/strict-kwargs/json, keeping only the
# keys update.py reads. Trimmed rather than invented: the shapes (including
# `yanked` / `yanked_reason` on each file entry) are PyPI's.
PYPI_FIXTURE: PypiFixture = {
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


@karva.fixture
def mirror(
    tmp_path: Path,
    monkeypatch: karva.MockEnv,
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
