# Release Publishing Checklist

## Metadata coherence

- `pyproject.toml` version matches package `__version__` values
- `edp_sdk.release.PROJECT_VERSION` matches the package version
- `edp_sdk.release.CHANNEL` and `RELEASE_MANIFEST.json` are both `stable`
- `CHANGELOG.md` contains the `2.0.0` section
- `CITATION.cff` points to `2.0.0`

## Code and tests

- `pytest` is green
- `edp-release-check` passes
- demo and CLI commands start correctly
- `edp-build-release --clean` produces `sdist`, `wheel`, checksum file and release index
- `python -m twine check dist/*.whl dist/*.tar.gz` passes

## GitHub readiness

- `.github/workflows/ci.yml` passes on `main`
- `.github/workflows/publish-pypi.yml` is enabled
- issue templates and contribution files are present
- release notes are copied from `CHANGELOG.md`
- `dist/RELEASE_SHA256SUMS.txt` and `dist/RELEASE_INDEX.json` are attached to the GitHub Release

## PyPI readiness

- package name availability is verified
- trusted publisher or token-based publishing is configured
- README renders correctly
- install from a clean virtual environment succeeds
