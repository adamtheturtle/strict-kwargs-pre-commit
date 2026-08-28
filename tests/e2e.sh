#!/usr/bin/env bash
# End-to-end check of the real consumer path.
#
# Builds a throwaway project that consumes this mirror exactly as a user
# would -- `repo:` pointing at this checkout, pinned to HEAD -- and drives it
# with pre-commit. This exercises what unit tests cannot: that pre-commit can
# build the package, that the wheel resolves from PyPI, and that the `entry:`
# actually invokes strict-kwargs correctly.
#
# Usage: tests/e2e.sh   (needs `pre-commit` and `git` on PATH)
set -euo pipefail

mirror="$(cd "$(dirname "$0")/.." && pwd)"
rev="$(git -C "$mirror" rev-parse HEAD)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cd "$work"

git init -q .
git config user.email e2e@example.com
git config user.name "e2e"

cat > .pre-commit-config.yaml <<EOF
repos:
  - repo: $mirror
    rev: $rev
    hooks:
      - id: strict-kwargs
EOF

cat > pyproject.toml <<'EOF'
[project]
name = "consumer"
version = "0"
EOF

cat > clean.py <<'EOF'
def greet(*, name: str) -> str:
    return f"hello {name}"


greet(name="world")
EOF

git add -A
git commit -qm consumer

echo "==> a compliant file must pass"
if ! output="$(pre-commit run --all-files 2>&1)"; then
    echo "$output"
    echo
    echo "FAIL: the hook rejected a file with no violations."
    echo "If the output above is 'unrecognized subcommand', the hook's entry:"
    echo "is missing the 'check' subcommand (issue #4)."
    exit 1
fi

echo "==> a positional-argument violation must be reported"
cat > bad.py <<'EOF'
def greet(name: str) -> str:
    return f"hello {name}"


greet("world")
EOF
git add bad.py

if output="$(pre-commit run --all-files 2>&1)"; then
    echo "$output"
    echo
    echo "FAIL: the hook passed a file that calls greet() positionally."
    exit 1
fi

# A non-zero exit is necessary but not sufficient: a hook that crashes also
# exits non-zero. Insist on the actual diagnostic, which is what distinguishes
# "working" from "broken in the way issue #4 was".
if ! grep -q 'KW001' <<<"$output"; then
    echo "$output"
    echo
    echo "FAIL: the hook failed, but produced no KW001 diagnostic --"
    echo "it errored out rather than checking the file."
    exit 1
fi

echo "==> ok: clean file passed, violation reported as KW001"
