"""Tests for ``update.py``.

Every test stubs the PyPI JSON endpoint (see ``conftest.PYPI_FIXTURE``), so
the suite is offline and does not change meaning when upstream releases.
"""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest
from conftest import PYPI_FIXTURE, PYPROJECT_TEMPLATE, README_TEMPLATE

import update


def test_bumps_pyproject(mirror: tuple[Path, Path]) -> None:
    """Both the version and the dependency pin move to the latest release."""
    pyproject, _ = mirror
    assert update.main(["update.py"]) == 0
    text = pyproject.read_text()
    assert 'version = "2026.8.27.post2"' in text
    assert '"strict-kwargs==2026.8.27.post2"' in text


def test_bumps_readme_rev(mirror: tuple[Path, Path]) -> None:
    """Regression test for #6: the README example rev syncs with pyproject.

    This is the bug that left the documented ``rev:`` three months stale.
    """
    _, readme = mirror
    assert update.main(["update.py"]) == 0
    assert "rev: 2026.8.27.post2  # pin to the latest release tag" in readme.read_text()
    assert "2026.8.16" not in readme.read_text()


def test_reports_changed(
    mirror: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """A bump prints ``changed=`` -- the string mirror.yml gates publishing on."""
    assert update.main(["update.py"]) == 0
    assert capsys.readouterr().out.strip() == "changed=2026.8.27.post2"


def test_reports_unchanged_when_in_sync(
    mirror: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """A second run is a no-op, so the workflow does not re-tag."""
    update.main(["update.py"])
    capsys.readouterr()
    assert update.main(["update.py"]) == 0
    assert capsys.readouterr().out.strip() == "unchanged=2026.8.27.post2"


def test_explicit_version(mirror: tuple[Path, Path]) -> None:
    """An explicit argument pins that version rather than the latest."""
    pyproject, readme = mirror
    assert update.main(["update.py", "2026.8.24"]) == 0
    assert 'version = "2026.8.24"' in pyproject.read_text()
    assert "rev: 2026.8.24" in readme.read_text()


def test_explicit_version_accepts_upstream_tag_form(mirror: tuple[Path, Path]) -> None:
    """``-post.N`` (upstream's git tag form) normalises to PyPI's ``.postN``."""
    pyproject, _ = mirror
    assert update.main(["update.py", "2026.8.27-post.2"]) == 0
    assert 'version = "2026.8.27.post2"' in pyproject.read_text()


def test_unknown_version_is_rejected(
    mirror: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """A version that is not on PyPI fails before anything is written."""
    pyproject, _ = mirror
    assert update.main(["update.py", "1999.1.1"]) == 1
    assert "is not on PyPI" in capsys.readouterr().err
    assert 'version = "2026.8.16"' in pyproject.read_text()


def test_refuses_explicitly_named_yanked_release(
    mirror: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A yanked version is refused, with the reason PyPI gave."""
    pyproject, _ = mirror
    data = {
        "info": PYPI_FIXTURE["info"],
        "releases": {
            **PYPI_FIXTURE["releases"],  # type: ignore[dict-item]
            "2026.9.1": [{"yanked": True, "yanked_reason": "broken wheel"}],
        },
    }
    monkeypatch.setattr(update, "_pypi", lambda: data)

    assert update.main(["update.py", "2026.9.1"]) == 1
    error = capsys.readouterr().err
    assert "is yanked on PyPI" in error
    assert "broken wheel" in error
    assert 'version = "2026.8.16"' in pyproject.read_text()


def test_skips_yanked_latest_release(
    mirror: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``info.version`` naming a yanked release falls back to the newest good one."""
    pyproject, _ = mirror
    data = {
        "info": {"version": "2026.9.1"},
        "releases": {
            **PYPI_FIXTURE["releases"],  # type: ignore[dict-item]
            "2026.9.1": [{"yanked": True, "yanked_reason": "broken wheel"}],
        },
    }
    monkeypatch.setattr(update, "_pypi", lambda: data)

    assert update.main(["update.py"]) == 0
    assert 'version = "2026.8.27.post2"' in pyproject.read_text()
    assert "skipping yanked release 2026.9.1" in capsys.readouterr().err


def test_release_with_no_files_is_skipped(
    mirror: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A registered version with no uploaded files cannot be installed."""
    pyproject, _ = mirror
    data = {
        "info": {"version": "2026.9.1"},
        "releases": {**PYPI_FIXTURE["releases"], "2026.9.1": []},  # type: ignore[dict-item]
    }
    monkeypatch.setattr(update, "_pypi", lambda: data)

    assert update.main(["update.py"]) == 0
    assert 'version = "2026.8.27.post2"' in pyproject.read_text()


@pytest.mark.parametrize(
    ("versions", "expected"),
    [
        (["2026.8.16", "2026.12.1"], "2026.12.1"),
        (["2026.8.27", "2026.8.27.post2"], "2026.8.27.post2"),
        (["2026.8.27.post2", "2026.8.27.post10"], "2026.8.27.post10"),
        (["2025.12.31", "2026.1.1"], "2026.1.1"),
    ],
)
def test_version_ordering(versions: list[str], expected: str) -> None:
    """Calver is ordered numerically, not lexically.

    A string sort would put ``2026.12.1`` before ``2026.8.16`` and
    ``post10`` before ``post2``.
    """
    assert max(versions, key=update._version_key) == expected


def test_unparseable_version_is_skipped() -> None:
    """A version outside the documented calver scheme is not ranked."""
    with pytest.raises(ValueError, match="unrecognised"):
        update._version_key("1.0.0rc1")


def test_verify_catches_version_line_that_stopped_matching(
    mirror: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """Regression test for #12.

    A reformatted ``version`` line makes the substitution a no-op. Without
    verification the script would report success having bumped nothing.
    """
    pyproject, _ = mirror
    pyproject.write_text(
        PYPROJECT_TEMPLATE.format(version="2026.8.16").replace(
            'version = "2026.8.16"', 'version="2026.8.16"', 1
        )
    )

    with pytest.raises(SystemExit) as excinfo:
        update.main(["update.py"])
    assert "sync did not apply cleanly" in str(excinfo.value)
    assert "expected '2026.8.27.post2'" in str(excinfo.value)


def test_verify_catches_dependency_pin_drift(mirror: tuple[Path, Path]) -> None:
    """A bumped version with an unbumped pin would ship a mismatched wheel."""
    pyproject, _ = mirror
    pyproject.write_text(
        PYPROJECT_TEMPLATE.format(version="2026.8.16").replace(
            '"strict-kwargs==2026.8.16"', '"strict-kwargs>=2026.8.16"', 1
        )
    )

    with pytest.raises(SystemExit) as excinfo:
        update.main(["update.py"])
    assert "dependency pins" in str(excinfo.value)


def test_verify_catches_missing_readme_rev(mirror: tuple[Path, Path]) -> None:
    """A README whose example config lost its ``rev:`` line fails the run."""
    _, readme = mirror
    readme.write_text("# strict-kwargs-pre-commit\n\nNo example here.\n")

    with pytest.raises(SystemExit) as excinfo:
        update.main(["update.py"])
    assert "no 'rev: 2026.8.27.post2' line" in str(excinfo.value)


def test_failed_verification_writes_nothing(mirror: tuple[Path, Path]) -> None:
    """A rejected sync leaves every file exactly as it was.

    Verification runs on the candidate strings, so a half-applied bump is
    never left on disk for the workflow to commit.
    """
    pyproject, readme = mirror
    broken = PYPROJECT_TEMPLATE.format(version="2026.8.16").replace(
        'version = "2026.8.16"', 'version="2026.8.16"', 1
    )
    pyproject.write_text(broken)
    readme_before = readme.read_text()

    with pytest.raises(SystemExit):
        update.main(["update.py"])

    assert pyproject.read_text() == broken
    assert readme.read_text() == readme_before
    assert "2026.8.16" in readme_before


def test_written_pyproject_is_still_valid_toml(mirror: tuple[Path, Path]) -> None:
    """The rewrite must not corrupt the file it edits with a regex."""
    pyproject, _ = mirror
    assert update.main(["update.py"]) == 0
    parsed = update.tomllib.loads(pyproject.read_text())
    assert parsed["project"]["version"] == "2026.8.27.post2"
    assert parsed["project"]["dependencies"] == ["strict-kwargs==2026.8.27.post2"]


def test_fetch_retries_transient_failures(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Regression test for #18: a blip retries instead of failing the cron."""
    attempts = []

    def flaky(*args: object, **kwargs: object) -> object:
        attempts.append(1)
        if len(attempts) < 3:
            raise urllib.error.URLError("connection reset")
        raise AssertionError("should not be reached in this test")

    monkeypatch.setattr(update.urllib.request, "urlopen", flaky)
    slept: list[float] = []

    with pytest.raises(AssertionError, match="should not be reached"):
        update._pypi(sleep=slept.append)

    assert len(attempts) == 3
    assert slept == [1, 2], "backoff should double between attempts"
    assert "retrying in 1s" in capsys.readouterr().err


def test_fetch_gives_up_after_the_last_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persistent failure still raises rather than looping forever."""

    def always_fails(*args: object, **kwargs: object) -> object:
        raise urllib.error.URLError("down")

    monkeypatch.setattr(update.urllib.request, "urlopen", always_fails)

    with pytest.raises(urllib.error.URLError):
        update._pypi(attempts=2, sleep=lambda _: None)


def test_fetch_retries_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """A truncated response is transient too, not a crash."""
    calls = []

    def bad_json(*args: object, **kwargs: object) -> object:
        calls.append(1)
        raise json.JSONDecodeError("truncated", "", 0)

    monkeypatch.setattr(update.urllib.request, "urlopen", bad_json)

    with pytest.raises(json.JSONDecodeError):
        update._pypi(attempts=2, sleep=lambda _: None)
    assert len(calls) == 2
