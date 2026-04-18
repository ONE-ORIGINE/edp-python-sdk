# Migration to 2.0.0

## From candidate builds to the stable line

The final stable line mainly freezes and aligns what was introduced in `2.0.0a8` to `2.0.0a11`:

- negotiation/attention remains enabled
- `M_C`, `L_t` and persistent stores remain available
- release metadata, docs and packaging now point to the stable line

## What changed for maintainers

- Git tags should now use `v2.0.0`
- the release channel is `stable` rather than `candidate`
- local build output now includes checksums and a release index

## Recommended validation

```bash
pytest
edp-release-check
edp-build-release --clean
python -m twine check dist/*.whl dist/*.tar.gz
```
