# strict-kwargs-pre-commit

[![CI](https://github.com/adamtheturtle/strict-kwargs-pre-commit/actions/workflows/ci.yml/badge.svg)](https://github.com/adamtheturtle/strict-kwargs-pre-commit/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/adamtheturtle/strict-kwargs-pre-commit?label=release)](https://github.com/adamtheturtle/strict-kwargs-pre-commit/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

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
    rev: 2026.8.28-mirror.1  # pin to the latest release tag
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

## Supported platforms

`strict-kwargs` ships prebuilt wheels only, with no source distribution, so
`pre-commit install-hooks` fails outright on a platform that has no wheel
rather than falling back to a source build.

| Platform | Wheel |
| --- | --- |
| Linux x86_64 (glibc >= 2.39) | `manylinux_2_39_x86_64` |
| macOS Apple Silicon | `macosx_11_0_arm64` |
| Windows x86_64 | `win_amd64` |
| Linux aarch64 | none — [#42](https://github.com/adamtheturtle/strict-kwargs-pre-commit/issues/42) |
| macOS Intel (x86_64) | none — [#43](https://github.com/adamtheturtle/strict-kwargs-pre-commit/issues/43) |
| musl / Alpine | none |

On an unsupported platform, run the hook from the
[upstream repo](https://github.com/adamtheturtle/strict-kwargs) instead, which
builds from source and needs a Rust toolchain.

## Pinning the `ty` version

`strict-kwargs` uses [`ty`](https://github.com/astral-sh/ty) as its
type-inference backend and depends on it as `ty>=0.0.52` — a floor, not a pin.
`ty` is pre-1.0, so a new release can land in your hook environment and change
which calls `strict-kwargs` can resolve. Pin it for reproducible results
across machines and over time:

```yaml
repos:
  - repo: https://github.com/adamtheturtle/strict-kwargs-pre-commit
    rev: 2026.8.28-mirror.1
    hooks:
      - id: strict-kwargs
        additional_dependencies: ["ty==0.0.75"]
```

pre-commit rebuilds the hook environment when `additional_dependencies`
changes, so bumping the pin is enough to pick up a new `ty`.

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

### Tag naming

This mirror's tags are the **PyPI** version string, which normalises a
post-release to `.postN`. Upstream's own git tags use `-post.N`:

| | Post-release | Ordinary release |
| --- | --- | --- |
| `rev:` for this mirror | `2026.8.27.post2` | `2026.8.16` |
| Upstream git tag | `2026.8.27-post.2` | `2026.8.16` |

The two only differ for post-releases. Always pin `rev:` to a tag from
[this repo's releases](https://github.com/adamtheturtle/strict-kwargs-pre-commit/releases);
an upstream tag name copied across will not resolve. `update.py` accepts
either form and normalises it.

### Mirror revisions

Occasionally something needs fixing *here* — in the hook definition or the
packaging — rather than upstream. Such a change has no upstream release to
ride along with, so it is published as:

```text
<upstream version>-mirror.<N>
```

for example `2026.8.27.post2-mirror.1`. That tag installs the **same**
`strict-kwargs` version as the tag it derives from; only the mirror's own
files differ. `pre-commit autoupdate` resolves the newest tag on the default
branch, so it moves to a mirror revision like any other release.

Ordinary syncs are unaffected: when upstream next releases, the tag is a plain
version again.

#### Cutting one

Rare enough not to be worth a workflow. From an up-to-date `main` with the fix
already merged:

1. Point every `rev:` in `README.md` at the new tag — `<version>-mirror.1`,
   or the next `N` if one already exists. Leave `pyproject.toml` alone: the
   `strict-kwargs==` pin must keep naming the upstream version.
2. Commit, then tag and publish:

   ```bash
   tag=2026.8.27.post2-mirror.1     # the tag from step 1

   git commit -am "Mirror revision ${tag}"
   git tag "${tag}"
   git push --atomic origin HEAD "refs/tags/${tag}"
   gh release create "${tag}" --title "${tag}" \
     --notes "Mirror-only fix; installs the same strict-kwargs release."
   ```

`update.py` recognises a `rev:` carrying a mirror revision of the current
version and leaves it in place, so the daily sync stays quiet afterwards.

## License

MIT — see [LICENSE](LICENSE). strict-kwargs itself is a separate project
under its own license.

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting.
