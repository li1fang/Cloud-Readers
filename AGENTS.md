# Cloud Readers Agent Guide

Scope: this file applies to the entire repository.

## Mission
- Deliver the S01–S05 pipeline described in README and `particle.yaml` equivalents: ingestion → extraction → kinematics (2/3 power law) → simulation → RCP_2025 serialization.
- Keep outputs aligned to `SPECS/rcp_2025.proto` (`manifest.json`, `index.json`, `channels/*.pbz`, `checksums.txt`).

## Engineering Conventions
- Runtime: Python >= 3.12. Use `uv` for dependency management and `ruff format`/`ruff check` for style/lint.
- CLI: commands live under `cr` with subcommands `extract`, `simulate`, `export`. Use Typer-style options with clear defaults and Rich tables/logging for UX.
- Kinematics: implement the Two-Thirds Power Law; ensure timestamps are monotonic (µs), coordinates normalized (0–1), and velocity/pressure are coupled.
- Simulation: IMU channels should be time-aligned to kinematics, with units (m/s², rad/s) and configurable sample rates/noise.
- Serialization: always emit columnar `.pbz` channels plus `manifest.json`, `index.json`, and `checksums.txt` consistent with the proto; avoid ad-hoc JSON bundles.

## Testing & CI
- Preferred local commands: `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`.
- Integration/E2E tests should exercise the full CLI pipeline (`cr extract` → `cr simulate` → `cr export`) against sample assets.
- For workflow automation, GitHub Actions is recommended for quick PR gating; Argo Workflows is preferred for heavier batch or data/regression suites.

## Documentation & PRs
- Keep README/CLI help in sync with implemented options and defaults.
- When adding new behaviors, document any new environment variables or file layouts.
- Final responses should summarize changes and list tests executed.
