#!/usr/bin/env python3
"""Sync this mirror to a strict-kwargs release on PyPI.

Rewrites the package ``version`` and the ``strict-kwargs==`` dependency pin in
``pyproject.toml``, and the ``rev:`` in the README's example
``.pre-commit-config.yaml``, so all three equal the target version. With no
argument the latest version on PyPI is used; pass an explicit version to pin
that one.

Exit status ``0`` and prints ``changed=<version>`` if any file was modified,
``unchanged=<version>`` if all were already in sync. Any error exits non-zero.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

PYPI_JSON = "https://pypi.org/pypi/strict-kwargs/json"
PYPROJECT = Path(__file__).parent / "pyproject.toml"
README = Path(__file__).parent / "README.md"


def _pypi() -> dict[str, Any]:
    with urllib.request.urlopen(PYPI_JSON, timeout=30) as response:  # noqa: S310
        data: dict[str, Any] = json.load(response)
    return data


def _normalize_version(version: str) -> str:
    # GitHub tags use -post.N syntax; PyPI normalises to .postN
    return re.sub(r"-post\.(\d+)$", r".post\1", version)


def _rewrite_pyproject(text: str, target: str) -> str:
    """Return ``text`` with the version and the dependency pin set to ``target``."""
    updated = re.sub(
        r'^version = ".*"$',
        f'version = "{target}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    return re.sub(
        r'"strict-kwargs==.*"',
        f'"strict-kwargs=={target}"',
        updated,
        count=1,
    )


def _rewrite_readme(text: str, target: str) -> str:
    """Return ``text`` with the example config's ``rev:`` set to ``target``.

    The mirror's git tags are the PyPI version string verbatim, so the ``rev:``
    a consumer pins is exactly ``target`` -- no ``-post.N`` translation needed
    here, unlike upstream (see ``_normalize_version``).
    """
    return re.sub(
        r"^(\s*rev: )\S+",
        lambda match: f"{match.group(1)}{target}",
        text,
        count=1,
        flags=re.MULTILINE,
    )


def main(argv: list[str]) -> int:
    data = _pypi()
    if len(argv) > 1:
        target = _normalize_version(argv[1])
        if target not in data["releases"]:
            available = ", ".join(sorted(data["releases"]))
            message = (
                f"error: strict-kwargs {target} is not on PyPI "
                f"(available: {available})"
            )
            print(message, file=sys.stderr)
            return 1
    else:
        target = data["info"]["version"]

    changed = False
    for path, rewrite in ((PYPROJECT, _rewrite_pyproject), (README, _rewrite_readme)):
        text = path.read_text(encoding="utf-8")
        updated = rewrite(text, target)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed = True

    print(f"{'changed' if changed else 'unchanged'}={target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
