# GitHub and PyPI Release

## 1. Local validation

```bash
pip install -e .[dev]
pytest
edp-release-check
edp-build-release --clean
python -m twine check dist/*.whl dist/*.tar.gz
```

`edp-build-release --clean` now builds `sdist` and `wheel`, then writes:

- `dist/RELEASE_SHA256SUMS.txt`
- `dist/RELEASE_INDEX.json`

These files are useful when attaching artifacts to a GitHub Release or verifying what is about to be uploaded to PyPI.

## 2. Prepare GitHub

```bash
git init
git branch -M main
git remote add origin git@github.com:ONE-ORIGINE/edp-python-sdk.git
git add .
git commit -m "release: generation 2 stable"
git push -u origin main
```

Then verify:

- **Actions** are enabled
- the `pypi` environment exists if you want protected publishing
- branch protection is configured on `main` if desired

## 3. Configure PyPI trusted publishing

On PyPI, open the project settings and add a trusted publisher with:

- owner: `ONE-ORIGINE`
- repository: `edp-python-sdk`
- workflow: `publish-pypi.yml`
- environment: `pypi`

## 4. Tag and create the release

```bash
git tag v2.0.0
git push origin v2.0.0
```

Create a GitHub Release from `v2.0.0`, attach the files in `dist/`, and paste the `2.0.0` section from `CHANGELOG.md`.

Recommended attachments:

- `dist/*.tar.gz`
- `dist/*.whl`
- `dist/RELEASE_SHA256SUMS.txt`
- `dist/RELEASE_INDEX.json`

When the GitHub Release is published, `.github/workflows/publish-pypi.yml` can publish the package automatically.

## 5. Manual fallback

```bash
python -m twine upload dist/*
```

## 6. After publishing

- verify the project page on PyPI
- install `edp-python-sdk==2.0.0` from a clean virtual environment
- run `edp-cli --mode ops` and `edp-demo`
- confirm the attached checksums match the artifacts you uploaded
