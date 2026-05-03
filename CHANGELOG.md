# Changelog

This changelog tracks local modernization work intended for a future pull request back to the upstream Aiper Home Assistant integration.

## Unreleased

### Added

- Added repo-level `AGENTS.md` with architecture notes, working rules, and modernization priorities for future agent sessions.
- Added `uv` development tooling with `pyproject.toml` and `uv.lock`.
- Added local Home Assistant development runtime via `docker-compose.yml` and `ha-config/configuration.yaml`.
- Added initial pytest suite covering config-flow validation helpers, diagnostics redaction, parser normalization, warning code handling, and consumable parsing.
- Added service dispatch tests for the raw AT-command service across multiple loaded config entries.

### Changed

- Documented development commands in `README.md`.
- Expanded `.gitignore` for Python tooling, Home Assistant runtime files, and generated caches.
- Normalized parsed Aiper datetime values to UTC-aware datetimes before exposing them to Home Assistant timestamp sensors.
- Refactored `aiper.send_at_command` to register once at integration setup and dynamically dispatch to the config entry that owns the requested serial number.
- Cleaned up lint issues surfaced by the new Ruff configuration.

### Fixed

- Fixed config-flow test scaffolding so tests run through the `uv` managed Python environment.
