# Agent / release instructions

Duplicate of `.cursor/rules/push-update.mdc` for clones where `.cursor/` is not committed. **Follow this when the user says “push update”.**

## Trigger

**Push update** = one coordinated release. Do **not** bump version or cut GitHub installers for vague “push to git” / “commit” requests.

## Versioning

- Bump SemVer and finalize `CHANGELOG.md` **only** during **push update** (not during normal edits).
- If push update is repeated with **no new code changes**, do **not** bump again.

## Steps

1. Finalize version: `CHANGELOG.md`, `src/version.py`, `pyproject.toml`, installer version strings (`tools/setup_launcher.py`, `tools/chronoarchiver_setup.spec`) as applicable.
2. Commit allowed files (not internal tracking `.md` except `CHANGELOG` / `README` / this file per `.gitignore` policy).
3. Push `main` to `origin`; tag `v<x.y.z>` (annotated); push tag → **Release Installers** workflow (Windows + macOS + source zip).
4. Confirm GitHub release assets.
5. **AUR**: `PKGBUILD` / `.SRCINFO`, push `aur` remote.
6. **Bazzite**: If `git remote get-url bazzite` exists, sync that repo, version match, push. If missing, report and give fix steps (add remote, document expected layout, SSH).

## Bazzite — if the agent cannot

This repo currently has **no `bazzite` git remote**. Add one when you have the packaging repository URL, for example:

```bash
git remote add bazzite git@github.com:OWNER/your-chronoarchiver-bazzite-repo.git
```

Then tell the agent what that repo contains (spec file, recipe paths) so push update can mirror version bumps and push there.
