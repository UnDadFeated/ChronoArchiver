# Push update (release orchestration)

This file mirrors **`.cursor/rules/push-update.mdc`** so clones without `.cursor/` still have the release checklist.

## Trigger

When the user says **push update** (or clearly means that single release flow), run the **full update** below. Do **not** treat generic phrases like “push to git”, “commit”, or “sync main” as this trigger.

## Versioning (overrides other project habits for SemVer)

- **Bump `MAJOR.MINOR.PATCH` and finalize `CHANGELOG.md` only during a push update** — not during ordinary feature work or partial git pushes.
- On a push update: move `[Unreleased]` into a new dated `## [x.y.z] - YYYY-MM-DD` section (or add the new version section with all pending notes), set `__version__` in `src/version.py`, `version` in `pyproject.toml`, and align embedded defaults in `tools/setup_launcher.py` / `tools/chronoarchiver_setup.spec` if the repo uses them for the setup build.
- **Zero-edit version lock**: If the user runs push update twice with **no new code changes** between runs, do **not** bump the version a second time.

## Push update — checklist (execute in order)

1. **Working tree**  
   Ensure all intended source changes are committed or included in this release. Do **not** commit internal tracking markdown (`TASKS.md`, `CONVERSATION_LOG.md`, etc.); `CHANGELOG.md` and `README.md` are allowed in git per project policy.

2. **Version + changelog**  
   Choose the next SemVer, update `CHANGELOG.md`, `src/version.py`, `pyproject.toml`, and installer-related version strings as above.

3. **GitHub (`origin`)**  
   Push `main`, then create an **annotated** tag `v<x.y.z>` on the release commit and **push the tag**. That should trigger **Release Installers** (`.github/workflows/release-installers.yml`) for Windows and macOS artifacts on the release.

4. **Verify installers**  
   Watch the Actions run; confirm the release on GitHub contains e.g. `ChronoArchiver-Setup-<ver>-win64.exe`, `ChronoArchiver-Setup-<ver>-mac64.zip`, and the source zip.

5. **AUR (`aur` remote)**  
   Update `PKGBUILD` `pkgver` (and `pkgrel` if required) in the **main** repo commit when applicable. For the AUR-only tree:

   - Add a short-lived worktree on `aur/master`, copy in the updated `PKGBUILD` from `main`, regenerate `.SRCINFO` with `makepkg --printsrcinfo > .SRCINFO`, commit on that branch, then push.
   - **Push command:** from that worktree directory (often **detached HEAD** after `git worktree add … aur/master`), run **`git push aur HEAD:master`**. That sends the current commit to the remote branch `master`. A plain `git push aur master` can fail in detached state because there is no local `master` branch name—`HEAD:master` is explicit: “push this exact commit to `master` on `aur`.”

**Done after step 5.** Stop there; do not add packaging steps, extra remotes, or follow-up instructions beyond this checklist.

## Contrast with older wording

- **Not** a push update: daily commits, “push main”, “fix and push”, AUR-only refresh without a full release. Those flows **do not** bump version or rebuild GitHub installers unless the user explicitly switches to **push update**.
