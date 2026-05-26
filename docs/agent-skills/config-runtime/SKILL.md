---
name: zhihu-config-runtime
description: Use when modifying config schema, runtime config loading, Cookie paths, logs, browser profile paths, or local output path resolution.
---

# Config Runtime

## Guardrails

- `pyproject.toml` remains the dependency source of truth.
- Keep local credentials, logs, browser profiles, caches, and SQLite runtime files out of tracked root paths.
- Prefer `core/config_schema.py` for typed shape and `core/config_runtime.py` for loading, defaults, updates, and path resolution.
- Config changes should be reflected in README only when users must act on them.

## Validation

Run `python -m unittest -q tests.test_config_schema tests.test_config_runtime tests.test_config_view tests.test_install_contract` for config or runtime path edits.
