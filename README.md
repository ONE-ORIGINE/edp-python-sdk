# EDP Python SDK — Generation 2 Stable 2.0.0

EDP Python SDK packages the **Environment Design Pattern**, **MEP**, **SAVOIR**, the **Contextualizer**, the **Impact Matrix**, the **canonical ENVX body**, and the **Generation 2 learning/persistence line** in the frozen **2.0.0 stable release** ready for GitHub and PyPI publication.

It ships with:

- `edp_sdk` — canonical runtime, protocol, policy, semantics, SAVOIR, Contextualizer, analytics, persistence and release tooling
- `drone_edp` — drone specialization over EDP + MEP + SAVOIR
- `mep_tools` — EnvLang, release audit/build helpers and schema tooling
- `examples` — packaged demo and CLI entry points

## Generation 2 stable scope

This stable release includes:

- canonical `ENVX` export with mathematical body
- `ContextMatrix (M_C)` contextualization and explain/export surface
- `LearningProjection (L_t)` derived from the Impact Matrix
- persistent native stores for context, learning and causal datasets
- deeper causal scoring with priors, leverage, recency and risk
- multi-agent runtime with collective attention, member alignment and phenomenon/circumstance pressure
- operational CLI for runtime inspection, learning, scoring and persistence

## Install locally

```bash
pip install -e .[dev]
```

## Validate the repository

```bash
pytest
edp-release-check
```

## Build local artifacts

```bash
edp-build-release --clean
python -m twine check dist/*.whl dist/*.tar.gz
```

If `build` is installed in your environment, this also works:

```bash
python -m build
python -m twine check dist/*.whl dist/*.tar.gz
```

## Run the demo and CLI

```bash
edp-demo
edp-cli --mode ops
edp-cli --mode drone
```

## Publish readiness

The repository now includes:

- GitHub Actions CI
- PyPI publishing workflow
- release audit tooling
- release build tooling
- step-by-step publishing docs in `docs/GITHUB_PYPI_RELEASE.md`

## Package layout

- `edp_sdk` — runtime, protocol, causal graph, scoring, learning and projections
- `drone_edp` — drone-native extensions
- `mep_tools` — release helpers, EnvLang and schema tooling
- `examples` — demo, CLI, scripts
- `docs` — architecture, CLI, protocol, learning, stores and release documentation

## Key documents

- `docs/TECHNICAL_ARCHITECTURE.md`
- `docs/ENVX_CANONICAL.md`
- `docs/GEN2_MATH_LEARNING.md`
- `docs/GEN2_PERSISTENT_STORES.md`
- `docs/GITHUB_PYPI_RELEASE.md`
- `docs/RELEASE_PUBLISHING.md`

## Status

This is the **Generation 2 final stable line** prepared for packaging, auditing and publication.


## Stable release documents

- `docs/GEN2_FINAL_STABLE.md`
- `docs/MIGRATION_TO_2_0_0.md`
- `docs/GITHUB_PYPI_RELEASE.md`
- `docs/RELEASE_PUBLISHING.md`
