# strict-kwargs-pre-commit

A [pre-commit](https://pre-commit.com/) mirror of
[strict-kwargs](https://github.com/adamtheturtle/strict-kwargs).

strict-kwargs is a Rust binary distributed as a maturin wheel. Running the
hook directly from the strict-kwargs repo would build that wheel from source,
requiring a Rust toolchain on every contributor's machine. This mirror exists
so the hook installs the **prebuilt wheel from PyPI** instead: no Rust
toolchain needed.

## Usage

Add this to your project's `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/adamtheturtle/strict-kwargs-pre-commit
    rev: 2026.5.16.post1  # pin to the latest release tag
    hooks:
      - id: strict-kwargs
```

Then:

```bash
pre-commit install
pre-commit run --all-files
```

Pin `rev` to a release tag (see
[Releases](https://github.com/adamtheturtle/strict-kwargs-pre-commit/releases)),
and let [`pre-commit
autoupdate`](https://pre-commit.com/#pre-commit-autoupdate) bump it. Each
mirror tag installs the identically-versioned `strict-kwargs` release from
PyPI. Pass extra arguments (config flags, paths) with `args:` as usual; by
default the hook checks the staged Python files.

## How versioning works

The git tag, the package `version`, and the `strict-kwargs==` dependency pin
in `pyproject.toml` are always the same string and track upstream releases
one-to-one. `update.py` performs the bump (run it manually or let
`.github/workflows/mirror.yml` run it on a schedule), then a tag and GitHub
release are published for the new version.

```bash
python update.py            # sync to the latest strict-kwargs on PyPI
python update.py 2026.5.16  # sync to a specific version
```

## License

MIT — see [LICENSE](LICENSE). strict-kwargs itself is a separate project
under its own license.
