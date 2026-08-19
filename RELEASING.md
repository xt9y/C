# Releasing C-BuildSystem

C-BuildSystem follows semantic versioning once the public 1.x `build.c` source API is frozen. Until 1.0, minor releases may still contain source-level API changes, but every user-visible incompatible change must be documented in `CHANGELOG.md`.

## Pre-release checklist

1. `main` is the release source; do not release from an unmerged branch.
2. `make clean && make && make test` passes on a clean checkout.
3. Linux, macOS, sanitizer and fuzz-smoke CI are green.
4. The scheduled/manual benchmark pipeline has no unexplained regression.
5. `CHANGELOG.md` contains the release notes and migration guidance.
6. `ROADMAP.md` does not claim unfinished release blockers are complete.
7. `C_VERSION` in `src/main.c` matches the intended tag.
8. Install/uninstall is checked with a temporary `DESTDIR` before publishing.

## Tagging

Release tags use `vMAJOR.MINOR.PATCH`, matching `c --version` without the leading `v`.

Example for a future 1.0.0 release:

```bash
# after the version/changelog commit is already on main
git switch main
git pull --ff-only
git tag -s v1.0.0 -m "C-BuildSystem 1.0.0"
git push origin v1.0.0
```

Do not move or reuse a published version tag. If a release needs correction, publish a new patch version.

## 1.0 gate

`v1.0.0` is intentionally not created merely because the project has many features. It marks the point where the documented 1.x source API and supported-platform contract are ready to be treated as stable.
