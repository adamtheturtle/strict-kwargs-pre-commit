#!/usr/bin/env python3
"""Sync this mirror to a strict-kwargs release on PyPI.

Rewrites the package ``version`` and the ``strict-kwargs==`` dependency pin in
``pyproject.toml``, and the ``rev:`` in the README's example
``.pre-commit-config.yaml``, so all three equal the target version. With no
argument the latest version on PyPI is used; pass an explicit version to pin
that one.

Yanked releases are never selected automatically and are refused when named
explicitly. After rewriting, ``pyproject.toml`` is re-parsed and both it and
the README are checked to actually carry the target version, so a regex that
silently stops matching fails the run instead of publishing a half-bumped
mirror.

Exit status ``0`` and prints ``changed=<version>`` if any file was modified,
``unchanged=<version>`` if all were already in sync. Any error exits non-zero.
"""

from __future__ import annotations

import json
import re
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

PYPI_JSON = "https://pypi.org/pypi/strict-kwargs/json"
# A mirror-only fix has no upstream version to be released under, so it is
# published as `<upstream version>-mirror.N`. Only the `strict-kwargs==` pin
# has to equal the upstream version; the tag consumers pin does not.
MIRROR_REVISION = r"(?:-mirror\.\d+)?"
# A scheduled run that trips over a transient PyPI blip should retry rather
# than page the maintainer with a red daily cron.
FETCH_ATTEMPTS = 3
PYPROJECT = Path(__file__).parent / "pyproject.toml"
README = Path(__file__).parent / "README.md"


def _pypi(
    *,
    attempts: int = FETCH_ATTEMPTS,
    sleep: Callable[[float], object] = time.sleep,
) -> dict[str, Any]:
    """Fetch the strict-kwargs release metadata, retrying transient failures."""
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(PYPI_JSON, timeout=30) as response:
                data: dict[str, Any] = json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            if attempt == attempts - 1:
                raise
            delay = 2**attempt
            print(
                f"warning: PyPI fetch failed ({error}); retrying in {delay}s",
                file=sys.stderr,
            )
            sleep(delay)
        else:
            return data
    raise AssertionError("unreachable: the final attempt returns or raises")


def _version_key(version: str) -> tuple[int, int, int, int]:
    """Sort key for the upstream calver scheme ``YYYY.M.D`` with optional ``.postN``."""
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:\.post(\d+))?", version)
    if match is None:
        raise ValueError(f"unrecognised strict-kwargs version: {version!r}")
    year, month, day, post = match.groups()
    return (int(year), int(month), int(day), int(post or 0))


def _is_usable(files: list[dict[str, Any]]) -> bool:
    """Whether a release has files and none of them are yanked."""
    return bool(files) and not all(file.get("yanked", False) for file in files)


def _yank_reason(files: list[dict[str, Any]]) -> str:
    """Return the first stated yank reason for a release, or a placeholder."""
    for file in files:
        reason = file.get("yanked_reason")
        if reason:
            assert isinstance(reason, str)
            return reason
    return "no reason given"


def _latest_usable(data: dict[str, Any]) -> str:
    """Return the newest release that is neither yanked nor file-less.

    ``info.version`` is not trusted for this: it can name a yanked release, and
    auto-mirroring one would hand every consumer a release PyPI has withdrawn.
    """
    candidates: list[tuple[tuple[int, int, int, int], str]] = []
    for version, files in data["releases"].items():
        if not _is_usable(files):
            continue
        try:
            key = _version_key(version)
        except ValueError:
            # A version outside the documented calver scheme cannot be ordered
            # against the rest; skip it rather than guess.
            continue
        candidates.append((key, version))

    if not candidates:
        message = "error: no unyanked strict-kwargs release found on PyPI"
        raise SystemExit(message)
    return max(candidates)[1]


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
    """Return ``text`` with every example config's ``rev:`` set to ``target``.

    Every ``rev:``, not just the first: the README carries more than one
    example config, and a rev left unrewritten is exactly the stale pin this
    function exists to prevent.

    The mirror's git tags are the PyPI version string verbatim, so the ``rev:``
    a consumer pins is exactly ``target`` -- no ``-post.N`` translation needed
    here, unlike upstream (see ``_normalize_version``).
    """
    already_current = re.compile(re.escape(target) + MIRROR_REVISION)

    def replace(match: re.Match[str]) -> str:
        # Leave a mirror revision of `target` alone: it is *newer* than the
        # bare version, so rewriting it would point the README back at an
        # older tag and report a spurious change.
        if already_current.fullmatch(match.group(2)):
            return match.group(0)
        return f"{match.group(1)}{target}"

    return re.sub(r"^(\s*rev: )(\S+)", replace, text, flags=re.MULTILINE)


def _verify(target: str, *, pyproject: str, readme: str) -> None:
    """Confirm the rewritten contents parse and carry ``target``.

    Both rewrites are regex substitutions, which fail silently by simply not
    matching. Without this check a formatting change in ``pyproject.toml``
    would make the script report success while bumping nothing, or bump the
    version but not the dependency pin -- and the workflow would tag and
    publish the result.

    Takes the candidate contents rather than re-reading, so a rewrite that
    does not check out leaves every file on disk untouched.
    """
    problems: list[str] = []

    parsed = tomllib.loads(pyproject)
    project = parsed["project"]
    if project["version"] != target:
        problems.append(
            f"pyproject.toml version is {project['version']!r}, expected {target!r}",
        )

    expected_pin = f"strict-kwargs=={target}"
    pins = [
        dependency
        for dependency in project["dependencies"]
        if dependency.startswith("strict-kwargs==")
    ]
    if pins != [expected_pin]:
        problems.append(
            f"pyproject.toml dependency pins are {pins!r}, expected [{expected_pin!r}]",
        )

    revs = re.findall(r"^\s*rev: (\S+)", readme, flags=re.MULTILINE)
    acceptable = re.compile(re.escape(target) + MIRROR_REVISION)
    if not revs:
        problems.append("README has no example config with a 'rev:' line")
    elif stale := sorted({rev for rev in revs if not acceptable.fullmatch(rev)}):
        problems.append(f"README rev: lines still pin {stale}, expected {target!r}")

    if problems:
        message = "error: sync did not apply cleanly:\n" + "\n".join(
            f"  - {problem}" for problem in problems
        )
        raise SystemExit(message)


def main(argv: list[str]) -> int:
    """Sync the mirror to the requested version and report what changed."""
    data = _pypi()
    if len(argv) > 1:
        target = _normalize_version(argv[1])
        if target not in data["releases"]:
            available = ", ".join(sorted(data["releases"]))
            message = (
                f"error: strict-kwargs {target} is not on PyPI (available: {available})"
            )
            print(message, file=sys.stderr)
            return 1
        if not _is_usable(data["releases"][target]):
            message = (
                f"error: strict-kwargs {target} is yanked on PyPI "
                f"({_yank_reason(data['releases'][target])}); refusing to mirror it"
            )
            print(message, file=sys.stderr)
            return 1
    else:
        target = _latest_usable(data)
        if target != data["info"]["version"]:
            print(
                f"warning: skipping yanked release {data['info']['version']}; "
                f"mirroring {target} instead",
                file=sys.stderr,
            )

    original_pyproject = PYPROJECT.read_text(encoding="utf-8")
    original_readme = README.read_text(encoding="utf-8")
    new_pyproject = _rewrite_pyproject(original_pyproject, target)
    new_readme = _rewrite_readme(original_readme, target)

    _verify(target, pyproject=new_pyproject, readme=new_readme)

    changed = False
    for path, original, updated in (
        (PYPROJECT, original_pyproject, new_pyproject),
        (README, original_readme, new_readme),
    ):
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed = True

    print(f"{'changed' if changed else 'unchanged'}={target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
