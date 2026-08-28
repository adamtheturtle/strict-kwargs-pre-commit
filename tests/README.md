# Tests

```bash
uv run --group dev pytest
```

The suite is offline: `conftest.PYPI_FIXTURE` is a trimmed copy of
<https://pypi.org/pypi/strict-kwargs/json>, so tests do not reach the network
and do not change meaning when upstream publishes a release.
