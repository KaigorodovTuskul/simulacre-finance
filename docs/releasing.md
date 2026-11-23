# Release process

Public source: https://github.com/KaigorodovTuskul/simulacre-finance.
Distribution name: `simulacre-finance`. Python import: `simulacre_finance`.
Releases contain a universal wheel and a source distribution.

## One-time PyPI setup

The owner's PyPI account must have verified email and completed 2FA setup.
Configure a GitHub Trusted Publisher for the project (or a pending publisher
before its first upload) with these exact fields:

| Field | Value |
| --- | --- |
| PyPI project | simulacre-finance |
| Repository owner | KaigorodovTuskul |
| Repository | simulacre-finance |
| Workflow filename | release.yml |
| GitHub environment | pypi |

The workflow's publish job alone receives `id-token: write`; checks run before
publication. No permanent PyPI API token is stored in this repository.

## Preparing a version

1. Update the version in `pyproject.toml` and `src/simulacre_finance/__init__.py`.
2. Write the changelog and run the README's test, lint, type and build commands.
3. Inspect wheel/sdist metadata, licenses, contents and isolated wheel examples.
4. Commit/push `main`; wait for checks to pass.
5. Tag the tested commit, e.g. `git tag -a v0.1.0 -m 'Simulacre Finance 0.1.0'`,
   and push that tag. The workflow verifies tag/version agreement, reruns checks,
   builds distributions, and publishes through PyPI Trusted Publishing.
6. Verify the public package page and install that exact version into a fresh
   environment using `pip install simulacre-finance==0.1.0` or the uv equivalent.
7. Create the matching GitHub release with the changelog and distribution assets.

Treat released artifacts as immutable. Corrections require a new version; do not
move a published release tag to silently replace the source.

Official references: [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
and [Python packaging](https://packaging.python.org/en/latest/tutorials/packaging-projects/).
